"""Ponto de entrada.

Uso:
  python -m bot.main                      # roda o bot de verdade no Telegram
  python -m bot.main --cli                # testa tudo no terminal, sem Telegram
  python -m bot.main --run-slot manha_daily   # dispara um evento da agenda no terminal
  python -m bot.main --simulate-day       # dispara todos os eventos do dia no terminal
"""
import argparse
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from . import commands, config, db, slots
from .transport import Console, Telegram


def run_cli():
    config.TELEGRAM_CHAT_ID = "cli"
    tp = Console()
    print("Modo CLI. Digite comandos (/ajuda). Use @caminho/arquivo.md para enviar um arquivo como texto. Ctrl+D para sair.")
    while True:
        try:
            line = input("você> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if line.startswith("@"):
            try:
                line = open(line[1:], encoding="utf-8").read()
            except OSError as exc:
                print(f"[erro] {exc}")
                continue
        if line:
            commands.handle({"chat": {"id": "cli"}, "text": line}, tp)


def run_live():
    if not config.TELEGRAM_TOKEN:
        sys.exit("Falta TELEGRAM_BOT_TOKEN no arquivo .env (veja o README).")
    tp = Telegram(config.TELEGRAM_TOKEN, config.TELEGRAM_CHAT_ID)
    offset = int(db.get_kv("offset", "0"))
    print("Bot rodando. Ctrl+C para parar.")
    if config.TELEGRAM_CHAT_ID:
        tp.send("🤖 Sistema", "Bot online. Digite /ajuda para ver os comandos.")
    else:
        print("TELEGRAM_CHAT_ID vazio: mande /start para o bot no Telegram para descobrir o seu.")

    while True:
        try:
            for update in tp.get_updates(offset):
                offset = update["update_id"] + 1
                db.set_kv("offset", offset)
                if update.get("message"):
                    commands.handle(update["message"], tp)
            if config.TELEGRAM_CHAT_ID:
                slots.check(tp, datetime.now(ZoneInfo(config.TZ)))
        except KeyboardInterrupt:
            print("\nEncerrando.")
            return
        except Exception as exc:
            print(f"[erro] {exc}")
            time.sleep(5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", action="store_true")
    ap.add_argument("--run-slot")
    ap.add_argument("--simulate-day", action="store_true")
    args = ap.parse_args()

    db.init()

    if args.cli:
        return run_cli()
    if args.run_slot or args.simulate_day:
        config.TELEGRAM_CHAT_ID = "cli"
        tp = Console()
        sched = slots.load_schedule()
        for slot in sched["slots"]:
            if args.simulate_day or slot["name"] == args.run_slot:
                slots.run_slot(slot, tp, force=True)
        return
    run_live()


if __name__ == "__main__":
    main()
