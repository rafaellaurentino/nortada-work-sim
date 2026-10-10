"""Cliente de IA gratuita. Se algo falhar, devolve None e o bot usa o catálogo de reserva."""
import json
import re

import requests

from . import config


def available():
    return bool(config.AI_API_KEY)


def generate(system, user, temperature=0.8, timeout=90):
    """Gera texto. Retorna None se a IA não estiver configurada ou falhar."""
    if not available():
        return None
    try:
        if config.AI_PROVIDER == "gemini":
            return _gemini(system, user, temperature, timeout)
        return _openai_compat(system, user, temperature, timeout)
    except Exception as exc:  # rede, cota, formato inesperado...
        print(f"[ai] erro: {exc}")
        return None


def _gemini(system, user, temperature, timeout):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.AI_MODEL}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": temperature},
    }
    r = requests.post(
        url, json=body, headers={"x-goog-api-key": config.AI_API_KEY}, timeout=timeout
    )
    r.raise_for_status()
    data = r.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _openai_compat(system, user, temperature, timeout):
    base = config.AI_BASE_URL.rstrip("/")
    body = {
        "model": config.AI_MODEL,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    r = requests.post(
        f"{base}/chat/completions",
        json=body,
        headers={"Authorization": f"Bearer {config.AI_API_KEY}"},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def extract_json(text):
    """Extrai o primeiro objeto JSON de uma resposta (aceita cercas ```json)."""
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?", "", text)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
