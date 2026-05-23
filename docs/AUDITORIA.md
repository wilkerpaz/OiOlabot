# Auditoria Completa do Projeto OiOlabot

> Data: 2026-05-23
> Escopo: todos os arquivos `.py` do projeto
> Contexto: auditoria pré-evolução — identificar bugs, inconsistências e riscos antes de qualquer refatoração

---

## Visão Geral da Arquitetura

O projeto é composto por **dois pares de processos**:

```
┌─────────────────────────────────────────────────────┐
│  Par 1 — Bot Principal (RSS + Boas-vindas)          │
│  ├── bot.py          → processo interativo (Pyrogram async)   │
│  └── feed_bot.py     → processo background (pyTelegramBotAPI sync, cron) │
│                                                      │
│  Par 2 — Bot de Liturgia Diária                     │
│  ├── ltd_bot.py      → processo interativo (Pyrogram async + APScheduler) │
│  └── feed_ltd_bot.py → processo background (pyTelegramBotAPI sync, cron)  │
└─────────────────────────────────────────────────────┘
```

Ambos os pares compartilham:
- Redis como única camada de persistência
- Módulos `util/` para acesso ao banco, datas, feeds e scrapers

---

## 1. Bugs Críticos (quebram funcionalidade)

### 1.1 Método inexistente chamado em `feed_bot.py`

**Arquivo:** `feed_bot.py:89`
**Código:**
```python
names_url = db.get_names_for_user_activated(url)
```
**Problema:** O método `get_names_for_user_activated()` **não existe** em `util/database.py`. O método correto é `get_name_urls_activated(url)`. Isso causa `AttributeError` toda vez que um feed tem novos posts para entregar.

**Correção:** Renomear a chamada para `get_name_urls_activated(url)`.

---

### 1.2 Método inexistente chamado em `bot.py`

**Arquivo:** `bot.py:561`
**Código:**
```python
urls = db.get_urls_deactivated()
```
**Problema:** O método `get_urls_deactivated()` **não existe** em `util/database.py`. Existe `get_name_urls_deactivated()` que retorna nomes de chaves, não URLs. O comando `/deactivatedurl` falha para administradores.

**Correção:** Usar `get_name_urls_deactivated()` ou criar método equivalente.

---

### 1.3 Comparação de username com `@` errada

**Arquivos:** `bot.py:127`, `ltd_bot.py:151`
**Código:**
```python
me = client.get_me()
if me.username == '@' + BOT_NAME_LD:   # bot.py
if me.username == '@' + BOT_NAME:      # ltd_bot.py
```
**Problema:** No Pyrogram, `me.username` retorna o username **sem** o prefixo `@`. A comparação sempre será `False`, impedindo que os bots identifiquem a si mesmos corretamente. Consequência: o bot de liturgia nunca se registra automaticamente quando adicionado a um grupo.

**Correção:**
```python
if me.username == BOT_NAME_LD:
if me.username == BOT_NAME:
```

---

### 1.4 Chamada async sem await em `ltd_bot.py`

**Arquivo:** `ltd_bot.py:152`
**Código:**
```python
def _introduce(client, update):
    me = client.get_me()
    if me.username == '@' + BOT_NAME:
        start(client, update)   # start é async — sem await
```
**Problema:** `start()` é uma coroutine (`async def`). Chamá-la sem `await` não executa a função — retorna um objeto coroutine que é descartado silenciosamente. O usuário nunca recebe a liturgia ao adicionar o bot.

**Correção:** `_introduce` deve ser `async def` e chamar `await start(client, update)`.

---

### 1.5 `send_document` com parâmetro renomeado no pyTelegramBotAPI 4.x

**Arquivo:** `feed_bot.py:36`
**Código:**
```python
bot.send_document(chat_id=chat_id, data=doc)
```
**Problema:** No pyTelegramBotAPI 4.x o parâmetro `data` foi renomeado para `document`. O backup nunca é entregue aos admins — silenciosamente falha.

