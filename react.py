import os
import yt_dlp
from fastapi import FastAPI
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.stream import StreamAudioEnded

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")

app = FastAPI()

client = Client(
    "assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)

call = PyTgCalls(client)

queue = {}

ydl_opts = {
    "format": "bestaudio",
    "quiet": True,
    "noplaylist": True,
}

def get_audio(query):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{query}", download=False)
        return info["entries"][0]["url"]

@app.on_event("startup")
async def startup():
    await client.start()
    await call.start()
    me = await client.get_me()
    print(f"✅ Logged in as {me.first_name}")

@call.on_stream_end()
async def on_stream_end(_, update: StreamAudioEnded):
    chat_id = update.chat_id
    if queue.get(chat_id):
        await call.change_stream(chat_id, AudioPiped(queue[chat_id].pop(0)))
    else:
        await call.leave_group_call(chat_id)

@app.get("/")
def root():
    return {"status": "online"}

@app.get("/join")
async def join(chat_id: int):
    await call.join_group_call(
        chat_id,
        AudioPiped("https://files.catbox.moe/kao3ip.jpeg")
    )
    return {"ok": True}

@app.get("/play")
async def play(chat_id: int, query: str):
    url = get_audio(query)

    if call.active_calls.get(chat_id):
        queue.setdefault(chat_id, []).append(url)
        return {"queued": query}
    else:
        await call.join_group_call(chat_id, AudioPiped(url))
        return {"playing": query}

@app.get("/skip")
async def skip(chat_id: int):
    if queue.get(chat_id):
        await call.change_stream(chat_id, AudioPiped(queue[chat_id].pop(0)))
        return {"skipped": True}
    else:
        await call.leave_group_call(chat_id)
        return {"ended": True}

@app.get("/stop")
async def stop(chat_id: int):
    queue.pop(chat_id, None)
    await call.leave_group_call(chat_id)
    return {"stopped": True}
