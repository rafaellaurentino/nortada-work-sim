"""Entrega do documento e revisão pelo engenheiro sênior (IA)."""
import re

from . import ai, config, db, tickets
from .personas import PERSONAS, bible, prompt

MAX_DOC_CHARS = 30000


def slugify(text):
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text[:40] or "ticket"


def save_doc(t, text):
    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.DOCS_DIR / f"ticket_{t['id']:03d}_{slugify(t['title'])}.md"
    path.write_text(text, encoding="utf-8")
    return path


def parse_score(text):
    m = re.search(r"NOTA GERAL:\s*([0-9]+(?:[.,][0-9]+)?)\s*/\s*10", text or "", re.I)
    return float(m.group(1).replace(",", ".")) if m else None


def build_user_prompt(t, doc):
    return (
        f"# TICKET #{t['id']} ({t['difficulty']} · {t['kind']}) — pedido por {t['persona']}\n"
        f"Título: {t['title']}\n\nPedido original:\n{t['body']}\n\n"
        f"Entregável esperado: {t['deliverable']}\n\n"
        f"Notas internas para você, sênior (o júnior não viu): {t['notes_for_senior']}\n\n"
        f"Prazo: {tickets.fmt_deadline(t['deadline_at'])} · Entregue em: {tickets.fmt_deadline(t['delivered_at'])}\n\n"
        f"# DOCUMENTO ENTREGUE PELO JÚNIOR\n{doc[:MAX_DOC_CHARS]}\n\n"
        "Faça a revisão seguindo EXATAMENTE o formato obrigatório da sua persona."
    )


def save_review(t, text):
    out = config.DOCS_DIR / "reviews"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"ticket_{t['id']:03d}_{slugify(t['title'])}_review.md"
    path.write_text(text, encoding="utf-8")
    return path


def run_review(tid, doc_text, tp, new_delivery=True):
    """new_delivery=False refaz só a revisão (/revisar), sem mexer em data de entrega nem no arquivo."""
    t = db.get_ticket(tid)
    if new_delivery:
        path = save_doc(t, doc_text)
        db.save_delivery(tid, path, tickets.now().isoformat(timespec="minutes"))
        t = db.get_ticket(tid)

    tp.send(PERSONAS["senior"], f"Recebi o documento do ticket #{tid}. Vou ler com calma e já volto.")
    db.set_kv("last_persona", "senior")
    db.set_kv("last_ticket", tid)

    system = prompt("senior") + "\n\n# CONTEXTO DA EMPRESA\n" + bible()
    user = build_user_prompt(t, doc_text)
    out = ai.generate(system, user, temperature=0.3, timeout=120) if ai.available() else None

    if out:
        score = parse_score(out)
        save_review(t, out)
        db.save_review(tid, out, score)
        tp.send(PERSONAS["senior"], out)
        if score is None:
            tp.send(PERSONAS["sistema"], f"Não consegui ler a nota automaticamente. Registre com /nota {tid} <0-10>.")
        return

    # Sem IA configurada (ou falhou): gera o prompt pronto para colar em qualquer chat gratuito.
    combined = f"{system}\n\n---\n\n{user}\n"
    tp.send_file(
        PERSONAS["senior"],
        f"prompt_revisao_ticket_{tid:03d}.md",
        combined.encode("utf-8"),
        caption=f"Revisão do ticket #{tid}",
    )
    tp.send(
        PERSONAS["sistema"],
        "A IA não respondeu (sem AI_API_KEY ou erro/cota). Cole o arquivo acima em um chat gratuito "
        "(Gemini, ChatGPT ou Claude), leia a revisão e registre a nota com "
        f"/nota {tid} <0-10>. Salve a resposta em docs/reviews/ para o seu portfólio.",
    )
