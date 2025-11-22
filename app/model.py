# app/model.py
# Interface simple pour appeler un LLM local.
import shutil
import subprocess
import typing

def generate_response(prompt: str, max_tokens: int = 256) -> str:
# Try ollama
if shutil.which('ollama'):
try:
proc = subprocess.run(['ollama','run','oobabooga/textgen', prompt], capture_output=True, text=True, timeout=60)
if proc.returncode==0 and proc.stdout.strip():
return proc.stdout.strip()
except Exception:
pass
# Fallback simple
return f"(fallback) J'ai reçu : {prompt}"
