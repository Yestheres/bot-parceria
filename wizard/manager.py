from __future__ import annotations

import json
import logging
import re
from typing import Any

import discord

from config import (
    DEFAULT_COLOR,
    EMBED_COLORS,
    MAX_DESCRIPTION_LENGTH,
    MAX_IMAGE_URL_LENGTH,
    MAX_SERVER_NAME_LENGTH,
)
from database import Database
from services.ai import improve_description
from services.invites import check_invite
from wizard.steps import STEP_QUESTIONS, Step

logger = logging.getLogger(__name__)

_MENTION_RE = re.compile(r"^<@!?\d+>\s*")


def strip_leading_mention(content: str) -> str:
    return _MENTION_RE.sub("", content or "").strip()


def _coerce_data(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


class WizardManager:
    def __init__(self, bot: discord.Client, db: Database) -> None:
        self.bot = bot
        self.db = db

    async def send_question(
        self,
        channel: discord.TextChannel,
        step: Step,
    ) -> None:
        question = STEP_QUESTIONS.get(step, "❓ Próxima pergunta...")
        await channel.send(question)

    async def process_answer(
        self,
        message: discord.Message,
        ticket: dict[str, Any],
    ) -> None:
        step = Step(ticket["step"])
        content = strip_leading_mention(message.content)
        data: dict[str, Any] = _coerce_data(ticket.get("data"))

        logger.info(
            "Wizard: step=%s | raw=%r | clean=%r | data_keys=%s",
            step.value, message.content[:60], content[:60], list(data.keys()),
        )

        if step == Step.NOME:
            await self._handle_nome(message, ticket, data, content)
        elif step == Step.DESCRICAO:
            await self._handle_descricao(message, ticket, data, content)
        elif step == Step.IA_SIM_NAO:
            await self._handle_ia_sim_nao(message, ticket, data, content)
        elif step == Step.LINK:
            await self._handle_link(message, ticket, data, content)
        elif step == Step.COR:
            await self._handle_cor(message, ticket, data, content)
        elif step == Step.FOTO:
            await self._handle_foto(message, ticket, data, content)

    # ------------------------------------------------------------------
    async def _handle_nome(self, message, ticket, data, content) -> None:
        if not content:
            await message.channel.send(f"{message.author.mention} ❌ Manda um nome, por favor.")
            return
        if len(content) > MAX_SERVER_NAME_LENGTH:
            await message.channel.send(
                f"{message.author.mention} ❌ Nome muito longo (máx. {MAX_SERVER_NAME_LENGTH})."
            )
            return
        data["name"] = content
        await self._advance(ticket, Step.DESCRICAO, data)

    async def _handle_descricao(self, message, ticket, data, content) -> None:
        if not content:
            await message.channel.send(f"{message.author.mention} ❌ Escreve uma descrição.")
            return
        if len(content) > MAX_DESCRIPTION_LENGTH:
            await message.channel.send(
                f"{message.author.mention} ❌ Descrição muito longa (máx. {MAX_DESCRIPTION_LENGTH})."
            )
            return
        data["description"] = content
        await self._advance(ticket, Step.IA_SIM_NAO, data)

    async def _handle_ia_sim_nao(self, message, ticket, data, content) -> None:
        answer = content.lower().strip()
        if answer not in {"sim", "não", "nao", "s", "n"}:
            await message.channel.send(f"{message.author.mention} ❌ Responde `sim` ou `não`.")
            return

        wants_ai = answer in {"sim", "s"}
        if wants_ai:
            ai_config = await self.db.get_ai_config(ticket["guild_id"])
            if ai_config is None:
                await message.channel.send(
                    "⚠️ A IA não está configurada nesse servidor. "
                    "Vou seguir com a descrição manual."
                )
            else:
                await message.channel.send("✨ Melhorando sua descrição com IA...")
                try:
                    improved = improve_description(
                        api_key=ai_config["api_key"],
                        base_url=ai_config["base_url"],
                        model=ai_config["model"],
                        server_name=data.get("name", ""),
                        description=data.get("description", ""),
                    )
                except Exception:
                    logger.exception("Erro na IA")
                    improved = None

                if improved:
                    data["description"] = improved
                    await message.channel.send(
                        "✅ Descrição melhorada:\n\n" + f">>> {improved}"
                    )
                else:
                    await message.channel.send(
                        "⚠️ Não consegui melhorar agora. Seguindo com a manual."
                    )

        await self._advance(ticket, Step.LINK, data)

    async def _handle_link(self, message, ticket, data, content) -> None:
        if not content:
            await message.channel.send(f"{message.author.mention} ❌ Manda o link do convite.")
            return
        await message.channel.send("🔎 Verificando o convite...")
        ok, reason, info = await check_invite(self.bot, content)
        if not ok:
            await message.channel.send(
                f"{message.author.mention} ❌ {reason}\n_Manda o link de novo._"
            )
            return
        data["link"] = content
        if info:
            data["invite_name"] = info.get("name")
            data["invite_icon"] = info.get("icon_url")
        await message.channel.send(f"✅ {reason}")
        await self._advance(ticket, Step.COR, data)

    async def _handle_cor(self, message, ticket, data, content) -> None:
        color = content.lower().strip()
        if color not in EMBED_COLORS:
            options = ", ".join(f"`{c}`" for c in EMBED_COLORS)
            await message.channel.send(
                f"{message.author.mention} ❌ Cor inválida. Opções: {options}"
            )
            return
        data["color"] = color
        await self._advance(ticket, Step.FOTO, data)

    async def _handle_foto(self, message, ticket, data, content) -> None:
        answer = content.lower().strip()
        if answer in {"padrão", "padrao", "default", "p"}:
            data["image_url"] = None
            await message.channel.send("✅ Vou usar o ícone do convite.")
        else:
            if not content.startswith(("http://", "https://")):
                await message.channel.send(
                    f"{message.author.mention} ❌ Manda uma URL válida ou responde `padrão`."
                )
                return
            if len(content) > MAX_IMAGE_URL_LENGTH:
                await message.channel.send(f"{message.author.mention} ❌ URL muito longa.")
                return
            data["image_url"] = content
            await message.channel.send("✅ Imagem salva.")
        await self._advance(ticket, Step.CONFIRMAR, data)

    # ------------------------------------------------------------------
    async def _advance(
        self,
        ticket: dict[str, Any],
        next_step: Step,
        data: dict[str, Any],
    ) -> None:
        await self.db.update_ticket_step(ticket["id"], next_step.value, data)
        channel = ticket_channel(ticket, self.bot)

        # Se chegou na confirmação, manda preview + botões de staff
        if next_step == Step.CONFIRMAR:
            await self._send_confirmation(channel, ticket, data)
        else:
            await self.send_question(channel, next_step)

    async def _send_confirmation(
        self,
        channel: discord.TextChannel,
        ticket: dict[str, Any],
        data: dict[str, Any],
    ) -> None:
        """Manda preview da embed + botões de aprovar/recusar."""
        from ui.staff_review import StaffReviewView

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

        embed.set_footer(text="Preview — aguardando decisão da staff")

        view = StaffReviewView(self.bot, ticket["id"])

        link = data.get("link")
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

        await channel.send(
            "✅ **Wizard concluído!**\n"
            "Staff, deem uma olhada no preview e decidam:",
            embed=embed,
            view=view,
        )


def ticket_channel(ticket: dict[str, Any], bot: discord.Client) -> discord.TextChannel:
    channel = bot.get_channel(ticket["channel_id"])
    if not isinstance(channel, discord.TextChannel):
        raise RuntimeError(f"Canal do ticket {ticket['id']} não encontrado.")
    return channel
