# Redis — Schema de Chaves

> Documento gerado em 2026-05-23, revisado em 2026-09-13 contra a implementação real do v2.
> `util/database.py` e `util/database_daily_liturgy.py` eram do v1 (hoje arquivados em `legacy/util/`).
> O schema abaixo reflete a implementação atual em `util/database/base.py`, `util/database/main_db.py`
> (MainDatabase, DB 0) e `util/database/liturgy_db.py` (LiturgyDatabase, DB 1), com os pontos onde o
> v2 divergiu do v1 sinalizados explicitamente.

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
| `chat_adm` | str | inteiro | user_id de quem adicionou o bot |
| `chat_name` | str | `@username`, título ou "Unknown" | Nome do grupo (ver `mixins/welcome.py: start_bot`) |
| `chat_lock` | str | `'True'` / `'False'` | Se `True`, só o adm pode mudar config |
| `chat_quiet` | str | `'True'` / `'False'` | Se `True`, silencia mensagens de erro |
| `chat_welcome` | str | `'False'` ou texto | Mensagem de boas-vindas personalizada |
| `chat_goodbye` | str | `'False'` ou texto | Mensagem de despedida personalizada |

**Exemplo de chave:** `group:-1001234567890`

> **Divergência do v1:** os campos `chat_id` e `chat_title`, que existiam no hash em `legacy/util/database.py`
> (`update_group`), **não são gravados pelo v2** (`mixins/welcome.py: start_bot` não os inclui). O `chat_id`
> já está implícito na chave; não há campo `chat_title` equivalente no v2 hoje.

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

> **Bug do v1, corrigido no v2:** a versão v1 (`set_last_send_daily_liturgy` em `legacy/util/database_daily_liturgy.py`)
> gravava `datetime.now()` sem timezone. O v2 (`LiturgyDatabase.add_daily_liturgy_subscription` /
> `set_last_send` em `util/database/liturgy_db.py`) já usa `DateHandler.get_datetime_now()`
> (com timezone) — não é mais um problema em produção.

---

### `audio_liturgy` — Hash
Cache de `file_id` de arquivos de áudio (homilia MP3) já enviados ao Telegram.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `{data}` | str | `file_id` retornado pelo Telegram após primeiro upload |

Reutilizar o `file_id` evita re-upload do mesmo arquivo MP3.

---

### `user_url:{user_id}:chat_id:{chat_id}:^{url}^` — Hash (não funcional no v2 atual)
Mesmo schema do DB 0. No v1, o DB 1 também suportava assinaturas RSS via `feed_ltd_bot.py`
(hoje em `legacy/`). No v2, `mixins/feed.py` (FeedMixin) é reaproveitado pelo LiturgyBot e chama
`self.db.add_url_subscription()`, `get_chat_urls()`, `remove_url_for_chat()` — mas
`util/database/liturgy_db.py` (LiturgyDatabase) **não implementa esses métodos**. Ou seja,
`/addurl`, `/listurl` e `/removeurl` no bot de liturgia hoje resultam em `AttributeError`
em vez de gravar esta chave. Confirmar com o time se isso é uma lacuna a corrigir ou uma
funcionalidade que deveria ser removida do LiturgyBot.

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

> O método `_find(pattern)` usa `SCAN` iterativo (cursor = 0 até retornar 0), não `KEYS` — seguro em produção.
> Grupos (`group:{chat_id}`) nunca são varridos em massa no código atual — sempre acessados por
> chave exata (`get_group_config`/`set_group_config`/`remove_group_config`). Não existe hoje um
> comando que liste todos os grupos registrados.

---

## Notas do v2 (atualizado 2026-09-13)

1. O schema de chaves **não é 100% compatível** com o v1: o hash `group:{chat_id}` perdeu os
   campos `chat_id` e `chat_title` (ver nota acima), e as assinaturas RSS no DB 1 não funcionam
   hoje (ver nota na seção `user_url` do DB 1). Fora isso, os padrões de chave permaneceram os mesmos.
2. `BaseDatabase._find()` encapsula o SCAN iterativo — preservado no v2 (`util/database/base.py`).
3. O delimitador `^` nas URLs é uma convenção do projeto; mantido no v2.
4. `decode_responses=True` em todos os clientes Redis — todas as leituras retornam `str`. Confirmado
   em `util/database/base.py`.
5. Não existe mais uma branch `v2` separada — este schema é o que roda em `master`, usado pelos
   processos `main.py`, `liturgy.py` e `worker.py` (ver `docs/DEPLOYMENT_GUIDE.md`).
