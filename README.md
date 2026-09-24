# OiOlabot — Bots Telegram para Comunidades Católicas Brasileiras

**Status:** ✅ PRODUÇÃO-READY (v2)

Dois bots Telegram especializados em automação para comunidades católicas brasileiras:
- **Bot Principal** — Boas-vindas/despedidas em grupos + assinatura de feeds RSS
- **Bot de Liturgia** — Entrega diária de leituras, homilia e santo do dia às 7h (America/Belem)

---

## 🚀 Funcionalidades

### MainBot (DB 0 — Grupos e RSS)

**Públicos:**
- `/help` — Lista de comandos disponíveis
- `/welcome`, `/goodbye` — Mensagens customizadas de boas-vindas/despedidas
- `/lock`, `/unlock` — Ativar/desativar boas-vindas automáticas
- `/quiet`, `/unquiet` — Ativar/desativar despedidas automáticas
- `/addurl`, `/listurl`, `/removeurl` — Gerenciar feeds RSS
- `/start`, `/stop` — Ativar/desativar bot
- `/me` — Informações do chat

**Admin (secretos):**
- `/owner` — Designar proprietário do grupo
- `/admin` — Listar comandos de admin
- `/addadmin`, `/removeadmin`, `/listadmin` — Gerenciar administradores
- `/backup` — Exportar backup do Redis (arquivo `.rdb`)
- `/deactivatedurl`, `/activateallurl`, `/allurl` — Gerenciar feeds globalmente
- `/activated`, `/deactivated` — Contagem de feeds ativos/inativos
- `/userinfo` — Chats com feeds ativos

### LiturgyBot (DB 1 — Liturgia Diária)

**Públicos:**
- `/help` — Lista de comandos
- `/hoje`, `/ontem`, `/amanha` — Leituras de um dia específico
- `/dominical` — Leitura de domingo
- `/santododia` — Santo do dia
- `/calendario` — Calendário interativo
- `/addurl`, `/listurl`, `/removeurl` — Gerenciar feeds RSS
- `/start`, `/stop`, `/welcome`, `/goodbye` — Controle geral

**Admin (secretos):**
- `/admin` — Listar comandos de admin
- `/addadmin`, `/removeadmin`, `/listadmin` — Gerenciar administradores
- `/senddailyliturgy` — Enviar liturgia para todos manualmente
- `/sendaudioliturgy` — Enviar áudio da homilia para todos
- `/activateallliturgy` — Ativar todas as assinaturas
- `/deactivated`, `/activated` — Listar usuários (in)ativos
- `/userinfoliturgy` — Detalhes das assinaturas
- `/userliturgydeactivated` — Chaves desativadas

---

## 📦 Arquitetura (v2)

**4 processos independentes:**

| Processo | Entrada | Função | Cron |
|----------|---------|--------|------|
| **MainBot** | `main.py` | Handlers de grupo + RSS | - |
| **LiturgyBot** | `liturgy.py` | Handlers de liturgia | - |
| **Worker** | `worker.py` | Distribuição de feeds + liturgia diária | Loop (10s entre ciclos) + 7am |
| **Watchdog** | `watchdog.py` | Verifica e reinicia serviços caídos, avisa via Telegram | 15min |

**Banco de dados:**
- **Redis DB 0:** MainBot + FeedJob (grupos, URLs RSS, metadados)
- **Redis DB 1:** LiturgyBot + FeedJob (URLs RSS) + LiturgyJob (assinaturas, cache, áudio)

**Padrões de design:**
- Abstract Factory (bots + databases)
- Mixins (deduplicação de handlers)
- Template Method (scrapers com fallback)
- Job-based scheduling (APScheduler)
- Intelligent error handling (ErrorHandler)

---

## 🔧 Instalação

### Requisitos
- Python 3.11+
- Redis 6+
- Git

### Setup

```bash
git clone https://github.com/wilkerpaz/OiOlabot.git
cd OiOlabot

# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com seus tokens e configurações
```

### Variáveis de Ambiente (`.env`)

Veja `.env.example` para a lista completa e atualizada. Principais:

```bash
# Telegram API
API_ID=<seu_api_id>
API_HASH=<seu_api_hash>

# Bot Tokens
DEV_TOKEN=<token_bot_principal>
DEV_TOKEN_LD=<token_bot_liturgia>

# Redis
DB=0                    # MainBot database
DB_LD=1                 # LiturgyBot database
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=         # Deixe vazio se não houver senha

# Watchdog
ADMIN_CHAT_ID=<seu_chat_id>  # Recebe alertas quando um serviço cai

# Configuração
TZ=America/Belem        # Fuso horário
LOG=INFO                # Nível de log
```

---

## 🏃 Como Executar

### Desenvolvimento (local)

```bash
# Terminal 1 — MainBot
python main.py

# Terminal 2 — LiturgyBot
python liturgy.py

# Terminal 3 — Worker (jobs de background)
python worker.py

# watchdog.py roda como verificação pontual (systemd timer em produção),
# não precisa ficar rodando em terminal separado no dia a dia
python watchdog.py
```

### Produção (NixOS + home-manager, `systemctl --user`)

Os serviços rodam como unidades systemd **de usuário** (via home-manager), não system-wide — sempre com `--user`:

```bash
# Status
systemctl --user status oiolabot-main oiolabot-liturgy oiolabot-worker oiolabot-watchdog

# Logs
journalctl --user -u oiolabot-main -f
journalctl --user -u oiolabot-liturgy -f
journalctl --user -u oiolabot-worker -f

# Reiniciar
systemctl --user restart oiolabot-main oiolabot-liturgy oiolabot-worker
```

