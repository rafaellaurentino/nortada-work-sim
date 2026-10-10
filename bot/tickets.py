"""Criação de tickets: tenta a IA; se não houver IA (ou falhar), usa o catálogo de reserva."""
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import yaml

from . import ai, config, db
from .personas import PERSONAS, bible, prompt

KIND_PERSONAS = {
    "adhoc": ["gerente", "marketing", "financeiro", "operacoes"],
    "bug": ["gerente", "operacoes"],
    "pipeline": ["gerente"],
    "modelagem": ["gerente"],
    "qualidade": ["gerente", "financeiro"],
    "otimizacao": ["gerente"],
    "incidente": ["financeiro", "operacoes", "marketing"],
    "review": ["gerente"],
    "entrevista": ["entrevistador"],
}

DEFAULT_HOURS = {"facil": 4, "medio": 8, "dificil": 24}
KIND_EXTRA = {
    "incidente": "É um INCIDENTE: tom de urgência, prazo curto (1 a 3 horas), com material de apoio "
    "(trecho de log, query, número divergente) escrito dentro do próprio ticket.",
    "entrevista": "É um desafio de ENTREVISTA técnica de nível júnior, com tempo sugerido e o que será avaliado.",
    "bug": "É um BUG: inclua dentro do ticket a query ou o trecho de código com defeito.",
    "review": "É um pedido de CODE REVIEW: inclua dentro do ticket o código a ser revisado.",
}


def now():
    return datetime.now(ZoneInfo(config.TZ))


def current_phase():
    return int(db.get_kv("phase", "1"))


def load_catalog():
    with open(config.ROOT / "tickets" / "catalog.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def pick_from_catalog(kind, difficulty, phase):
    cat = load_catalog()
    used = set(db.used_catalog_ids())
    fresh = [t for t in cat if t["id"] not in used and t["phase"] <= phase]
    special = kind in ("entrevista", "incidente")

    ladder = [
        [t for t in fresh if t["kind"] == kind and t["difficulty"] == difficulty],
        [t for t in fresh if t["kind"] == kind],
        [
            t for t in fresh
            if t["difficulty"] == difficulty
            and (special or t["kind"] not in ("entrevista", "incidente"))
        ],
    ]
    for pool in ladder:
        if pool:
            return random.choice(pool)
    # catálogo esgotado nessa fase: reaproveita um ticket do mesmo tipo
    reuse = [t for t in cat if t["phase"] <= phase and t["kind"] == kind]
    reuse = reuse or [t for t in cat if t["phase"] <= phase] or cat
    return random.choice(reuse)


def generate_with_ai(kind, difficulty, phase, persona_key):
    if not ai.available():
        return None
    recent = db.recent_titles(12)
    system = (
        prompt(persona_key)
        + "\n\n# CONTEXTO DA EMPRESA\n"
        + bible()
        + "\n\n# TAREFA\nVocê vai criar UM novo ticket de trabalho para o engenheiro de dados júnior."
    )
    user = (
        f"Tipo do ticket: {kind}\nDificuldade: {difficulty} (para um júnior)\nFase atual do júnior: {phase}\n"
        f"{KIND_EXTRA.get(kind, '')}\n"
        f"Evite repetir estes temas recentes: {recent}\n\n"
        "Escreva o campo body exatamente como você mandaria no chat (em personagem, português do Brasil), "
        "com contexto de negócio. Use SOMENTE tabelas e colunas da bíblia da empresa.\n"
        "Responda APENAS com JSON válido, sem texto fora dele, neste formato:\n"
        '{"title": "...", "body": "...", "deliverable": "o que precisa ser entregue", '
        '"notes_for_senior": "critérios de avaliação e armadilhas (o júnior não vê isso)", '
        '"deadline_hours": 4}'
    )
    data = ai.extract_json(ai.generate(system, user))
    if not data or not data.get("title") or not data.get("body"):
        return None
    return data


def make_ticket(kind, difficulty):
    phase = current_phase()
    persona_key = random.choice(KIND_PERSONAS.get(kind, ["gerente"]))
    data = generate_with_ai(kind, difficulty, phase, persona_key)

    if data:
        hours = data.get("deadline_hours")
        base = {
            "catalog_id": None,
            "kind": kind,
            "difficulty": difficulty,
            "persona": persona_key,
            "title": str(data["title"]).strip(),
            "body": str(data["body"]).strip(),
            "deliverable": str(data.get("deliverable", "")).strip(),
            "notes_for_senior": str(data.get("notes_for_senior", "")).strip(),
            "source": "ai",
        }
    else:
        item = pick_from_catalog(kind, difficulty, phase)
        hours = None
        base = {
            "catalog_id": item["id"],
            "kind": item["kind"],
            "difficulty": item["difficulty"],
            "persona": item["persona"],
            "title": item["title"],
            "body": item["body"].strip(),
            "deliverable": item.get("deliverable", ""),
            "notes_for_senior": str(item.get("notes_for_senior", "")).strip(),
            "source": "catalog",
        }

    if not isinstance(hours, (int, float)) or not 1 <= hours <= 72:
        hours = 3 if base["kind"] == "incidente" else DEFAULT_HOURS.get(base["difficulty"], 8)
    created = now()
    base["phase"] = phase
    base["created_at"] = created.isoformat(timespec="minutes")
    base["deadline_at"] = (created + timedelta(hours=hours)).isoformat(timespec="minutes")
    return base


def fmt_deadline(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m %H:%M")
    except (TypeError, ValueError):
        return "-"


def format_ticket(tid, t):
    text = (
        f"🎫 Ticket #{tid} · {t['difficulty']} · {t['kind']}\n"
        f"{t['title']}\n\n{t['body']}\n\n"
    )
    if t.get("deliverable"):
        text += f"📦 Entregável: {t['deliverable']}\n"
    text += f"⏰ Prazo: {fmt_deadline(t['deadline_at'])}\n\nPara entregar: /entregar {tid}"
    return text


def issue(kind, difficulty, tp):
    ticket = make_ticket(kind, difficulty)
    tid = db.create_ticket(ticket)
    tp.send(PERSONAS[ticket["persona"]], format_ticket(tid, ticket))
    db.set_kv("last_ticket", tid)
    db.set_kv("last_persona", ticket["persona"])
    return tid
