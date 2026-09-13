from __future__ import annotations

import logging
from typing import Any

import discord

from config import EMBED_COLORS, DEFAULT_COLOR

logger = logging.getLogger(__name__)


class StaffReviewView(discord.ui.View):
    """Botões que a staff usa pra aprovar/recusar no canal do ticket."""

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

        # Só staff (Manage Guild) pode usar
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

        # Pede pro staff escolher o canal de publicação
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
            f"❌ Parceria recusada por {interaction.user.mention}."
        )

        # Desabilita botões
        for child in self.children:
            child.disabled = True  # type: ignore[attr-defined]
        await interaction.message.edit(view=self) if interaction.message else None


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

        # Valida permissões do bot no canal escolhido
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

        # Salva como canal padrão
        await db.set_publication_channel(interaction.guild_id, channel.id)
        await db.close_ticket(self.ticket_id, status="approved")

        await interaction.followup.send(
            f"✅ Parceria publicada em {channel.mention}!", ephemeral=True
        )
        await interaction.channel.send(
            f"✅ Parceria aprovada e publicada por {interaction.user.mention}."
        )
