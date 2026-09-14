from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from config import BOT_NAME, DISCORD_TOKEN, WIZARD_TIMEOUT_SECONDS
from database import Database
from wizard.steps import Step

logger = logging.getLogger("parceria")

BRT = ZoneInfo("America/Sao_Paulo")
BIRTHDAY_HOUR = 8  # 8h BRT


class ParceriaBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )
        self.database = Database()

    async def setup_hook(self) -> None:
        await self.database.connect()

        for ext in ("cogs.geral", "cogs.config", "cogs.parceria", "cogs.aniversario"):
            try:
                await self.load_extension(ext)
                logger.info("Cog carregado: %s", ext)
            except Exception:
                logger.exception("Falha ao carregar %s", ext)
                raise

        synced = await self.tree.sync()
        logger.info("%s comandos slash sincronizados.", len(synced))

        self.check_stale_tickets.start()
        self.birthday_tick.start()

    async def on_ready(self) -> None:
        if self.user:
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="/parceria | /ajuda",
                ),
                status=discord.Status.online,
            )
            logger.info("Conectado como %s (ID %s)", self.user, self.user.id)

        # Catch-up: se já passou das 8h hoje e ainda não rodou, roda agora
        try:
            await self._birthday_catchup()
        except Exception:
            logger.exception("Erro no catch-up de aniversário")

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        ticket = await self.database.get_ticket_by_channel(message.channel.id)
        if ticket and ticket["status"] == "open":
            if message.author.id != ticket["user_id"]:
                return
            if ticket["step"] in (Step.CONFIRMAR.value, Step.DONE.value):
                return

            logger.info(
                "Wizard msg: user=%s step=%s content=%r",
                message.author.id, ticket["step"], message.content[:80],
            )
            from wizard.manager import WizardManager
            wizard = WizardManager(self, self.database)
            try:
                await wizard.process_answer(message, ticket)
            except Exception:
                logger.exception("Erro no wizard")
                try:
                    await message.channel.send(
                        "❌ Tive um erro processando sua resposta. Chama a staff."
                    )
                except discord.HTTPException:
                    pass
            return

        await self.process_commands(message)

    # ------------------------------------------------------------------
    # Task: fechar tickets parados
    # ------------------------------------------------------------------
    @tasks.loop(minutes=5)
    async def check_stale_tickets(self) -> None:
        try:
            stale = await self.database.list_stale_tickets(WIZARD_TIMEOUT_SECONDS)
            for ticket in stale:
                channel = self.get_channel(ticket["channel_id"])
                await self.database.close_ticket(ticket["id"], status="timeout")
                if isinstance(channel, discord.TextChannel):
                    try:
                        await channel.send(
                            "⏰ Tempo esgotado. Esse ticket foi fechado por inatividade.\n"
                            "Se quiser tentar de novo, use `/parceria`."
                        )
                    except discord.HTTPException:
                        pass
                    await asyncio.sleep(5)
                    try:
                        await channel.delete(reason="Timeout do wizard")
                    except discord.HTTPException:
                        pass
                logger.info("Ticket %s fechado por timeout.", ticket["id"])
        except Exception:
            logger.exception("Erro no check_stale_tickets")

    @check_stale_tickets.before_loop
    async def _before_stale(self) -> None:
        await self.wait_until_ready()

    # ------------------------------------------------------------------
    # Task: aniversários
    # ------------------------------------------------------------------
    @tasks.loop(minutes=15)
    async def birthday_tick(self) -> None:
        """Roda a cada 15 min. Se já passou das 8h e ainda não processou hoje, processa.

        Também limpa cargos de aniversariante de dias anteriores.
        """
        try:
            await self._birthday_catchup()
        except Exception:
            logger.exception("Erro no birthday_tick")

    @birthday_tick.before_loop
    async def _before_birthday(self) -> None:
        await self.wait_until_ready()

    async def _birthday_catchup(self) -> None:
        agora = datetime.now(BRT)
        hoje = agora.date()

        # Só processa parabéns se já passou das 8h
        if agora.hour < BIRTHDAY_HOUR:
            return

        guilds = await self.database.list_guilds_with_birthday_config()
        for g in guilds:
            gid = g["guild_id"]
            run = await self.database.get_birthday_run(gid)
            last_congrats = run["last_congrats_date"] if run else None
            last_cleanup = run["last_role_cleanup_date"] if run else None

            # Já mandou parabéns hoje? Pula
            if last_congrats == hoje:
                pass
            else:
                await self._send_birthday_congrats(gid, hoje)
                await self.database.set_last_congrats_date(gid, hoje)

            # Já limpou cargos hoje? Pula
            if last_cleanup == hoje:
                pass
            else:
                await self._cleanup_birthday_roles(gid)
                await self.database.set_last_role_cleanup_date(gid, hoje)

    async def _send_birthday_congrats(self, guild_id: int, hoje) -> None:
        aniversariantes = await self.database.get_birthdays_on(guild_id, hoje.month, hoje.day)
        if not aniversariantes:
            return

        channel_id = await self.database.get_birthday_channel(guild_id)
        if not channel_id:
            return

        guild = self.get_guild(guild_id)
        if not guild:
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            try:
                channel = await self.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.warning("Canal de aniversário %s não encontrado.", channel_id)
                return

        role_id = await self.database.get_birthday_role(guild_id)
        role = guild.get_role(role_id) if role_id else None

        for b in aniversariantes:
            member = guild.get_member(b["user_id"])
            if member is None:
                try:
                    member = await guild.fetch_member(b["user_id"])
                except (discord.NotFound, discord.HTTPException):
                    member = None

            # Adiciona cargo temporário (se configurado e possível)
            if role and member:
                me = guild.me
                if me and me.guild_permissions.manage_roles and role < me.top_role:
                    try:
                        if role not in member.roles:
                            await member.add_roles(role, reason="Aniversariante do dia")
                    except discord.HTTPException:
                        logger.exception("Falha ao dar cargo de aniversariante")

            # Manda parabéns
            embed = discord.Embed(
                title="🎉🎂 FELIZ ANIVERSÁRIO! 🎂🎉",
                description=(
                    f"<@{b['user_id']}> hoje é o seu dia!\n\n"
                    "A comunidade toda te deseja um feliz aniversário! 🥳🎈\n"
                    "Aproveite muito! 🎁"
                ),
                color=discord.Color.magenta(),
            )
            if member and member.display_avatar:
                embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"🎈 {hoje.strftime('%d/%m/%Y')}")

            try:
                await channel.send(content=f"<@{b['user_id']}>", embed=embed)
            except discord.HTTPException:
                logger.exception("Falha ao mandar parabéns")

    async def _cleanup_birthday_roles(self, guild_id: int) -> None:
        """Remove o cargo de aniversariante de quem ainda tem (de ontem pra trás)."""
        role_id = await self.database.get_birthday_role(guild_id)
        if not role_id:
            return

        guild = self.get_guild(guild_id)
        if not guild:
            return

        role = guild.get_role(role_id)
        if not role:
            return

        me = guild.me
        if not me or not me.guild_permissions.manage_roles or role >= me.top_role:
            return

        for member in list(role.members):
            try:
                await member.remove_roles(role, reason="Fim do dia de aniversário")
            except discord.HTTPException:
                logger.exception("Falha ao remover cargo de aniversariante")

    async def close(self) -> None:
        self.check_stale_tickets.cancel()
        self.birthday_tick.cancel()
        await self.database.close()
        await super().close()


async def main() -> None:
    bot = ParceriaBot()
    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot encerrado manualmente.")
