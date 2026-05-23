# OiOlabot — Estado Atual do Projeto

> Documento de mapeamento criado em 2026-05-23.
> Objetivo: registrar o estado real antes de qualquer atualização, preservando 100% da intenção original.

---

## 1. Visão Geral

**OiOlabot** é um conjunto de bots para Telegram com duas responsabilidades centrais:

1. **Gestão de grupos** — boas-vindas e despedidas automáticas a novos membros, com mensagens configuráveis por grupo.
2. **Distribuição de conteúdo** — assinatura de feeds RSS genéricos e entrega diária de liturgia, homilia e santo do dia (fontes: Canção Nova).

O projeto é totalmente em português, voltado ao Brasil (fuso America/Belem), com forte viés de conteúdo católico.

---

## 2. Estrutura de Arquivos

```
OiOlabot/
├── bot.py                       # Bot de boas-vindas + gestão de RSS (Pyrogram)
├── login.py                     # Helper de autenticação Pyrogram
├── feed_bot.py                  # Parser/distribuidor de RSS (pyTelegramBotAPI)
├── feed_ltd_bot.py              # Parser/distribuidor de RSS litúrgico (pyTelegramBotAPI)
├── ltd_bot.py                   # Bot de liturgia diária (Pyrogram + APScheduler)
├── requirements.txt             # Dependências Python
├── README.md                    # Descrição mínima
├── config.ini_example           # Exemplo de configuração
├── .env_old                     # Referência de variáveis de ambiente antigas
└── util/
    ├── __init__.py
    ├── database.py              # Camada Redis — bot.py
    ├── database_daily_liturgy.py# Camada Redis — ltd_bot.py
    ├── datehandler.py           # Utilitários de data/fuso
    ├── feedhandler.py           # Parsing de feeds RSS
    ├── calendar.py              # Widget de calendário inline (Telegram)
    ├── liturgiadiaria.py        # Scraper de leituras do dia
    ├── homiliadodia.py          # Scraper de homilia + download de áudio
    └── santododia.py            # Scraper de santo do dia
```

---

## 3. Bots e Suas Responsabilidades

### 3.1 `bot.py` — Bot Principal (Pyrogram, async)

**Propósito:** Acolher novos membros em grupos e gerenciar assinaturas de RSS.

| Comando | Função |
|---------|--------|
| `/start` | Ativa o bot e exibe ajuda |
| `/help` | Menu de ajuda |
| `/welcome [msg]` | Define mensagem de boas-vindas |
| `/goodbye [msg]` | Define mensagem de despedida |
| `/disable_welcome` / `/disable_goodbye` | Desativa as mensagens |
| `/lock` / `/unlock` | Controla quem pode alterar configurações |
| `/quiet` / `/unquiet` | Silencia/ativa mensagens de erro |
| `/addurl [url]` | Adiciona assinatura de RSS |
| `/listurl` | Lista assinaturas ativas |
| `/removeurl [url]` | Remove assinatura |
| `/me` | Info do usuário/chat |
| Admin: `/backup`, `/getkey`, `/removekey`, `/admin`, `/owner` etc. | Administração |

**Persistência:** Redis (DB configurável via variável `DB`).

**Chaves Redis:**
- `group:{chat_id}` → configurações do grupo (adm, lock, welcome, goodbye, quiet)
- `user_url:{user_id}:chat_id:{chat_id}:^{url}^` → assinatura de URL
- `url:^{url}^` → metadados do feed (last_update, last_url)

---

### 3.2 `ltd_bot.py` — Bot de Liturgia Diária (Pyrogram + APScheduler, async)

**Propósito:** Enviar leituras diárias, homilia e santo do dia; job automático às 7h.

| Comando | Função |
|---------|--------|
| `/start` | Ativa entrega diária |
| `/stop` | Desativa entrega |
| `/hoje`, `/ontem`, `/amanha` | Liturgia do dia |
| `/dominical` | Liturgia dominical |
| `/santododia` | Santo do dia |
| `/calendario` | Seletor de data inline |
| `/help` | Ajuda |
| Admin: `/senddailyliturgy`, `/sendaudioliturgy`, `/activated`, `/deactivated` etc. | Administração |

**Persistência:** Redis (DB configurável via variável `DB_LD`).

**Chaves Redis:**
- `daily_liturgy:user_id:{id}:chat_id:{chat_id}` → inscrição do usuário
- `audio_liturgy` → hash de file_ids de áudio (cache no Telegram)
- `last_send` → timestamp do último envio por usuário

---

### 3.3 `feed_bot.py` — Distribuidor de RSS (pyTelegramBotAPI, sync)

**Propósito:** Executado por cron externo; busca feeds RSS ativos e entrega novos posts.

