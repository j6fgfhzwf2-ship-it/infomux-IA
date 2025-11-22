# AiSphere - Infomux-IA

## Installation

```bash
git clone https://github.com/j6fgfhzwf2-ship-it/infomux-IA.git
cd infomux-IA
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
Lancer le backend
python3 app/server.py
Lancer l'interface GUI
pyinstaller pyinstaller.spec   # Compile la .app
open dist/AiSphere.app         # Ouvre l'application sur macOS
Notes
Place ton modèle GGUF dans models/your-model.gguf
La sphère animée change de couleur rose-bleu-blanc
Fonctionne entièrement local

---

Avec ces fichiers, ton projet sur GitHub sera **prêt pour compiler l’application** sur ton Mac.  

Si tu veux, je peux maintenant te **donner le workflow GitHub Actions complet** pour que chaque release génère automatiquement les fichiers `.app` / `.exe` / `.AppImage`.  

Veux‑tu que je fasse ça ?
