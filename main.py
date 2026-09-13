from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands, tasks

from config import BOT_NAME, DISCORD_TOKEN, WIZARD_TIMEOUT_SECONDS
from database import Database
from wizard.steps import Step

logger = logging.getLogger("parceria")


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
        # Conecta no banco (roda migrations)
        await self.database.connect()

        # Carrega cogs
        for ext in ("cogs.geral", "cogs.config", "cogs.parceria"):
            try:
                await self.load_extension(ext)
                logger.info("Cog carregado: %s", ext)
            except Exception:
                logger.exception("Falha ao carregar %s", ext)
                raise

        # Sincroniza comandos slash
        synced = await self.tree.sync()
        logger.info("%s comandos slash sincronizados.", len(synced))

        # Inicia tarefa de timeout
        self.check_stale_tickets.start()

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

    async def on_message(self, message: discord.Message) -> None:
        # Ignora bots e DMs
        if message.author.bot or not message.guild:
            return

        # Se for canal de ticket aberto
        ticket = await self.database.get_ticket_by_channel(message.channel.id)
        if ticket and ticket["status"] == "open":
            # Só o dono do ticket interage com o wizard
            if message.author.id != ticket["user_id"]:
                return

            # Passos finais não processam texto (só botões)
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

        # Mensagem normal: processa comandos com prefixo (se houver)
        await self.process_commands(message)

    @tasks.loop(minutes=5)
    async def check_stale_tickets(self) -> None:
        """Fecha tickets parados há mais de X segundos."""
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

    async def close(self) -> None:
        self.check_stale_tickets.cancel()
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
