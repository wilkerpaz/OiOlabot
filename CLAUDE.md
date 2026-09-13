# OiOlabot — Contexto para Claude Code

## O que é este projeto

Dois bots Telegram para comunidades católicas brasileiras:
- **Bot principal** (`main.py`) — boas-vindas/despedidas em grupos + assinatura de feeds RSS
- **Bot de liturgia** (`liturgy.py`) — entrega diária de leituras, homilia e santo do dia às 7h (America/Belem)

Todo conteúdo é em português. O projeto roda em NixOS.

---

## Estado atual: só existe `master` — v1 está arquivado em `legacy/`

**Não existe branch `v2`.** Toda a arquitetura v2 (`main.py`, `liturgy.py`, `worker.py`, `watchdog.py` + `factories/`, `bots/`, `mixins/`, `worker/`) vive direto na `master` e é o que roda em produção — ✅ **PRODUÇÃO-READY**.

O código v1 original (`bot.py`, `ltd_bot.py`, `feed_bot.py`, `feed_ltd_bot.py`, `login.py` e os módulos `util/` exclusivos deles) **não foi corrigido, foi substituído** — está movido para `legacy/`, não roda em lugar nenhum, e é mantido só como referência histórica. Os bugs documentados em `docs/AUDITORIA.md` continuam lá, sem correção, porque não há mais planos de rodar esse código.

**Não porte código do `legacy/` direto para o v2 sem reescrever para async** (veja "Porting de v1 para v2" abaixo).

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
| `DB=0` | `.env` | `main.py`, `FeedJob` (`worker.py`) — grupos, RSS, assinaturas |
| `DB_LD=1` | `.env` | `liturgy.py`, `LiturgyJob` (`worker.py`) — liturgia diária |

Schema completo em `docs/REDIS_SCHEMA.md`.

---

## Arquitetura v2 — Quatro processos independentes

O v2 roda como **4 systemd `--user` services** isolados (via home-manager, não systemd system-wide):

| Processo | Entry Point | Responsabilidade | Cron |
|----------|-------------|------------------|------|
| **MainBot** | `main.py` | Boas-vindas/despedidas (grupos) + RSS handlers | - |
| **LiturgyBot** | `liturgy.py` | Handlers para comandos de liturgia | - |
| **Worker** | `worker.py` | Distribuição de feeds + liturgia diária | Cada 5min + 7am |
| **Watchdog** | `watchdog.py` | Verifica os outros 3 serviços + Redis, reinicia se caído, avisa via Telegram (`ADMIN_CHAT_ID`) | Cada 15min |

**Banco de dados por processo:**
- MainBot e FeedJob (main) → Redis DB 0 (grupos, RSS)
- LiturgyBot e LiturgyJob → Redis DB 1 (assinaturas, cache)

---

## Padrões do v2

- **Abstract Factory** — `factories/` cria `(Client, Database)` por bot
- **Mixins** — `mixins/` deduplicação: WelcomeMixin, FeedMixin, LiturgyMixin, AdminMainMixin, AdminLiturgyMixin
- **Template Method** — `BaseScraper.safe_fetch()` com fallback automático
- **Async/await** — Kurigram (Client), redis.asyncio, httpx (scrapers), APScheduler
- **Job-based scheduling** — Worker executa 2 jobs via APScheduler CronTrigger (FeedJob + LiturgyJob); o healthcheck virou processo separado (`watchdog.py`), não um 3º job do APScheduler
- **Error classification** — ErrorHandler separa erros permanentes (bot blocked, chat deleted) de transitórios (rate limit, timeout)

---

## Tratamento de Erros v2

Subscriptions são desativadas **apenas em erros permanentes** (Telegram API 403/400 com "blocked", "not a member", "chat not found", etc). Erros transitórios (429 rate limit, 5xx server error) são logados e a subscription mantém-se ativa para próxima tentativa.

- **Permanente** — Bot bloqueado pelo usuário, usuário deativado, chat deletado → deactivate_subscription/deactivate_url_for_chat
- **Transitório** — Rate limit (429), timeout, server error (5xx) → log + retry no próximo ciclo
- **Implementação** — `worker/error_handler.py::ErrorHandler.classify_response()` usado por FeedJob e LiturgyJob

---

## Estrutura de diretórios (v2)

