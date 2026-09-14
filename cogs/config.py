from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


def is_staff(member: discord.Member) -> bool:
    perms = member.guild_permissions
    return perms.administrator or perms.manage_guild


class Config(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    config_group = app_commands.Group(
        name="configurar",
        description="Configura o bot no servidor.",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    # ------------------------------------------------------------------
    # /configurar staff
    # ------------------------------------------------------------------
    @config_group.command(name="staff", description="Define o canal onde as parcerias chegam.")
    @app_commands.describe(canal="Canal privado da staff.")
    async def config_staff(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not is_staff(interaction.user):
            await interaction.followup.send("Sem permissão.", ephemeral=True)
            return

        db = self.bot.database  # type: ignore[attr-defined]
        await db.set_approval_channel(interaction.guild.id, canal.id)
        await interaction.followup.send(
            f"✅ Canal da staff definido: {canal.mention}", ephemeral=True
        )

    # ------------------------------------------------------------------
    # /configurar publicacao
    # ------------------------------------------------------------------
    @config_group.command(name="publicacao", description="Define o canal padrão de publicação.")
    @app_commands.describe(canal="Canal onde as parcerias aprovadas serão publicadas.")
    async def config_publicacao(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not is_staff(interaction.user):
            await interaction.followup.send("Sem permissão.", ephemeral=True)
            return

        me = interaction.guild.me
        if me:
            perms = canal.permissions_for(me)
            if not (perms.view_channel and perms.send_messages and perms.embed_links):
                await interaction.followup.send(
                    "Preciso de Ver, Enviar Mensagens e Inserir Links nesse canal.",
                    ephemeral=True,
                )
                return

        db = self.bot.database  # type: ignore[attr-defined]
        await db.set_publication_channel(interaction.guild.id, canal.id)
        await interaction.followup.send(
            f"✅ Canal de publicação definido: {canal.mention}", ephemeral=True
        )

    # ------------------------------------------------------------------
    # /configurar categoria
    # ------------------------------------------------------------------
    @config_group.command(name="categoria", description="Categoria onde os tickets serão criados.")
    @app_commands.describe(categoria="Categoria dos tickets abertos.")
    async def config_categoria(
        self,
        interaction: discord.Interaction,
        categoria: discord.CategoryChannel,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not is_staff(interaction.user):
            await interaction.followup.send("Sem permissão.", ephemeral=True)
            return

        db = self.bot.database  # type: ignore[attr-defined]
        await db.set_ticket_category(interaction.guild.id, categoria.id)
        await interaction.followup.send(
            f"✅ Categoria dos tickets: **{categoria.name}**", ephemeral=True
        )

    # ------------------------------------------------------------------
    # /configurar fechados
    # ------------------------------------------------------------------
    @config_group.command(name="fechados", description="Categoria onde tickets fechados serão movidos.")
    @app_commands.describe(categoria="Categoria dos tickets fechados.")
    async def config_fechados(
        self,
        interaction: discord.Interaction,
        categoria: discord.CategoryChannel,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not is_staff(interaction.user):
            await interaction.followup.send("Sem permissão.", ephemeral=True)
            return

        db = self.bot.database  # type: ignore[attr-defined]
        await db.set_closed_category(interaction.guild.id, categoria.id)
        await interaction.followup.send(
            f"✅ Categoria dos fechados: **{categoria.name}**", ephemeral=True
        )

    # ------------------------------------------------------------------
    # /configurar aniversarios
    # ------------------------------------------------------------------
    @config_group.command(name="aniversarios", description="Canal onde os parabéns serão enviados.")
    @app_commands.describe(canal="Canal dos parabéns.")
    async def config_aniversarios(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not is_staff(interaction.user):
            await interaction.followup.send("Sem permissão.", ephemeral=True)
            return

        me = interaction.guild.me
        if me:
            perms = canal.permissions_for(me)
            if not (perms.view_channel and perms.send_messages and perms.embed_links):
                await interaction.followup.send(
                    "Preciso de Ver, Enviar Mensagens e Inserir Links nesse canal.",
                    ephemeral=True,
                )
                return

        db = self.bot.database  # type: ignore[attr-defined]
        await db.set_birthday_channel(interaction.guild.id, canal.id)
        await interaction.followup.send(
            f"✅ Canal dos parabéns: {canal.mention}", ephemeral=True
        )

    # ------------------------------------------------------------------
    # /configurar aniversarios-cargo
    # ------------------------------------------------------------------
    @config_group.command(name="aniversarios-cargo", description="Cargo temporário dado no dia do aniversário.")
    @app_commands.describe(cargo="Cargo que será dado e removido no dia.")
    async def config_aniversarios_cargo(
        self,
        interaction: discord.Interaction,
        cargo: discord.Role,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not is_staff(interaction.user):
            await interaction.followup.send("Sem permissão.", ephemeral=True)
            return

        me = interaction.guild.me
        if me and cargo >= me.top_role:
            await interaction.followup.send(
                "❌ Esse cargo tá acima do meu na hierarquia. Não vou conseguir atribuir.",
                ephemeral=True,
            )
            return

        db = self.bot.database  # type: ignore[attr-defined]
        await db.set_birthday_role(interaction.guild.id, cargo.id)
        await interaction.followup.send(
            f"✅ Cargo de aniversariante: {cargo.mention}", ephemeral=True
        )

    # ------------------------------------------------------------------
    # /configurar ia
    # ------------------------------------------------------------------
    @config_group.command(name="ia", description="
