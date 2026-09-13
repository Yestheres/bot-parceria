# 🤝 Parceria

Bot de Discord para gerenciar parcerias entre servidores, com wizard interativo em canal privado.

## Como funciona

1. Usuário roda `/parceria`
2. O bot cria um **canal privado** só pra ele + staff
3. O bot faz 6 perguntas (nome, descrição, IA, link, cor, foto)
4. Ao final, a staff vê o preview e aprova/recusa
5. Aprovado → bot publica no canal de parcerias

## Comandos

### Público
- `/parceria` — abre um ticket de parceria
- `/cancelar` — cancela seu ticket aberto
- `/sobre` — info do bot
- `/ajuda` — lista de comandos

### Staff
- `/configurar staff <canal>` — onde os tickets chegam
- `/configurar publicacao <canal>` — onde publicar aprovadas
- `/configurar categoria <categoria>` — categoria dos tickets
- `/configurar fechados <categoria>` — categoria dos tickets fechados
- `/configurar ia <api_key> [modelo] [base_url]` — configura IA (só dono)
- `/configurar ia-remover` — remove IA (só dono)
- `/configurar ver` — mostra config atual

## Setup local

```bash
git clone https://github.com/Yestheres/bot-parceria
cd bot-parceria
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate no Windows
pip install -r requirements.txt
