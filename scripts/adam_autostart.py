#!/usr/bin/env python3
"""Adam boot autostart switch — terminal UI.

Same logic as the web Settings toggle (System/adam/autostart.py): enables or
disables the systemd units from system.autostart.units and flips the Docker
restart policy of the ASR container. Changes apply to the NEXT boot only —
nothing is started or stopped right now.

Usage:
    python3 scripts/adam_autostart.py            # interactive TUI
    python3 scripts/adam_autostart.py --status   # print state, exit 0=on 1=off 2=partial
    python3 scripts/adam_autostart.py --on
    python3 scripts/adam_autostart.py --off

Keys in TUI: Space/Enter — toggle, r — refresh, i — install sudo rights, q — quit.
"""
from __future__ import annotations

import argparse
import curses
import json
import locale
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "System"))

from adam import autostart  # noqa: E402  (stdlib-only module)

CONFIG_JSON = PROJECT_ROOT / "System" / "Config.json"
INSTALLER = PROJECT_ROOT / "scripts" / "adam_install_systemd.sh"

STATE_LABEL = {"on": "ВКЛЮЧЁН", "off": "ВЫКЛЮЧЕН", "partial": "ЧАСТИЧНО"}
EXIT_CODE = {"on": 0, "off": 1, "partial": 2}


def load_cfg() -> dict:
    try:
        raw = json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
        section = raw.get("system", {}).get("autostart")
    except (OSError, ValueError):
        section = None
    return autostart.resolve_cfg(section)


def running_state(item: dict, timeout: float) -> str:
    """Current runtime state (informational — the switch doesn't change it)."""
    if item["kind"] == "systemd":
        cmd = ["systemctl", "is-active", item["name"]]
    else:
        cmd = ["docker", "inspect", "-f", "{{.State.Status}}", item["name"]]
    try:
        out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             text=True, timeout=timeout).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    return out or "?"


def print_report(result: dict) -> None:
    for r in result.get("results", []):
        mark = "ok " if r["ok"] else "ERR"
        print(f"  [{mark}] {r['name']}: {r['detail']}")


def run_cli(args: argparse.Namespace, cfg: dict) -> int:
    if args.status:
        st = autostart.status(cfg)
        print(f"Автозапуск: {STATE_LABEL[st['state']]}")
        for item in st["items"]:
            print(f"  {'✔' if item['enabled'] else '✘'} {item['name']:<28} {item['state']}")
        if not autostart.can_manage(cfg):
            print("  (нет NOPASSWD-прав для веб-тумблера — запустите scripts/adam_install_systemd.sh)")
        return EXIT_CODE[st["state"]]

    if not autostart.can_manage(cfg):
        print("Нет NOPASSWD-прав. Сначала: sudo scripts/adam_install_systemd.sh", file=sys.stderr)
        return 3
    result = autostart.set_enabled(cfg, enabled=args.on)
    print_report(result)
    print(f"Автозапуск: {STATE_LABEL[result['status']['state']]}")
    return 0 if result["ok"] else 4


# ── TUI ──────────────────────────────────────────────────────────────────────

def _addstr(win, y: int, x: int, text: str, attr: int = 0) -> None:
    h, w = win.getmaxyx()
    if 0 <= y < h and x < w:
        win.addnstr(y, x, text, max(0, w - x - 1), attr)