**Correção:**
```python
bot.send_document(chat_id=chat_id, document=doc)
```

---

### 1.6 `update.delete()` sem await em `ltd_bot.py`

**Arquivo:** `ltd_bot.py:214`
**Código:**
```python
def stop(_, update):
    ...
    update.delete()
```
**Problema:** `stop` é uma função síncrona mas `update.delete()` no Pyrogram é uma coroutine. A mensagem de `/stop` nunca é deletada.

**Correção:** `stop` deve ser `async def` e usar `await update.delete()`.

---

### 1.7 Função `get_user_info` definida duas vezes em `ltd_bot.py`

**Arquivo:** `ltd_bot.py:485` e `ltd_bot.py:941`
**Problema:** Duas funções com o mesmo nome `get_user_info`. O handler do `/me` (linha 485) é sobrescrito pelo handler do `/userinfoliturgy` (linha 941). O comando `/me` nunca funciona no `ltd_bot.py`.

**Correção:** Renomear uma das funções (`get_user_info_liturgy` para a segunda).

---

### 1.8 `owner()` pode lançar `AttributeError` em `ltd_bot.py`

**Arquivo:** `ltd_bot.py:808`
**Código:**
```python
chat_name = '@' + update.chat.username
```
**Problema:** Não há verificação de `None` para `update.chat.username`. Se o grupo não tiver username, lança `TypeError`. Em `bot.py` o mesmo trecho tem tratamento correto com fallback.

**Correção:**
```python
chat_name = '@' + update.chat.username if update.chat.username else update.from_user.first_name
```

---

## 2. Bugs Médios (degradam funcionalidade)

### 2.1 Handlers síncronos em `ltd_bot.py` (Pyrogram async)

**Arquivo:** `ltd_bot.py`
**Problema:** Pyrogram moderno exige que todos os handlers sejam `async def`. Os seguintes handlers são `def` e podem causar comportamento inesperado ou warnings:

| Função | Linha |
|--------|-------|
| `stop` | 207 |
| `inline_handler` | 280 |
| `new_chat_members` | 303 |
| `left_chat_member` | 313 |
| `set_welcome` | 349 |
| `set_goodbye` | 375 |
| `disable_welcome` | 398 |
| `disable_goodbye` | 404 |
| `lock` | 410 |
| `unlock` | 416 |
| `quiet` | 422 |
| `unquiet` | 428 |
| `get_user_info` | 485 |
| `add_url` | 528 |
| `list_url` | 575 |
| `remove_url` | 598 |
| `list_url_deactivated` | 687 |
| `activate_all_urls` | 707 |
| `activate_all_liturgy` | 723 |
| `all_url` | 739 |
| `get_key` | 763 |
| `remove_key` | 782 |
| `owner` | 800 |
| `users_deactivated` | 920 |
| `users_activated` | 930 |
| `get_user_info` (2ª) | 941 |
| `get_key_liturgy_deactivated` | 970 |
| `admin` | 1003 |

**Correção:** Converter todos para `async def`.

---

### 2.2 Inconsistência de timezone em `ltd_bot.py`

**Arquivo:** `ltd_bot.py:243,247,252,255`
**Código:**
```python
date = datetime.now() + timedelta(days=-1)  # sem timezone
```
**Problema:** Dentro de `check_button`, os comandos `/ontem`, `/hoje`, `/amanha`, `/dominical` usam `datetime.now()` sem timezone. O restante do sistema usa `DateHandler.get_datetime_now()` que retorna datetime com fuso `America/Belem`. Isso pode buscar a liturgia do dia errado em horários de borda.

**Correção:** Substituir por `DateHandler.get_datetime_now()` em todos os casos.

---

### 2.3 `set_last_send_daily_liturgy` usa datetime sem timezone

**Arquivo:** `util/database_daily_liturgy.py:185`
**Código:**
```python
mapping = {'last_send': str(DateHandler.datetime.now())}
```
**Problema:** `DateHandler.datetime.now()` retorna datetime naive (sem timezone), diferente do padrão do projeto que usa `DateHandler.get_datetime_now()` com timezone `America/Belem`.

