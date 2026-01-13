import yt_dlp
from fastapi import FastAPI
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import ExternalMedia

API_ID = int("YOUR_API_ID")
API_HASH = "YOUR_API_HASH"
SESSION = "assistant"

app = FastAPI()

client = Client(SESSION, api_id=API_ID, api_hash=API_HASH)
call = PyTgCalls(client)

queue = {}

def get_audio(title):
    ydl_opts = {"format": "bestaudio", "noplaylist": True, "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{title}", download=False)
        return info["entries"][0]["url"]

@app.on_event("startup")
async def start():
    await client.start()
    await call.start()
    print("VC engine started")

@call.on_stream_end()
async def on_end(_, chat_id):
    if chat_id in queue and queue[chat_id]:
        title = queue[chat_id].pop(0)
        await call.change_stream(chat_id, ExternalMedia(get_audio(title)))
    else:
        await call.leave_group_call(chat_id)

@app.get("/join")
async def join(chat: str):
    chat = int(chat.replace("@", ""))
    await call.join_group_call(chat, ExternalMedia("https://files.catbox.moe/kao3ip.jpeg"))
    return {"ok": True}

@app.get("/play")
async def play(chatid: int, title: str):
    if call.get_call(chatid):
        queue.setdefault(chatid, []).append(title)
    else:
        await call.join_group_call(chatid, ExternalMedia(get_audio(title)))
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
