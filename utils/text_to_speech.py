
import asyncio
import edge_tts


async def speak_edge_tts(
    text,
    voice="en-US-AriaNeural",
    rate="+0%",
    pitch="+0Hz",
):
    """Generate speech and return MP3 audio bytes."""

    communicate = edge_tts.Communicate(
        text,
        voice,
        rate=rate,
        pitch=pitch,
    )

    audio_chunks = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])

    if not audio_chunks:
        raise RuntimeError("Edge TTS did not generate any audio.")

    return b"".join(audio_chunks)


def speak_text(
    text,
    voice="en-US-GuyNeural",
    rate="+0%",
    pitch="+0Hz",
):
    """Return MP3 audio bytes for Streamlit browser playback."""

    return asyncio.run(
        speak_edge_tts(text, voice, rate, pitch)
    )