**Correção:**
```python
mapping = {'last_send': str(DateHandler.get_datetime_now())}
```

---

### 2.4 Variável `THREADS` do `.env` ignorada em `feed_bot.py` e `feed_ltd_bot.py`

**Arquivos:** `feed_bot.py:17,43`, `feed_ltd_bot.py:17,34`
**Código:**
```python
THREADS = config('THREADS')   # lida do .env
...
threads = 2                    # hardcoded — THREADS nunca usada
pool = ThreadPool(threads)
```
**Problema:** A configuração `THREADS` é lida mas nunca aplicada. O pool sempre usa 2 threads.

**Correção:** `pool = ThreadPool(int(THREADS))`

---

### 2.5 Lógica de welcome inalcançável em `bot.py` e `ltd_bot.py`

**Arquivo:** `bot.py:102-116`, `ltd_bot.py:126-141`
**Código:**
```python
text_group = db.get_value_name_key(...)
if not text_group:
    return              # sai se falsy

welcome_text = f'Hello...'
if text_group:          # sempre True aqui
    text = welcome_text + '\n' + text_group
else:                   # NUNCA EXECUTADO
    text = welcome_text
```
**Problema:** O `else` na linha 136 (ltd_bot.py) / 112 (bot.py) nunca é executado — se `text_group` é falsy, a função já retornou antes. O texto padrão de boas-vindas sem mensagem personalizada nunca é enviado.

**Correção:** Remover o `if not text_group: return` ou reestruturar a lógica.

---

### 2.6 `_dummy` handler registrado dentro do `if __name__` em `ltd_bot.py`

**Arquivo:** `ltd_bot.py:1020-1022`
**Código:**
```python
if __name__ == "__main__":
    @bot.on_message(filters.command("noop_internal_start") & filters.private)
    async def _dummy(client, message):
        pass
```
**Problema:** Handler registrado como workaround para o APScheduler. É código residual da correção aplicada — pode ser removido pois não cumpre função real.

---

### 2.7 `bot.loop.run_until_complete()` depreciado

**Arquivo:** `ltd_bot.py:1031`
**Código:**
```python
bot.loop.run_until_complete(start_scheduler())
```
**Problema:** `Client.loop` foi removido ou depreciado em versões mais recentes do Pyrogram. A forma correta é iniciar o scheduler dentro de um handler `on_start` ou usar `asyncio.get_event_loop()`.

---

## 3. Problemas de Qualidade

### 3.1 Código duplicado entre `bot.py` e `ltd_bot.py`

Os dois bots compartilham funções quase idênticas sem reutilização:

| Função | bot.py | ltd_bot.py |
|--------|--------|------------|
| `_check()` | linha 68 | linha 92 |
| `_welcome()` | linha 94 | linha 118 |
| `_introduce()` | linha 121 | linha 145 |
| `goodbye()` | linha 198 | linha 325 |
| `command_control()` | linha 307 | linha 434 |
| `get_chat_by_username()` | linha 332 | linha 459 |
| `feed_url()` | linha 377 | linha 504 |
| `add_url()` | linha 401 | linha 528 |
| `list_url()` | linha 448 | linha 575 |
| `remove_url()` | linha 471 | linha 598 |
| `error()` / `errors()` | linha 656 | linha 818 |

**Impacto:** Qualquer correção precisa ser aplicada em dois lugares. Risco alto de divergência entre implementações.

---

### 3.2 Código duplicado entre `feed_bot.py` e `feed_ltd_bot.py`

`feed_ltd_bot.py` é quase uma cópia de `feed_bot.py`. As diferenças são:
- Import de `DatabaseHandler` diferente
- Sem função `backup()`
- Função `errors()` com tratamento ligeiramente diferente

**Impacto:** Mesma manutenção dupla.

---

### 3.3 Textos de ajuda em inglês no bot de liturgia

