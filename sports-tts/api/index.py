import re
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import edge_tts

app = FastAPI(title="Bengali Sports Stadium TTS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

ALLOWED_VOICES = {
    "bn-IN-BashkarNeural",   # পশ্চিমবঙ্গ স্পষ্ট পুরুষ কণ্ঠ
    "bn-BD-PradeepNeural",   # গম্ভীর পুরুষ কণ্ঠ
    "bn-IN-TanishaaNeural",  # পশ্চিমবঙ্গ স্পষ্ট মহিলা কণ্ঠ
    "bn-BD-NabanitaNeural",  # মহিলা কণ্ঠ
}


def clean_rate(val: str) -> str:
    s = (val or "+0%").strip()
    if re.fullmatch(r"[+-]?\d{1,2}%", s):
        return s if s[0] in "+-" else f"+{s}"
    return "+0%"


def clean_pitch(val: str) -> str:
    s = (val or "+0Hz").strip()
    if re.fullmatch(r"[+-]?\d{1,2}Hz", s):
        return s if s[0] in "+-" else f"+{s}"
    return "+0Hz"


async def generate_mp3(text: str, voice: str, rate: str, pitch: str) -> bytes:
    last_err = None
    for _ in range(2):
        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=rate,
                pitch=pitch,
            )
            chunks = []
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    chunks.append(chunk["data"])
            audio_bytes = b"".join(chunks)
            if len(audio_bytes) >= 600:
                return audio_bytes
            last_err = RuntimeError("Incomplete audio received")
        except Exception as exc:
            last_err = exc
    raise last_err or RuntimeError("TTS synthesis failed")


@app.get("/")
async def health():
    return {"status": "ok", "message": "Bengali Sports TTS Server is running on Vercel"}


@app.get("/api/tts")
async def tts_endpoint(
    text: str = Query(..., min_length=1, max_length=480),
    voice: str = Query("bn-IN-BashkarNeural"),
    rate: str = Query("+0%"),
    pitch: str = Query("+0Hz"),
):
    clean_text = text.strip()
    if not clean_text:
        return JSONResponse({"error": "Empty text"}, status_code=400)

    use_voice = voice if voice in ALLOWED_VOICES else "bn-IN-BashkarNeural"
    use_rate = clean_rate(rate)
    use_pitch = clean_pitch(pitch)

    try:
        audio_bytes = await generate_mp3(clean_text, use_voice, use_rate, use_pitch)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "public, s-maxage=86400, max-age=86400",
            "Access-Control-Allow-Origin": "*",
        },
    )