**Fluxo:**
1. Carrega todas as URLs ativas do Redis.
2. Para cada URL: compara entradas novas com `last_url` / `date_last_url`.
3. Envia mensagens aos chats assinantes.
4. Falhas de entrega desativam o feed para aquele chat.
5. Atualiza metadados (`last_url`, `last_update`) no Redis.

---

### 3.4 `feed_ltd_bot.py` — Distribuidor de RSS Litúrgico (pyTelegramBotAPI, sync)

Variante do `feed_bot.py` usando `DatabaseHandler` de `database_daily_liturgy.py`, dedicada ao feed litúrgico.

---

### 3.5 `login.py` — Helper de Autenticação

Inicializa um `Client` Pyrogram para o fluxo de autenticação manual (número de telefone).

---

## 4. Módulos Utilitários

### `util/database.py`
Abstração Redis para `bot.py`. Métodos principais: SCAN de padrões, verificações de existência, CRUD de grupos, URLs e assinaturas.

### `util/database_daily_liturgy.py`
Abstração Redis para `ltd_bot.py`. Adiciona gerenciamento de inscrições de liturgia, controle de `last_send` e ativação em massa.

### `util/datehandler.py`
Centraliza datas com fuso `America/Belem`. Métodos: `get_datetime_now()`, `parse_datetime()`, `date()`, `time()`, `combine()`.

### `util/feedhandler.py`
Parsing de RSS com `feedparser`. Tratamento especial para o feed Evangelhoddia (extrai `summary` como `daily_liturgy`). Valida acessibilidade da URL antes de assinar.

### `util/liturgiadiaria.py`
Scraper da leitura diária em liturgia.cancaonova.com. Faz POST AJAX para obter o link do dia, depois raspa o conteúdo da página de leituras (regex `liturgia-\d`).

### `util/homiliadodia.py`
Scraper de homiliadodia em homilia.cancaonova.com. Baixa texto e arquivo MP3 via `wget`, limpa arquivos antigos de `/tmp/`.

### `util/santododia.py`
Scraper do santo do dia em santo.cancaonova.com. Retorna nome e descrição do santo.

### `util/calendar.py`
Widget de calendário inline para Telegram. Suporta navegação entre meses e seleção de data. Nomes dos dias em português.

---

## 5. Dependências Atuais

| Pacote | Versão | Uso |
|--------|--------|-----|
| Pyrogram | 2.0.100 | Bot async principal |
| TgCrypto | 1.2.2 | Criptografia Pyrogram |
| pyTelegramBotAPI | 3.7.4 | Bots sincronos (feed) |
| APScheduler | 3.7.0 | Job scheduler (7h diário) |
| redis | 3.5.3 | Persistência |
| feedparser | 6.0.8 | Parsing de RSS |
| beautifulsoup4 | 4.10.0 | Scraping HTML |
| lxml | 4.6.3 | Parser XML |
| requests | 2.26.0 | HTTP |
| python-decouple | 3.4 | Variáveis de ambiente |
| pytz | 2021.1 | Fusos horários |
| Babel | 2.9.1 | Internacionalização |
| python-dateutil | 2.8.2 | Utilitários de data |
| streamlink | 2.0.0 | Download de streams |
| wget | 3.2 | Download de áudio MP3 |

---

## 6. Variáveis de Ambiente (`.env`)

Todas gerenciadas via `python-decouple`. Mapeamento exato por arquivo:

| Variável | Usado em | Descrição |
|----------|----------|-----------|
| `API_ID` | `bot.py`, `ltd_bot.py`, `login.py` | ID da aplicação Telegram |
| `API_HASH` | `bot.py`, `ltd_bot.py`, `login.py` | Hash da aplicação Telegram |
| `DEV_TOKEN` | `bot.py`, `feed_bot.py` | Token do bot principal |
| `DEV_TOKEN_LD` | `ltd_bot.py`, `feed_ltd_bot.py` | Token do bot de liturgia |
| `BOT_NAME` | `bot.py`, `feed_bot.py` | Nome de sessão do bot principal |
| `BOT_NAME_LD` | `bot.py`, `ltd_bot.py`, `feed_ltd_bot.py` | Nome de sessão do bot de liturgia |
| `REDIS` | `util/database.py`, `util/database_daily_liturgy.py` | Senha do Redis (vazio se sem senha) |
| `DB` | `bot.py`, `feed_bot.py` | Número do DB Redis — bot principal |
| `DB_LD` | `ltd_bot.py`, `feed_ltd_bot.py` | Número do DB Redis — liturgia |
| `TZ` | `util/datehandler.py` | Fuso horário (ex: `America/Belem`) |
| `PATH_REDIS` | `bot.py`, `feed_bot.py` | Caminho do `dump.rdb` para backup |
| `THREADS` | `feed_bot.py`, `feed_ltd_bot.py` | Threads para parsing paralelo de feeds |
| `CHANNEL_LD` | `ltd_bot.py` | ID do canal para distribuição de áudio |
| `LOG` | `bot.py`, `ltd_bot.py`, `feed_bot.py`, `feed_ltd_bot.py` | Nível de log (`INFO`, `DEBUG` etc.) |

