# Kurigram — Base de Conhecimento

> Gerado em: 2026-05-23
> Fonte: https://github.com/KurimuzonAkuma/pyrogram
> Versão de referência: 2.2.23

Kurigram é o fork ativo do Pyrogram. **Todos os imports continuam `from pyrogram import ...`** — o nome do pacote no PyPI é `kurigram`, mas o namespace interno permanece `pyrogram`.

---

## 1. Instalação

```bash
pip install kurigram
# Remove TgCrypto separado — Kurigram já inclui
```

`requirements.txt` do v2:
```
kurigram==2.2.23   # substitui Pyrogram==2.0.106 + TgCrypto
```

---

## 2. Padrão de Handler

Todo handler deve ser `async def`. Assinatura obrigatória:

```python
from pyrogram import Client
from pyrogram.types import Message

async def meu_handler(client: Client, message: Message) -> None:
    ...
```

Registro via decorator:

```python
@bot.on_message(filters.command("start") & filters.private)
async def start(client: Client, message: Message) -> None:
    await message.reply("Olá!")
```

Ou via `add_handler` (útil em classes/mixins):

```python
from pyrogram.handlers import MessageHandler

client.add_handler(MessageHandler(meu_handler, filters.command("start")))
```

---

## 3. Ciclo de Vida do Client

### Inicialização completa (recomendada para v2)

```python
from pyrogram import Client, idle

app = Client("nome", api_id=..., api_hash=..., bot_token=...)

async def main():
    await app.start()
    await idle()          # mantém o processo vivo até SIGINT/SIGTERM
    await app.stop()

asyncio.run(main())
```

### Atalho (equivalente)

```python
app.run()   # start + idle + stop internamente
```

### Múltiplos bots em paralelo

```python
async def main():
    await asyncio.gather(
        main_bot.start(),
        liturgy_bot.start(),
    )
    await idle()
    await asyncio.gather(
        main_bot.stop(),
        liturgy_bot.stop(),
    )

asyncio.run(main())
```

---

## 4. Lifecycle Hooks (novidade do Kurigram)

Kurigram adiciona `@client.on_start()` e `@client.on_stop()`. São a solução correta para substituir o `bot.loop.run_until_complete()` depreciado do v1.

```python
@bot.on_start()
async def on_startup(client: Client) -> None:
    # executado após client.start() — ideal para iniciar o scheduler
    scheduler.start()

@bot.on_stop()
async def on_shutdown(client: Client) -> None:
    # executado antes de client.stop()
    scheduler.shutdown()
```

> **Relevância para o v2:** `LiturgyBot` usa isso para iniciar/parar o APScheduler sem depender de `bot.loop`.

---

## 5. Tratamento de Erros Centralizado (novidade do Kurigram)

```python
from pyrogram.handlers import ErrorHandler

@bot.on_error()
async def on_error(client: Client, update, exception: Exception) -> None:
    # captura exceções não tratadas em qualquer handler
    logger.error(f"Erro em update {update}: {exception}")
```

Aceita filtro de tipo de exceção:

```python
@bot.on_error(exceptions=RPCError)
async def on_rpc_error(client, update, exc):
    ...
```

---

## 6. Filtros Built-in

### Filtros de contexto (mais usados neste projeto)

```python
filters.private          # mensagens diretas (DM)
filters.group            # grupos e supergrupos
filters.channel          # canais
filters.new_chat_members # evento: novo membro no grupo
filters.left_chat_member # evento: membro saiu do grupo
filters.command("cmd")   # mensagem começa com /cmd
filters.text             # mensagem tem texto
filters.incoming         # mensagem recebida (não enviada pelo bot)
```

### Filtros de remetente

```python
filters.me               # o próprio bot
filters.bot              # qualquer bot
filters.admin            # admin do chat (novo no Kurigram)
filters.user([user_id])  # usuário específico
filters.chat([chat_id])  # chat específico
```

### Composição

```python
# AND
filters.command("start") & filters.private

# OR
filters.photo | filters.video

# NOT
~filters.bot

# Combinado
filters.command(["hoje", "amanha"]) & (filters.private | filters.group)
```

### Filtro customizado

```python
from pyrogram.filters import create

async def meu_filtro_func(filt, client, message):
    return message.from_user and message.from_user.id in ADMIN_IDS

meu_filtro = create(meu_filtro_func, name="MeuFiltro")

@bot.on_message(meu_filtro)
async def handler(client, message): ...
```

---

## 7. `filters.command` — detalhes

```python
# Um comando
filters.command("start")

# Vários comandos no mesmo handler
filters.command(["hoje", "ontem", "amanha"])

# Prefixo customizado (padrão é "/")
filters.command("cmd", prefixes="!")

# Case sensitive (padrão False)
filters.command("Start", case_sensitive=True)
```

Após o filtro, os argumentos do comando ficam em `message.command`:

```python
# /addurl https://exemplo.com
cmd  = message.command[0]   # "addurl"
url  = message.command[1]   # "https://exemplo.com"
args = message.command[1:]  # ["https://exemplo.com"]
```

