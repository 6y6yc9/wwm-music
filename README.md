# 🎵 WWM Music Auto-Player

Automatic melody player for in-game instruments in **Where Winds Meet** (and similar games).  
Supports MIDI import, YouTube download with AI transcription, and 14 in-game instruments.

*Автоматический проигрыватель мелодий для игры **Where Winds Meet**. Поддерживает импорт MIDI, скачивание с YouTube с AI-транскрипцией и 14 игровых инструментов. (См. русскую версию характеристик ниже).*

![Version](https://img.shields.io/badge/version-2.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-orange)

WWM Music player ([download](https://github.com/6y6yc9/wwm-music/releases/tag/v2.0))
If you don’t know how to use GitHub, download the app here:
Google drive ([download](https://drive.google.com/file/d/1PQiYP-RzxFrKrhgLiB_wP2zXPAb-5gGw/view?usp=drive_link))
---

## 🎯 Features

| Feature | Description |
|---------|----------|
| 🎹 **MIDI Import** | Import `.mid` files with track selection and flexible conversion |
| 🔴 **YouTube Import** | Download from YouTube → AI transcription → auto conversion |
| 🔀 **Source Separation** | Audio stem separation (Demucs): vocals, melody, no drums |
| 🎵 **Smart Melody** | AI extraction of recognizable melodies from multi-track files |
| 🎼 **Smart Multi-Track** | Independent transposition of each track for clean playback |
| 🥁 **Rhythm Filter** | Noise reduction while preserving rhythmic patterns |
| 🎮 **Low-Level Input** | DirectInput scan codes — works in games with anti-cheat |
| 📁 **55+ Ready Melodies** | Pre-bundled melodies (anime, rock, pop, classical, etc.) |
| 🎻 **14 Instruments** | Guqin, Pipa, Erhu, Konghou, Xiao, Dizi, Suona, Hulusi, Xun, Guzheng, Fangxiang, Bianzhong, Ramskin Drum + Default Piano |

---

## ⚙️ Requirements

- **OS:** Windows 10/11 (uses Windows SendInput API)
- **Python:** 3.8+
- **FFmpeg:** Required for YouTube features ([download](https://ffmpeg.org/download.html))

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/wwm-music.git
cd wwm-music
```

### 2. Install dependencies

**Basic Installation** (MIDI + Playback only):
```bash
pip install -r requirements.txt
```

**Full Installation** (+ YouTube + AI Transcription + Source Separation):
```bash
pip install -r requirements-full.txt
```

> ⚠️ Full installation includes PyTorch and Demucs (~2 GB). If you only need MIDI import, the basic installation is sufficient.

### 3. FFmpeg (for YouTube)

If you plan to use YouTube import, install [FFmpeg](https://ffmpeg.org/download.html) and add it to your system PATH.

---

## 🚀 Quick Start

**Method 1: Double-click**
- Find the `START.bat` file and run it.

**Method 2: Command Line**
```bash
cd path/to/wwm-music
python main.py
```

---

## 🎮 How to Use

### MIDI Import
1. Click **🎹 Import MIDI** → select a `.mid` file
2. Select tracks and adjust conversion options
3. Click **▶ Play** → switch to the game window within 3 seconds
4. Ensure your instrument is open in-game!

### YouTube Import
1. Click **🔴 YouTube** → paste the link
2. Select separation mode (Vocals / Melody / Full No Drums)
3. Choose transcription preset
4. Wait for download and AI processing
5. The melody will load automatically

### Load Ready Melody
1. Click **📁 Load Melody** → choose a `.txt` file from `melodies/`
2. Click **▶ Play**

> 📖 Detailed documentation for conversion options: [USAGE_GUIDE.md](USAGE_GUIDE.md)

---

## 🎹 Key Mapping

| Octave | Keys | Notes |
|--------|---------|------|
| **High Pitch** | Q W E R T Y U | 1 2 3 4 5 6 7 |
| **Medium Pitch** | A S D F G H J | 1 2 3 4 5 6 7 |
| **Low Pitch** | Z X C V B N M | 1 2 3 4 5 6 7 |

---

## 📝 Melody Format

Melodies are stored in `.txt` files:

```
KEY DURATION_MS [PAUSE_MS]
```

Example:
```txt
# Twinkle Twinkle Little Star
A 400 100    # Note A (Mid 1), play 400ms, pause 100ms
A 400 100
D 400 100    # Note D (Mid 3)
D 400 100
F 800 0      # Note F (Mid 4), play 800ms
```

---

## 🛠️ Project Structure

```
wwm-music/
├── main.py                 # GUI application (tkinter)
├── midi_converter.py       # Converter MIDI → text format
├── note_parser.py          # Melody file parser
├── key_simulator.py        # Key simulator (pynput)
├── key_simulator_lowlevel.py  # Key simulator (DirectInput/SendInput)
├── playback_engine.py      # Playback engine with drift compensation
├── youtube_downloader.py   # YouTube audio downloader (yt-dlp)
├── audio_transcriber.py    # AI transcription audio → MIDI (Basic Pitch)
├── audio_separator.py      # Source separation (Demucs)
├── instruments.json        # Configuration for 14 instruments
├── requirements.txt        # Basic dependencies
├── requirements-full.txt   # Full dependencies (YouTube + AI)
├── START.bat               # Quick launcher (Windows)
├── melodies/               # 55+ ready melodies
├── tools/                  # Development scripts
│   ├── analyze_key.py
│   ├── analyze_midi.py
│   ├── create_test_midi.py
│   └── debug_midi_range.py
├── USAGE_GUIDE.md          # Detailed options guide
├── HOW_TO_START.md         # Troubleshooting & startup guide
├── LICENSE                 # MIT License
└── README.md               # This file
```

---

## 🐛 Known Limitations

- **Windows only** — Uses Windows SendInput API for game compatibility
- Minimum note duration: ~50ms
- YouTube transcription requires FFmpeg in PATH
- Source Separation (Demucs) requires ~2 GB of additional dependencies

---

## 🤝 Testing & Bug Reports

Found a bug? Have an idea? Create an [Issue](../../issues) describing:
1. Steps to reproduce
2. Expected behavior
3. Actual behavior
4. Screenshot / text of the error

---

## 🇷🇺 Русское описание (Russian Description)

Автоматический проигрыватель мелодий на музыкальных инструментах в игре **Where Winds Meet** (и подобных).
Приложение переводит MIDI-файлы или скачанные видео с YouTube в нажатия кнопок на клавиатуре.

**Ключевые особенности:**
- **Импорт MIDI:** детальная настройка треков, квантизация 1/16, арпеджиатор аккордов.
- **Импорт YouTube:** скачивание звука, разделение аудиодорожек с помощью AI (Demucs) и перевод в ноты (Basic Pitch).
- **Smart Melody & Smart Multi-Track:** автоматическое улучшение звучания полифонических мелодий и независимая транспозиция дорожек.
- **14 Инструментов:** адаптировано под реальные игровые частоты (Гуцинь, Пипа, Эрху, Дизи, и др.).
- **Обход античитов:** используется низкоуровневый `SendInput API` (DirectInput scan codes).

**Как запустить:**
Запустите `START.bat` или введите в консоли `python main.py`. См. `HOW_TO_START.md` для решения проблем с установкой и `USAGE_GUIDE.md` для описания полного функционала.

---

## 📄 License

[MIT License](LICENSE) — use freely! 🎉
