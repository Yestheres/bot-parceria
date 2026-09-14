from __future__ import annotations

import logging
from typing import Any

import discord

from config import DEFAULT_COLOR, EMBED_COLORS

logger = logging.getLogger(__name__)


class StaffReviewView(discord.ui.View):
    """Botões que a staff usa pra aprovar/recusar/fechar no canal do ticket."""

    def __init__(self, bot: discord.Client, ticket_id: int) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_id = ticket_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Essa ação só funciona dentro do servidor.", ephemeral=True
            )
            return False

        perms = interaction.user.guild_permissions
        if not (perms.administrator or perms.manage_guild):
            await interaction.response.send_message(
                "Só a staff pode revisar parcerias.", ephemeral=True
            )
            return False

        return True

    @discord.ui.button(
        label="Aprovar e publicar",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="staff:approve",
    )
    async def approve(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        db = self.bot.database  # type: ignore[attr-defined]
        ticket = await db.get_ticket_by_channel(interaction.channel_id)
        if not ticket or ticket["status"] != "open":
            await interaction.followup.send("Esse ticket já foi fechado.", ephemeral=True)
            return

        await interaction.followup.send(
            "Escolha o **canal onde a parceria vai ser publicada**:",
            view=PublicationChannelView(self.bot, self.ticket_id),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Recusar",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="staff:reject",
    )
    async def reject(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        db = self.bot.database  # type: ignore[attr-defined]
        ticket = await db.get_ticket_by_channel(interaction.channel_id)
        if not ticket or ticket["status"] != "open":
            await interaction.followup.send("Esse ticket já foi fechado.", ephemeral=True)
            return

        await db.close_ticket(self.ticket_id, status="rejected")
        await interaction.channel.send(
            f"❌ Parceria recusada por {interaction.user.mention}.\n"
            f"_Staff, use **🔒 Fechar ticket** pra arquivar esse canal._"
        )

        # Desabilita os botões de aprovar/recusar
        for child in self.children:
            if isinstance(child, discord.ui.Button) and not child.custom_id.startswith("staff:close"):
                child.disabled = True
        if interaction.message:
            try:
                await interaction.message.edit(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(
        label="Fechar ticket",
        style=discord.ButtonStyle.secondary,
        emoji="🔒",
        custom_id="staff:close",
    )
    async def close(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            return

        db = self.bot.database  # type: ignore[attr-defined]
        ticket = await db.get_ticket_by_channel(interaction.channel_id)
        if not ticket or ticket["status"] != "open":
            await interaction.followup.send("Esse ticket já foi fechado.", ephemeral=True)
            return

        # Fecha no banco
        await db.close_ticket(self.ticket_id, status="closed")

        # Avisa no canal antes de mover
        try:
            await interaction.channel.send(
                f"🔒 Ticket fechado por {interaction.user.mention}. "
                "Movendo pra arquivo..."
            )
        except discord.HTTPException:
            pass

        # Move pra categoria de fechados (se configurada) e renomeia
        closed_category_id = await db.get_closed_category(interaction.guild.id)
        new_category = None
        if closed_category_id:
            cat = interaction.guild.get_channel(closed_category_id)
            if isinstance(cat, discord.CategoryChannel):
                new_category = cat

        # Renomeia
        old_name = interaction.channel.name
        new_name = f"fechado-{old_name}"[:100]

        try:
            await interaction.channel.edit(
                name=new_name,
                category=new_category,
                reason=f"Ticket fechado por {interaction.user}",
            )
        except discord.HTTPException:
            logger.exception("Falha ao mover/renomear canal")
            await interaction.followup.send(
                "Não consegui mover o canal pra categoria de fechados. "
                "Verifique minhas permissões.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            "✅ Ticket fechado e movido pra arquivo.", ephemeral=True
        )


class PublicationChannelView(discord.ui.View):
    """Select pra staff escolher onde publicar a parceria aprovada."""

    def __init__(self, bot: discord.Client, ticket_id: int) -> None:
        super().__init__(timeout=120)
        self.bot = bot
        self.ticket_id = ticket_id

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Escolha o canal de publicação",
        min_values=1,
        max_values=1,
        custom_id="staff:publication_channel",
    )
    async def choose(
        self,
        interaction: discord.Interaction,
        select: discord.ui.ChannelSelect,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        db = self.bot.database  # type: ignore[attr-defined]
        ticket = await db.get_ticket_by_channel(interaction.channel_id)
        if not ticket or ticket["status"] != "open":
            await interaction.followup.send("Ticket já fechado.", ephemeral=True)
            return

        channel = select.values[0].resolve()
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("Canal inválido.", ephemeral=True)
            return

        me = interaction.guild.me if interaction.guild else None
        if me:
            perms = channel.permissions_for(me)
            if not (perms.view_channel and perms.send_messages and perms.embed_links):
                await interaction.followup.send(
                    "Não tenho permissão pra publicar nesse canal "
                    "(preciso de Ver, Enviar Mensagens e Inserir Links).",
                    ephemeral=True,
                )
                return

        data: dict[str, Any] = dict(ticket["data"] or {})
        if isinstance(data, str):
            import json as _json
            try:
                data = _json.loads(data)
            except Exception:
                data = {}

        color_name = data.get("color", DEFAULT_COLOR)
        color_int = EMBED_COLORS.get(color_name, EMBED_COLORS[DEFAULT_COLOR])

        embed = discord.Embed(
            title=data.get("invite_name") or data.get("name") or "Parceria",
            description=data.get("description") or "*sem descrição*",
            color=discord.Color(color_int),
        )
        icon = data.get("invite_icon")
        if icon:
            embed.set_thumbnail(url=icon)
        img = data.get("image_url")
        if img:
            embed.set_image(url=img)

        link = data.get("link")
        view = discord.ui.View()
        if link:
            if not link.startswith(("http://", "https://")):
                link = "https://" + link
            view.add_item(
                discord.ui.Button(
                    label="Entrar no servidor",
                    style=discord.ButtonStyle.link,
                    url=link,
                )
            )

        try:
            await channel.send(embed=embed, view=view)
        except discord.HTTPException:
            logger.exception("Falha ao publicar parceria")
            await interaction.followup.send(
                "Não consegui publicar nesse canal. Tenta outro.",
                ephemeral=True,
            )
            return

        await db.set_publication_channel(interaction.guild_id, channel.id)
        await db.close_ticket(self.ticket_id, status="approved")

        await interaction.followup.send(
            f"✅ Parceria publicada em {channel.mention}!", ephemeral=True
        )

        # Avisa no ticket pra staff fechar
        try:
            await interaction.channel.send(
                f"✅ Parceria aprovada e publicada em {channel.mention} "
                f"por {interaction.user.mention}.\n"
                f"_Staff, use **🔒 Fechar ticket** pra arquivar esse canal._"
            )
        except discord.HTTPException:
            pass
