import os
import yt_dlp
from fastapi import FastAPI
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.stream import StreamAudioEnded

# ===== ENV =====
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]   # required

app = FastAPI()

# Use only session string — no files, no phone login
client = Client(
    name="pyrogram",            # internal name (not used for auth)
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True,
)

call = PyTgCalls(client)
queue = {}

# ===== YOUTUBE =====
def get_audio(title):
    ydl_opts = {
        "format": "bestaudio",
        "noplaylist": True,
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{title}", download=False)
        return info["entries"][0]["url"]

# ===== STARTUP =====
@app.on_event("startup")
async def start():
    await client.start()
    await call.start()
    print("VC engine started")

# ===== AUTO QUEUE =====
@call.on_stream_end()
async def on_end(_, update: StreamAudioEnded):
    chat_id = update.chat_id
    if chat_id in queue and queue[chat_id]:
        title = queue[chat_id].pop(0)
        await call.change_stream(chat_id, AudioPiped(get_audio(title)))
    else:
        await call.leave_group_call(chat_id)

# ===== API =====
@app.get("/join")
async def join(chatid: int):
    await call.join_group_call(chatid, AudioPiped("https://files.catbox.moe/kao3ip.jpeg"))
    return {"ok": True}

@app.get("/play")
async def play(chatid: int, title: str):
    if call.active_calls.get(chatid):
        queue.setdefault(chatid, []).append(title)
    else:
        await call.join_group_call(chatid, AudioPiped(get_audio(title)))
    return {"ok": True}

@app.get("/pause")
async def pause(chatid: int):
    await call.pause_stream(chatid)
    return {"ok": True}

@app.get("/resume")
async def resume(chatid: int):
    await call.resume_stream(chatid)
    return {"ok": True}

@app.get("/stop")
async def stop(chatid: int):
    await call.leave_group_call(chatid)
    queue.pop(chatid, None)
    return {"ok": True}
