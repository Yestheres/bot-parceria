from __future__ import annotations

from enum import Enum


class Step(str, Enum):
    """Cada passo do wizard. Guardado no banco como string."""
    NOME = "nome"
    DESCRICAO = "descricao"
    IA_SIM_NAO = "ia_sim_nao"
    LINK = "link"
    COR = "cor"
    FOTO = "foto"
    CONFIRMAR = "confirmar"   # passo final: preview + botão enviar
    DONE = "done"             # wizard terminou, aguardando staff


# Ordem das perguntas
STEP_ORDER: list[Step] = [
    Step.NOME,
    Step.DESCRICAO,
    Step.IA_SIM_NAO,
    Step.LINK,
    Step.COR,
    Step.FOTO,
    Step.CONFIRMAR,
]


# Texto de cada pergunta
STEP_QUESTIONS: dict[Step, str] = {
    Step.NOME: (
        "❓ **Pergunta 1/6** — Qual é o **nome do seu servidor**?\n"
        "_Manda só o nome, sem enfeites._"
    ),
    Step.DESCRICAO: (
        "❓ **Pergunta 2/6** — Agora me manda uma **descrição** do seu servidor.\n"
        "_Escreve do jeito que você quiser, a gente organiza depois._"
    ),
    Step.IA_SIM_NAO: (
        "❓ **Pergunta 3/6** — Quer que eu **melhore a descrição com IA**?\n"
        "_Responde `sim` ou `não`._"
    ),
    Step.LINK: (
        "❓ **Pergunta 4/6** — Me manda o **convite do seu servidor** "
        "(ex.: `discord.gg/abc123`).\n"
        "_⚠️ Precisa ser um convite **permanente** (sem expiração)._"
    ),
    Step.COR: (
        "❓ **Pergunta 5/6** — Escolhe uma **cor** pra embed:\n"
        "`azul`, `roxo`, `verde`, `amarelo`, `vermelho`, `rosa`, `cinza`"
    ),
    Step.FOTO: (
        "❓ **Pergunta 6/6** — Quer uma **imagem/banner** pro seu servidor?\n"
        "_Manda uma URL de imagem ou responde `padrão` pra usar o ícone do convite._"
    ),
    Step.CONFIRMAR: (
        "✅ **Pronto!** Dá uma olhada no preview abaixo.\n"
        "_Se tiver tudo certo, clica em **Enviar para a staff**._"
    ),
}
