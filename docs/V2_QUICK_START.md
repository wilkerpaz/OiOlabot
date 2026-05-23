# OiOlabot v2 — Quick Start for Developers

Fast reference for working with the v2 codebase.

## Project Structure

```
factories/           Create (Client, Database) per bot via Abstract Factory
bots/               BaseBot with mixins (WelcomeMixin, FeedMixin, LiturgyMixin)
mixins/             Shared handlers: /welcome, /addurl, /hoje, /lock, etc.
util/database/      Redis async operations for MainDatabase (DB 0) and LiturgyDatabase (DB 1)
util/scrapers/      Content fetchers (LiturgiaScraper, HomiliaScraper, SantoScraper)
worker/             Background jobs (FeedJob every 5min, LiturgyJob at 7am)
main.py, liturgy.py, worker.py    Entry points for 3 systemd services
```

## Adding a Handler

1. **Identify which mixin:**
   - Welcome/goodbye? → `mixins/welcome.py`
   - RSS feeds? → `mixins/feed.py`
   - Liturgy commands? → `mixins/liturgy.py`

2. **Add async method:**
   ```python
   # mixins/feed.py
   async def my_new_command(self, client, message):
       """Handler docstring."""
       try:
           # Get data from database
           data = await self.db.get_something()
           # Send response
           await message.reply("Response")
       except Exception as e:
           logger.error(f"Error: {e}")
   ```

3. **Register in _register_*_handlers():**
   ```python
   self.client.add_handler(
       MessageHandler(self.my_new_command, filters.command("mycommand"))
   )
   ```

4. **Test:**
   ```bash
   pytest tests/test_v2_architecture.py -v -k "my_new_command"
   ```

## Adding a Database Method

1. **Choose database class:**
   - Groups/RSS → `util/database/main_db.py` (MainDatabase)
   - Daily liturgy → `util/database/liturgy_db.py` (LiturgyDatabase)

2. **Add async method:**
   ```python
   # util/database/main_db.py
   async def get_my_data(self, key: str) -> dict | None:
       """Get custom data from Redis."""
       if not await self.exists(key):
           return None
       return await self.redis.hgetall(key)
   ```

3. **Use in handlers:**
   ```python
   # mixins/feed.py
   async def my_handler(self, client, message):
       data = await self.db.get_my_data("some_key")
   ```

## Adding a Scraper

1. **Create scraper class in `util/scrapers/`:**
   ```python
   # util/scrapers/my_scraper.py
   from util.scrapers.base import BaseScraper
   
   class MyScraper(BaseScraper):
       async def fetch(self) -> str | None:
           """Fetch content from external source."""
           async with httpx.AsyncClient() as client:
               response = await client.get("https://...")
               return response.text
   ```

2. **Use in handlers:**
   ```python
   scraper = MyScraper()
   content = await scraper.safe_fetch()  # Automatic fallback on error
   await message.reply(content)
   ```

## Running Tests

```bash
# All tests
pytest tests/

# Specific test class
pytest tests/test_v2_architecture.py::TestMixins -v

# Async tests only
pytest tests/ -k "asyncio" -v

# With coverage (after pip install pytest-cov)
pytest tests/ --cov=. --cov-report=html
```

## Working with Redis

```python
# In any handler or database method
# All operations are async

# Hash operations
await self.redis.hset("key", mapping={"field": "value"})
value = await self.redis.hget("key", "field")
all_data = await self.redis.hgetall("key")

# List operations
await self.redis.lpush("list_key", "value")
values = await self.redis.lrange("list_key", 0, -1)

# Key operations
await self.redis.delete("key")
exists = await self.redis.exists("key")

# Pattern scanning
keys = [k async for k in self.redis.scan_iter(match="pattern*")]

# Pipeline (atomic multi-operation)
async with self.redis.pipeline() as pipe:
    pipe.hset("key1", mapping={...})
    pipe.hset("key2", mapping={...})
    await pipe.execute()
```

## Async/Await Patterns

```python
# Don't use sync I/O, use async equivalents
# ❌ Wrong
import requests
response = requests.get("https://...")

# ✅ Right
import httpx
async with httpx.AsyncClient() as client:
    response = await client.get("https://...")

# For sync libraries (feedparser), use asyncio.to_thread()
# ✅ Right
parsed = await asyncio.to_thread(feedparser.parse, url)
```

## Debugging

```bash
# Live logs
journalctl -u oiolabot-main -f
journalctl -u oiolabot-worker -f

# Check bot is running
ps aux | grep "python main.py"

# Test database connection
python -c "
import asyncio
from util.database.main_db import MainDatabase
db = MainDatabase(0)
print(asyncio.run(db.redis.ping()))
"

# Test scraper
python -c "
import asyncio
from util.scrapers.liturgia import LiturgiaScraper
s = LiturgiaScraper()
print(asyncio.run(s.safe_fetch()))
"
```

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Cannot use `await` outside async function` | Missing `async def` | Add `async` to function signature |
| `No module named 'kurigram'` | Kurigram not installed | `pip install kurigram` |
| `Redis connection refused` | Redis not running | `systemctl start redis` |
| `AttributeError: 'Client' has no attribute 'on_start'` | Using old Pyrogram | Use `kurigram` instead |
| `Event loop is closed` | Async cleanup issue | Add `async with` context managers |

## Environment Variables

```bash
# View current .env
cat .env

# Update a value
sed -i "s/API_ID=.*/API_ID=123456/" .env

# Test with override
API_ID=999 python main.py
```

## Git Workflow

```bash
# Always work on v2 branch
git checkout v2

# Create feature branch
git checkout -b feature/my-feature

# Make changes, test
pytest tests/
python main.py  # Manual test

# Commit with clear message
git commit -m "feature: Add my feature

- What it does
- How to test it

Fixes: #issue_number (if applicable)"

# Push and create PR
git push origin feature/my-feature
```

## Performance Tips

- Use `asyncio.gather()` to run multiple async operations in parallel
- Use `pipeline()` for multiple Redis operations (reduces round-trips)
- Cache expensive results (e.g., feed parsing results)
- Use `DEBUG` logging level only in development
- Monitor memory usage in long-running worker (check for leaks)

## Key Files to Know

| File | Purpose |
|------|---------|
| `factories/*.py` | How bots are created (dependency injection) |
| `bots/base.py` | Lifecycle hooks (`on_start`, `on_stop`) |
| `util/database/base.py` | Redis utility methods (`_find`, `exists`, `close`) |
| `util/scrapers/base.py` | Error handling template (`safe_fetch`) |
| `worker/*.py` | Background job implementations |
| `CLAUDE.md` | Project guidelines and conventions |
| `docs/V2_SPEC.md` | Detailed architecture specification |

## Next Steps

1. Read `docs/V2_SPEC.md` for full architecture
2. Read `docs/DEPLOYMENT_GUIDE.md` for deployment instructions
3. Run `pytest tests/` to verify environment
4. Pick a feature from `docs/AUDITORIA.md` and implement it
5. Check memory at `.claude/projects/...../memory/` for context
