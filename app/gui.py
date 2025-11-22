ort queue
import numpy as np
import sounddevice as sd
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QBrush, QRadialGradient, QColor
import requests
import time

SAMPLE_RATE = 16000
BLOCK_SECONDS = 0.2
RECORD_SECONDS = 4.0
COLOR_PINK = (255,95,153)
COLOR_BLUE = (95,165,255)
COLOR_WHITE = (255,255,255)

audio_q = queue.Queue()

def audio_callback(indata, frames, time_info, status):
if status: pass
audio_q.put(indata.copy())

class SphereWidget(QWidget):
def __init__(self):
super().__init__()
self.setMinimumSize(420,420)
self.base_radius = 140.0
self.pulse = 0.0
self.rms = 0.0
self.tick = 0.0
try:
sd.default.samplerate = SAMPLE_RATE
sd.default.channels = 1
self.stream = sd.InputStream(callback=audio_callback, blocksize=int(SAMPLE_RATE*BLOCK_SECONDS))
self.stream.start()
except Exception as e:
print('micro non dispo:', e)
self.stream = None
self.timer = QTimer()
self.timer.timeout.connect(self.on_tick)
self.timer.start(50)
def on_tick(self):
rms = 0.0
count = 0
while not audio_q.empty():
block = audio_q.get()
arr = block.flatten()
rms += np.mean(np.square(arr))
count += 1
if count:
rms = np.sqrt(rms/count)
self.rms = max(0.0, self.rms*0.85 + float(rms)*0.15)
self.tick += 0.05
breathe = (np.sin(self.tick)+1.0)/2.0
target = min(1.0, breathe*0.8 + self.rms*20.0)
self.pulse = self.pulse*0.8 + target*0.2
self.update()

