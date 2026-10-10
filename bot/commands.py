"""Tratamento das mensagens do usuário: comandos, entrega de documentos e conversa com as personas."""
import json
import random

from . import ai, config, db, review, tickets
from .personas import NAMES, PERSONAS, bible, prompt

HELP = """Comandos:
/fila - tickets abertos e aguardando revisão
/ver <id> - relê um ticket
/entregar <id> - inicia a entrega do documento (envie um .md/.txt ou cole o texto)
/cancelar - cancela a entrega em andamento
/agora <facil|medio|dificil|incidente|entrevista> - pede um ticket na hora
/fase <1-8> - define sua fase atual no roadmap
/placar - seu desempenho
/nota <id> <0-10> - registra a nota manualmente
/revisar <id> - pede a revisão de novo do documento já entregue
/ajuda - esta mensagem

Qualquer outra mensagem vira conversa com a pessoa do último ticket (tire dúvidas, peça contexto)."""

NOW_CHOICES = {
    "facil": [("adhoc", "facil"), ("bug", "facil")],
    "medio": [("adhoc", "medio"), ("pipeline", "medio"), ("modelagem", "medio"),
              ("qualidade", "medio"), ("otimizacao", "medio"), ("review", "medio")],
    "dificil": [("pipeline", "dificil"), ("modelagem", "dificil"), ("qualidade", "dificil"),
                ("incidente", "dificil")],
    "incidente": [("incidente", "dificil"), ("incidente", "medio")],
    "entrevista": [("entrevista", "facil"), ("entrevista", "medio"), ("entrevista", "dificil")],
}


def sys_msg(tp, text):
    tp.send(PERSONAS["sistema"], text)


def handle(msg, tp):
    chat_id = str(msg["chat"]["id"])
    text = (msg.get("text") or msg.get("caption") or "").strip()

    # Primeiro uso: ainda não configurou o chat id. Só responde ao /start.
    if not config.TELEGRAM_CHAT_ID:
        if text.startswith("/start"):
            tp.send_raw(
                chat_id,
                f"Seu chat id é {chat_id}. Coloque esse número em TELEGRAM_CHAT_ID no arquivo .env "
                "e reinicie o bot.",
            )
        return
    if chat_id != str(config.TELEGRAM_CHAT_ID):
        return  # ignora qualquer outra pessoa

    awaiting = db.get_kv("awaiting_doc")

    if msg.get("document") and awaiting:
        return receive_doc_file(msg["document"], int(awaiting), tp)
    if text.startswith("/"):
        return command(text, tp)
    if awaiting and text:
        return receive_doc(int(awaiting), text, tp)
    if text:
        return chat_in_character(text, tp)


def command(text, tp):
    parts = text.split()
    cmd = parts[0].split("@")[0].lower()
    args = parts[1:]

    if cmd in ("/start", "/ajuda", "/help"):
        sys_msg(tp, "Bem-vindo(a) à Nortada! Você é o(a) engenheiro(a) de dados júnior.\n\n" + HELP)
    elif cmd == "/fila":
        cmd_fila(tp)
    elif cmd == "/ver":
        cmd_ver(args, tp)
    elif cmd == "/entregar":
        cmd_entregar(args, tp)
    elif cmd == "/cancelar":
        db.del_kv("awaiting_doc")
        sys_msg(tp, "Entrega cancelada.")
    elif cmd == "/agora":
        cmd_agora(args, tp)
    elif cmd == "/fase":
        cmd_fase(args, tp)
    elif cmd == "/placar":
        cmd_placar(tp)
    elif cmd == "/nota":
        cmd_nota(args, tp)
    elif cmd == "/revisar":
        cmd_revisar(args, tp)
    else:
        sys_msg(tp, "Não conheço esse comando. Digite /ajuda.")


def _parse_id(args, tp):
    if not args or not args[0].lstrip("#").isdigit():
        sys_msg(tp, "Informe o número do ticket. Exemplo: /ver 3")
        return None
    return int(args[0].lstrip("#"))