O `oiolabot-watchdog` roda via `systemd.user.timers` a cada 15min — não precisa (nem deve) ser reiniciado manualmente como serviço contínuo.

A definição real desses serviços fica em `nix/home.nix` (config de referência; o arquivo aplicado de fato no servidor vive em `~/.config/home-manager/home.nix` e é ativado com `home-manager switch`). `nix/service.nix` é uma referência alternativa para deploy via módulo NixOS system-wide, não é o método usado atualmente. Ver `docs/DEPLOYMENT_GUIDE.md` para mais detalhes.

---

## 📁 Estrutura do Projeto

```
bots/                    # Classe dos bots
├── base.py             # BaseBot (lifecycle hooks)
├── main_bot.py         # MainBot (grupos + RSS)
└── liturgy_bot.py      # LiturgyBot (liturgia)

factories/               # Criação de bots e databases
├── base.py
├── main_factory.py
└── liturgy_factory.py

mixins/                  # Handlers (reutilizáveis)
├── welcome.py          # Boas-vindas/despedidas
├── feed.py             # Gerencimento de feeds
├── liturgy.py          # Leituras e santo do dia
├── admin_main.py       # Admin: MainBot
└── admin_liturgy.py    # Admin: LiturgyBot

util/
├── database/           # Redis abstractions
│   ├── base.py
│   ├── main_db.py
│   └── liturgy_db.py
├── scrapers/           # Web scrapers
│   ├── base.py         # BaseScraper + make_client
│   ├── liturgia.py     # Leituras diárias (português)
│   ├── homilia.py      # Homilia do dia
│   ├── audio.py        # MP3 da homilia
│   └── santo.py        # Santo do dia
├── feedhandler.py      # Parse RSS feeds
├── datehandler.py      # Timezone-aware dates
└── calendar.py         # Calendar interativo

worker/
├── error_handler.py    # Classificação de erros Telegram
├── feed_job.py         # Distribuição de feeds
├── feed_loop.py        # Loop do FeedJob (10s de pausa entre ciclos)
└── liturgy_job.py      # Envio de liturgia (7am)

legacy/                 # v1 (Pyrogram original) — arquivado, não roda em produção
├── bot.py, ltd_bot.py, feed_bot.py, feed_ltd_bot.py, login.py
└── util/               # database.py, homiliadodia.py, liturgiadiaria.py, santododia.py

tests/                  # Suíte de testes (pytest)

nix/                    # Configuração NixOS/home-manager
├── home.nix            # Espelho de referência dos serviços systemd --user reais
├── service.nix         # Referência alternativa (módulo NixOS system-wide, não usado hoje)
└── default.nix

docs/                   # Documentação
├── KURIGRAM_KB.md      # API Kurigram
├── REDIS_SCHEMA.md     # Schema Redis
├── DEPLOYMENT_GUIDE.md # Como fazer deploy
└── V2_SPEC.md          # Especificação completa

CLAUDE.md                                       # Contexto para Claude Code (raiz do projeto)
main.py, liturgy.py, worker.py, watchdog.py     # Entry points
requirements.txt                                # Dependências
```

---

## 🛠 Melhorias em v2

### Scrapers
- ✅ **HTTP 302 redirects** — `BaseScraper.make_client()` com `follow_redirects=True`
- ✅ **AudioScraper novo** — Extrai MP3 da homilia via iframe semântico
- ✅ **Datas em português** — "sexta-feira, 23 de maio de 2026"
- ✅ **Cache de arquivos** — MP3s em `/tmp/` para evitar re-downloads

### Error Handling
- ✅ **Classificação inteligente** — Distingue erros permanentes (bot blocked) de transitórios (rate limit)
- ✅ **Deactivação seletiva** — Só desativa subscriptions em erros permanentes
- ✅ **Retry automático** — Erros transitórios são logados e retentados no próximo ciclo

### Comandos
- ✅ **Paridade com v1 + melhorias**
- ✅ **Admin handlers secretos** — 12 MainBot + 11 LiturgyBot
- ✅ **Resposta inteligente** — `/help` não lista comandos secretos

---

## 📚 Documentação

- **[CLAUDE.md](CLAUDE.md)** — Contexto para Claude Code (arquitetura, padrões, deployment)
- **[docs/KURIGRAM_KB.md](docs/KURIGRAM_KB.md)** — API Kurigram (handlers, filtros, lifecycle)
- **[docs/REDIS_SCHEMA.md](docs/REDIS_SCHEMA.md)** — Schema Redis e padrões de chave
- **[docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)** — Deploy em produção (NixOS + systemd)
- **[docs/V2_SPEC.md](docs/V2_SPEC.md)** — Especificação completa da refatoração v2

---

## 🔐 Segurança

- ✅ Tokens salvos em `.env` (nunca commitados)
- ✅ Sessões Pyrogram em `.session` (ignoradas por `.gitignore`)
- ✅ `.vscode/` e `.claude/` ignorados (configurações locais)
- ✅ Nenhum token ou credencial hardcoded no código

---

## 📝 Licença

[Adicione informações de licença se aplicável]

## 👤 Autor

Desenvolvido por **Wilker Paz**

---

## 🤝 Contribuindo

Para contribuir:
1. Trabalhe na branch `master` (v2 é a versão de produção)
2. Siga os padrões em `CLAUDE.md`
3. Escreva testes para novo código
4. Faça commits descritivos
5. Abra um Pull Request

---

## 📞 Suporte

Para dúvidas, bugs ou sugestões: abra uma issue no GitHub ou contate o desenvolvedor.

---

**Última atualização:** Setembro 2026 | **Versão:** 2.0 (PRODUÇÃO-READY)