**Arquivo:** `ltd_bot.py:55-89`
**Problema:** `help_text` e `help_text_feed` são em inglês, mas todos os comandos e respostas do bot de liturgia são em português. Inconsistência visível ao usuário.

---

### 3.4 Comentários e código morto

**Arquivo:** `ltd_bot.py:653-668`
```python
# @bot.on_message(filters.regex(r'^/(stop)...'))
# def stop(client, update):
#    ...
```
Bloco de `stop` comentado mas uma versão do `stop` está ativa na linha 207. O código comentado causa confusão.

---

### 3.5 `backup()` em `feed_bot.py` usa PATH_REDIS que não existe

**Arquivo:** `feed_bot.py:30-36`
**Problema:** `PATH_REDIS` aponta para `/var/lib/redis/dump.rdb`. O Redis só salva o dump quando `SAVE` é executado explicitamente ou por configuração. Se o arquivo não existir no momento do backup, `open(PATH_REDIS, 'rb')` lança `FileNotFoundError`.

---

### 3.6 Scraping frágil sem tratamento de mudança de layout

**Arquivos:** `util/liturgiadiaria.py`, `util/homiliadodia.py`, `util/santododia.py`
**Problema:** Todos dependem de estrutura HTML específica do Canção Nova. Não há verificação de versão, fallback ou alerta quando o scraping falha silenciosamente.

---

### 3.7 MP3 salvo em `/tmp/` com nome contendo data em português

**Arquivo:** `util/homiliadodia.py`
**Código:**
```python
"/tmp/%s.mp3" % date_full  # date_full = "sexta-feira, 23 de maio de 2026"
```
**Problema:** O nome do arquivo contém espaços e caracteres especiais (vírgulas, letras acentuadas). Em alguns sistemas isso pode causar falha ao abrir ou referenciar o arquivo.

---

## 4. Riscos de Segurança

### 4.1 Controle de admin via Redis sem autenticação forte

**Arquivos:** `bot.py:555`, `ltd_bot.py:695` e vários outros
**Código:**
```python
if str(chat_id) not in db.list_admins():
    return
```
**Problema:** A lista de admins é armazenada no Redis (`admins` list). Se o Redis estiver acessível sem senha (como está no desenvolvimento atual), qualquer processo local pode se adicionar como admin.

---

### 4.2 Credenciais no `.env` sem `.gitignore`

**Problema:** Verificar se `.env` está no `.gitignore` para evitar commit acidental de tokens e hashes de senha do Redis.

---

## 5. Resumo por Arquivo

### `bot.py`
| # | Tipo | Descrição | Criticidade |
|---|------|-----------|------------|
| 1 | Bug crítico | `get_urls_deactivated()` não existe | Alta |
| 2 | Bug crítico | Comparação `me.username` com `@` incorreta | Alta |
| 3 | Qualidade | Lógica de welcome inalcançável | Média |
| 4 | Qualidade | Código duplicado com `ltd_bot.py` | Média |

### `ltd_bot.py`
| # | Tipo | Descrição | Criticidade |
|---|------|-----------|------------|
| 1 | Bug crítico | `start()` chamado sem `await` em `_introduce()` | Alta |
| 2 | Bug crítico | `update.delete()` sem `await` em `stop()` | Alta |
| 3 | Bug crítico | `get_user_info` definida duas vezes | Alta |
| 4 | Bug crítico | Comparação `me.username` com `@` incorreta | Alta |
| 5 | Bug crítico | `owner()` falha se `chat.username` for None | Alta |
| 6 | Bug médio | 27 handlers síncronos em bot assíncrono | Alta |
| 7 | Bug médio | `datetime.now()` sem timezone em 4 lugares | Média |
| 8 | Bug médio | `bot.loop.run_until_complete()` depreciado | Média |
| 9 | Bug médio | Handler `_dummy` residual | Baixa |
| 10 | Qualidade | Textos de ajuda em inglês | Baixa |
| 11 | Qualidade | Código duplicado com `bot.py` | Média |
| 12 | Qualidade | Bloco de `stop` comentado | Baixa |