```
factories/
  ├── base.py              # BotFactory (ABC)
  ├── main_factory.py      # MainBotFactory
  └── liturgy_factory.py   # LiturgyBotFactory

bots/
  ├── base.py              # BaseBot (ABC, lifecycle hooks)
  ├── main_bot.py          # MainBot = WelcomeMixin + FeedMixin + AdminMainMixin + BaseBot
  └── liturgy_bot.py       # LiturgyBot = WelcomeMixin + FeedMixin + LiturgyMixin + AdminLiturgyMixin + BaseBot

mixins/
  ├── welcome.py           # Handlers: /welcome, /goodbye, /lock, /unlock, /quiet, /unquiet, /start, /stop, /chatinfo
  ├── feed.py              # Handlers: /addurl, /listurl, /removeurl
  ├── liturgy.py           # Handlers: /hoje, /ontem, /amanha, /dominical, /santododia, /calendario
  ├── admin_main.py        # Admin handlers: /owner, /admin, /backup, /deactivatedurl, /activateallurl, /allurl
  └── admin_liturgy.py     # Admin handlers: /admin, /senddailyliturgy, /sendaudioliturgy, /activateallliturgy, /deactivated, /activated, /userinfoliturgy, /userliturgydeactivated

util/
  ├── database/
  │   ├── base.py          # BaseDatabase (Redis async, scan_iter, pipeline)
  │   ├── main_db.py       # MainDatabase (12 métodos: config, URLs, metadata, deactivate_url_for_chat)
  │   └── liturgy_db.py    # LiturgyDatabase (11 métodos: subscriptions, cache, deactivate_subscription)
  ├── scrapers/
  │   ├── base.py          # BaseScraper (ABC, safe_fetch + fallback, make_client com follow_redirects)
  │   ├── liturgia.py      # LiturgiaScraper (leituras diárias via httpx, datas em português)
  │   ├── homilia.py       # HomiliaScraper (homilia do dia, 302 redirects suportados)
  │   ├── audio.py         # AudioScraper (MP3 homilia, cache, iframe semântico)
  │   └── santo.py         # SantoScraper (santo do dia, 302 redirects suportados)
  ├── feedhandler.py       # FeedHandler (asyncio.to_thread para sync feedparser)
  ├── datehandler.py       # DateHandler (timezone-aware, copiado de v1)
  └── calendar.py          # Inline calendar (copiado de v1, compatível com Kurigram)

worker/
  ├── error_handler.py     # ErrorHandler: classifica respostas Telegram (permanent, transient, unknown)
  ├── feed_job.py          # FeedJob: distribui feeds RSS (5min), deactiva em erro permanent
  └── liturgy_job.py       # LiturgyJob: envia liturgia diária (7am), deactiva em erro permanent

legacy/                     # v1 (Pyrogram original) — arquivado, NÃO roda em produção
  ├── bot.py, ltd_bot.py, feed_bot.py, feed_ltd_bot.py, login.py
  └── util/                # database.py, database_daily_liturgy.py, homiliadodia.py, liturgiadiaria.py, santododia.py

tests/                      # Suíte de testes (pytest)

main.py                     # Entry point: MainBot(MainBotFactory()).run()
liturgy.py                  # Entry point: LiturgyBot(LiturgyBotFactory()).run()
worker.py                   # Entry point: APScheduler com 2 jobs (FeedJob + LiturgyJob)
watchdog.py                 # Entry point: verifica/reinicia serviços caídos, alerta via Telegram

nix/
  ├── default.nix          # Build Python 3.11 com kurigram + deps
  ├── home.nix             # Espelho de referência dos 4 serviços systemd --user reais (gitignored; o arquivo aplicado de fato fica em ~/.config/home-manager/home.nix no servidor)
  └── service.nix          # Referência alternativa NÃO usada hoje (módulo NixOS system-wide, usuário dedicado)
```

---

## Melhorias em Scrapers (v2)

1. **Redirecionamentos HTTP** — `BaseScraper.make_client()` com `follow_redirects=True` (httpx tem False por padrão)
2. **AudioScraper** — Novo, extrai homilia em MP3 da Canção Nova. Iframe selection semântico via `div.embeds-audio` (evita confusão com YouTube iframe)
3. **Datas em português** — `LiturgiaScraper._format_portuguese_date()` mostra "sexta-feira, 23 de maio de 2026"
4. **Cache de arquivos** — AudioScraper cache MP3s em `/tmp/{date}.mp3` para evitar re-downloads

---

## Deployment (NixOS + home-manager)

4 serviços systemd **de usuário** (`systemctl --user`, via home-manager), rodando como o usuário normal (sem `oiolabot` dedicado, sem `/opt/oiolabot` — o clone fica em `~/OiOlabot`):

```bash
# Ver status
systemctl --user status oiolabot-main oiolabot-liturgy oiolabot-worker oiolabot-watchdog

# Logs
journalctl --user -u oiolabot-main -f
journalctl --user -u oiolabot-liturgy -f
journalctl --user -u oiolabot-worker -f

# Reiniciar
systemctl --user restart oiolabot-main oiolabot-liturgy oiolabot-worker
```

O `oiolabot-watchdog` roda via `systemd.user.timers` (a cada 15min) — não é reiniciado manualmente como serviço contínuo. A definição real dos 4 serviços fica em `~/.config/home-manager/home.nix` no servidor (aplicada com `home-manager switch`); `nix/home.nix` neste repo é um espelho de referência sincronizado manualmente.