---

## 8. Handlers disponíveis

| Decorator | Handler class | Quando usar |
|-----------|--------------|-------------|
| `on_message` | `MessageHandler` | Mensagens novas |
| `on_edited_message` | `EditedMessageHandler` | Mensagens editadas |
| `on_callback_query` | `CallbackQueryHandler` | Botões inline |
| `on_inline_query` | `InlineQueryHandler` | Queries inline |
| `on_chat_member_updated` | `ChatMemberUpdatedHandler` | Alterações de membro |
| `on_chat_join_request` | `ChatJoinRequestHandler` | Solicitações de entrada |
| `on_deleted_messages` | `DeletedMessagesHandler` | Mensagens deletadas |
| `on_user_status` | `UserStatusHandler` | Online/offline |
| `on_poll` | `PollHandler` | Atualizações de enquete |
| `on_start` | `StartHandler` | Client iniciado (**novo**) |
| `on_stop` | `StopHandler` | Client parado (**novo**) |
| `on_connect` | `ConnectHandler` | Conexão estabelecida (**novo**) |
| `on_disconnect` | `DisconnectHandler` | Conexão perdida (**novo**) |
| `on_error` | `ErrorHandler` | Erros não tratados (**novo**) |
| `on_raw_update` | `RawUpdateHandler` | Updates brutos MTProto |

---

## 9. Envio de Mensagens — métodos principais

```python
# Texto
await client.send_message(chat_id, "texto")
await message.reply("resposta")

# Documento
await client.send_document(chat_id, document="path/ou/file_id", caption="legenda")

# Áudio
await client.send_audio(chat_id, audio="path/ou/file_id")

# Foto
await client.send_photo(chat_id, photo="path/ou/file_id")

# Editar
await message.edit_text("novo texto")

# Deletar
await message.delete()

# Resposta com botões inline
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
await message.reply(
    "escolha:",
    reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("Opção", callback_data="opcao")
    ]])
)
```

---

## 10. Informações do Update

```python
# Remetente
message.from_user.id
message.from_user.username    # sem "@"
message.from_user.first_name

# Chat
message.chat.id
message.chat.type             # enums.ChatType.PRIVATE / GROUP / SUPERGROUP / CHANNEL
message.chat.username         # pode ser None em grupos sem username

# Conteúdo
message.text
message.caption
message.document
message.audio
message.photo

# Contexto
message.command               # lista após /comando (se filtro command ativo)
message.reply_to_message      # mensagem citada, ou None
```

---

## 11. Informações do Bot (substituindo `client.get_me()`)

```python
me = await client.get_me()
me.id
me.username    # SEM "@" — comparar diretamente com BOT_NAME
me.first_name
me.is_bot
```

> **Bug do v1 corrigido:** `me.username == '@' + BOT_NAME` → correto é `me.username == BOT_NAME`

---

## 12. Tratamento de Erros RPCError

```python
from pyrogram.errors import RPCError, FloodWait, UserIsBlocked, ChatWriteForbidden

try:
    await client.send_message(chat_id, text)
except FloodWait as e:
    await asyncio.sleep(e.value)
except (UserIsBlocked, ChatWriteForbidden):
    db.disable_url_chat(chat_id)
except RPCError as e:
    logger.error(f"RPC error: {e}")
```

---

## 13. Padrão de Mixin com Kurigram (v2)

Handlers em Mixins são registrados via `add_handler` dentro de `register_handlers()`, não via decorators (decorators exigem acesso direto ao `client` no momento da definição).

```python
from pyrogram.handlers import MessageHandler
from pyrogram import filters

class WelcomeMixin:
    async def _welcome(self, client, message):
        ...

    async def set_welcome(self, client, message):
        ...

    def register_welcome_handlers(self):
        self.client.add_handler(
            MessageHandler(self._welcome, filters.new_chat_members)
        )
        self.client.add_handler(
            MessageHandler(self.set_welcome, filters.command("welcome") & filters.group)
        )
```

---

## 14. O que NÃO usar (depreciado ou removido)

| Depreciado | Substituto |
|-----------|-----------|
| `bot.loop.run_until_complete(...)` | `@bot.on_start()` decorator |
| `client.loop` property | `asyncio.get_event_loop()` |
| `parse_mode=` em alguns métodos | `enums.ParseMode.HTML` / `MARKDOWN` |
| `pyTelegramBotAPI` (sync) | Kurigram cobre tudo de forma async |

---

## 15. Novos recursos do Kurigram irrelevantes para este projeto

Os itens abaixo existem no Kurigram mas estão fora do escopo do OiOlabot:
- Business API (`on_business_message`, `on_business_connection`)
- AI features (`compose_text_with_ai`, `summarize_message`, `translate_message_text`)
- Guest messages (`on_guest_message`)
- Paid media (`send_paid_media`, `send_paid_reaction`)
- Checklists (`send_checklist`)
- Gifts API (`gift`, `gift_code`, filtros `gift_offer_*`)
