# Nortada Work Simulator

Simulador de rotina de **engenheiro(a) de dados júnior** numa empresa fictícia (Nortada Marketplace).
As demandas chegam pelo **Telegram** em horários do dia, geradas por IA gratuita (ou, se não houver IA,
por um catálogo de 26 tickets de reserva). Para cada ticket você entrega um **documento** e um
**engenheiro sênior (IA)** faz a revisão com nota e perguntas.

> Tudo é simulação. Ao divulgar no LinkedIn/GitHub, deixe claro que são projetos de simulação de rotina,
> não experiência profissional. Isso é mais honesto e recrutadores valorizam.

## Como funciona

```
 schedule.yaml ──► bot (Python) ──► Telegram ──► você
      │               │  ▲                         │
      │               ▼  │                         ▼
      │          IA gratuita (Gemini/Groq)    /entregar <id> + documento.md
      ▼               │                            │
 tickets/catalog.yaml │ (reserva)                  ▼
                      └──────────────► Henrique (sênior IA): nota + perguntas
                                                   │
                       state.db (SQLite) ◄─────────┘   docs/ (seu portfólio)
```

Elenco: **Marina** (gerente), **Carlos** (financeiro), **Bia** (marketing), **Joel** (operações),
**Paula** (entrevistas) e **Henrique** (sênior revisor).

## Passo a passo

### 0. Pré-requisitos
- Python 3.10+ e Git
- PostgreSQL (você já usou no projeto Chinook)

### 1. Criar o bot no Telegram (grátis)
1. No Telegram, procure **@BotFather** e envie `/newbot`.
2. Escolha nome e username. Ele devolve o **token**. Cole em `TELEGRAM_BOT_TOKEN` no `.env`.
3. Abra uma conversa com o seu bot e mande `/start` (com o bot rodando, passo 4). Ele responde com o seu **chat id**.
   Cole em `TELEGRAM_CHAT_ID` e reinicie o bot. A partir daí ele só responde a você.

### 2. Conseguir uma chave de IA gratuita
- **Google AI Studio** (https://aistudio.google.com): crie uma API key gratuita e cole em `AI_API_KEY`.
  Confira no AI Studio qual modelo gratuito está disponível hoje e ajuste `AI_MODEL` se preciso.
- Alternativa: Groq, OpenRouter etc. (APIs compatíveis com OpenAI). Use `AI_PROVIDER=openai_compat`,
  `AI_BASE_URL` e `AI_MODEL` (veja `.env.example`).
- **Os limites das camadas gratuitas mudam.** Se a cota acabar, o bot continua com o catálogo de
  reserva e, na revisão, te entrega um arquivo-prompt para colar em qualquer chat gratuito.

### 3. Preparar o projeto
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env  (depois preencha)
```

### 4. Testar sem Telegram (recomendado antes de tudo)
```bash
python -m bot.main --cli              # chat no terminal: tente /agora facil, /fila, /entregar 1
python -m bot.main --simulate-day     # dispara todos os eventos do dia de uma vez
```

### 5. Rodar de verdade
```bash
python -m bot.main
```
Deixe o terminal aberto durante o seu "expediente". O bot só envia os eventos enquanto estiver rodando.
(Eventos atrasados até 3 horas ainda são enviados quando você liga o bot.)

### 6. Carregar os dados da empresa (Postgres)
1. Baixe o dataset Olist no Kaggle e coloque os CSVs em `data/`.
2. `createdb dw_nortada`
3. Na raiz do projeto: `psql -d dw_nortada -f sql/olist_schema.sql`
   (usa `\copy`, que só funciona no `psql`, não no SQLTools).

## Comandos no Telegram
| Comando | O que faz |
|---|---|
| `/fila` | tickets abertos e aguardando revisão |
| `/ver <id>` | relê um ticket |
| `/entregar <id>` | inicia a entrega; envie um `.md`/`.txt` (ou cole o texto) |
| `/agora facil\|medio\|dificil\|incidente\|entrevista` | pede um ticket na hora (treino extra) |
| `/fase <1-8>` | define seu nível no roadmap (tickets respeitam a fase) |
| `/placar` | notas, atrasos e andamento |
| `/nota <id> <0-10>` | registra nota manualmente (modo sem IA) |
| `/revisar <id>` | refaz a revisão de um documento já entregue |
| texto livre | conversa com a pessoa do último ticket (tire dúvidas) |

## Sua rotina de trabalho (sugestão)
1. Ligue o bot e comece o dia. Tickets chegam em `schedule.yaml` (8h30, 10h30, 13h30, 15h45, 17h50, 19h).
2. Faça perguntas de esclarecimento antes de executar, como no trabalho real.
3. Resolva no Postgres; salve o SQL/Python em uma branch do Git.
4. Escreva o documento (template em `templates/documento_ticket.md`) e entregue com `/entregar`.
5. Responda às perguntas do Henrique por escrito, no próprio documento (versão 2).
6. Suba o documento e o código no GitHub (`docs/`, `tickets/`). Use mensagens de commit claras.
7. Domingo é folga (escala 6x1). Descanso faz parte do aprendizado.

## Personalizar
- `schedule.yaml`: horários, probabilidade (`chance`) e tipos de ticket de cada evento.
- `company/bible.md`: a "realidade" da empresa. Quanto mais detalhada, mais consistentes as IAs.
- `personas/*.md`: o jeito de cada personagem. Ajuste o tom e a exigência do sênior.
- `tickets/catalog.yaml`: adicione seus próprios tickets de reserva.

## Estrutura
```
nortada-work-sim/
├── bot/            # código (Telegram, IA, agenda, banco, revisão)
├── company/        # bíblia da empresa
├── personas/       # prompts das personas
├── templates/      # template do documento
├── tickets/        # catálogo de reserva
├── sql/            # schema + carga do Olist
├── docs/           # seus documentos e revisões (criado pelo bot)
└── schedule.yaml
```

## Segurança
- Nunca suba `.env` (token e chave) para o Git; já está no `.gitignore`.
- O bot ignora qualquer chat que não seja o seu `TELEGRAM_CHAT_ID`.
- Os documentos são enviados ao provedor de IA que você escolher; não inclua dados reais de pessoas.
