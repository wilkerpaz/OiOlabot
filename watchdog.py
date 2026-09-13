"""Watchdog: checks OiOlabot systemd services and restarts/alerts on failure.

Runs standalone via a systemd timer (not part of the async worker process).
Checks each service with `systemctl --user is-active`; if one is down, resets
any exhausted restart-limit lockout, restarts it, and reports the outcome to
the admin's Telegram chat via a raw Bot API call.
"""

import logging
import subprocess
from pathlib import Path

import httpx
from decouple import config

logging.basicConfig(
    level=config("LOG", default="INFO"),
    format="%(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

SERVICES = ["redis-server", "oiolabot-main", "oiolabot-liturgy", "oiolabot-worker"]
PAUSE_FLAG = Path.home() / ".oiolabot-watchdog-pause"


def is_active(unit: str) -> bool:
    """Check whether a systemd --user unit is currently active."""
    result = subprocess.run(
        ["systemctl", "--user", "is-active", unit],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == "active"


def restart(unit: str) -> None:
    """Clear any restart-limit lockout and restart a systemd --user unit."""
    subprocess.run(["systemctl", "--user", "reset-failed", unit], capture_output=True)
    subprocess.run(["systemctl", "--user", "restart", unit], check=True)


def notify(text: str) -> None:
    """Send an alert to the admin's Telegram chat via the Bot API."""
    token = config("DEV_TOKEN")
    chat_id = config("ADMIN_CHAT_ID")
    try:
        httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")


def main() -> None:
    """Check every service; restart and alert on any that are down."""
    if PAUSE_FLAG.exists():
        logger.info(f"Watchdog paused ({PAUSE_FLAG} exists) — skipping this run")
        return

    for unit in SERVICES:
        if is_active(unit):
            continue

        logger.warning(f"{unit} is down, attempting restart")
        try:
            restart(unit)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error restarting {unit}: {e}")
            notify(f"🔴 {unit} estava parado e a tentativa de reiniciar FALHOU: {e}")
            continue

        if is_active(unit):
            logger.info(f"{unit} restarted successfully")
            notify(f"⚠️ {unit} estava parado e foi reiniciado automaticamente.")
        else:
            logger.error(f"{unit} restart attempt did not bring it back up")
            notify(f"🔴 {unit} estava parado e a tentativa de reiniciar FALHOU. Verifique manualmente.")


if __name__ == "__main__":
    main()
