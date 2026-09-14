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
    @config_group.command(name="ia", description="Configura a IA do servidor.")
    @app_commands.describe(
        api_key="Sua chave de API (OpenAI, OpenRouter, etc.).",
        modelo="Modelo (ex.: gpt-4o-mini, glm-4.5-flash).",
        base_url="URL base (padrão: OpenRouter).",
    )
    async def config_ia(
        self,
        interaction: discord.Interaction,
        api_key: str,
        modelo: str = "glm-4.5-flash",
        base_url: str = "https://openrouter.ai/api/v1",
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.followup.send(
                "Só o **dono do servidor** pode configurar a IA.", ephemeral=True
            )
            return

        if len(api_key) < 10:
            await interaction.followup.send("Chave muito curta.", ephemeral=True)
            return

        db = self.bot.database  # type: ignore[attr-defined]
        await db.set_ai_config(interaction.guild.id, api_key, modelo, base_url)

        masked = f"...{api_key[-4:]}" if len(api_key) > 4 else "***"
        await interaction.followup.send(
            f"✅ IA configurada.\n"
            f"• Modelo: `{modelo}`\n"
            f"• Base URL: `{base_url}`\n"
            f"• Chave: `{masked}`",
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    # /configurar ia-remover
    # ------------------------------------------------------------------
    @config_group.command(name="ia-remover", description="Remove a IA configurada do servidor.")
    async def config_ia_remover(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.followup.send(
                "Só o dono do servidor pode remover a IA.", ephemeral=True
            )
            return

        db = self.bot.database  # type: ignore[attr-defined]
        await db.clear_ai_config(interaction.guild.id)
        await interaction.followup.send("✅ IA removida.", ephemeral=True)

    # ------------------------------------------------------------------
    # /configurar ver
    # ------------------------------------------------------------------
    @config_group.command(name="ver", description="Mostra a configuração atual do servidor.")
    async def config_ver(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not is_staff(interaction.user):
            await interaction.followup.send("Sem permissão.", ephemeral=True)
            return

        db = self.bot.database  # type: ignore[attr-defined]
        gid = interaction.guild.id

        approval = await db.get_approval_channel(gid)
        publication = await db.get_publication_channel(gid)
        category = await db.get_ticket_category(gid)
        closed = await db.get_closed_category(gid)
        ai = await db.get_ai_config(gid)
        bday_channel = await db.get_birthday_channel(gid)
        bday_role = await db.get_birthday_role(gid)

        def fmt_ch(cid: int | None) -> str:
            return f"<#{cid}>" if cid else "❌ não definido"

        def fmt_cat(cid: int | None) -> str:
            if not cid:
                return "❌ não definida"
            ch = interaction.guild.get_channel(cid)
            return f"**{ch.name}**" if ch else f"`{cid}`"

        def fmt_role(rid: int | None) -> str:
            if not rid:
                return "❌ não definido"
            r = interaction.guild.get_role(rid)
            return f"**{r.name}**" if r else f"`{rid}`"

        embed = discord.Embed(
            title="⚙️ Configuração do servidor",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Canal da staff", value=fmt_ch(approval), inline=False)
        embed.add_field(name="Canal de publicação", value=fmt_ch(publication), inline=False)
        embed.add_field(name="Categoria dos tickets", value=fmt_cat(category), inline=False)
        embed.add_field(name="Categoria dos fechados", value=fmt_cat(closed), inline=False)
        embed.add_field(name="Canal dos parabéns", value=fmt_ch(bday_channel), inline=False)
        embed.add_field(name="Cargo de aniversariante", value=fmt_role(bday_role), inline=False)
        if ai:
            masked = f"...{ai['api_key'][-4:]}" if ai["api_key"] else "***"
            embed.add_field(
                name="IA",
                value=f"✅ `{ai['model']}`\n`{ai['base_url']}`\nChave: `{masked}`",
                inline=False,
            )
        else:
            embed.add_field(name="IA", value="❌ não configurada", inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Config(bot))
