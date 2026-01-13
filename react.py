import os
import yt_dlp
from fastapi import FastAPI
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream

API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "your_api_hash_here")
SESSION = os.getenv("SESSION_STRING") or "assistant"

app = FastAPI()

# Initialize client
client = Client(
    name="assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION if SESSION != "assistant" else None,
    in_memory=True
)

# Initialize PyTgCalls
call = PyTgCalls(client)

queue = {}

def get_audio(title):
    """Get audio URL from YouTube"""
    ydl_opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "geo-bypass": True,
        "no-check-certificate": True,
        "prefer-ffmpeg": True,
        "extract_flat": True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{title}", download=False)
            if info and 'entries' in info and info['entries']:
                return info["entries"][0]["url"]
        except Exception as e:
            print(f"Error extracting audio: {e}")
    return None

@app.on_event("startup")
async def start():
    """Start the bot"""
    try:
        await client.start()
        await call.start()
        print("✅ VC Bot Started Successfully")
        print(f"✅ Bot: {await client.get_me()}")
    except Exception as e:
        print(f"❌ Startup Error: {e}")

@call.on_stream_end()
async def on_stream_end(chat_id: int):
    """Handle stream end event"""
    try:
        if chat_id in queue and queue[chat_id]:
            title = queue[chat_id].pop(0)
            audio_url = get_audio(title)
            if audio_url:
                await call.change_stream(
                    chat_id,
                    MediaStream(
                        audio_url,
                        video_flags=MediaStream.IGNORE
                    )
                )
        else:
            await call.leave_group_call(chat_id)
            if chat_id in queue:
                del queue[chat_id]
    except Exception as e:
        print(f"Stream end error: {e}")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "online", "service": "Telegram VC Bot"}

@app.get("/join")
async def join_vc(chat: str):
    """Join a voice chat"""
    try:
        chat_id = int(chat.replace("@", "").replace("-100", ""))
        await call.join_group_call(
            chat_id,
            MediaStream(
                "https://files.catbox.moe/kao3ip.jpeg",
                video_flags=MediaStream.IGNORE
            )
        )
        return {"ok": True, "chat_id": chat_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/play")
async def play_song(chat_id: int, title: str):
    """Play a song in voice chat"""
    try:
        if await call.get_active_call(chat_id):
            queue.setdefault(chat_id, []).append(title)
            return {"ok": True, "status": "Added to queue", "position": len(queue[chat_id])}
        else:
            audio_url = get_audio(title)
            if audio_url:
                await call.join_group_call(
                    chat_id,
                    MediaStream(
                        audio_url,
                        video_flags=MediaStream.IGNORE
                    )
                )
                return {"ok": True, "status": "Playing"}
            else:
                return {"ok": False, "error": "Could not get audio URL"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/pause")
async def pause_stream(chat_id: int):
    """Pause the stream"""
    try:
        await call.pause_stream(chat_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/resume")
async def resume_stream(chat_id: int):
    """Resume the stream"""
    try:
        await call.resume_stream(chat_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/stop")
async def stop_stream(chat_id: int):
    """Stop and leave voice chat"""
    try:
        await call.leave_group_call(chat_id)
        if chat_id in queue:
            del queue[chat_id]
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/queue")
async def get_queue(chat_id: int):
    """Get current queue"""
    return {"ok": True, "queue": queue.get(chat_id, [])}
