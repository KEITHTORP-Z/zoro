import yt_dlp
from fastapi import FastAPI
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import ExternalMedia

API_ID = 39884622           # your Telegram API ID
API_HASH = "9027d8c0e0a141e3feb76832dfebcb34" # your Telegram API Hash
SESSION = "1BZWaqwUAUGY7J82D4VeZIULZnItj7ejdbWHKqbHus1qCMBe9UWydimKEDjkth420Pl6Mw1YoJDHvvbK8yUk-iVrBPPQbqluuT8NNesAz4_qtQzyMItDdgR5thRbjfV5IMKYsQHNUUdWyynIfHFoyU0NWgZKv852j--gfmswhTxR9f-uPI5w2acd-zT5PX7uRSPArVQCjdRtNB3pcTiciDAJrxhpOSDAv61drkc-ZtnqrCbWzCg8j1faNPRuNEpN36Is6n3v0YHuJ-UWRyrt3nkRK-tLThmKklZKH9-YjxgFhE0NFL6M7gmHar5IkZiObz7lsT-EJ6GAJLVTYgxeaSzBwKvYAVis="     # will create assistant.session


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
