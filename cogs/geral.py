from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import BOT_NAME, EMBED_COLORS


class Geral(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="sobre", description="Mostra informações sobre o bot.")
    async def sobre(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title=f"✨ {BOT_NAME}",
            description="Bot de parcerias entre servidores Discord.",
            color=discord.Color.blurple(),
        )
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="🏠 Servidores", value=f"`{len(self.bot.guilds)}`", inline=True)
        embed.add_field(name="📦 discord.py", value=f"`{discord.__version__}`", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ajuda", description="Mostra os comandos do bot.")
    async def ajuda(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title=f"📖 Ajuda — {BOT_NAME}",
            description="Comandos disponíveis:",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="/parceria",
            value="Abre um canal privado pra você montar sua proposta de parceria.",
            inline=False,
        )
        embed.add_field(
            name="/cancelar",
            value="Cancela o ticket de parceria aberto por você.",
            inline=False,
        )
        embed.add_field(
            name="/configurar",
            value="(Staff) Configura canais, categoria, cargo da staff e IA.",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Geral(bot))
