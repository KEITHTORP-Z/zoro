import os
import asyncio
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pyrogram import Client

# Pyrogram errors - use generic exceptions
# Note: AlreadyJoinedError, NoActiveGroupCall, GroupCallNotFound don't exist in this version
# We'll use generic Exception and handle them differently

# Import from py-tgcalls 0.9.7
from pytgcalls import PyTgCalls
from pytgcalls import StreamType
from pytgcalls.types import Update
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio, MediumQualityVideo
from pytgcalls.types.stream import StreamAudioEnded

import yt_dlp

# Configuration
API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "your_api_hash")
SESSION_STRING = os.getenv("SESSION_STRING", "")

# Initialize FastAPI
app = FastAPI(title="Telegram VC Bot API")

# Store queues and active calls
queues: Dict[int, List[str]] = {}
current_streams: Dict[int, Dict] = {}
user_client = None
call = None

class TelegramVC:
    def __init__(self):
        self.queues = {}
        self.current_streams = {}
        
    async def get_audio_url(self, query: str) -> Optional[str]:
        """Extract audio URL from YouTube/SoundCloud/etc."""
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'noplaylist': True,
            'extract_flat': False,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
                
                if 'entries' in info:
                    info = info['entries'][0]
                
                # Get the audio URL
                if 'url' in info:
                    return info['url']
                elif 'formats' in info:
                    formats = info['formats']
                    audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
                    if audio_formats:
                        best_format = max(audio_formats, key=lambda x: x.get('abr', 0) or 0)
                        return best_format['url']
                
                return None
                
        except Exception as e:
            print(f"❌ Error extracting audio: {e}")
            return None
    
    async def handle_stream_end(self, chat_id: int):
        """Handle when a stream ends"""
        print(f"🎵 Stream ended in chat {chat_id}")
        
        if chat_id in self.queues and self.queues[chat_id]:
            query = self.queues[chat_id].pop(0)
            try:
                audio_url = await self.get_audio_url(query)
                if audio_url:
                    await call.change_stream(
                        chat_id,
                        AudioPiped(
                            audio_url,
                            HighQualityAudio(),
                        )
                    )
                    self.current_streams[chat_id] = {"query": query, "url": audio_url}
                    print(f"▶️ Playing next in queue: {query}")
                else:
                    print(f"❌ Could not get audio URL for: {query}")
            except Exception as e:
                print(f"❌ Error playing next: {e}")
        else:
            if chat_id in self.current_streams:
                del self.current_streams[chat_id]
            print(f"🏁 Queue empty for chat {chat_id}")

vc_bot = TelegramVC()

# PyTgCalls event handlers
@call.on_stream_end()
async def stream_end_handler(client: PyTgCalls, update: Update):
    """Handle stream end event from py-tgcalls 0.9.7"""
    await vc_bot.handle_stream_end(update.chat_id)

@app.on_event("startup")
async def startup_event():
    """Start the bot on startup"""
    global user_client, call
    
    if not SESSION_STRING:
        print("❌ SESSION_STRING environment variable is required!")
        return
    
    try:
        # Initialize user client with session string
        user_client = Client(
            "user_client",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=SESSION_STRING,
            in_memory=True
        )
        
        # Initialize PyTgCalls
        call = PyTgCalls(user_client)
        
        # Start both clients
        await user_client.start()
        await call.start()
        
        # Get user info
        user = await user_client.get_me()
        print(f"✅ User: {user.first_name} (@{user.username})")
        print("✅ PyTgCalls started successfully")
        print("✅ Telegram VC Bot API is running!")
        
    except Exception as e:
        print(f"❌ Startup error: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown"""
    global user_client, call
    
    try:
        if call:
            await call.stop()
        if user_client:
            await user_client.stop()
        print("✅ Bot stopped successfully")
    except Exception as e:
        print(f"❌ Shutdown error: {e}")

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "online",
        "service": "Telegram VC Bot API",
        "endpoints": [
            "/health",
            "/play?chat_id=CHAT_ID&query=SONG_NAME",
            "/pause?chat_id=CHAT_ID",
            "/resume?chat_id=CHAT_ID",
            "/skip?chat_id=CHAT_ID",
            "/stop?chat_id=CHAT_ID",
            "/queue?chat_id=CHAT_ID",
            "/current?chat_id=CHAT_ID",
            "/join?chat_id=CHAT_ID"
        ]
    }

