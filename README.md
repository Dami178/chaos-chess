# ♚ Chaos Chess

> Шахматы с динамическими правилами, управляемыми ИИ (Groq / OpenAI)

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)
![License](https://img.shields.io/badge/License-MIT-purple)

---

## 🚀 Быстрый старт (локально)

### 1. Клонировать репозиторий

```bash
git clone <your-repo-url>
cd chaos-chess
```

### 2. Создать виртуальное окружение и установить зависимости

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Настроить переменные окружения

Создайте файл `.env` в папке `backend/` (или экспортируйте переменные):

```env
# Для Groq (рекомендуется — бесплатный тариф):
GROQ_API_KEY=gsk_...

# ИЛИ для OpenAI:
OPENAI_API_KEY=sk-...

# Опционально — модель LLM:
LLM_MODEL=llama-3.3-70b-versatile
```

> **Без ключей** приложение работает с упрощённым парсером ключевых слов — ИИ не используется, но базовые правила меняются.

### 4. Запустить сервер

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Откройте браузер: **http://localhost:8000**

---

## 🐳 Docker

```bash
# Из корня проекта:
docker build -t chaos-chess .

docker run -p 8000:8000 \
  -e GROQ_API_KEY=gsk_... \
  chaos-chess
```

---

## ☁️ Деплой на Render.com

1. Создайте новый сервис **Web Service → Deploy from Git**
2. Укажите **Dockerfile** как Runtime
3. В разделе **Environment** добавьте секреты:
   - `GROQ_API_KEY` или `OPENAI_API_KEY`
4. Используйте `render.yaml` для автоматической конфигурации

---

## 🎮 Как играть

1. **Укажите лимит изменений** правил (по умолчанию: 3)
2. **Нажмите «Начать партию»**
3. **Делайте ходы** перетаскиванием фигур
4. **Меняйте правила** — введите запрос на русском или английском, например:
   - *"Запрети рокировку"*
   - *"Пешки могут ходить только на захват"*
   - *"Все пешки превращаются в коней"*
   - *"No castling and capture only"*

---

## 📂 Структура проекта

```
chaos-chess/
├── backend/
│   ├── main.py          # FastAPI + WebSocket сервер
│   ├── engine.py        # Игровой движок (chess.Board + правила)
│   ├── rule_manager.py  # LLM интеграция (Groq / OpenAI)
│   └── requirements.txt
├── frontend/
│   └── index.html       # SPA (chessboard.js + WebSocket клиент)
├── Dockerfile           # Multi-stage Docker build
├── render.yaml          # Render.com deployment config
└── README.md
```

---

## 🧩 Поддерживаемые правила

| Ключ | Тип | Описание |
|------|-----|----------|
| `allow_castling` | bool | Разрешить/запретить рокировку |
| `allow_en_passant` | bool | Взятие на проходе |
| `allow_promotion` | bool | Превращение пешки |
| `promotion_piece` | str | Фигура для превращения (`queen`, `rook`, `bishop`, `knight`) |
| `pawn_double_move` | bool | Двойной ход пешки |
| `capture_only` | bool | Только взятия |
| `inverse_colors` | bool | Инверсия цветов |
| `extra_description` | str | Описание правил от ИИ |

---

## 🛠️ Технологии

- **Backend**: Python 3.12, FastAPI, python-chess, openai SDK, uvicorn
- **Frontend**: HTML5, Vanilla JS, chessboard.js, chess.js, jQuery
- **AI**: Groq API (llama-3.3-70b) / OpenAI API

---

## 📄 Лицензия

MIT — свободно для личного и коммерческого использования.
