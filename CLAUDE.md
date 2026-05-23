# OiOlabot — Contexto para Claude Code

## O que é este projeto

Dois bots Telegram para comunidades católicas brasileiras:
- **Bot principal** (`bot.py`) — boas-vindas/despedidas em grupos + assinatura de feeds RSS
- **Bot de liturgia** (`ltd_bot.py`) — entrega diária de leituras, homilia e santo do dia às 7h (America/Belem)

Todo conteúdo é em português. O projeto roda em NixOS.

---

## Estado atual: v1 (master) e v2 (branch `v2`)

- **`master`** — código funcional com bugs críticos conhecidos. Ver `docs/AUDITORIA.md`.
- **`v2`** — ✅ **COMPLETO** — pronto para deployment. 4 commits, 6 fases implementadas. Ver `docs/V2_SPEC.md` e memory `v2_architecture_complete.md`.

**Não misture correções do v1 com desenvolvimento do v2.** Trabalhe sempre na branch apropriada.

---

## Framework: Kurigram (não Pyrogram, não pyrofork)

O Pyrogram original está **arquivado** desde 2023. O projeto adota **Kurigram**:

- PyPI: `kurigram` (`pip install kurigram`)
- GitHub: https://github.com/KurimuzonAkuma/pyrogram
- **Imports não mudam:** `from pyrogram import Client, filters` — continua igual
- Não usar `pyrofork` (Mayuri-Chan/pyrofork, menos ativo, 280 stars vs 737)

---

## Redis — dois bancos

| Banco | Variável | Usado por |
|-------|----------|-----------|
| `DB=0` | `.env` | `bot.py`, `feed_bot.py` — grupos, RSS, assinaturas |
| `DB_LD=1` | `.env` | `ltd_bot.py`, `feed_ltd_bot.py` — liturgia diária |

Schema completo em `docs/REDIS_SCHEMA.md`.

---

## Arquitetura v2 — Três processos independentes

O v2 roda como **3 systemd services** isolados:

| Processo | Entry Point | Responsabilidade | Cron |
|----------|-------------|------------------|------|
| **MainBot** | `main.py` | Boas-vindas/despedidas (grupos) + RSS handlers | - |
| **LiturgyBot** | `liturgy.py` | Handlers para comandos de liturgia | - |
| **Worker** | `worker.py` | Distribuição de feeds + liturgia diária | Cada 5min + 7am |

**Banco de dados por processo:**
- MainBot e FeedJob (main) → Redis DB 0 (grupos, RSS)
- LiturgyBot e LiturgyJob → Redis DB 1 (assinaturas, cache)

---

## Padrões do v2

- **Abstract Factory** — `factories/` cria `(Client, Database)` por bot
- **Mixins** — `mixins/` deduplicação: WelcomeMixin, FeedMixin, LiturgyMixin
- **Template Method** — `BaseScraper.safe_fetch()` com fallback automático
- **Async/await** — Kurigram (Client), redis.asyncio, httpx (scrapers), APScheduler
- **Job-based scheduling** — Worker executa 3 jobs via APScheduler CronTrigger

---

## Estrutura de diretórios (v2)

```
factories/
  ├── base.py              # BotFactory (ABC)
  ├── main_factory.py      # MainBotFactory
  └── liturgy_factory.py   # LiturgyBotFactory

bots/
  ├── base.py              # BaseBot (ABC, lifecycle hooks)
  ├── main_bot.py          # MainBot = WelcomeMixin + FeedMixin + BaseBot
  └── liturgy_bot.py       # LiturgyBot = WelcomeMixin + FeedMixin + LiturgyMixin + BaseBot

mixins/
  ├── welcome.py           # Handlers: /welcome, /goodbye, /lock, /unlock, /quiet, /unquiet
  ├── feed.py              # Handlers: /addurl, /listurl, /removeurl
  └── liturgy.py           # Handlers: /hoje, /ontem, /amanha, /dominical, /santododia, /calendario

util/
  ├── database/
  │   ├── base.py          # BaseDatabase (Redis async, scan_iter, pipeline)
  │   ├── main_db.py       # MainDatabase (11 métodos: config, URLs, metadata)
  │   └── liturgy_db.py    # LiturgyDatabase (9 métodos: subscriptions, cache)
  ├── scrapers/
  │   ├── base.py          # BaseScraper (ABC, safe_fetch + fallback)
  │   ├── liturgia.py      # LiturgiaScraper (leituras diárias via httpx)
  │   ├── homilia.py       # HomiliaScraper (homilia do dia)
  │   └── santo.py         # SantoScraper (santo do dia)
  ├── feedhandler.py       # FeedHandler (asyncio.to_thread para sync feedparser)
  ├── datehandler.py       # DateHandler (timezone-aware, copiado de v1)
  └── calendar.py          # Inline calendar (copiado de v1, compatível com Kurigram)

worker/
  ├── feed_job.py          # FeedJob: distribui feeds RSS (5min)
  └── liturgy_job.py       # LiturgyJob: envia liturgia diária (7am)

main.py                     # Entry point: MainBot(MainBotFactory()).run()
liturgy.py                  # Entry point: LiturgyBot(LiturgyBotFactory()).run()
worker.py                   # Entry point: APScheduler com 3 jobs

nix/
  ├── default.nix          # Build Python 3.11 com kurigram + deps
  └── service.nix          # 3 systemd services (oiolabot-main, -liturgy, -worker)
```