### Exemplo de `.env` mínimo para desenvolvimento

```ini
API_ID=
API_HASH=
DEV_TOKEN=
DEV_TOKEN_LD=
BOT_NAME=OiOlabot
BOT_NAME_LD=LiturgiaDiaria_bot
REDIS=
DB=0
DB_LD=1
TZ=America/Belem
PATH_REDIS=/var/lib/redis/dump.rdb
THREADS=2
CHANNEL_LD=
LOG=INFO
```

---

## 7. Serviços Externos

| Serviço | Uso | Módulo |
|---------|-----|--------|
| Telegram Bot API | Toda a comunicação | Todos os bots |
| liturgia.cancaonova.com | Leituras diárias | `liturgiadiaria.py` |
| homilia.cancaonova.com | Homilia + áudio MP3 | `homiliadodia.py` |
| santo.cancaonova.com | Santo do dia | `santododia.py` |
| feeds RSS genéricos | Assinaturas de usuários | `feedhandler.py` |
| Redis (localhost:6379) | Toda a persistência | `database.py`, `database_daily_liturgy.py` |

---

## 8. Arquitetura e Fluxos de Dados

```
Usuário → Telegram → Pyrogram (bot.py / ltd_bot.py)
                          ↓
                       Redis ←→ Metadados
                          ↓
               feed_bot.py (cron externo)
                          ↓
            FeedHandler → RSS Feeds externos
                          ↓
               Telegram (entrega aos chats)

APScheduler (ltd_bot.py) → 7h diário
    ↓
BuscarLiturgia → liturgia.cancaonova.com
HomiliadoDia   → homilia.cancaonova.com
SantodoDia     → santo.cancaonova.com
    ↓
Telegram (entrega aos inscritos)
```

---

## 9. Pontos de Atenção (Estado Atual)

### 9.1 Mistura de Frameworks
O projeto usa **Pyrogram** (async) e **pyTelegramBotAPI** (sync) em paralelo. Isso indica uma migração parcial — os bots interativos já estão em Pyrogram, mas os distribuidores de feed ainda usam a API legada.

### 9.2 Dependências Desatualizadas
Praticamente todas as dependências estão em versões antigas (2021–2022). Algumas já tiveram mudanças de API relevantes (ex.: remoção de `parse_mode` já registrada nos commits).

### 9.3 Scraping Frágil
Os três scrapers (`liturgiadiaria.py`, `homiliadodia.py`, `santododia.py`) dependem da estrutura HTML específica do site Canção Nova. Qualquer redesign do site quebra a funcionalidade.

### 9.4 Sem Containerização
Não há `Dockerfile` nem `docker-compose.yml`. A implantação é manual e depende de Redis local.

### 9.5 Scheduling Híbrido
- `ltd_bot.py` usa APScheduler interno.
- `feed_bot.py` depende de cron externo (não documentado).

### 9.6 Sem Testes Automatizados
Nenhum arquivo de teste identificado no projeto.

### 9.7 Redis como Único Storage
Não há fallback se o Redis ficar indisponível. Sem migrações ou schema versionado.

### 9.8 Download de Áudio via `wget`
`homiliadodia.py` usa `wget` para baixar MP3 e salva em `/tmp/`. Processo frágil e sem controle de erros robusto.

---

## 10. Intenção Central (a preservar na evolução)

1. **Boas-vindas personalizáveis** por grupo, com controle de permissões por admins.
2. **Assinatura de RSS** — qualquer feed público, entrega automática para chats do Telegram.
3. **Liturgia diária automatizada** — leitura, homilia e santo do dia entregues às 7h sem intervenção do usuário.
4. **Seleção de data por calendário** — usuário pode consultar qualquer dia, não só o atual.
5. **Conteúdo 100% em português**, focado na comunidade brasileira.
6. **Baixa fricção para o usuário final** — `/start` é suficiente para ativar tudo.

---

## 11. Histórico Recente (git log)

| Commit | Descrição |
|--------|-----------|
| ea4d770 | Ajuste para NixOS |
| 8b18adb | Remoção de `parse_mode` (mudança de API) |
| f9ef972 | Atualização da versão do Pyrogram |
| 0151caf | Atualização da versão do Pyrogram |
| 8aeff4b | Atualização da versão do Pyrogram |

---

*Este documento deve ser atualizado a cada ciclo de evolução do projeto.*
