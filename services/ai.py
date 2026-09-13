from __future__ import annotations

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "Você é uma IA especializada em melhorar descrições de servidores Discord "
    "para propostas de parceria. "
    "Não invente fatos que não foram informados. "
    "Apenas embeleze o texto, use emojis de forma natural e mantenha a proposta "
    "fiel ao que foi dito. "
    "Responda em português, sem listas, sem mencionar que você é IA. "
    "Máximo de 3 parágrafos curtos."
)


def improve_description(
    api_key: str,
    base_url: str,
    model: str,
    server_name: str,
    description: str,
) -> str | None:
    """Chama a IA pra melhorar a descrição. Retorna None se falhar."""
    url = f"{base_url.rstrip('/')}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Servidor: {server_name}\n\n"
                    f"Descrição atual:\n{description}\n\n"
                    "Reescreva essa descrição de forma mais bonita, acolhedora e "
                    "persuasiva. Mantenha a essência. Adicione emojis com moderação."
                ),
            },
        ],
        "temperature": 0.7,
    }

    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            return content or None
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        logger.warning("IA HTTPError %s: %s", e.code, body)
        return None
    except URLError as e:
        logger.warning("IA URLError: %s", e)
        return None
    except (KeyError, ValueError, TimeoutError) as e:
        logger.warning("IA erro ao parsear resposta: %s", e)
        return None
