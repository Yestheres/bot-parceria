from __future__ import annotations

import logging
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


class WizardManager:
    """Motor do wizard: processa cada resposta do usuário e avança o estado."""

    def __init__(self, bot: discord.Client, db: Database) -> None:
        self.bot = bot
        self.db = db

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    async def send_question(
        self,
        channel: discord.TextChannel,
        step: Step,
    ) -> None:
        """Manda a pergunta do passo atual."""
        question = STEP_QUESTIONS.get(step, "❓ Próxima pergunta...")
        await channel.send(question)

    async def process_answer(
        self,
        message: discord.Message,
        ticket: dict[str, Any],
    ) -> None:
        """Processa a resposta do usuário pro passo atual do ticket.

        Se a resposta for válida, avança o passo. Se não, pede de novo.
        """
        step = Step(ticket["step"])
        content = (message.content or "").strip()
        data: dict[str, Any] = dict(ticket["data"] or {})

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
        else:
            # CONFIRMAR / DONE: não processa texto aqui, só botão
            pass

    # ------------------------------------------------------------------
    # Handlers por passo
    # ------------------------------------------------------------------
    async def _handle_nome(
        self,
        message: discord.Message,
        ticket: dict[str, Any],
        data: dict[str, Any],
        content: str,
    ) -> None:
        if not content:
            await message.reply("❌ Manda um nome, por favor.")
            return
        if len(content) > MAX_SERVER_NAME_LENGTH:
            await message.reply(
                f"❌ Nome muito longo. Máximo: {MAX_SERVER_NAME_LENGTH} caracteres."
            )
            return

        data["name"] = content
        await self._advance(ticket, Step.DESCRICAO, data)

    async def _handle_descricao(
        self,
        message: discord.Message,
        ticket: dict[str, Any],
        data: dict[str, Any],
        content: str,
    ) -> None:
        if not content:
            await message.reply("❌ Escreve uma descrição, por favor.")
            return
        if len(content) > MAX_DESCRIPTION_LENGTH:
            await message.reply(
                f"❌ Descrição muito longa. Máximo: {MAX_DESCRIPTION_LENGTH} caracteres."
            )
            return

        data["description"] = content
        await self._advance(ticket, Step.IA_SIM_NAO, data)

    async def _handle_ia_sim_nao(
        self,
        message: discord.Message,
        ticket: dict[str, Any],
        data: dict[str, Any],
        content: str,
    ) -> None:
        answer = content.lower().strip()
        if answer not in {"sim", "não", "nao", "s", "n"}:
            await message.reply("❌ Responde `sim` ou `não`.")
            return

        wants_ai = answer in {"sim", "s"}

        if wants_ai:
            ai_config = await self.db.get_ai_config(ticket["guild_id"])
            if ai_config is None:
                await message.reply(
                    "⚠️ A IA **não está configurada** nesse servidor. "
                    "Vou seguir com a sua descrição manual.\n"
                    "_Peça pra staff configurar com `/configurar ia`._"
                )
            else:
                await message.channel.send("✨ Melhorando sua descrição com IA...")
                try:
                    improved = improve_description(
                        api_key=ai_config["api_key"],
                        base_url=ai_config["base_url"],
                        model=ai_config["model"],
                        server_name=data.get("name", ""),
                        description=data["description"],
                    )
                except Exception:
                    logger.exception("Erro ao chamar IA")
                    improved = None

                if improved:
                    data["description"] = improved
                    await message.channel.send(
                        "✅ Descrição melhorada! Confere abaixo:\n\n"
                        f">>> {improved}"
                    )
                else:
                    await message.channel.send(
                        "⚠️ Não consegui melhorar a descrição agora. "
                        "Vou seguir com a que você mandou."
                    )

        await self._advance(ticket, Step.LINK, data)

    async def _handle_link(
        self,
        message: discord.Message,
        ticket: dict[str, Any],
        data: dict[str, Any],
        content: str,
    ) -> None:
        if not content:
            await message.reply("❌ Manda o link do convite, por favor.")
            return

        await message.channel.send("🔎 Verificando o convite...")
        ok, reason, info = await check_invite(self.bot, content)

        if not ok:
            await message.reply(
                f"❌ {reason}\n\n_Manda o link de novo, por favor._"
            )
            return

        data["link"] = content
        if info:
            data["invite_name"] = info.get("name")
            data["invite_icon"] = info.get("icon_url")

        await message.channel.send(f"✅ {reason}")
        await self._advance(ticket, Step.COR, data)

    async def _handle_cor(
        self,
        message: discord.Message,
        ticket: dict[str, Any],
        data: dict[str, Any],
        content: str,
    ) -> None:
        color = content.lower().strip()
        if color not in EMBED_COLORS:
            options = ", ".join(f"`{c}`" for c in EMBED_COLORS)
            await message.reply(f"❌ Cor inválida. Escolhe uma dessas: {options}")
            return

        data["color"] = color
        await self._advance(ticket, Step.FOTO, data)

    async def _handle_foto(
        self,
        message: discord.Message,
        ticket: dict[str, Any],
        data: dict[str, Any],
        content: str,
    ) -> None:
        answer = content.lower().strip()

        if answer in {"padrão", "padrao", "default", "p"}:
            data["image_url"] = None
            await message.reply("✅ Vou usar o ícone do convite.")
        else:
            # Trata como URL
            if not content.startswith(("http://", "https://")):
                await message.reply(
                    "❌ Manda uma URL válida (começando com `http`) "
                    "ou responde `padrão`."
                )
                return
            if len(content) > MAX_IMAGE_URL_LENGTH:
                await message.reply("❌ URL muito longa.")
                return

            data["image_url"] = content
            await message.reply("✅ Imagem salva.")

        await self._advance(ticket, Step.CONFIRMAR, data)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _advance(
        self,
        ticket: dict[str, Any],
        next_step: Step,
        data: dict[str, Any],
    ) -> None:
        await self.db.update_ticket_step(ticket["id"], next_step.value, data)
        await self.send_question(ticket_channel(ticket, self.bot), next_step)


def ticket_channel(ticket: dict[str, Any], bot: discord.Client) -> discord.TextChannel:
    """Resolve o canal do ticket a partir do cache do bot."""
    channel = bot.get_channel(ticket["channel_id"])
    if not isinstance(channel, discord.TextChannel):
        raise RuntimeError(f"Canal do ticket {ticket['id']} não encontrado no cache.")
    return channel
