"""Canais de mensagem: Telegram (real) e Console (para testar sem Telegram)."""
import json

import requests

from . import config


def chunk(text, size=3900):
    """Telegram limita cada mensagem a 4096 caracteres."""
    parts = []
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        cut = cut if cut > size // 2 else size
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    parts.append(text)
    return parts


class Console:
    """Imprime no terminal. Usado em --cli, --dry-run, --run-slot e --simulate-day."""

    def send(self, who, text):
        print(f"\n=== {who} ===\n{text}\n")

    def send_raw(self, chat_id, text):
        print(f"\n[sistema] {text}\n")

    def send_file(self, who, filename, content, caption=""):
        out = config.ROOT / "outbox"
        out.mkdir(exist_ok=True)
        path = out / filename
        path.write_bytes(content)
        print(f"\n=== {who} === (arquivo salvo em {path}) {caption}\n")

    def download(self, file_id):
        raise RuntimeError("download não existe no modo console")


class Telegram:
    def __init__(self, token, chat_id):
        self.chat_id = chat_id
        self.base = f"https://api.telegram.org/bot{token}"
        self.file_base = f"https://api.telegram.org/file/bot{token}"

    def _post(self, method, timeout=40, **kw):
        r = requests.post(f"{self.base}/{method}", timeout=timeout, **kw)
        r.raise_for_status()
        return r

    def send(self, who, text, chat_id=None):
        target = chat_id or self.chat_id
        full = f"{who}\n\n{text}"
        for part in chunk(full):
            self._post("sendMessage", data={"chat_id": target, "text": part})

    def send_raw(self, chat_id, text):
        self._post("sendMessage", data={"chat_id": chat_id, "text": text})

    def send_file(self, who, filename, content, caption=""):
        cap = f"{who}\n{caption}".strip()[:1000]
        self._post(
            "sendDocument",
            data={"chat_id": self.chat_id, "caption": cap},
            files={"document": (filename, content)},
        )

    def get_updates(self, offset, timeout=25):
        r = self._post(
            "getUpdates",
            timeout=timeout + 15,
            data={
                "offset": offset,
                "timeout": timeout,
                "allowed_updates": json.dumps(["message"]),
            },
        )
        return r.json().get("result", [])

    def download(self, file_id):
        info = self._post("getFile", data={"file_id": file_id}).json()["result"]["file_path"]
        r = requests.get(f"{self.file_base}/{info}", timeout=60)
        r.raise_for_status()
        return r.content
