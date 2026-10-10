"""Teste de fumaça com IA simulada (sem internet). Rode: python -m tests.test_smoke"""
import json
import os
import tempfile

tmp = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(tmp, "test.db")
os.environ["DOCS_DIR"] = os.path.join(tmp, "docs")
os.environ["AI_API_KEY"] = "fake"
os.environ["AI_PROVIDER"] = "gemini"
os.environ["TELEGRAM_CHAT_ID"] = "1"

from bot import ai, commands, config, db, slots, tickets  # noqa: E402
from bot.transport import chunk  # noqa: E402


class FakeResponse:
    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        pass

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": self._text}]}}]}


def fake_post(url, json=None, headers=None, timeout=None, **kw):
    system = json["systemInstruction"]["parts"][0]["text"]
    user = json["contents"][0]["parts"][0]["text"]
    if "Responda APENAS com JSON" in user:
        ticket = {
            "title": "Ticket gerado pela IA",
            "body": "Oi! Preciso de um relatório rápido de pedidos por estado.",
            "deliverable": "Query + tabela",
            "notes_for_senior": "Cuidar de nulos",
            "deadline_hours": 5,
        }
        return FakeResponse("```json\n" + __import__("json").dumps(ticket) + "\n```")
    if "Formato OBRIGATÓRIO" in system or "FORMATO OBRIGATÓRIO" in system.upper():
        return FakeResponse("NOTA GERAL: 7,5/10\n\nCRITÉRIOS\n1. ...")
    return FakeResponse("Pode usar sim, mas me avisa se achar algo estranho.")


class Recorder:
    def __init__(self):
        self.sent = []

    def send(self, who, text):
        self.sent.append((who, text))

    def send_raw(self, chat_id, text):
        self.sent.append(("raw", text))

    def send_file(self, who, filename, content, caption=""):
        self.sent.append((who, f"[arquivo {filename}]"))


def main():
    db.init()
    ai.requests.post = fake_post
    tp = Recorder()

    # 1) ticket gerado pela IA
    tid = tickets.issue("adhoc", "facil", tp)
    t = db.get_ticket(tid)
    assert t["source"] == "ai" and t["title"] == "Ticket gerado pela IA", dict(t)
    assert "Prazo" in tp.sent[-1][1]

    # 2) conversa em personagem
    commands.handle({"chat": {"id": 1}, "text": "posso usar a tabela de reviews?"}, tp)
    assert "me avisa" in tp.sent[-1][1], tp.sent[-1]

    # 3) entrega + revisão com nota lida automaticamente
    commands.handle({"chat": {"id": 1}, "text": f"/entregar {tid}"}, tp)
    doc = "# Doc\n" + "texto do documento " * 30
    commands.handle({"chat": {"id": 1}, "text": doc}, tp)
    t = db.get_ticket(tid)
    assert t["status"] == "reviewed" and t["score"] == 7.5, dict(t)

    # 4) segurança: outro chat é ignorado
    before = len(tp.sent)
    commands.handle({"chat": {"id": 999}, "text": "/fila"}, tp)
    assert len(tp.sent) == before

    # 5) utilidades
    assert ai.extract_json('x ```json\n{"a": 1}\n``` y') == {"a": 1}
    assert len(chunk("linha\n" * 2000)) > 1
    assert slots.load_schedule()["slots"]

    # 6) catálogo de reserva quando a IA falha
    config.AI_API_KEY = ""
    tid2 = tickets.issue("adhoc", "facil", tp)
    assert db.get_ticket(tid2)["source"] == "catalog"
    print("OK: todos os testes passaram")


if __name__ == "__main__":
    main()
