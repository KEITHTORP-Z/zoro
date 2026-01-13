import os
import yt_dlp
import asyncio
from fastapi import FastAPI
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types.stream import MediaStream
from pytgcalls.types import AudioQuality
from pyrogram.raw.functions.phone import CreateGroupCall
from pyrogram.raw.types import InputPeerChannel
from pytgcalls.exceptions import NoActiveGroupCall, GroupCallNotFound

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

pytgcalls = PyTgCalls(client)

queue = {}

ydl_opts = {
    "quiet": True,
    "nocheckcertificate": True,
    "geo_bypass": True,
    "format": "bestaudio",
}


def get_audio(title):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{title}", download=False)
        return info["entries"][0]["url"]


async def create_vc(chat_id):
    peer = await client.resolve_peer(chat_id)
    await client.invoke(
        CreateGroupCall(
            peer=InputPeerChannel(
                channel_id=peer.channel_id,
                access_hash=peer.access_hash,
            ),
            random_id=client.rnd_id() // 9000000000,
        )
    )


async def play_stream(chat_id, url):
    try:
        await pytgcalls.play(
            chat_id,
            MediaStream(url, AudioQuality.HIGH)
        )
    except (NoActiveGroupCall, GroupCallNotFound):
        await create_vc(chat_id)
        await play_stream(chat_id, url)


@app.on_event("startup")
async def start():
    await client.start()
    await pytgcalls.start()
    print("VC engine ready")


@app.get("/join")
async def join(chat: int):
    await play_stream(chat, "https://files.catbox.moe/kao3ip.jpeg")
    return {"ok": True}


@app.get("/play")
async def play(chat: int, title: str):
    url = get_audio(title)

    if chat in pytgcalls.calls:
        queue.setdefault(chat, []).append(url)
    else:
        await play_stream(chat, url)

    return {"playing": title}


@app.get("/skip")
async def skip(chat: int):
    if queue.get(chat):
        await pytgcalls.change_stream(
            chat,
            MediaStream(queue[chat].pop(0), AudioQuality.HIGH)
        )
        return {"ok": True}
    else:
        await pytgcalls.leave(chat)
        return {"stopped": True}


@app.get("/stop")
async def stop(chat: int):
    queue.pop(chat, None)
    await pytgcalls.leave(chat)
    return {"stopped": True}
