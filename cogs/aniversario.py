from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

BRT = ZoneInfo("America/Sao_Paulo")

MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

DIAS_POR_MES = {
    1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30,
    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31,
}


def validar_data(dia: int, mes: int) -> str | None:
    """Retorna mensagem de erro, ou None se válida."""
    if mes < 1 or mes > 12:
        return "Mês inválido. Use de 1 a 12."
    if dia < 1 or dia > DIAS_POR_MES[mes]:
        return f"Dia inválido pra {MESES_PT[mes]}. Use de 1 a {DIAS_POR_MES[mes]}."
    return None


def is_staff(member: discord.Member) -> bool:
    perms = member.guild_permissions
    return perms.administrator or perms.manage_guild


class Aniversario(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    grupo = app_commands.Group(
        name="aniversario",
        description="Gerencia aniversários do servidor.",
    )

    # ------------------------------------------------------------------
    # /aniversario definir
    # ------------------------------------------------------------------
    @grupo.command(name="definir", description="Define o seu aniversário (ou de outra pessoa, se for staff).")
    @app_commands.describe(
        dia="Dia do aniversário (1-31).",
        mes="Mês do aniversário (1-12).",
        usuario="[Staff] Defina o aniversário de outra pessoa.",
    )
    async def definir(
        self,
        interaction: discord.Interaction,
        dia: int,
        mes: int,
        usuario: discord.Member | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.followup.send("Esse comando só funciona em servidor.", ephemeral=True)
            return

        erro = validar_data(dia, mes)
        if erro:
            await interaction.followup.send(f"❌ {erro}", ephemeral=True)
            return

        # Se especificou outro usuário, precisa ser staff
        alvo = usuario or interaction.user
        if usuario is not None and usuario.id != interaction.user.id:
            if not is_staff(interaction.user):
                await interaction.followup.send(
                    "❌ Só a staff pode definir o aniversário de outra pessoa.",
                    ephemeral=True,
                )
                return

        db = self.bot.database  # type: ignore[attr-defined]
        await db.upsert_birthday(
            guild_id=interaction.guild.id,
            user_id=alvo.id,
            day=dia,
            month=mes,
            created_by=interaction.user.id,
        )

        if alvo.id == interaction.user.id:
            await interaction.followup.send(
                f"✅ Aniversário definido: **{dia:02d}/{mes:02d}** ({dia} de {MESES_PT[mes]}).",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"✅ Aniversário de {alvo.mention} definido: **{dia:02d}/{mes:02d}**.",
                ephemeral=True,
            )

    # ------------------------------------------------------------------
    # /aniversario remover
    # ------------------------------------------------------------------
    @grupo.command(name="remover", description="Remove o seu aniversário (ou de outra pessoa, se for staff).")
    @app_commands.describe(usuario="[Staff] Remova o aniversário de outra pessoa.")
    async def remover(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return

        alvo = usuario or interaction.user
        if usuario is not None and usuario.id != interaction.user.id:
            if not is_staff(interaction.user):
                await interaction.followup.send(
                    "❌ Só a staff pode remover o aniversário de outra pessoa.",
                    ephemeral=True,
                )
                return

        db = self.bot.database  # type: ignore[attr-defined]
        removido = await db.remove_birthday(interaction.guild.id, alvo.id)

        if removido:
            if alvo.id == interaction.user.id:
                await interaction.followup.send("✅ Seu aniversário foi removido.", ephemeral=True)
            else:
                await interaction.followup.send(
                    f"✅ Aniversário de {alvo.mention} removido.", ephemeral=True
                )
        else:
            await interaction.followup.send(
                "❌ Não encontrei nenhum aniversário registrado.", ephemeral=True
            )

    # ------------------------------------------------------------------
    # /aniversario listar
    # ------------------------------------------------------------------
    @grupo.command(name="listar", description="Lista os próximos aniversários do servidor.")
    async def listar(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            return

        db = self.bot.database  # type: ignore[attr-defined]
        todos = await db.list_birthdays_for_guild(interaction.guild.id)

        if not todos:
            await interaction.followup.send(
                "📭 Nenhum aniversário registrado ainda.", ephemeral=True
            )
            return

        hoje = datetime.now(BRT).date()

        # Ordena por "próximo aniversário" a partir de hoje
        def proximo_dia(item):
            d, m = item["day"], item["month"]
            try:
                este_ano = hoje.replace(month=m, day=d)
            except ValueError:
                # 29/02 em ano não bissexto
                este_ano = hoje.replace(month=2, day=28)
            if este_ano < hoje:
                try:
                    return este_ano.replace(year=este_ano.year + 1)
                except ValueError:
                    return este_ano.replace(year=este_ano.year + 1, day=28)
            return este_ano

        todos.sort(key=proximo_dia)

        linhas = []
        for item in todos[:30]:  # limite de 30 pra não estourar
            uid = item["user_id"]
            d, m = item["day"], item["month"]
            proximo = proximo_dia(item)
            dias_faltando = (proximo - hoje).days
            if dias_faltando == 0:
                quando = "🎉 **HOJE!**"
            elif dias_faltando == 1:
                quando = "amanhã"
            else:
                quando = f"em {dias_faltando} dias"
            linhas.append(f"<@{uid}> — **{d:02d}/{m:02d}** ({quando})")

        embed = discord.Embed(
            title="🎂 Próximos aniversários",
            description="\n".join(linhas),
            color=discord.Color.birthday() if hasattr(discord.Color, "birthday") else discord.Color.magenta(),
        )
        embed.set_footer(text=f"Total: {len(todos)} aniversários registrados")

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # /aniversario hoje
    # ------------------------------------------------------------------
    @grupo.command(name="hoje", description="Mostra quem faz aniversário hoje.")
    async def hoje(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            return

        agora = datetime.now(BRT)
        db = self.bot.database  # type: ignore[attr-defined]
        aniversariantes = await db.get_birthdays_on(interaction.guild.id, agora.month, agora.day)

        if not aniversariantes:
            await interaction.followup.send(
                "😴 Ninguém faz aniversário hoje.", ephemeral=True
            )
            return

        mencoes = ", ".join(f"<@{b['user_id']}>" for b in aniversariantes)
        await interaction.followup.send(
            f"🎉 **Aniversariantes de hoje:** {mencoes}", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Aniversario(bot))