def tui(stdscr, cfg: dict) -> None:
    curses.curs_set(0)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    green, red, yellow = (curses.color_pair(i) for i in (1, 2, 3))
    state_attr = {"on": green | curses.A_BOLD, "off": red | curses.A_BOLD, "partial": yellow | curses.A_BOLD}
    timeout = float(cfg["command_timeout_sec"])

    message = ""
    report: list[dict] = []
    confirm = False

    while True:
        stdscr.erase()
        _addstr(stdscr, 0, 2, "Адам Чип · автозапуск при загрузке Jetson", curses.A_BOLD)
        _addstr(stdscr, 1, 2, "загрузка…", curses.A_DIM)
        stdscr.refresh()

        st = autostart.status(cfg)
        manage = autostart.can_manage(cfg)

        stdscr.erase()
        _addstr(stdscr, 0, 2, "Адам Чип · автозапуск при загрузке Jetson", curses.A_BOLD)
        _addstr(stdscr, 2, 2, "Состояние: ")
        _addstr(stdscr, 2, 13, STATE_LABEL[st["state"]], state_attr[st["state"]])

        _addstr(stdscr, 4, 4, f"{'компонент':<30}{'при загрузке':<18}сейчас", curses.A_DIM)
        row = 5
        for item in st["items"]:
            mark, attr = ("✔", green) if item["enabled"] else ("✘", red)
            _addstr(stdscr, row, 2, mark, attr)
            _addstr(stdscr, row, 4, f"{item['name']:<30}{item['state']:<18}{running_state(item, timeout)}")
            row += 1

        row += 1
        _addstr(stdscr, row, 2, "Переключение действует со следующей загрузки — сейчас ничего не", curses.A_DIM)
        _addstr(stdscr, row + 1, 2, "запускается и не останавливается. Логвьюер (:8083) — в наборе.", curses.A_DIM)
        row += 3
        if not manage:
            _addstr(stdscr, row, 2, "Нет прав sudo для переключения — нажмите i, чтобы установить.", yellow)
            row += 2

        for r in report:
            _addstr(stdscr, row, 2, f"{'ok ' if r['ok'] else 'ERR'} {r['name']}: {r['detail']}",
                    green if r["ok"] else red)
            row += 1
        if message:
            _addstr(stdscr, row + 1, 2, message, curses.A_BOLD)

        target_on = st["state"] != "on"
        if confirm:
            verb = "ВКЛЮЧИТЬ" if target_on else "ВЫКЛЮЧИТЬ"
            footer = f"{verb} автозапуск? y — да, любая другая клавиша — отмена"
        else:
            footer = "Пробел/Enter — переключить   r — обновить   i — права sudo   q — выход"
        h, _ = stdscr.getmaxyx()
        _addstr(stdscr, h - 1, 2, footer, curses.A_REVERSE)
        stdscr.refresh()

        key = stdscr.getch()
        message = ""

        if confirm:
            confirm = False
            if key in (ord("y"), ord("Y"), ord("н"), ord("Н")):
                if not manage:
                    message = "Нет прав — сначала i."
                    continue
                result = autostart.set_enabled(cfg, enabled=target_on)
                report = result["results"]
                message = "Готово." if result["ok"] else "Есть ошибки — см. выше."
            else:
                message = "Отменено."
            continue

        if key in (ord("q"), ord("Q"), 27):
            return
        if key in (ord(" "), curses.KEY_ENTER, 10, 13):
            confirm = True
            report = []
        elif key in (ord("r"), ord("R")):
            report = []
        elif key in (ord("i"), ord("I")):
            curses.endwin()
            print("\nЗапуск установщика systemd-юнитов и sudo-правил…\n")
            rc = subprocess.call(["sudo", str(INSTALLER)])
            input(f"\nУстановщик завершился с кодом {rc}. Enter — вернуться в меню…")
            stdscr.clear()
            report = []


def main() -> int:
    parser = argparse.ArgumentParser(description="Adam boot autostart switch")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true", help="print state and exit")
    group.add_argument("--on", action="store_true", help="enable autostart")
    group.add_argument("--off", action="store_true", help="disable autostart")
    args = parser.parse_args()
    cfg = load_cfg()

    if args.status or args.on or args.off:
        return run_cli(args, cfg)
    if not sys.stdout.isatty():
        args.status = True
        return run_cli(args, cfg)
    locale.setlocale(locale.LC_ALL, "")  # needed for ✔/✘ and Cyrillic in curses
    curses.wrapper(tui, cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
