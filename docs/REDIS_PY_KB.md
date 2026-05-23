# redis-py — Base de Conhecimento para o v2

> Gerado em: 2026-05-23
> Versão de referência: redis-py 7.4.0
> Fonte: https://github.com/redis/docs
> Escopo: migração sync → async e padrões usados neste projeto

---

## 1. Mudança central do v1 para o v2

O v2 é totalmente async (Kurigram + APScheduler). A camada Redis precisa acompanhar.

| v1 (`StrictRedis`, sync) | v2 (`redis.asyncio.Redis`, async) |
|--------------------------|-----------------------------------|
| `from redis import StrictRedis` | `from redis.asyncio import Redis` |
| `r = StrictRedis(...)` | `r = Redis(...)` |
| `r.hset(name, mapping=m)` | `await r.hset(name, mapping=m)` |
| `r.hget(name, key)` | `await r.hget(name, key)` |
| `r.scan(cursor, match)` | `r.scan_iter(match)` (sem cursor manual) |
| `r.close()` | `await r.aclose()` |

> **Nota:** `StrictRedis` foi fundido com `Redis` no redis-py 4.0. O alias ainda funciona mas o nome correto é `Redis`. No namespace async, sempre `redis.asyncio.Redis`.

---

## 2. Conexão async

```python
from redis.asyncio import Redis

redis_client = Redis(
    host="localhost",
    port=6379,
    password=password or None,
    decode_responses=True,
    db=db
)
```

O client já gerencia um pool de conexões internamente. Para uma aplicação de longa duração (como este bot), o padrão correto é:

```python
# Criar uma vez no startup (dentro de on_start ou BaseDatabase.__init__)
self.redis = Redis(host="localhost", port=6379, decode_responses=True, db=db)

# Usar em todos os handlers — o pool cuida da concorrência
await self.redis.hset(...)

# Fechar no shutdown (dentro de on_stop)
await self.redis.aclose()
```

**Nunca criar um `Redis()` por chamada** — paga o custo de conexão a cada operação e anula o pool.

---

## 3. Substituição do `_find()` por `scan_iter()`

O `_find()` atual faz SCAN manual com cursor. redis-py tem `scan_iter()` que encapsula isso:

**v1 — cursor manual:**
```python
def _find(self, search):
    cursor = None
    names = []
    while cursor != 0:
        if cursor is None:
            cursor = 0
        fined = self.redis.scan(cursor, str(search))
        cursor = fined[0]
        names.extend(fined[1])
    return sorted(set(names))
```

**v2 — `scan_iter()`:**
```python
async def _find(self, pattern: str) -> list[str]:
    return sorted({key async for key in self.redis.scan_iter(match=pattern)})
```

`scan_iter()` usa cursor internamente, nunca bloqueia, e é seguro em produção (ao contrário de `KEYS *`).

Variantes disponíveis:
```python
# Chaves do keyspace
async for key in r.scan_iter(match="user_url*"):
    ...

# Campos de um hash
async for field in r.hscan_iter("minha_chave"):
    ...
```

---

## 4. Comandos usados neste projeto — versão async

### Hash (estrutura mais usada)

```python
# Criar/atualizar — recebe dict
await r.hset("group:-123", mapping={"chat_id": "-123", "chat_lock": "True"})

# Ler um campo
valor = await r.hget("group:-123", "chat_lock")  # retorna str ou None

# Ler vários campos
valores = await r.hmget("group:-123", "chat_lock", "chat_quiet")  # lista

# Ler todos os campos
todos = await r.hgetall("group:-123")  # dict

# Verificar se campo existe
existe = await r.hexists("group:-123", "chat_lock")  # bool
```

### Existência e deleção

```python
# Chave existe?
existe = await r.exists("group:-123")  # int: 1 ou 0

# Deletar uma ou mais chaves
await r.delete("group:-123")
await r.delete("chave1", "chave2", "chave3")
```

### List (usada em `admins`)

```python
# Ler lista inteira
admins = await r.lrange("admins", 0, -1)   # equivalente a lrange(0, llen)

# Tamanho
tamanho = await r.llen("admins")

# Adicionar
await r.rpush("admins", str(user_id))
```

### Rename

```python
# Renomear chave (usado em update_owner)
await r.rename("chave_antiga", "chave_nova")
```

### Save (backup)

```python
# Força escrita do dump.rdb
await r.save()
# ou BGSAVE para não bloquear
await r.bgsave()
```

---

## 5. Pipelining (operações em lote)

Para ativar/desativar muitas chaves de uma vez (ex: `activated_all_urls`), pipeline evita N round-trips:

```python
async with r.pipeline() as pipe:
    for name in names:
        pipe.hset(name, mapping={"disable": "False"})
    await pipe.execute()
```

**Uso atual em `activated_all_urls`:** faz `set_name_key` em loop — no v2 substituir por pipeline.

---

## 6. Ciclo de vida no v2 (integração com Kurigram `on_start`/`on_stop`)

```python
class BaseDatabase:
    def __init__(self, db: int):
        self.redis = Redis(
            host="localhost",
            port=6379,
            password=config("REDIS") or None,
            decode_responses=True,
            db=db
        )

    async def close(self) -> None:
        await self.redis.aclose()


# Em BaseBot, via on_start/on_stop do Kurigram:
@self.client.on_start()
async def _on_start(client):
    # Redis já conecta lazily — não precisa de connect() explícito
    pass

@self.client.on_stop()
async def _on_stop(client):
    await self.db.close()
```

---

## 7. Tratamento de erros redis-py

```python
from redis.exceptions import ConnectionError, TimeoutError, RedisError

try:
    await r.hset(name, mapping=mapping)
except ConnectionError:
    logger.error("Redis indisponível")
except TimeoutError:
    logger.error("Timeout na operação Redis")
except RedisError as e:
    logger.error(f"Erro Redis: {e}")
```

---

## 8. O que NÃO usar no v2

| Evitar | Motivo |
|--------|--------|
| `StrictRedis` | Alias depreciado — usar `Redis` ou `redis.asyncio.Redis` |
| `redis.scan(cursor, match)` manual | Usar `scan_iter()` |
| `KEYS *` | Bloqueia o servidor em produção |
| `r.close()` | Depreciado — usar `await r.aclose()` |
| Uma conexão nova por operação | Usar o client compartilhado com pool interno |
| `DateHandler.datetime.now()` para `last_send` | Usar `DateHandler.get_datetime_now()` (bug do v1) |

---

## 9. Referências

- redis-py async: https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html
- scan_iter: `content/develop/clients/redis-py/scaniter.md` no repo redis/docs
- Async connection: `content/develop/clients/redis-py/async.md` no repo redis/docs
- Schema de chaves deste projeto: `docs/REDIS_SCHEMA.md`
