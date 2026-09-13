from __future__ import annotations

import logging
from urllib.parse import urlparse

import discord

logger = logging.getLogger(__name__)


def extract_invite_code(link: str) -> str | None:
    """Extrai o código do convite de uma URL do Discord."""
    link = (link or "").strip()
    if not link:
        return None

    if not link.startswith(("http://", "https://")):
        link = "https://" + link

    parsed = urlparse(link)
    hostname = (parsed.hostname or "").lower()
    parts = [p for p in parsed.path.split("/") if p]

    if hostname in {"discord.gg", "discord.me", "discord.li"}:
        return parts[0] if parts else None

    if hostname in {
        "discord.com", "www.discord.com",
        "discordapp.com", "www.discordapp.com",
    }:
        if len(parts) >= 2 and parts[0].lower() == "invite":
            return parts[1]

    return None


async def check_invite(
    bot: discord.Client,
    link: str,
) -> tuple[bool, str, dict[str, str | None] | None]:
    """Valida um convite do Discord."""
    code = extract_invite_code(link)
    if code is None:
        return False, "O link não parece ser um convite do Discord válido.", None

    canonical = f"https://discord.gg/{code}"

    try:
        invite = await bot.fetch_invite(
            canonical,
            with_counts=False,
            with_expiration=True,
        )
    except discord.NotFound:
        return False, "Esse convite não existe ou já expirou.", None
    except discord.Forbidden:
        return False, "Não consegui verificar esse convite (sem permissão).", None
    except discord.HTTPException as e:
        logger.warning("Erro HTTP ao checar convite %s: %s", canonical, e)
        return False, "Não consegui verificar o convite agora. Tente de novo em alguns segundos.", None

    if invite.guild is None:
        return False, "Esse convite não aponta pra um servidor.", None

    if invite.max_age is None or invite.max_age > 0:
        return (
            False,
            "Esse convite é **temporário**. Gere um convite **permanente** "
            "(sem tempo de expiração) e mande de novo.",
            None,
        )

    from datetime import datetime, timezone
    if invite.expires_at is not None and invite.expires_at <= datetime.now(timezone.utc):
        return False, "Esse convite já expirou.", None

    icon_url = invite.guild.icon.url if invite.guild.icon else None
    info = {
        "name": invite.guild.name,
        "icon_url": icon_url,
    }
    return True, "Convite válido e permanente.", info