**Requisitos:**
1. `.env` com: `API_ID`, `API_HASH`, `DEV_TOKEN`, `DEV_TOKEN_LD`, `DB`, `DB_LD`, `TZ`, `LOG`, `ADMIN_CHAT_ID` (pro watchdog)
2. Redis rodando: `redis-server` em localhost:6379, **bind restrito a `127.0.0.1`/`::1`** (`protected-mode yes`) — nunca `0.0.0.0`
3. Python 3.11+ num único venv (`.venv`) com: `kurigram`, `httpx`, `redis[asyncio]`, `feedparser`, `beautifulsoup4`, `apscheduler`
4. `loginctl enable-linger <usuário>` — sem isso, os serviços `--user` não sobrevivem sem sessão logada

---

## O que NÃO fazer

- Não usar `pyrogram` nem `pyrofork` em código novo — usar `kurigram`
- Não usar `pyTelegramBotAPI` no v2 — Kurigram cobre tudo
- Não usar Docker — deploy via home-manager (`nix/home.nix` é a referência; `nix/service.nix` é uma alternativa não usada)
- Não commitar `.env` — contém tokens e hash da API Telegram (já vazou uma vez via `config.ini_example`, ver histórico do commit `86f1ce4`)
- Não copiar código do `legacy/` (v1) direto pro v2 sem reescrever para async (veja "Porting de v1 para v2")
- Não hardcodear IDs de admin — use o sistema de admins do Redis (`/addadmin`, `/removeadmin`, `/listadmin`)

---

## Arquivos de referência

### Documentação (docs/)
| Arquivo | Conteúdo |
|---------|----------|
| `docs/AUDITORIA.md` | Bugs do v1 — documento histórico, v1 está arquivado e não será corrigido |
| `docs/V2_SPEC.md` | Especificação original da refatoração v2 (histórico de design) |
| `docs/V2_QUICK_START.md` | Guia rápido de início para desenvolvimento v2 |
| `docs/KURIGRAM_KB.md` | API Kurigram: handlers, filtros, lifecycle, padrões do v2 |
| `docs/REDIS_PY_KB.md` | redis-py async: migração StrictRedis→asyncio, scan_iter, pipeline |
| `docs/REDIS_SCHEMA.md` | Schema de chaves Redis: key patterns, campos, dois bancos |
| `docs/DEPLOYMENT_GUIDE.md` | Guia de deploy em produção (home-manager + systemd --user) |

### Configuração
| Arquivo | Conteúdo |
|---------|----------|
| `.env` | Variáveis de ambiente (nunca commitar) |
| `config.ini_example` | Referência de configuração |
| `requirements.txt` | Dependências Python (v2: kurigram, httpx, redis[asyncio], apscheduler) |

---

## Comandos v2

### MainBot (DB=0)
- Públicos: `/help`, `/welcome`, `/goodbye`, `/lock`, `/unlock`, `/quiet`, `/unquiet`, `/addurl`, `/listurl`, `/removeurl`, `/start`, `/stop`, `/me`
- Admin (12): `/owner`, `/admin`, `/addadmin`, `/removeadmin`, `/listadmin`, `/backup`, `/deactivatedurl`, `/activateallurl`, `/allurl`, `/activated`, `/deactivated`, `/userinfo`

### LiturgyBot (DB=1)
- Públicos: `/help`, `/start`, `/stop`, `/hoje`, `/ontem`, `/amanha`, `/dominical`, `/santododia`, `/calendario`, `/welcome`, `/goodbye`, `/addurl`, `/listurl`, `/removeurl`
- Admin (11): `/admin`, `/addadmin`, `/removeadmin`, `/listadmin`, `/senddailyliturgy`, `/sendaudioliturgy`, `/activateallliturgy`, `/deactivated`, `/activated`, `/userinfoliturgy`, `/userliturgydeactivated`

**Nota:** Admin handlers não aparecem em `/help`. **Não são IDs hardcoded** — a lista de admins vive no Redis (chave `admins`, gerenciada via `MainDatabase.add_admin/remove_admin/list_admins/is_admin` em `util/database/main_db.py`) e é administrada dinamicamente com `/addadmin`, `/removeadmin`, `/listadmin`.

---

## Como Trabalhar com v2

### Primeiro acesso
```bash
git clone https://github.com/wilkerpaz/OiOlabot.git
cd OiOlabot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Validar imports
.venv/bin/python -c "from factories.main_factory import MainBotFactory; print('OK')"
```

### Adicionar feature
1. Identifique qual mixin (`welcome.py`, `feed.py`, `liturgy.py`) ou qual job (`feed_job.py`, `liturgy_job.py`)
2. Implemente o método async
3. Teste com `pytest` (crie testes em `tests/` se adicionar nova lógica)
4. Commit na `master` (não existe branch `v2`)

### Porting de v1 (legacy/) para v2
Se precisar trazer código do `legacy/`:
1. Identifique o padrão (é um handler? É uma scraper? É database?)
2. Reescreva para async (use `async def`, `await`, `httpx.AsyncClient`)
3. Coloque no lugar certo (mixin vs util)
4. Teste isoladamente antes de integrar

---
