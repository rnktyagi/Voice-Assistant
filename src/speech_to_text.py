import io
import os
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

async def speech_2_text(audio_bytes: bytes) -> str:
    if not audio_bytes:
        return ""

    if not os.getenv("GROQ_API_KEY"):
        raise ValueError("GROQ_API_KEY is missing.")

    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"

        transcription = await client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-large-v3",
            response_format="json",
            temperature=0.0,
        )

        return transcription.text.strip()

    except Exception as e:
        print(f"Groq STT Error: {e}")
        return "System Note: The speech-to-text API is currently unavailable."