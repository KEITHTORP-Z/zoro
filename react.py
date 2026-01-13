import os
import uuid
import aiohttp
from fastapi import FastAPI
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.stream import StreamAudioEnded

# ---------------- CONFIG ----------------

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")

JIOSAAVN_API = "https://jiosaavn-api.lagendplayersyt.workers.dev/api/search/songs?query="

# ---------------------------------------

app = FastAPI()

client = Client(
    "assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)

call = PyTgCalls(client)

queue = {}          # chat_id → [file1, file2]
now_playing = {}    # chat_id → current file


# ---------------- JIOSAAVN ----------------

async def get_saavn_song(query: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(JIOSAAVN_API + query) as resp:
            data = await resp.json()

    if not data["success"] or not data["data"]["results"]:
        return None

    song = data["data"]["results"][0]

    best = None
    for d in song["downloadUrl"]:
        if d["quality"] == "320kbps":
            best = d["url"]
            break

    if not best:
        best = song["downloadUrl"][-1]["url"]

    return {
        "title": song["name"],
        "artist": song["artists"]["primary"][0]["name"],
        "url": best
    }


async def download_song(url: str) -> str:
    filename = f"/tmp/{uuid.uuid4().hex}.mp4"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            with open(filename, "wb") as f:
                while True:
                    chunk = await resp.content.read(1024 * 64)
                    if not chunk:
                        break
                    f.write(chunk)

    return filename


# ---------------- STARTUP ----------------

@app.on_event("startup")
async def startup():
    await client.start()
    await call.start()
    me = await client.get_me()
    print(f"✅ Logged in as {me.first_name}")


# ---------------- STREAM END ----------------

@call.on_stream_end()
async def on_stream_end(_, update: StreamAudioEnded):
    chat_id = update.chat_id

    if queue.get(chat_id):
        next_file = queue[chat_id].pop(0)
        now_playing[chat_id] = next_file
        await call.change_stream(chat_id, AudioPiped(next_file))
    else:
        now_playing.pop(chat_id, None)
        await call.leave_group_call(chat_id)


# ---------------- API ----------------

@app.get("/")
def root():
    return {"status": "online"}


@app.get("/join")
async def join(chat_id: int):
    # Silent track so VC starts
    silent = "https://files.catbox.moe/kao3ip.jpeg"
    await call.join_group_call(chat_id, AudioPiped(silent))
    return {"ok": True}


@app.get("/play")
async def play(chat_id: int, query: str):
    song = await get_saavn_song(query)
    if not song:
        return {"error": "Song not found"}

    file = await download_song(song["url"])

    if call.active_calls.get(chat_id):
        queue.setdefault(chat_id, []).append(file)
        return {
            "queued": song["title"],
            "artist": song["artist"]
        }
    else:
        await call.join_group_call(chat_id, AudioPiped(file))
        now_playing[chat_id] = file
        return {
            "playing": song["title"],
            "artist": song["artist"]
        }


@app.get("/skip")
async def skip(chat_id: int):
    if queue.get(chat_id):
        next_file = queue[chat_id].pop(0)
        now_playing[chat_id] = next_file
        await call.change_stream(chat_id, AudioPiped(next_file))
        return {"skipped": True}
    else:
        now_playing.pop(chat_id, None)
        await call.leave_group_call(chat_id)
        return {"ended": True}


@app.get("/stop")
async def stop(chat_id: int):
    queue.pop(chat_id, None)
    now_playing.pop(chat_id, None)
    await call.leave_group_call(chat_id)
    return {"stopped": True}
