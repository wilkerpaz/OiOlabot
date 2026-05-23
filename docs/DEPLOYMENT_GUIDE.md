# OiOlabot v2 — Deployment Guide

Complete step-by-step instructions for deploying OiOlabot v2 on NixOS.

## Prerequisites

- NixOS system (tested on latest stable)
- Redis server (redis-server package)
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

---

## Phase 2: Environment Setup

### 2.1 Clone or Checkout v2 Branch
```bash
cd /path/to/OiOlabot
git checkout v2
```

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
```

### 2.4 Secure .env
```bash
chmod 600 .env
```

---

## Phase 3: Redis Deployment

### 3.1 Start Redis Server
```bash
# On NixOS with systemd
sudo systemctl start redis

# Or manually with nix-shell
nix-shell -p redis --run "redis-server"
```

### 3.2 Verify Redis is Running
```bash
redis-cli ping
# Should output: PONG

# Check database status
redis-cli INFO
```

### 3.3 Create Redis Databases
```bash
redis-cli SELECT 0  # Main bot database
redis-cli SELECT 1  # Liturgy bot database
redis-cli DBSIZE    # Should be 0 (empty)
```

---

## Phase 4: Python Environment

### 4.1 Install Dependencies
```bash
pip install -r requirements.txt
```

**Or with nix-shell:**
```bash
nix-shell nix/default.nix
```

### 4.2 Verify Imports
```bash
python -c "from factories.main_factory import MainBotFactory; print('OK')"
python -c "from factories.liturgy_factory import LiturgyBotFactory; print('OK')"
python -c "from worker import FeedJob; print('OK')"
```

### 4.3 Run Tests
```bash
pip install pytest pytest-asyncio
python -m pytest tests/test_v2_architecture.py -v
# All 28 tests should pass
```

---

## Phase 5: Manual Testing (Before Systemd)

### 5.1 Test MainBot
```bash
# In terminal 1
python main.py
# Should log: "Starting MainBot..." and "Scheduler started"
# Press Ctrl+C to stop

# In terminal 2 (separate), test with your bot
# Send /start to the main bot
# Should reply with welcome message
```

### 5.2 Test LiturgyBot
```bash
# In terminal 1
python liturgy.py
# Should log: "Starting LiturgyBot..."

# Test with your liturgy bot
# Send /hoje to the liturgy bot
# Should reply with today's liturgy
```

### 5.3 Test Worker
```bash
# In terminal 1
python worker.py
# Should log: "Starting Worker..." and "Scheduler started with 3 jobs"
# Should log FeedJob runs every 5 minutes
# At 7 AM (America/Belem time), should log LiturgyJob run

# Or simulate timing with fake system clock
```

---

## Phase 6: NixOS Systemd Deployment

### 6.1 Create oiolabot User and Group
```bash
sudo useradd -r -d /opt/oiolabot -s /sbin/nologin oiolabot
sudo mkdir -p /opt/oiolabot
sudo chown oiolabot:oiolabot /opt/oiolabot
```

### 6.2 Deploy Application Files
```bash
# Copy repository to /opt/oiolabot
sudo cp -r /path/to/OiOlabot/* /opt/oiolabot/
sudo cp /path/to/OiOlabot/.env /opt/oiolabot/.env
sudo chown -R oiolabot:oiolabot /opt/oiolabot
sudo chmod 600 /opt/oiolabot/.env
```

### 6.3 Enable Systemd Services
```bash
# Add service configuration from nix/service.nix to your configuration.nix
# Or use home-manager for user-level services

# Then rebuild and activate
sudo nixos-rebuild switch

# Verify services are created
sudo systemctl list-units | grep oiolabot
```

### 6.4 Start Services
```bash
sudo systemctl start oiolabot-main
sudo systemctl start oiolabot-liturgy
sudo systemctl start oiolabot-worker

# Verify they're running
sudo systemctl status oiolabot-main oiolabot-liturgy oiolabot-worker

# Enable on boot
sudo systemctl enable oiolabot-main oiolabot-liturgy oiolabot-worker
```

### 6.5 Monitor Logs
```bash
# Follow logs in real-time
journalctl -u oiolabot-main -f
journalctl -u oiolabot-liturgy -f
journalctl -u oiolabot-worker -f

# Or view recent logs
journalctl -u oiolabot-main -n 50
journalctl -u oiolabot-liturgy -n 50
journalctl -u oiolabot-worker -n 50
```

---

## Phase 7: Verification Checklist

### Services Running
- [ ] `systemctl status oiolabot-main` → active (running)
- [ ] `systemctl status oiolabot-liturgy` → active (running)
- [ ] `systemctl status oiolabot-worker` → active (running)

### Redis
- [ ] `redis-cli ping` → PONG
- [ ] `redis-cli DBSIZE` → shows key count in DB 0

### Bots Responsive
- [ ] Send `/start` to main bot → gets welcome
- [ ] Send `/addurl <rss_url>` to main bot → gets confirmation
- [ ] Send `/hoje` to liturgy bot → gets today's readings
- [ ] Send `/start` to liturgy bot → gets confirmation

### Worker Processing
- [ ] Check logs: `journalctl -u oiolabot-worker | grep "FeedJob"`
- [ ] Check logs: `journalctl -u oiolabot-worker | grep "LiturgyJob"`

### Timezone
- [ ] Verify `TZ` in `.env` matches your location
- [ ] Check worker logs at 7 AM — should see LiturgyJob run
- [ ] Check Redis for daily liturgy subscriptions

---

## Troubleshooting

### Redis Not Connecting
```bash
# Check Redis is running
sudo systemctl status redis

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
journalctl -u oiolabot-main -n 30 --no-pager

# Verify .env file exists and is readable
ls -la /opt/oiolabot/.env

# Verify Python dependencies installed
python -m pip list | grep kurigram
```

### High CPU or Memory Usage
```bash
# Check which process is consuming resources
htop -p $(systemctl show -p MainPID oiolabot-main)

# Check for stuck database connections
redis-cli MONITOR

# Restart the service
sudo systemctl restart oiolabot-main
```

---

## Updating to Latest v2

```bash
# Pull latest changes
git fetch origin
git checkout v2
git pull origin v2

# Reinstall dependencies (in case of version bumps)
pip install --upgrade -r requirements.txt

# Run tests to verify
python -m pytest tests/test_v2_architecture.py

# Restart services
sudo systemctl restart oiolabot-main oiolabot-liturgy oiolabot-worker
```

---

## Rollback to Previous Version

```bash
# If deployment fails, revert to previous commit
git log v2 --oneline | head
git checkout <previous-commit-hash>

# Restart services
sudo systemctl restart oiolabot-main oiolabot-liturgy oiolabot-worker
```

---

## Support

For issues or questions:
1. Check logs: `journalctl -u oiolabot-*`
2. Review `.env` configuration
3. Verify Redis is running and accessible
4. Check Telegram bot tokens with `curl` to Telegram API
5. Run integration tests: `pytest tests/`

---

## Next Steps After Deployment

1. **Add Admin Users** — Use `/lock` command to restrict settings to admins
2. **Configure Daily Liturgy Time** — Adjust `TZ` in `.env` if needed
3. **Set Up RSS Feeds** — Use `/addurl` to subscribe to feeds
4. **Monitor Logs** — Regularly check `journalctl` for errors
5. **Backup Redis** — Set up Redis persistence and backup strategy
