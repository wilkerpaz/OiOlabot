# OiOlabot v2 — Especificação de Refatoração

> Criado em: 2026-05-23
> Status: Aprovado para implementação
> Contexto: Ver `ESTADO_DO_PROJETO.md` e `AUDITORIA.md` para diagnóstico completo do v1

---

## 1. Motivação

O v1 acumulou dívida estrutural que torna qualquer evolução custosa:

- Dois frameworks em paralelo: **Pyrogram** (async) e **pyTelegramBotAPI** (sync)
- ~11 funções idênticas duplicadas entre `bot.py` e `ltd_bot.py`
- `feed_bot.py` e `feed_ltd_bot.py` são cópias com diferença mínima
- 27 handlers síncronos em contexto assíncrono (`ltd_bot.py`)
- 8 bugs críticos identificados na auditoria

A estratégia adotada é **estabilizar o v1** com correções cirúrgicas enquanto o v2 é construído em paralelo em branch separado (`v2`), substituindo o v1 quando validado.

---

## 2. Decisões de Arquitetura

> **Nota (2026-05-23):** Pyrogram está arquivado desde 2023 (último commit de código: 2023-04-30).
> O v2 adota **Kurigram** (`kurigram`, fork ativo em https://github.com/KurimuzonAkuma/pyrogram),
> API 100% compatível — imports continuam `from pyrogram import ...` sem mudança no código.
> Ativo semanalmente, suporta Bot API 10.0. Não confundir com `pyrofork` (Mayuri-Chan, menos ativo).

| Decisão | v1 | v2 |
|---------|----|----|
| Framework bot | Pyrogram + pyTelegramBotAPI | Kurigram (único) |
| Scheduling | APScheduler interno + cron externo | Worker único com APScheduler |
| Containerização | Nenhuma | Serviços NixOS nativos (systemd via nix) |
| Deploy | Manual | `nix/service.nix` declarativo |
| Padrões de design | Nenhum formal | Abstract Factory + Mixins + Template Method |

---

## 3. Estrutura de Arquivos

```
OiOlabot/
│
├── main.py                        # entry point: sobe MainBot + LiturgyBot
├── worker.py                      # entry point: FeedWorker + LiturgyJob agendados
│
├── factories/
│   ├── __init__.py
│   ├── base.py                    # BotFactory (ABC)
│   ├── main_factory.py            # MainBotFactory
│   └── liturgy_factory.py         # LiturgyBotFactory
│
├── bots/
│   ├── __init__.py
│   ├── base.py                    # BaseBot — ciclo de vida + registro de handlers
│   ├── main_bot.py                # MainBot(WelcomeMixin, FeedMixin, BaseBot)
│   └── liturgy_bot.py             # LiturgyBot(WelcomeMixin, FeedMixin, LiturgyMixin, BaseBot)
│
├── mixins/
│   ├── __init__.py
│   ├── welcome.py                 # WelcomeMixin
│   ├── feed.py                    # FeedMixin
│   └── liturgy.py                 # LiturgyMixin
│
├── worker/
│   ├── __init__.py
│   ├── feed_job.py                # FeedJob — distribui RSS (parametrizado)
│   └── liturgy_job.py             # LiturgyJob — envia liturgia diária às 7h
│
├── util/
│   ├── __init__.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── base.py                # BaseDatabase — operações Redis genéricas
│   │   ├── main_db.py             # MainDatabase(BaseDatabase)
│   │   └── liturgy_db.py          # LiturgyDatabase(BaseDatabase)
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py                # BaseScraper (ABC) — interface + safe_fetch
│   │   ├── liturgia.py
│   │   ├── homilia.py
│   │   └── santo.py
│   ├── datehandler.py             # sem mudança
│   ├── feedhandler.py             # sem mudança
│   └── calendar.py                # sem mudança
│
├── nix/
│   ├── default.nix                # dependências Python via nix
│   └── service.nix                # módulo NixOS: dois serviços systemd
│
├── requirements.txt
├── .env
└── config.ini_example
```

---

## 4. Design Patterns

### 4.1 Abstract Factory — criação da família de objetos por bot

**Problema:** cada bot precisa de um conjunto coerente de `(Client, Database, Scheduler)`. Instanciar esses três objetos espalhados pelo código acopla configuração e lógica.

**Solução:** uma fábrica por tipo de bot garante que os três objetos sempre sejam criados juntos e compatíveis.

```
BotFactory (ABC)
├── create_client()      → pyrogram.Client
├── create_database()    → BaseDatabase
└── create_scheduler()   → AsyncIOScheduler | None

    ├── MainBotFactory
    │     create_client()      → Client(token=DEV_TOKEN, name=BOT_NAME)
    │     create_database()    → MainDatabase(db=DB)
    │     create_scheduler()   → None
    │
    └── LiturgyBotFactory
          create_client()      → Client(token=DEV_TOKEN_LD, name=BOT_NAME_LD)
          create_database()    → LiturgyDatabase(db=DB_LD)
          create_scheduler()   → AsyncIOScheduler
```

---

### 4.2 Mixins — handlers compartilhados sem herança profunda

**Problema:** `bot.py` e `ltd_bot.py` duplicam ~11 handlers. Qualquer correção precisa ser aplicada em dois lugares.

**Solução:** extrair handlers comuns em Mixins independentes; cada bot os compõe conforme necessário.

```
WelcomeMixin
├── _check(update)           → valida permissões de grupo
├── _welcome(update)         → envia mensagem de boas-vindas
├── _introduce(update)       → bot adicionado ao grupo → dispara start()
├── goodbye(update)          → mensagem de despedida
├── set_welcome(update)
├── set_goodbye(update)
├── disable_welcome(update)
├── disable_goodbye(update)
├── lock(update)
├── unlock(update)
├── quiet(update)
└── unquiet(update)

FeedMixin
├── add_url(update)
├── list_url(update)
├── remove_url(update)
├── feed_url(update)          → valida URL antes de assinar
└── get_chat_by_username(update)

LiturgyMixin
├── hoje(update)
├── ontem(update)
├── amanha(update)
├── dominical(update)
├── santododia(update)
└── calendario(update)        → widget de calendário inline
```

---

### 4.3 Template Method — scrapers com fallback garantido

**Problema:** os três scrapers (`liturgia`, `homilia`, `santo`) dependem de HTML frágil do Canção Nova. Não há tratamento de falha — erros de scraping chegam silenciosamente ao usuário.

**Solução:** `BaseScraper` define o fluxo; subclasses implementam apenas o `fetch()` concreto.

```
BaseScraper (ABC)
├── fetch() → str | None      → implementado por cada scraper
└── safe_fetch() → str        → chama fetch(), captura exceção, retorna fallback

    ├── LiturgiaScraper(BaseScraper)
    ├── HomiliaScraper(BaseScraper)
    └── SantoScraper(BaseScraper)
```

---

## 5. Hierarquia de Bots

```
BaseBot
├── __init__(factory: BotFactory)
│     self.client    = factory.create_client()
│     self.db        = factory.create_database()
│     self.scheduler = factory.create_scheduler()
├── register_handlers()   → abstrato
└── run()                 → inicia client; se scheduler, inicia junto

    ├── MainBot(WelcomeMixin, FeedMixin, BaseBot)
    │     Exclusivo: /backup, /admin, /getkey, /removekey, /owner
    │
    └── LiturgyBot(WelcomeMixin, FeedMixin, LiturgyMixin, BaseBot)
          Exclusivo: /start, /stop, /activated, /deactivated,
                     /senddailyliturgy, /sendaudioliturgy, /userinfoliturgy
```

---

## 6. Hierarquia de Database

```
BaseDatabase
├── connect()
├── exists(key)
├── scan(pattern)
├── get(key)
├── set(key, value)
└── delete(key)

    ├── MainDatabase(BaseDatabase)
    │     Grupos:   get/set welcome, goodbye, lock, quiet
    │     URLs:     add, remove, list, activate, deactivate
    │     Admins:   list_admins, add_admin
    │     Backup:   dump path
    │
    └── LiturgyDatabase(BaseDatabase)
          Inscrições:  add, remove, list (ativas/inativas)
          last_send:   get, set (com timezone correto)
          Áudio:       cache file_id por data
```

---

## 7. Worker — substituição do cron externo

O `worker.py` centraliza todos os jobs background, eliminando o cron externo não documentado e o APScheduler interno do `ltd_bot.py`.

```
worker.py
└── scheduler = AsyncIOScheduler

    ├── FeedJob(db=MainDatabase, token=DEV_TOKEN)
    │     run() → distribui RSS do bot principal
    │     agendado: a cada N minutos (configurável via .env)
    │
    ├── FeedJob(db=LiturgyDatabase, token=DEV_TOKEN_LD)
    │     run() → distribui RSS do bot de liturgia
    │     agendado: a cada N minutos
    │
    └── LiturgyJob(db=LiturgyDatabase, token=DEV_TOKEN_LD, scrapers=[...])
          run() → busca liturgia + homilia + santo → envia aos inscritos
          agendado: 07:00 America/Belem diariamente
```

**`FeedJob` é parametrizado** — um único arquivo serve os dois bots. A diferença entre `feed_bot.py` e `feed_ltd_bot.py` desaparece.

---

## 8. Entry Points

### `main.py` — bots interativos

```python
main_bot    = MainBot(MainBotFactory())
liturgy_bot = LiturgyBot(LiturgyBotFactory())

asyncio.gather(
    main_bot.run(),
    liturgy_bot.run()
)
```

### `worker.py` — jobs background

```python
scheduler.add_job(FeedJob(MainDatabase(), DEV_TOKEN).run,    ...)
scheduler.add_job(FeedJob(LiturgyDatabase(), DEV_TOKEN_LD).run, ...)
scheduler.add_job(LiturgyJob(...).run, cron(hour=7))
scheduler.start()
```

---

## 9. Deploy — NixOS (sem Docker)

NixOS já provê reprodutibilidade, isolamento e rollback nativos. Docker replicaria essas garantias com overhead adicional.

### `nix/service.nix` — dois serviços systemd declarativos

```
oiolabot-main.service
├── ExecStart: python main.py
├── Restart: on-failure
└── EnvironmentFile: /path/to/.env

oiolabot-worker.service
├── ExecStart: python worker.py
├── Restart: on-failure
└── EnvironmentFile: /path/to/.env
```

O `oiolabot-worker.service` substitui integralmente o cron externo atual.

---

## 10. Variáveis de Ambiente

Sem mudança em relação ao v1. O `.env` existente é compatível com o v2.

| Variável | Usado em |
|----------|----------|
| `API_ID`, `API_HASH` | factories (ambas) |
| `DEV_TOKEN` | MainBotFactory, FeedJob(main) |
| `DEV_TOKEN_LD` | LiturgyBotFactory, FeedJob(liturgy), LiturgyJob |
| `BOT_NAME`, `BOT_NAME_LD` | factories |
| `REDIS` | BaseDatabase |
| `DB`, `DB_LD` | MainDatabase, LiturgyDatabase |
| `TZ` | datehandler, LiturgyJob |
| `PATH_REDIS` | MainDatabase.backup() |
| `THREADS` | FeedJob (agora efetivamente usado) |
| `CHANNEL_LD` | LiturgyJob |
| `LOG` | todos |
| `FEED_INTERVAL` | **novo** — intervalo do FeedJob em minutos |

---

## 11. O que é preservado do v1

- Toda a lógica de negócio (comandos, fluxos, respostas ao usuário)
- Schema de chaves Redis (sem migração de dados)
- Variáveis de ambiente (`.env` compatível)
- Módulos `datehandler.py`, `feedhandler.py`, `calendar.py`
- Conteúdo 100% em português
- Fuso `America/Belem`

---

## 12. Plano de Execução

### Fase 0 — v1 estabilizado (branch `master`)
Corrigir os 8 bugs críticos identificados na auditoria. Sem refatoração.
Ver `AUDITORIA.md` § 6 Fase 1.

### Fase 1 — Esqueleto v2 (branch `v2`)
1. Criar estrutura de diretórios
2. Implementar `BotFactory` + `BaseBot` + `BaseDatabase` + `BaseScraper`
3. Validar inicialização e conexão com Redis/Telegram

### Fase 2 — Migração dos Mixins
1. `WelcomeMixin` — extraído de `bot.py`
2. `FeedMixin` — extraído de `bot.py`
3. `LiturgyMixin` — extraído de `ltd_bot.py`
4. Validar `MainBot` completo em staging

### Fase 3 — Worker e Scrapers
1. Implementar `FeedJob` parametrizado
2. Implementar `LiturgyJob` com `BaseScraper`
3. Validar envio às 7h e distribuição de feeds

### Fase 4 — NixOS e encerramento
1. Escrever `nix/service.nix`
2. Testar deploy completo
3. Substituir v1 em produção
4. Arquivar `feed_bot.py`, `feed_ltd_bot.py`, `login.py` (obsoletos no v2)

---

## 13. O que NÃO está no escopo do v2

- Testes automatizados (pode ser Fase 5 futura)
- Novos comandos ou features
- Mudança de storage (Redis permanece)
- Suporte a outros idiomas

---

*Documento gerado em 2026-05-23. Atualizar ao encerrar cada fase.*
