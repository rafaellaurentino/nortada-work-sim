"""Agenda do dia: decide quando cada evento (ticket, pressão, cobrança) acontece."""
import random
from datetime import datetime, timedelta

import yaml

from . import ai, config, db, tickets
from .personas import PERSONAS, STAKEHOLDERS, bible, prompt

PRESSURE_TEMPLATES = [
    "Conseguiu olhar o ticket #{id} ({title})? Preciso disso o quanto antes.",
    "Oi, o #{id} ({title}) está andando? Tenho gente me cobrando por aqui.",
    "Passando pra saber do #{id} ({title}). Tem previsão de quando fica pronto?",
]


def load_schedule():
    with open(config.ROOT / "schedule.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _pressao(tp):
    pending = [t for t in db.open_tickets() if t["persona"] != "entrevistador"]
    if not pending:
        return False
    t = pending[0]
    key = t["persona"]
    msg = None
    if ai.available():
        msg = ai.generate(
            prompt(key) + "\n\n# CONTEXTO DA EMPRESA\n" + bible(),
            f"Você pediu o ticket #{t['id']} '{t['title']}':\n{t['body']}\n\n"
            "Ele ainda não foi entregue. Escreva UMA mensagem curta (1 a 3 frases) cobrando, "
            "em personagem, sem dar a solução. Responda só com a mensagem.",
            temperature=0.9,
        )
    if not msg:
        msg = random.choice(PRESSURE_TEMPLATES).format(id=t["id"], title=t["title"])
    tp.send(PERSONAS[key], msg.strip())
    db.set_kv("last_ticket", t["id"])
    db.set_kv("last_persona", key)
    return True


def _cobranca(tp):
    pending = db.open_tickets()
    if not pending:
        return False
    now = tickets.now()
    lines = []
    for t in pending:
        late = ""
        try:
            if datetime.fromisoformat(t["deadline_at"]) < now:
                late = " ⚠️ ATRASADO"
        except (TypeError, ValueError):
            pass
        lines.append(f"- #{t['id']} {t['title']} (prazo {tickets.fmt_deadline(t['deadline_at'])}){late}")
    tp.send(
        PERSONAS["gerente"],
        "Fechando o dia. Ainda tenho estes tickets sem documento:\n"
        + "\n".join(lines)
        + "\n\nSó considero pronto com o documento para o Henrique. Use /entregar <id>.",
    )
    return True


def run_slot(slot, tp, force=False):
    """Executa um evento. Retorna True se algo foi enviado."""
    if not force and random.random() > slot.get("chance", 1.0):
        return False
    action = slot.get("action", "tickets")
    if action == "pressao":
        return _pressao(tp)
    if action == "cobranca":
        return _cobranca(tp)

    items = slot.get("items", [])
    intro = slot.get("intro")
    if intro:
        who = "entrevistador" if any(i["kind"] == "entrevista" for i in items) else "gerente"
        tp.send(PERSONAS[who], intro)
    for item in items:
        tickets.issue(item["kind"], item["difficulty"], tp)
    return True


def check(tp, now):
    """Roda os eventos cuja hora já chegou (janela de 3h) e que ainda não foram enviados hoje."""
    sched = load_schedule()
    if now.weekday() in sched.get("days_off", []):
        return []
    ran = []
    day = now.strftime("%Y-%m-%d")
    for slot in sched["slots"]:
        if "weekdays" in slot and now.weekday() not in slot["weekdays"]:
            continue
        hh, mm = map(int, slot["time"].split(":"))
        start = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if not (start <= now < start + timedelta(hours=3)):
            continue
        if db.slot_sent(day, slot["name"]):
            continue
        db.mark_slot(day, slot["name"])
        if run_slot(slot, tp):
            ran.append(slot["name"])
    return ran