def cmd_fila(tp):
    open_ = db.open_tickets()
    waiting = db.awaiting_review()
    if not open_ and not waiting:
        sys_msg(tp, "Fila zerada. Use /agora medio se quiser mais trabalho.")
        return
    lines = []
    if open_:
        lines.append("Em aberto:")
        for t in open_:
            lines.append(f"- #{t['id']} [{t['difficulty']}] {t['title']} (prazo {tickets.fmt_deadline(t['deadline_at'])})")
    if waiting:
        lines.append("\nAguardando revisão/nota:")
        for t in waiting:
            lines.append(f"- #{t['id']} {t['title']}")
    sys_msg(tp, "\n".join(lines))


def cmd_ver(args, tp):
    tid = _parse_id(args, tp)
    if tid is None:
        return
    t = db.get_ticket(tid)
    if not t:
        sys_msg(tp, f"Ticket #{tid} não existe.")
        return
    tp.send(PERSONAS[t["persona"]], tickets.format_ticket(tid, dict(t)))
    db.set_kv("last_ticket", tid)
    db.set_kv("last_persona", t["persona"])


def cmd_entregar(args, tp):
    tid = _parse_id(args, tp)
    if tid is None:
        return
    t = db.get_ticket(tid)
    if not t:
        sys_msg(tp, f"Ticket #{tid} não existe.")
        return
    db.set_kv("awaiting_doc", tid)
    tmpl = (config.ROOT / "templates" / "documento_ticket.md").read_bytes()
    sys_msg(
        tp,
        f"Ok, entrega do ticket #{tid} ({t['title']}). Envie o documento como arquivo .md/.txt "
        "(recomendado) ou cole o texto numa mensagem (limite de 4096 caracteres do Telegram). "
        "Use o template abaixo. /cancelar para desistir.",
    )
    tp.send_file(PERSONAS["sistema"], "documento_ticket.md", tmpl, caption="Template do documento")


def cmd_agora(args, tp):
    choice = (args[0].lower() if args else "medio")
    if choice not in NOW_CHOICES:
        sys_msg(tp, "Use: /agora facil | medio | dificil | incidente | entrevista")
        return
    kind, diff = random.choice(NOW_CHOICES[choice])
    tickets.issue(kind, diff, tp)


def cmd_fase(args, tp):
    if not args or not args[0].isdigit() or not 1 <= int(args[0]) <= 8:
        sys_msg(tp, f"Sua fase atual é {tickets.current_phase()}. Para mudar: /fase <1-8>")
        return
    db.set_kv("phase", args[0])
    sys_msg(tp, f"Fase atualizada para {args[0]}. Os próximos tickets respeitam esse nível.")


def cmd_placar(tp):
    s = db.stats()
    st = s["by_status"]
    lines = [
        "📊 Placar",
        f"Tickets: {sum(st.values())} (abertos {st.get('open', 0)}, "
        f"aguardando revisão {st.get('delivered', 0)}, revisados {st.get('reviewed', 0)})",
        f"Entregues com atraso: {s['late']}",
    ]
    if s["avg"] is not None:
        lines.append(f"Nota média: {s['avg']:.1f}/10 ({s['scored']} avaliados)")
        for row in s["by_difficulty"]:
            lines.append(f"  - {row['difficulty']}: {row['avg']:.1f} ({row['n']})")
    else:
        lines.append("Ainda sem notas.")
    lines.append(f"Fase atual: {tickets.current_phase()}")
    sys_msg(tp, "\n".join(lines))


