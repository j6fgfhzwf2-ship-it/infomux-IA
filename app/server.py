# app/server.py
"""
FastAPI local backend pour assistant vocal local.

Fonctionnalités exposées:
- POST /transcribe : upload d'un fichier audio WAV -> transcription texte (Whisper si disponible)
- POST /generate   : { "prompt": "..." } -> génération texte via ollama CLI (si dispo) ou fallback
- POST /speak      : { "text": "...", "filename": "out.wav" } -> crée un wav TTS (Coqui TTS si dispo, sinon pyttsx3)
- GET  /audio/{filename} -> récupère le wav généré

Usage:
    pip install fastapi uvicorn python-multipart pydantic soundfile
    (installer whisper, coqui-tts, ollama selon ton choix)
    uvicorn app.server:app --host 127.0.0.1 --port 8000

Note: tout est local. Pas de censure intégrée.
"""

import os
import shutil
import subprocess
import tempfile
import uuid
import threading
import time
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Optional libs
WHISPER_AVAILABLE = False
COQUI_TTS_AVAILABLE = False
PYTTSX3_AVAILABLE = False
try:
    import whisper
    WHISPER_AVAILABLE = True
except Exception:
    WHISPER_AVAILABLE = False

try:
    # Coqui TTS (pip: TTS)
    # from TTS.api import TTS
    from TTS.api import TTS  # type: ignore
    COQUI_TTS_AVAILABLE = True
except Exception:
    COQUI_TTS_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except Exception:
    PYTTSX3_AVAILABLE = False

import soundfile as sf  # for reading/writing wav

# ----- Configuration -----
MODEL_WHISPER = "base"     # change to "tiny","small","base","large" selon ressources
TTS_MODEL_NAME = None      # None => use default Coqui TTS model
AUDIO_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "generated_audio")
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)
# -------------------------


app = FastAPI(title="Assistant local - backend")

# Allow CORS from local frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "*"],  # adapt if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Utilities ----------
def safe_filename(name: str) -> str:
    # generate safe filename with uuid suffix
    base = os.path.basename(name)
    uid = uuid.uuid4().hex[:8]
    return f"{os.path.splitext(base)[0]}_{uid}.wav"


def clean_old_files(older_than_seconds: int = 3600):
    """Remove files older than threshold in AUDIO_OUTPUT_DIR."""
    now = time.time()
    for fname in os.listdir(AUDIO_OUTPUT_DIR):
        path = os.path.join(AUDIO_OUTPUT_DIR, fname)
        try:
            if os.path.isfile(path) and (now - os.path.getmtime(path) > older_than_seconds):
                os.remove(path)
        except Exception:
            pass


# Spawn a background cleaner thread
def start_cleaner_thread():
    def loop():
        while True:
            try:
                clean_old_files(older_than_seconds=2 * 3600)  # 2 hours
            except Exception:
                pass
            time.sleep(600)
    t = threading.Thread(target=loop, daemon=True)
    t.start()


start_cleaner_thread()


# ---------- Models ----------
class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: Optional[int] = 256


class SpeakRequest(BaseModel):
    text: str
    filename: Optional[str] = None  # optional, will be generated if not provided
    # vocoder params could be added here (speaker id, speed, etc.)


# ---------- STT / Transcription ----------
# We lazy-load whisper model on first use to minimize startup time.
_whisper_model = None


