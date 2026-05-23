# Redis — Schema de Chaves

> Documento gerado em 2026-05-23.
> Derivado de `util/database.py` e `util/database_daily_liturgy.py`.

---

## Bancos (databases)

| Variável `.env` | Número | Responsável |
|-----------------|--------|-------------|
| `DB` | 0 (padrão) | Bot principal — grupos, RSS, assinaturas |
| `DB_LD` | 1 (padrão) | Bot de liturgia — inscrições, last_send, áudio |

Os dois bancos **não compartilham chaves**. Cada `DatabaseHandler` é instanciado com seu `db` específico.

---

## DB 0 — Bot Principal

### `group:{chat_id}` — Hash
Configurações de um grupo onde o bot foi adicionado.

| Campo | Tipo | Valores | Descrição |
|-------|------|---------|-----------|
| `chat_id` | str | inteiro negativo | ID do grupo Telegram |
| `chat_adm` | str | inteiro | user_id de quem adicionou o bot |
| `chat_name` | str | `@username` ou nome | Username do grupo |
| `chat_title` | str | texto | Título do grupo |
| `chat_lock` | str | `'True'` / `'False'` | Se `True`, só o adm pode mudar config |
| `chat_quiet` | str | `'True'` / `'False'` | Se `True`, silencia mensagens de erro |
| `chat_welcome` | str | `'False'` ou texto | Mensagem de boas-vindas personalizada |
| `chat_goodbye` | str | `'False'` ou texto | Mensagem de despedida personalizada |

**Exemplo de chave:** `group:-1001234567890`

---

### `url:^{url}^` — Hash
Metadados de um feed RSS registrado.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `last_update` | str | datetime com tz do último item entregue |
| `last_url` | str | URL do último item entregue |

**Exemplo de chave:** `url:^https://feeds.exemplo.com/rss^`

> **Nota:** A URL é delimitada por `^` para facilitar o SCAN por padrão sem colidir com separadores de path.

---

### `user_url:{user_id}:chat_id:{chat_id}:^{url}^` — Hash
Assinatura de um feed RSS para um chat específico.

| Campo | Tipo | Valores | Descrição |
|-------|------|---------|-----------|
| `chat_id` | str | inteiro | ID do chat assinante |
| `chat_name` | str | texto | Nome/username do chat |
| `user_id` | str | inteiro | user_id de quem assinou |
| `disable` | str | `'True'` / `'False'` | Se `True`, feed desativado para este chat |

**Exemplo de chave:** `user_url:987654321:chat_id:-1001234567890:^https://feeds.exemplo.com/rss^`

---

### `admins` — List
Lista de `user_id` (strings) com acesso a comandos de administração.

**Acesso:** `LRANGE admins 0 -1`

---

### `backup` — Hash
Controle de quando o último backup do Redis foi feito.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `last_backup` | str | datetime com tz do último backup |

---

## DB 1 — Bot de Liturgia

### `daily_liturgy:user_id:{user_id}:chat_id:{chat_id}` — Hash
Inscrição de um usuário/chat para receber liturgia diária.

| Campo | Tipo | Valores | Descrição |
|-------|------|---------|-----------|
| `chat_id` | str | inteiro | ID do chat inscrito |
| `chat_name` | str | texto | Nome/username do chat |
| `user_id` | str | inteiro | user_id de quem ativou |
| `disable` | str | `'True'` / `'False'` | Se `True`, inscrição desativada |
| `last_send` | str | datetime | Última vez que a liturgia foi enviada |

**Exemplo de chave:** `daily_liturgy:user_id:987654321:chat_id:-1001234567890`

> **Bug conhecido (v1):** `set_last_send_daily_liturgy` grava `datetime.now()` sem timezone.
> Correção prevista na Fase 2 da auditoria: usar `DateHandler.get_datetime_now()`.

---

### `audio_liturgy` — Hash
Cache de `file_id` de arquivos de áudio (homilia MP3) já enviados ao Telegram.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `{data}` | str | `file_id` retornado pelo Telegram após primeiro upload |

Reutilizar o `file_id` evita re-upload do mesmo arquivo MP3.

---

### `user_url:{user_id}:chat_id:{chat_id}:^{url}^` — Hash
Mesmo schema do DB 0. O DB 1 também suporta assinaturas RSS (via `feed_ltd_bot.py`).

---

### `admins` — List
Mesmo schema do DB 0. Lista independente — admins do bot de liturgia.

---

### `backup` — Hash
Mesmo schema do DB 0.

---

## Padrões de SCAN usados no código

| Padrão | O que retorna |
|--------|--------------|
| `user_url*` | Todas as assinaturas RSS |
| `user_url*{chat_id}*` | Assinaturas de um chat específico |
| `user_url*{url}*` | Assinaturas de uma URL específica |
| `daily_liturgy*` | Todas as inscrições de liturgia |
| `daily_liturgy*chat_id:{chat_id}*` | Inscrição de um chat específico |
| `group:*` | Todos os grupos registrados |

> O método `_find(pattern)` usa `SCAN` iterativo (cursor = 0 até retornar 0), não `KEYS` — seguro em produção.

---

## Notas para o v2

1. O schema de chaves **não muda** no v2 — compatibilidade total, sem migração.
2. `BaseDatabase._find()` encapsula o SCAN iterativo — preservar este comportamento.
3. O delimitador `^` nas URLs é uma convenção do projeto; manter no v2.
4. `decode_responses=True` em todos os clientes Redis — todas as leituras retornam `str`.