### `feed_bot.py`
| # | Tipo | Descrição | Criticidade |
|---|------|-----------|------------|
| 1 | Bug crítico | `get_names_for_user_activated()` não existe | Alta |
| 2 | Bug crítico | `send_document(data=...)` → deve ser `document=` | Alta |
| 3 | Bug médio | `THREADS` lida mas ignorada | Baixa |
| 4 | Bug médio | `backup()` falha se dump.rdb não existir | Média |

### `feed_ltd_bot.py`
| # | Tipo | Descrição | Criticidade |
|---|------|-----------|------------|
| 1 | Bug médio | `THREADS` lida mas ignorada | Baixa |
| 2 | Qualidade | Código duplicado com `feed_bot.py` | Média |

### `util/database.py`
| # | Tipo | Descrição | Criticidade |
|---|------|-----------|------------|
| 1 | Bug crítico | `get_names_for_user_activated()` ausente (chamado por `feed_bot.py`) | Alta |
| 2 | Qualidade | Comentários de docstring desnecessários em todos os métodos | Baixa |

### `util/database_daily_liturgy.py`
| # | Tipo | Descrição | Criticidade |
|---|------|-----------|------------|
| 1 | Bug médio | `set_last_send_daily_liturgy` usa `datetime.now()` sem timezone | Média |

### `util/homiliadodia.py`
| # | Tipo | Descrição | Criticidade |
|---|------|-----------|------------|
| 1 | Risco | Nome de arquivo MP3 com caracteres especiais | Média |
| 2 | Risco | Scraping frágil sem fallback | Média |

### `util/liturgiadiaria.py` / `util/santododia.py`
| # | Tipo | Descrição | Criticidade |
|---|------|-----------|------------|
| 1 | Risco | Scraping frágil sem fallback | Média |

---

## 6. Prioridade de Correção Sugerida

### Fase 1 — Bugs críticos (corrigir antes de rodar em produção)
1. `feed_bot.py` → renomear `get_names_for_user_activated` para `get_name_urls_activated`
2. `util/database.py` → adicionar alias `get_names_for_user_activated` ou corrigir chamada
3. `bot.py` e `ltd_bot.py` → corrigir comparação `me.username` (remover `@`)
4. `ltd_bot.py` → `_introduce()`: tornar async e adicionar `await` na chamada de `start()`
5. `ltd_bot.py` → `stop()`: tornar async e adicionar `await update.delete()`
6. `ltd_bot.py` → renomear segunda `get_user_info` para `get_user_info_liturgy`
7. `ltd_bot.py` → `owner()`: adicionar verificação de `None` para `chat.username`
8. `feed_bot.py` → `send_document(data=doc)` → `send_document(document=doc)`

### Fase 2 — Bugs médios (qualidade e confiabilidade)
1. `ltd_bot.py` → converter todos os handlers para `async def`
2. `ltd_bot.py` e `bot.py` → corrigir lógica de welcome inalcançável
3. `ltd_bot.py` → substituir `datetime.now()` por `DateHandler.get_datetime_now()`
4. `util/database_daily_liturgy.py` → corrigir `set_last_send_daily_liturgy`
5. `feed_bot.py` e `feed_ltd_bot.py` → usar `int(THREADS)` no pool
6. `ltd_bot.py` → resolver `bot.loop.run_until_complete()` depreciado

### Fase 3 — Refatoração (evolução do projeto)
1. Extrair funções comuns de `bot.py` e `ltd_bot.py` para módulo compartilhado
2. Unificar `feed_bot.py` e `feed_ltd_bot.py`
3. Traduzir textos de ajuda para português
4. Adicionar tratamento de erros nos scrapers
5. Corrigir nome de arquivo MP3 com caracteres especiais

---

*Auditoria gerada em 2026-05-23. Atualizar após cada ciclo de correção.*