---

## Deployment (NixOS)

Três systemd services, cada um com seu próprio user `oiolabot`:

```bash
# Ver status
systemctl status oiolabot-main oiolabot-liturgy oiolabot-worker

# Logs
journalctl -u oiolabot-main -f
journalctl -u oiolabot-liturgy -f
journalctl -u oiolabot-worker -f

# Reiniciar
systemctl restart oiolabot-main oiolabot-liturgy oiolabot-worker
```

**Requisitos:**
1. `.env` com: `API_ID`, `API_HASH`, `DEV_TOKEN`, `DEV_TOKEN_LD`, `DB`, `DB_LD`, `TZ`, `LOG`
2. Redis rodando: `redis-server` em localhost:6379
3. Python 3.11+ com: `kurigram`, `httpx`, `redis[asyncio]`, `feedparser`, `beautifulsoup4`, `apscheduler`

---

## O que NÃO fazer

- Não usar `pyrogram` nem `pyrofork` em código novo — usar `kurigram`
- Não usar `pyTelegramBotAPI` no v2 — Kurigram cobre tudo
- Não usar Docker — deploy via `nix/service.nix` (systemd NixOS)
- Não commitar `.env` — contém tokens e hash da API Telegram
- Não aplicar correções do v1 diretamente em v2 (porta com cuidado, adapte para async)
- Não modificar handlers sem testar em ambas as branches (se aplicável)

---

## Arquivos de referência

### Documentação (docs/)
| Arquivo | Conteúdo |
|---------|----------|
| `docs/ESTADO_DO_PROJETO.md` | Mapeamento completo do v1 (para referência) |
| `docs/AUDITORIA.md` | Bugs críticos e plano de correção do v1 |
| `docs/V2_SPEC.md` | Especificação completa da refatoração v2 |
| `docs/KURIGRAM_KB.md` | API Kurigram: handlers, filtros, lifecycle, padrões do v2 |
| `docs/REDIS_PY_KB.md` | redis-py async: migração StrictRedis→asyncio, scan_iter, pipeline |
| `docs/REDIS_SCHEMA.md` | Schema de chaves Redis: key patterns, campos, dois bancos |

### Configuração
| Arquivo | Conteúdo |
|---------|----------|
| `.env` | Variáveis de ambiente (nunca commitar) |
| `config.ini_example` | Referência de configuração |
| `requirements.txt` | Dependências Python (v2: kurigram, httpx, redis[asyncio], apscheduler) |

### Memory (persistente entre sessões)
| Arquivo | Conteúdo |
|---------|----------|
| `v2_architecture_complete.md` | Status v2: 6 fases completas, pronto para deploy |
| `reference_kurigram.md` | Por que Kurigram (não Pyrogram/pyrofork), imports unchanged |
| `reference_redis_schema.md` | Schema Redis com dois bancos e key patterns |
| `reference_redis_async.md` | Guia de migração StrictRedis → redis.asyncio |

---

## Como Trabalhar com v2

### Primeiro acesso
```bash
git checkout v2
pip install -r requirements.txt
# Validar imports
python -c "from factories.main_factory import MainBotFactory; print('OK')"
```

### Adicionar feature
1. Identifique qual mixin (`welcome.py`, `feed.py`, `liturgy.py`) ou qual job (`feed_job.py`, `liturgy_job.py`)
2. Implemente o método async
3. Teste com `pytest` (crie testes em `tests/` se adicionar nova lógica)
4. Commit na branch `v2`

### Porting de v1 para v2
Se precisar trazer código do v1:
1. Identifique o padrão (é um handler? É uma scraper? É database?)
2. Reescreva para async (use `async def`, `await`, `httpx.AsyncClient`)
3. Coloque no lugar certo (mixin vs util)
4. Teste isoladamente antes de integrar

---