@app.get("/health")
async def health():
    """Health check with bot status"""
    global user_client
    
    if not user_client or not call:
        return {"status": "error", "message": "Bot not initialized"}
    
    try:
        user = await user_client.get_me()
        return {
            "status": "healthy",
            "user": {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name
            },
            "active_calls": len(vc_bot.current_streams),
            "total_queues": len(vc_bot.queues)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/join")
async def join_vc(chat_id: int):
    """Join voice chat"""
    global call
    
    if not call:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        # Join with silent audio
        await call.join_group_call(
            chat_id,
            AudioPiped(
                "http://docs.evostream.com/sample_content/assets/sintel1m720p.mp4",
                HighQualityAudio(),
            ),
            stream_type=StreamType().local_stream
        )
        
        print(f"✅ Joined voice chat: {chat_id}")
        return {"status": "success", "message": f"Joined voice chat {chat_id}"}
        
    except Exception as e:
        error_msg = str(e)
        if "already joined" in error_msg.lower():
            return {"status": "info", "message": "Already in voice chat"}
        elif "no active" in error_msg.lower() or "group call" in error_msg.lower():
            return {"status": "error", "message": "No active group call. Start a voice chat first!"}
        else:
            return {"status": "error", "message": error_msg}

@app.get("/play")
async def play(chat_id: int, query: str):
    """Play audio in voice chat"""
    global call
    
    if not call:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        # Get audio URL
        audio_url = await vc_bot.get_audio_url(query)
        if not audio_url:
            return {"status": "error", "message": "Could not find audio"}
        
        # Check if already in call by trying to get active call
        try:
            active_call = await call.get_active_call(chat_id)
            if active_call:
                # Add to queue
                vc_bot.queues.setdefault(chat_id, []).append(query)
                position = len(vc_bot.queues[chat_id])
                return {
                    "status": "success", 
                    "message": f"Added to queue (Position: {position})",
                    "query": query
                }
        except Exception:
            # No active call, we'll join fresh
            pass
        
        # Join and play
        await call.join_group_call(
            chat_id,
            AudioPiped(
                audio_url,
                HighQualityAudio(),
            ),
            stream_type=StreamType().local_stream
        )
        
        vc_bot.current_streams[chat_id] = {"query": query, "url": audio_url}
        return {
            "status": "success",
            "message": "Now playing",
            "query": query,
            "url": audio_url[:100] + "..." if len(audio_url) > 100 else audio_url
        }
        
    except Exception as e:
        error_msg = str(e)
        if "no active" in error_msg.lower() or "group call" in error_msg.lower():
            return {"status": "error", "message": "No active group call. Start a voice chat first!"}
        else:
            return {"status": "error", "message": error_msg}

@app.get("/pause")
async def pause(chat_id: int):
    """Pause playback"""
    global call
    
    if not call:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        await call.pause_stream(chat_id)
        return {"status": "success", "message": "Playback paused"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/resume")
async def resume(chat_id: int):
    """Resume playback"""
    global call
    
    if not call:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        await call.resume_stream(chat_id)
        return {"status": "success", "message": "Playback resumed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/skip")
async def skip(chat_id: int):
    """Skip current track"""
    global call
    
    if not call:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        # Leave current call
        await call.leave_group_call(chat_id)
        
        # Clear current stream
        if chat_id in vc_bot.current_streams:
            del vc_bot.current_streams[chat_id]
        
        # Check if there's something in queue
        if chat_id in vc_bot.queues and vc_bot.queues[chat_id]:
            await asyncio.sleep(1)  # Small delay
            query = vc_bot.queues[chat_id].pop(0)
            
            # Play next
            audio_url = await vc_bot.get_audio_url(query)
            if audio_url:
                await call.join_group_call(
                    chat_id,
                    AudioPiped(
                        audio_url,
                        HighQualityAudio(),
                    ),
                    stream_type=StreamType().local_stream
                )
                vc_bot.current_streams[chat_id] = {"query": query, "url": audio_url}
                return {"status": "success", "message": f"Skipped to: {query}"}
        
        return {"status": "success", "message": "Skipped, queue is empty"}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/stop")
async def stop(chat_id: int):
    """Stop playback and leave VC"""
    global call
    
    if not call:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        await call.leave_group_call(chat_id)
        
        # Clear data
        if chat_id in vc_bot.queues:
            del vc_bot.queues[chat_id]
        if chat_id in vc_bot.current_streams:
            del vc_bot.current_streams[chat_id]
        
        return {"status": "success", "message": "Stopped playback and left voice chat"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/queue")
async def get_queue(chat_id: int):
    """Get current queue"""
    if not call:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    queue = vc_bot.queues.get(chat_id, [])
    return {
        "status": "success",
        "chat_id": chat_id,
        "queue": queue,
        "total": len(queue)
    }

@app.get("/current")
async def get_current(chat_id: int):
    """Get currently playing track"""
    if not call:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    current = vc_bot.current_streams.get(chat_id)
    
    if current:
        return {
            "status": "success",
            "chat_id": chat_id,
            "current": current
        }
    else:
        return {
            "status": "success",
            "chat_id": chat_id,
            "current": None,
            "message": "No track currently playing"
        }

# Clean queue endpoint
@app.delete("/queue")
async def clear_queue(chat_id: int):
    """Clear the queue"""
    if chat_id in vc_bot.queues:
        del vc_bot.queues[chat_id]
        return {"status": "success", "message": "Queue cleared"}
    else:
        return {"status": "success", "message": "No queue to clear"}
