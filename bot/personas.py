"""Elenco da Nortada: nomes de exibição e carregamento dos prompts."""
from . import config

PERSONAS = {
    "gerente": "👩‍💼 Marina · Gerente de Dados",
    "financeiro": "💰 Carlos · Financeiro",
    "marketing": "📣 Bia · Marketing",
    "operacoes": "📦 Joel · Operações",
    "entrevistador": "🎤 Paula · Entrevistadora",
    "senior": "🧑‍💻 Henrique · Eng. Sênior",
    "sistema": "🤖 Sistema",
}

NAMES = {
    "gerente": "Marina",
    "financeiro": "Carlos",
    "marketing": "Bia",
    "operacoes": "Joel",
    "entrevistador": "Paula",
    "senior": "Henrique",
}

STAKEHOLDERS = ("financeiro", "marketing", "operacoes")


def _read(rel):
    return (config.ROOT / rel).read_text(encoding="utf-8")


def bible():
    return _read("company/bible.md")


def prompt(key):
    if key == "gerente":
        return _read("personas/gerente.md")
    if key == "entrevistador":
        return _read("personas/entrevistador.md")
    if key == "senior":
        return _read("personas/senior.md")
    return _read("personas/stakeholders.md") + f"\n\nNesta conversa você é {NAMES[key]}."
