import io
import edge_tts

async def text_2_speech(text: str) -> io.BytesIO:
    """
    Convert text to speech using Microsoft Edge TTS.

    Returns:
        io.BytesIO containing MP3 audio bytes.
        This is fully compatible with the existing FastAPI endpoint.
    """

    if not text:
        return io.BytesIO()

    try:
        communicate = edge_tts.Communicate(
            text=text,
            voice="en-US-AriaNeural",
        )

        audio_buffer = io.BytesIO()

        async for chunk in communicate.stream():

            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        audio_buffer.seek(0)

        return audio_buffer

    except Exception as e:
        print(f"Edge TTS Error: {e}")
        return io.BytesIO()