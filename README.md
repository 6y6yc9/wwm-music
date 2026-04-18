# 🎵 WWM Music Auto-Player

Автоматический проигрыватель мелодий на музыкальных инструментах в игре **Where Winds Meet** (и подобных).  
Поддерживает импорт MIDI, загрузку с YouTube, AI-транскрипцию и 14 игровых инструментов.

*Automatic melody player for in-game instruments in **Where Winds Meet**. Supports MIDI import, YouTube download with AI transcription, and 14 in-game instruments.*

![Version](https://img.shields.io/badge/version-2.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## 🎯 Возможности / Features

| Функция | Описание |
|---------|----------|
| 🎹 **MIDI Import** | Импорт `.mid` файлов с выбором треков и гибкой конвертацией |
| 🔴 **YouTube Import** | Скачивание с YouTube → AI-транскрипция → автоматическая конвертация |
| 🔀 **Source Separation** | Разделение аудио на стемы (Demucs): вокал, мелодия, без ударных |
| 🎵 **Smart Melody** | AI-извлечение узнаваемой мелодии из многотрековых файлов |
| 🎼 **Smart Multi-Track** | Независимая транспозиция каждого трека для чистого звучания |
| 🥁 **Rhythm Filter** | Удаление шума с сохранением ритмического паттерна |
| 🎮 **Low-Level Input** | DirectInput scan codes — работает в играх с античитом |
| 📁 **55+ Ready Melodies** | Коллекция готовых мелодий (аниме, рок, поп, классика, и др.) |
| 🎻 **14 Instruments** | Guqin, Pipa, Erhu, Konghou, Xiao, Dizi, Suona, Hulusi, Xun, Guzheng, Fangxiang, Bianzhong, Ramskin Drum + Default Piano |

---

## ⚙️ Системные требования / Requirements

- **OS:** Windows 10/11 (используется Windows SendInput API)
- **Python:** 3.8+
- **FFmpeg:** необходим для YouTube-функций ([скачать](https://ffmpeg.org/download.html))

---

## 📦 Установка / Installation

### 1. Клонировать репозиторий

```bash
git clone https://github.com/YOUR_USERNAME/wwm-music.git
cd wwm-music
```

### 2. Установить зависимости

**Базовая установка** (MIDI + воспроизведение):
```bash
pip install -r requirements.txt
```

**Полная установка** (+ YouTube + AI-транскрипция + Source Separation):
```bash
pip install -r requirements-full.txt
```

> ⚠️ Полная установка включает PyTorch и Demucs (~2 GB). Если вам нужен только MIDI-импорт — достаточно базовой.

### 3. FFmpeg (для YouTube)

Если планируете использовать YouTube-импорт, установите [FFmpeg](https://ffmpeg.org/download.html) и добавьте его в PATH.

---

## 🚀 Запуск / Quick Start

**Способ 1: Двойной клик**
- Найдите файл `START.bat` и запустите его

**Способ 2: Командная строка**
```bash
cd path/to/wwm-music
python main.py
```

---

## 🎮 Использование / How to Use

### Импорт MIDI
1. Нажмите **🎹 Import MIDI** → выберите `.mid` файл
2. Выберите треки и настройте опции конвертации
3. Нажмите **▶ Play** → переключитесь в игру за 3 секунды
4. Убедитесь, что инструмент открыт в игре!

### Импорт с YouTube
1. Нажмите **🔴 YouTube** → вставьте ссылку
2. Выберите режим разделения (Vocals / Melody / Full No Drums)
3. Выберите пресет транскрипции
4. Дождитесь скачивания и AI-обработки
5. Мелодия загрузится автоматически

### Загрузка готовой мелодии
1. Нажмите **📁 Load Melody** → выберите `.txt` файл из `melodies/`
2. Нажмите **▶ Play**

> 📖 Подробная документация по всем опциям конвертации: [USAGE_GUIDE.md](USAGE_GUIDE.md)

---

## 🎹 Маппинг клавиш / Key Mapping

| Октава | Клавиши | Ноты |
|--------|---------|------|
| **High Pitch** | Q W E R T Y U | 1 2 3 4 5 6 7 |
| **Medium Pitch** | A S D F G H J | 1 2 3 4 5 6 7 |
| **Low Pitch** | Z X C V B N M | 1 2 3 4 5 6 7 |

---

## 📝 Формат мелодий / Melody Format

Мелодии хранятся в `.txt` файлах:

```
КЛАВИША ДЛИТЕЛЬНОСТЬ_МС [ПАУЗА_МС]
```

Пример:
```txt
# Twinkle Twinkle Little Star
A 400 100    # Нота A (Mid 1), играть 400мс, пауза 100мс
A 400 100
D 400 100    # Нота D (Mid 3)
D 400 100
F 800 0      # Нота F (Mid 4), играть 800мс
```

---

## 🛠️ Структура проекта / Project Structure

```
wwm-music/
├── main.py                 # GUI приложение (tkinter)
├── midi_converter.py       # Конвертер MIDI → текстовый формат
├── note_parser.py          # Парсер файлов мелодий
├── key_simulator.py        # Симулятор нажатий (pynput)
├── key_simulator_lowlevel.py  # Симулятор нажатий (DirectInput/SendInput)
├── playback_engine.py      # Движок воспроизведения с drift compensation
├── youtube_downloader.py   # Загрузка аудио с YouTube (yt-dlp)
├── audio_transcriber.py    # AI-транскрипция аудио → MIDI (Basic Pitch)
├── audio_separator.py      # Source separation (Demucs)
├── instruments.json        # Конфигурация 14 инструментов
├── requirements.txt        # Базовые зависимости
├── requirements-full.txt   # Полные зависимости (YouTube + AI)
├── START.bat               # Быстрый запуск (Windows)
├── melodies/               # 55+ готовых мелодий
├── tools/                  # Утилиты разработки
│   ├── analyze_key.py
│   ├── analyze_midi.py
│   ├── create_test_midi.py
│   └── debug_midi_range.py
├── USAGE_GUIDE.md          # Подробный гайд по опциям
├── HOW_TO_START.md         # Инструкция по запуску
├── LICENSE                 # MIT License
└── README.md               # Этот файл
```

---

## 🐛 Известные ограничения / Known Limitations

- **Только Windows** — используется Windows SendInput API для совместимости с играми
- Минимальная длительность ноты: ~50мс
- YouTube-транскрипция требует FFmpeg в PATH
- Source Separation (Demucs) требует ~2 GB дополнительных зависимостей

---

## 🤝 Тестирование / Testing

Нашли баг? Есть идея? Создайте [Issue](../../issues) с описанием:
1. Что вы делали (шаги для воспроизведения)
2. Что ожидали
3. Что произошло на самом деле
4. Скриншот / текст ошибки

---

## 📄 Лицензия / License

[MIT License](LICENSE) — используйте свободно! 🎉
