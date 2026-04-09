from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import StreamingResponse
from app.config import config
from openai import AsyncOpenAI
import httpx
import json

router = APIRouter()

@router.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)):
    """Accepts audio blob, passes to OpenAI Whisper API, returns transcript."""
    if not config.OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is missing for Whisper STT.")
        
    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    
    filename = audio.filename if audio.filename else "recording.webm"
    if not filename.endswith((".webm", ".wav", ".mp3", ".m4a")):
        filename += ".webm"
        
    try:
        content = await audio.read()
        transcript = await client.audio.transcriptions.create(model="whisper-1", file=(filename, content))
        return {"transcript": transcript.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Whisper Error: {str(e)}")

@router.post("/tts")
async def text_to_speech(text: str = Form(...), provider: str = Form(...)):
    """Receives text, streams back audio using Mistral Voxtral TTS or ElevenLabs depending on provider."""
    from fastapi.responses import Response
    
    if provider == "mistral":
        if not config.MISTRAL_API_KEY: raise HTTPException(status_code=500, detail="MISTRAL_API_KEY is missing.")
        url = "https://api.mistral.ai/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {config.MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "voxtral-mini-tts-latest", 
            "input": text,
            "voice": "mistral"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code != 200:
                print(f"❌ Mistral TTS Error: {response.text}")
                raise HTTPException(status_code=response.status_code, detail=f"Mistral TTS Rejected: {response.text}")
            return Response(content=response.content, media_type="audio/mpeg")

    # ElevenLabs Route
    if provider == "elevenlabs":
        if not config.ELEVENLABS_API_KEY: raise HTTPException(status_code=500, detail="ELEVENLABS_API_KEY is missing.")
        url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM" 
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": config.ELEVENLABS_API_KEY
        }
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code != 200:
                print(f"❌ ElevenLabs TTS Error: {response.text}")
                raise HTTPException(status_code=response.status_code, detail=f"ElevenLabs TTS Rejected: {response.text}")
            return Response(content=response.content, media_type="audio/mpeg")
        
    raise HTTPException(status_code=400, detail="Unsupported Provider Requested")
