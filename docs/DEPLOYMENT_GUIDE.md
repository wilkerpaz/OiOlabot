# OiOlabot v2 — Deployment Guide

Complete step-by-step instructions for deploying OiOlabot v2 on NixOS with home-manager.

## Prerequisites

- NixOS system with **home-manager** configured for your user
- Redis server (via `pkgs.redis`, run as a home-manager user service)
- Python 3.11+
- git (for cloning/managing the repository)
- Telegram API credentials (from https://my.telegram.org)
- Two bot tokens from BotFather (https://t.me/BotFather)

---

## Phase 1: Telegram Setup

### 1.1 Get API Credentials
1. Go to https://my.telegram.org
2. Sign in with your Telegram account
3. Select "API development tools"
4. Create or select an application
5. Copy the `api_id` and `api_hash` — you'll need these in `.env`

### 1.2 Create Bot Tokens
1. Message @BotFather on Telegram
2. Create two bots:
   - `/newbot` → name your main bot → get token
   - `/newbot` → name your liturgy bot → get token
3. Save both tokens — you'll need these in `.env`

### 1.3 Get Your Admin Chat ID
The watchdog (Phase 6) alerts you on Telegram when a service goes down. Message your main bot with `/me` (or use @userinfobot) to get your chat ID — you'll need it as `ADMIN_CHAT_ID` in `.env`.

---

## Phase 2: Environment Setup

### 2.1 Clone the Repository
```bash
git clone https://github.com/wilkerpaz/OiOlabot.git ~/OiOlabot
cd ~/OiOlabot
```
There is no separate `v2` branch — the v2 architecture lives directly on `master`. Legacy v1 files (not used in production) sit in `legacy/` for reference.

### 2.2 Create .env File
```bash
cp .env.example .env
```

### 2.3 Edit .env with Your Credentials
```bash
nano .env
```

Fill in the following:
- `API_ID` — from Telegram API credentials
- `API_HASH` — from Telegram API credentials
- `DEV_TOKEN` — main bot token from BotFather
- `DEV_TOKEN_LD` — liturgy bot token from BotFather
- `REDIS_HOST` — `localhost` (or your Redis server hostname)
- `REDIS_PASSWORD` — your Redis password (empty if none)
- `TZ` — timezone for daily liturgy (e.g., `America/Belem`)
- `ADMIN_CHAT_ID` — your Telegram chat ID, for watchdog alerts

**Example .env:**
```
API_ID=123456789
API_HASH=abc123def456ghi789jkl012mno345p
DEV_TOKEN=1234567890:ABCDEfghijklmnopqrstuvwxyz1234567890-
DEV_TOKEN_LD=0987654321:zyxwvutsrqponmlkjihgfedcba0987654321-
DB=0
DB_LD=1
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
LOG=INFO
TZ=America/Belem
ADMIN_CHAT_ID=your_telegram_chat_id
```

### 2.4 Secure .env
```bash
chmod 600 .env
```

---

## Phase 3: Redis Deployment

Redis runs as a **home-manager user service** (`systemd --user`), bound to `localhost` only — see `nix/home.nix` for the reference definition (`bind 127.0.0.1 ::1`, `protected-mode yes`). Do not bind it to `0.0.0.0`.

### 3.1 Verify Redis is Running
```bash
systemctl --user status redis-server
redis-cli ping
# Should output: PONG
```

### 3.2 Create Redis Databases
```bash
redis-cli SELECT 0  # Main bot database
redis-cli SELECT 1  # Liturgy bot database
redis-cli DBSIZE    # Should be 0 (empty) on a fresh install
```

---

## Phase 4: Python Environment

### 4.1 Create the Virtual Environment
```bash
python3 -m venv ~/.venv
~/.venv/bin/pip install --upgrade pip
~/.venv/bin/pip install -r requirements.txt
```
Only Kurigram + `requirements.txt` are needed — v1's extra dependencies (real Pyrogram, `pyTelegramBotAPI`, `babel`, `streamlink`) are not required for anything that runs in production.

### 4.2 Verify Imports
```bash
~/.venv/bin/python -c "from factories.main_factory import MainBotFactory; print('OK')"
~/.venv/bin/python -c "from factories.liturgy_factory import LiturgyBotFactory; print('OK')"
~/.venv/bin/python -c "from worker.feed_job import FeedJob; print('OK')"
~/.venv/bin/python -c "import watchdog; print('OK')"
```

### 4.3 Run Tests
```bash
~/.venv/bin/pip install pytest pytest-asyncio
~/.venv/bin/python -m pytest tests/ -v
# All tests should pass
```

---

## Phase 5: Manual Testing (Before Systemd)

### 5.1 Test MainBot
```bash
# In terminal 1
~/.venv/bin/python main.py
# Should log: "Starting MainBot..." and "MainBot initialized"
# Press Ctrl+C to stop

# In terminal 2 (separate), test with your bot
# Send /start to the main bot
# Should reply with confirmation
```

### 5.2 Test LiturgyBot
```bash
# In terminal 1
~/.venv/bin/python liturgy.py
# Should log: "Starting LiturgyBot..."

# Test with your liturgy bot
# Send /hoje to the liturgy bot
# Should reply with today's liturgy
```

### 5.3 Test Worker
```bash
# In terminal 1
~/.venv/bin/python worker.py
# Should log: "Starting Worker..." and "Scheduler started with 2 jobs: FeedJob (5min) + LiturgyJob (7am)"
# Should log FeedJob runs every 5 minutes
# At 7 AM (America/Belem time), should log LiturgyJob run
```

### 5.4 Test Watchdog
```bash
~/.venv/bin/python watchdog.py
# Silent exit if everything is up; logs a warning and sends a Telegram
# alert to ADMIN_CHAT_ID for any service it finds down
```

---

## Phase 6: Home-Manager Systemd Deployment

Services run as **user-level** systemd units (`systemctl --user`), managed by home-manager — not system-wide, no dedicated `oiolabot` system user, no `/opt/oiolabot`.

### 6.1 Add Service Definitions to Your home-manager Config
Copy the `systemd.user.services.*` and `systemd.user.timers.oiolabot-watchdog` blocks from `nix/home.nix` in this repo into your own `~/.config/home-manager/home.nix`, adjusting paths if your username or clone location differs. `nix/home.nix` in this repo is a reference mirror of what's actually deployed — keep the two in sync when either changes.

`nix/service.nix` is an alternative reference for a system-wide NixOS module deployment (dedicated user, `/opt/oiolabot`, `sudo systemctl`) — it is **not** the method currently used in production.

### 6.2 Apply the Configuration
```bash
home-manager switch
```
This builds and activates the new generation, creating symlinks under `~/.config/systemd/user/` and (re)starting any changed services automatically.

### 6.3 Verify Services Are Running
```bash
systemctl --user list-units --type=service,timer | grep oiolabot

systemctl --user status oiolabot-main oiolabot-liturgy oiolabot-worker
systemctl --user list-timers oiolabot-watchdog
```

### 6.4 Enable Linger (Survive Logout/Reboot)
User services only keep running without an active login session if linger is enabled:
```bash
loginctl show-user "$USER" | grep Linger   # confirm current state
loginctl enable-linger "$USER"             # if not already "yes"
```

### 6.5 Monitor Logs
```bash
# Follow logs in real-time
journalctl --user -u oiolabot-main -f
journalctl --user -u oiolabot-liturgy -f
journalctl --user -u oiolabot-worker -f
journalctl --user -u oiolabot-watchdog -f

# Or view recent logs
journalctl --user -u oiolabot-main -n 50
```

---

## Phase 7: Verification Checklist

### Services Running
- [ ] `systemctl --user status oiolabot-main` → active (running)
- [ ] `systemctl --user status oiolabot-liturgy` → active (running)
- [ ] `systemctl --user status oiolabot-worker` → active (running)
- [ ] `systemctl --user list-timers oiolabot-watchdog` → armed, next run within 15min

### Redis
- [ ] `redis-cli ping` → PONG
- [ ] `redis-cli DBSIZE` → shows key count in DB 0
- [ ] Redis bound to `127.0.0.1`/`::1` only (`ss -tlnp | grep 6379`), not `0.0.0.0`

### Bots Responsive
- [ ] Send `/start` to main bot → gets confirmation
- [ ] Send `/addurl <rss_url>` to main bot → gets confirmation
- [ ] Send `/hoje` to liturgy bot → gets today's readings
- [ ] Send `/start` to liturgy bot → gets confirmation

### Worker Processing
- [ ] Check logs: `journalctl --user -u oiolabot-worker | grep "Sent entry"`
- [ ] Check logs at 7 AM (`TZ` timezone) for the daily liturgy send

### Watchdog
- [ ] Manually stop a service (`systemctl --user stop oiolabot-worker`), trigger the watchdog (`systemctl --user start oiolabot-watchdog.service`), confirm it restarts the service and you receive a Telegram alert

### Timezone
- [ ] Verify `TZ` in `.env` matches your location
- [ ] Check worker logs at 7 AM — should see LiturgyJob run

---

## Troubleshooting

### Redis Not Connecting
```bash
# Check Redis is running
systemctl --user status redis-server

# Check connection parameters
redis-cli -h <REDIS_HOST> -p <REDIS_PORT> ping

# Check .env has correct REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
```

### Bot Token Not Working
```bash
# Verify token format: should start with digits and contain ':'
# Example: 1234567890:ABCDEfghijklmnopqrstuvwxyz

# Test with Telegram API directly
curl -X GET https://api.telegram.org/bot<TOKEN>/getMe
```

### Systemd Service Fails to Start
```bash
# Check logs for errors
journalctl --user -u oiolabot-main -n 30 --no-pager

# Verify .env file exists and is readable
ls -la ~/OiOlabot/.env

# Verify Python dependencies installed
~/.venv/bin/pip list | grep -i kurigram
```

### Service Restarted But Stays Down (systemd gave up)
Systemd's default restart-limit (`StartLimitBurst`/`StartLimitIntervalSec`) can mark a unit `failed` after repeated rapid crashes and stop retrying. The watchdog already clears this automatically (`systemctl --user reset-failed <unit>` before restarting), but to do it by hand:
```bash
systemctl --user reset-failed oiolabot-worker
systemctl --user restart oiolabot-worker
```

### High CPU or Memory Usage
```bash
# Check which process is consuming resources
htop -p $(systemctl --user show -p MainPID --value oiolabot-main)

# Check for stuck database connections
redis-cli MONITOR

# Restart the service
systemctl --user restart oiolabot-main
```

---

## Updating to Latest master

```bash
# Pull latest changes
cd ~/OiOlabot
git pull origin master

# Reinstall dependencies (in case of version bumps)
~/.venv/bin/pip install --upgrade -r requirements.txt

# Run tests to verify
~/.venv/bin/python -m pytest tests/

# If nix/home.nix changed (new/changed service definitions), sync the
# equivalent blocks into ~/.config/home-manager/home.nix and apply:
home-manager switch

# Otherwise, just restart the affected services:
systemctl --user restart oiolabot-main oiolabot-liturgy oiolabot-worker
```

---

## Rollback to Previous Version

```bash
cd ~/OiOlabot

# If deployment fails, revert to previous commit
git log --oneline | head
git checkout <previous-commit-hash>

# Restart services
systemctl --user restart oiolabot-main oiolabot-liturgy oiolabot-worker
```

---

## Support

For issues or questions:
1. Check logs: `journalctl --user -u oiolabot-main -u oiolabot-liturgy -u oiolabot-worker -u oiolabot-watchdog`
2. Review `.env` configuration
3. Verify Redis is running and accessible, and bound to localhost only
4. Check Telegram bot tokens with `curl` to Telegram API
5. Run tests: `~/.venv/bin/python -m pytest tests/`

---

## Next Steps After Deployment

1. **Add Admin Users** — Use `/addadmin <user_id>` (requires an existing admin)
2. **Configure Daily Liturgy Time** — Adjust `TZ` in `.env` if needed
3. **Set Up RSS Feeds** — Use `/addurl` to subscribe to feeds
4. **Monitor Logs** — Regularly check `journalctl --user` for errors
5. **Confirm the Watchdog Works** — Do the manual-stop test in Phase 7 at least once
6. **Backup Redis** — Use the `/backup` admin command, or set up your own Redis persistence strategy