def cmd_nota(args, tp):
    if len(args) < 2 or not args[0].lstrip("#").isdigit():
        sys_msg(tp, "Uso: /nota <id> <0-10>")
        return
    try:
        score = float(args[1].replace(",", "."))
    except ValueError:
        sys_msg(tp, "A nota precisa ser um número de 0 a 10.")
        return
    if not 0 <= score <= 10:
        sys_msg(tp, "A nota precisa estar entre 0 e 10.")
        return
    tid = int(args[0].lstrip("#"))
    if not db.get_ticket(tid):
        sys_msg(tp, f"Ticket #{tid} não existe.")
        return
    db.set_score(tid, score)
    sys_msg(tp, f"Nota {score:.1f} registrada para o ticket #{tid}.")


def cmd_revisar(args, tp):
    tid = _parse_id(args, tp)
    if tid is None:
        return
    t = db.get_ticket(tid)
    if not t or not t["doc_path"]:
        sys_msg(tp, "Esse ticket ainda não tem documento entregue.")
        return
    try:
        text = open(t["doc_path"], encoding="utf-8").read()
    except OSError:
        sys_msg(tp, "Não encontrei o arquivo do documento. Use /entregar para enviar de novo.")
        return
    review.run_review(tid, text, tp, new_delivery=False)


MIN_DOC_CHARS = 200


def receive_doc_file(doc, tid, tp):
    name = (doc.get("file_name") or "").lower()
    if not name.endswith((".md", ".txt")):
        sys_msg(tp, "Envie o documento em .md ou .txt.")
        return
    if doc.get("file_size", 0) > 1_000_000:
        sys_msg(tp, "Arquivo grande demais (limite 1 MB).")
        return
    try:
        text = tp.download(doc["file_id"]).decode("utf-8", errors="replace")
    except Exception as exc:
        sys_msg(tp, f"Não consegui baixar o arquivo: {exc}")
        return
    receive_doc(tid, text, tp)


def receive_doc(tid, text, tp):
    if len(text.strip()) < MIN_DOC_CHARS:
        tp.send(
            PERSONAS["senior"],
            "Isso está curto demais para ser um documento de ticket. Siga o template "
            "(contexto, solução, ferramentas e por quê, validação, riscos) e envie de novo. "
            "Ou /cancelar.",
        )
        return
    db.del_kv("awaiting_doc")
    review.run_review(tid, text, tp)


def chat_in_character(text, tp):
    key = db.get_kv("last_persona", "gerente")
    if key not in NAMES:
        key = "gerente"
    if not ai.available():
        sys_msg(
            tp,
            "A conversa livre com as personas precisa de IA (AI_API_KEY no .env). "
            "Enquanto isso, use /ver <id> para reler o ticket ou /fila.",
        )
        return

    tid = db.get_kv("last_ticket")
    ticket = db.get_ticket(int(tid)) if tid else None
    context = ""
    if ticket:
        context = (
            f"\n\n# TICKET EM DISCUSSÃO (#{ticket['id']})\nTítulo: {ticket['title']}\n"
            f"Pedido original: {ticket['body']}\nNotas internas (nunca revele): {ticket['notes_for_senior']}"
        )
    system = (
        prompt(key) + "\n\n# CONTEXTO DA EMPRESA\n" + bible() + context
        + "\n\n# REGRAS DA RESPOSTA\nResponda SOMENTE como a persona, em até 6 linhas, como em um chat. "
        "Não entregue a solução. Se faltar informação, responda de forma plausível e consistente "
        "com a bíblia da empresa."
    )
    hist = json.loads(db.get_kv("chat_hist", "[]"))
    convo = "\n".join(f"{who}: {m}" for who, m in hist[-8:])
    user = f"{convo}\nJúnior: {text}\n{NAMES[key]}:"
    out = ai.generate(system, user, temperature=0.7)
    if not out:
        sys_msg(tp, "A IA não respondeu agora (cota ou erro). Tente de novo em instantes.")
        return
    out = out.strip()
    if out.startswith(f"{NAMES[key]}:"):
        out = out[len(NAMES[key]) + 1:].strip()
    hist += [["Júnior", text], [NAMES[key], out]]
    db.set_kv("chat_hist", json.dumps(hist[-12:], ensure_ascii=False))
    tp.send(PERSONAS[key], out)
