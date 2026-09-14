from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from wizard.manager import WizardManager
from wizard.steps import Step

logger = logging.getLogger(__name__)


class Parceria(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.wizard = WizardManager(bot, bot.database)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # /parceria
    # ------------------------------------------------------------------
    @app_commands.command(
        name="parceria",
        description="Abre um canal privado pra você montar sua proposta de parceria.",
    )
    async def parceria(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.followup.send(
                "Esse comando só funciona em servidor.", ephemeral=True
            )
            return

        db = self.bot.database  # type: ignore[attr-defined]
        gid = interaction.guild.id
        uid = interaction.user.id

        # Já tem ticket aberto?
        existing = await db.get_open_ticket(gid, uid)
        if existing:
            ch = interaction.guild.get_channel(existing["channel_id"])
            if ch:
                await interaction.followup.send(
                    f"⚠️ Você já tem uma parceria em andamento: {ch.mention}",
                    ephemeral=True,
                )
            else:
                await db.close_ticket(existing["id"], status="closed")
                await interaction.followup.send(
                    "⚠️ Encontrei um ticket antigo quebrado e fechei. "
                    "Roda `/parceria` de novo.",
                    ephemeral=True,
                )
            return

        # Configuração existe?
        approval = await db.get_approval_channel(gid)
        if not approval:
            await interaction.followup.send(
                "❌ A staff ainda não configurou o canal de parcerias. "
                "Peça pra usar `/configurar staff`.",
                ephemeral=True,
            )
            return

        category_id = await db.get_ticket_category(gid)
        category = interaction.guild.get_channel(category_id) if category_id else None
        if category_id and not isinstance(category, discord.CategoryChannel):
            category = None  # type: ignore[assignment]

        # Cria canal
        overwrites: dict = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True,
            ),
        }

        staff_role_id = await db.get_staff_role(gid)
        if staff_role_id:
            role = interaction.guild.get_role(staff_role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True,
                )

        safe_name = "".join(
            c for c in interaction.user.name.lower() if c.isalnum() or c in "-_"
        )[:20] or "user"

        try:
            channel = await interaction.guild.create_text_channel(
                name=f"parceria-{safe_name}",
                category=category,  # type: ignore[arg-type]
                overwrites=overwrites,  # type: ignore[arg-type]
                topic=f"Parceria de {interaction.user} ({interaction.user.id})",
                reason="Nova solicitação de parceria",
            )
        except discord.HTTPException:
            logger.exception("Falha ao criar canal de parceria")
            await interaction.followup.send(
                "❌ Não consegui criar o canal. Verifique minhas permissões "
                "(preciso de Gerenciar Canais).",
                ephemeral=True,
            )
            return

        ticket_id = await db.create_ticket(
            guild_id=gid,
            channel_id=channel.id,
            user_id=uid,
            step=Step.NOME.value,
        )
        if ticket_id is None:
            await channel.delete(reason="Falha ao criar ticket no banco")
            await interaction.followup.send(
                "❌ Não consegui registrar o ticket. Tenta de novo.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"✅ Criei seu canal privado: {channel.mention}\n"
            "Responde as perguntas por lá.",
            ephemeral=True,
        )

        await channel.send(
            f"👋 Olá, {interaction.user.mention}!\n"
            "Vou te fazer algumas perguntas pra montar sua proposta de parceria.\n"
            "**Responda cada uma aqui no canal.**\n"
        )
        await self.wizard.send_question(channel, Step.NOME)

    # ------------------------------------------------------------------
    # /cancelar
    # ------------------------------------------------------------------
    @app_commands.command(
        name="cancelar",
        description="Cancela o seu ticket de parceria aberto.",
    )
    async def cancelar(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return

        db = self.bot.database  # type: ignore[attr-defined]
        ticket = await db.get_open_ticket(interaction.guild.id, interaction.user.id)
        if not ticket:
            await interaction.followup.send(
                "Você não tem nenhuma parceria aberta.", ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(ticket["channel_id"])
        await db.close_ticket(ticket["id"], status="cancelled")

        if isinstance(channel, discord.TextChannel):
            try:
                await channel.delete(reason=f"Cancelado por {interaction.user}")
            except discord.HTTPException:
                logger.exception("Falha ao deletar canal cancelado")

        await interaction.followup.send("✅ Parceria cancelada.", ephemeral=True)

    # ------------------------------------------------------------------
    # /fechar  (staff)
    # ------------------------------------------------------------------
    @app_commands.command(
        name="fechar",
        description="[Staff] Fecha o ticket de parceria do canal atual.",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def fechar(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild or not isinstance(
            interaction.channel, discord.TextChannel
        ):
            return

        db = self.bot.database  # type: ignore[attr-defined]
        ticket = await db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            await interaction.followup.send(
                "Esse canal não é um ticket de parceria.", ephemeral=True
            )
            return
        if ticket["status"] != "open":
            await interaction.followup.send(
                "Esse ticket já foi fechado.", ephemeral=True
            )
            return

        await db.close_ticket(ticket["id"], status="closed")

        # Tenta mover pra categoria de fechados
        closed_category_id = await db.get_closed_category(interaction.guild.id)
        new_category = None
        if closed_category_id:
            cat = interaction.guild.get_channel(closed_category_id)
            if isinstance(cat, discord.CategoryChannel):
                new_category = cat

        new_name = f"fechado-{interaction.channel.name}"[:100]

        try:
            await interaction.channel.edit(
                name=new_name,
                category=new_category,
                reason=f"Fechado por {interaction.user}",
            )
        except discord.HTTPException:
            logger.exception("Falha ao mover/renomear canal")
            await interaction.followup.send(
                "Não consegui mover o canal. Verifique minhas permissões.",
                ephemeral=True,
            )
            return

        await interaction.followup.send("✅ Ticket fechado.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Parceria(bot))