def get_whisper_model():
    global _whisper_model
    if not WHISPER_AVAILABLE:
        raise RuntimeError("Whisper n'est pas installé. Installe 'openai-whisper' ou 'faster-whisper'.")
    if _whisper_model is None:
        print("Chargement du modèle Whisper:", MODEL_WHISPER)
        _whisper_model = whisper.load_model(MODEL_WHISPER)
    return _whisper_model


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """
    Upload a WAV/MP3 file and transcribe into text using Whisper (local).
    """
    if not WHISPER_AVAILABLE:
        raise HTTPException(status_code=500, detail="Whisper non présent sur le système. Installe 'openai-whisper' ou 'faster-whisper'.")

    # Save temp file
    suffix = os.path.splitext(file.filename)[1] or ".wav"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(tmp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        model = get_whisper_model()
        res = model.transcribe(tmp_path)
        text = res.get("text", "")
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur transcription: {e}")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# ---------- LLM generation ----------
def generate_response(prompt: str, max_tokens: int = 256) -> str:
    """
    Essaie d'appeler ollama CLI si dispo :
      ollama run <model> "<prompt>"
    Sinon fallback minimal.
    Remplace cette fonction par ton wrapper llama.cpp / text-generation-webui si besoin.
    """
    # If ollama is installed, use it.
    if shutil.which("ollama"):
        try:
            # Note: user should configure default model in ollama, or change parameters here.
            # We call: ollama run <model> "<prompt>"
            # For safety in shell quoting we pass via list and avoid shell=True.
            # If you want a certain model, change 'oobabooga/textgen' to your model id.
            # If ollama run supports --max-tokens, add it accordingly.
            cmd = ["ollama", "run", "oobabooga/textgen", prompt]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode == 0:
                out = proc.stdout.strip()
                if out:
                    return out
        except Exception as e:
            # fallthrough to fallback
            print("ollama error:", e)

    # Fallback: simple echo style / local deterministic reply
    # Replace by direct call to your local model server if you have one.
    fallback = f"(Fallback LLM) J'ai reçu : {prompt[:1000]}"
    return fallback


@app.post("/generate")
async def generate(req: GenerateRequest):
    try:
        text = generate_response(req.prompt, req.max_tokens or 256)
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur génération: {e}")


# ---------- TTS ----------
# Coqui TTS object lazy init
_coqui_tts = None


def get_coqui_tts():
    global _coqui_tts
    if not COQUI_TTS_AVAILABLE:
        raise RuntimeError("Coqui TTS non installé.")
    if _coqui_tts is None:
        # Load default or a user-provided model
        if TTS_MODEL_NAME:
            _coqui_tts = TTS(TTS_MODEL_NAME)
        else:
            _coqui_tts = TTS()  # will pick a default model
    return _coqui_tts


# pyttsx3 engine (if available)
_pyttsx3_engine = None
_pyttsx3_lock = threading.Lock()


def get_pyttsx3_engine():
    global _pyttsx3_engine
    if not PYTTSX3_AVAILABLE:
        raise RuntimeError("pyttsx3 non installé.")
    if _pyttsx3_engine is None:
        _pyttsx3_engine = pyttsx3.init()
    return _pyttsx3_engine


def tts_coqui_to_file(text: str, out_path: str):
    tts = get_coqui_tts()
    # TTS.tts_to_file method: (text, file_path)
    tts.tts_to_file(text=text, file_path=out_path)
    return out_path


def tts_pyttsx3_to_file(text: str, out_path: str):
    # pyttsx3 supports save_to_file
    engine = get_pyttsx3_engine()
    # run in separate thread because runAndWait blocks event loop
    def _save():
        with _pyttsx3_lock:
            engine.save_to_file(text, out_path)
            engine.runAndWait()
    t = threading.Thread(target=_save, daemon=True)
    t.start()
    t.join(timeout=30)  # wait up to 30s for synthesis
    # ensure file exists (pyttsx3 may not return immediately)
    if not os.path.exists(out_path):
        raise RuntimeError("pyttsx3 n'a pas généré le fichier audio.")
    return out_path


@app.post("/speak")
async def speak(req: SpeakRequest):
    """
    Generate a WAV audio file for the provided text.
    Returns: { "filename": "<name>" } where the file can be fetched from /audio/<filename>
    """
    if not req.text:
        raise HTTPException(status_code=400, detail="Le champ 'text' est vide.")

    fname_raw = req.filename or f"speech_{int(time.time())}.wav"
    fname = safe_filename(fname_raw)
    out_path = os.path.join(AUDIO_OUTPUT_DIR, fname)

    try:
        if COQUI_TTS_AVAILABLE:
            # Use coqui for higher quality
            tts_coqui_to_file(req.text, out_path)
        elif PYTTSX3_AVAILABLE:
            # Use pyttsx3 (offline) as fallback
            tts_pyttsx3_to_file(req.text, out_path)
        else:
            raise HTTPException(status_code=500, detail="Aucun moteur TTS disponible (installe Coqui TTS ou pyttsx3).")
        return {"filename": fname, "url": f"/audio/{fname}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur TTS: {e}")


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    # Security: avoid path traversal
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Nom de fichier invalide.")
    path = os.path.join(AUDIO_OUTPUT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Fichier audio introuvable.")
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type="audio/wav", filename=filename)


# ---------- Health & Info ----------
@app.get("/info")
async def info():
    info = {
        "whisper_available": WHISPER_AVAILABLE,
        "coqui_tts_available": COQUI_TTS_AVAILABLE,
        "pyttsx3_available": PYTTSX3_AVAILABLE,
        "ollama_installed": bool(shutil.which("ollama")),
        "audio_output_dir": AUDIO_OUTPUT_DIR,
    }
    return info


# ---------- CLI run convenience ----------
if __name__ == "__main__":
    import uvicorn
    print("Démarrage du backend local sur http://127.0.0.1:8000")
    uvicorn.run("app.server:app", host="127.0.0.1", port=8000, log_level="info", reload=False)

