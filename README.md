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
- `/chatinfo` — Informações do grupo

**Admin (secretos):**
- `/owner` — Designar proprietário do grupo
- `/admin` — Listar comandos de admin
- `/backup` — Exportar configuração do grupo
- `/deactivatedurl`, `/activateallurl`, `/allurl` — Gerenciar feeds globalmente

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
- `/senddailyliturgy` — Enviar liturgia para todos manualmente
- `/sendaudioliturgy` — Enviar áudio da homilia para todos
- `/activateallliturgy` — Ativar todas as assinaturas
- `/deactivated`, `/activated` — Listar usuários (in)ativos
- `/userinfoliturgy` — Detalhes das assinaturas
- `/userliturgydeactivated` — Chaves desativadas

---

## 📦 Arquitetura (v2)

**3 processos independentes:**

| Processo | Entrada | Função | Cron |
|----------|---------|--------|------|
| **MainBot** | `main.py` | Handlers de grupo + RSS | - |
| **LiturgyBot** | `liturgy.py` | Handlers de liturgia | - |
| **Worker** | `worker.py` | Distribuição de feeds + liturgia diária | 5min + 7am |

**Banco de dados:**
- **Redis DB 0:** MainBot + FeedJob (grupos, URLs, metadados)
- **Redis DB 1:** LiturgyBot + LiturgyJob (assinaturas, cache, áudio)

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
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com seus tokens e configurações
```

### Variáveis de Ambiente (`.env`)

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
```

### Produção (NixOS + systemd)

```bash
# Status
systemctl status oiolabot-main oiolabot-liturgy oiolabot-worker

# Logs
journalctl -u oiolabot-main -f
journalctl -u oiolabot-liturgy -f
journalctl -u oiolabot-worker -f

# Reiniciar
systemctl restart oiolabot-{main,liturgy,worker}
```

Ver `docs/DEPLOYMENT_GUIDE.md` para deploy em produção.

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
├── feed_job.py         # Distribuição de feeds (5min)
└── liturgy_job.py      # Envio de liturgia (7am)

docs/                   # Documentação
├── CLAUDE.md           # Contexto para Claude Code
├── KURIGRAM_KB.md      # API Kurigram
├── REDIS_SCHEMA.md     # Schema Redis
├── DEPLOYMENT_GUIDE.md # Como fazer deploy
└── V2_SPEC.md          # Especificação completa

main.py, liturgy.py, worker.py  # Entry points
requirements.txt                 # Dependências
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
- ✅ **21 comandos implementados** — Paridade com v1 + melhorias
- ✅ **Admin handlers secretos** — 6 MainBot + 8 LiturgyBot
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

**Última atualização:** Maio 2026 | **Versão:** 2.0 (PRODUÇÃO-READY)
