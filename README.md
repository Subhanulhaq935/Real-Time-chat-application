# 💬 PulseChat — Real-Time Chat Application

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React_18-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite_6-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![WebSockets](https://img.shields.io/badge/WebSockets-010101?style=for-the-badge&logo=socketdotio&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
[![PWA](https://img.shields.io/badge/PWA_Ready-5A0FC8?style=for-the-badge&logo=pwa&logoColor=white)](https://web.dev/progressive-web-apps/)

A high-performance, full-stack, WhatsApp-inspired 1-on-1 real-time messaging platform. Engineered with **FastAPI**, **PostgreSQL (Neon)**, **WebSockets**, and **React 18 (Vite)**. Features instant 0ms offline-first caching, live read receipts, voice notes, emoji reactions, message editing & deletion, global online/last seen status, in-chat search, and Dark/Light themes.

---

## 🌐 Live Deployment

| Service | Platform | URL |
| :--- | :--- | :--- |
| **Frontend Application** | Vercel | [Live App](https://real-time-chat-application-subhanulhaq935-gmailcoms-projects.vercel.app) |
| **Backend REST & WS API** | Render | [API Service](https://chat-backend-9mbl.onrender.com) |
| **Interactive API Docs** | Swagger UI | [Swagger Docs](https://chat-backend-9mbl.onrender.com/docs) |
| **Health Check** | Render | [Health Endpoint](https://chat-backend-9mbl.onrender.com/health) |

---

## ✨ Features

### ⚡ 1. Ultra-Fast Instant Chatting (0ms Loading)
- **Offline-First Persistent Cache**: Conversation lists and message histories hydrate immediately (`0.00ms`) from `localStorage` upon page load or conversation click.
- **Stale-While-Revalidate**: Network requests run silently in the background to sync new updates without blocking spinners.
- **Optimistic UI**: Sent messages appear on screen instantly before server confirmation.
- **Multi-Chat Warmup**: Prefetches recent conversation histories in the background.

### 🎙️ 2. Voice Notes (Voice Messages)
- **In-Chat Audio Recorder**: Record voice notes directly from the input bar with live elapsed timer, blinking recording indicator, and one-tap send/cancel.
- **Custom Waveform Player**: Sleek voice player with play/pause, seekable progress slider, duration readout, and variable speed control (`1x`, `1.5x`, `2x`).
- **Blob Streaming**: Handles mobile-compatible media playback safely.

### 👍 3. Emoji Reactions & Long Press
- **WhatsApp-Style Long Press / Double Click**: Touch & hold (450ms with mobile haptic feedback) or double-click to summon the quick reaction bar (`👍`, `❤️`, `😂`, `😮`, `😢`, `🙏`).
- **Reaction Pills & Tooltips**: Aggregated reaction badges on message bubbles showing count and user names.
- **Multiple Ways to Remove Reaction**: Tap the reaction pill, re-click the active emoji, or select "Remove React" from the message menu.

### ✏️ 4. Message Edit & Delete
- **Inline Message Editing**: Edit sent text messages with real-time propagation and `(edited)` indicator tag.
- **Delete for Everyone**: Permanently revoke messages for all chat participants in real time.
- **Delete for Me**: Privately remove messages from your personal view while keeping them intact for the other person.
- **Glassmorphic 3-Dots Menu**: WhatsApp Web-style dropdown card with smart upward/downward collision detection.

### 🟢 5. Online Status & "Last Seen"
- **Real-Time Presence**: Track whether contacts are actively `Online` with live pulsing status indicators.
- **Detailed Timestamps**: Formatted last seen readouts (e.g., *"Last seen today at 5:15 PM"*, *"Last seen yesterday at 11:30 AM"*).
- **Live "Typing..." Indicators**: Shows pulsing typing alerts in both the chat header and the conversations sidebar.

### 🔍 6. In-Chat Message Search
- **Instant Search**: Search conversation history for specific words or phrases.
- **Keyword Highlighting & Navigation**: Highlights all matches inside bubbles and provides `↑` and `↓` jump navigation with a live match counter.

### 🎨 7. Modern UI / UX & PWA
- **Dark & Light Mode**: Toggle between WhatsApp dark theme (`#111b21`, `#202c33`) and clean light mode.
- **Installable PWA**: Install PulseChat as a native desktop or mobile app with offline service workers.
- **Fully Responsive**: Optimized for phones (drawer layout with back navigation), tablets, and widescreen desktop monitors.

### 🔐 8. Security & Authentication
- **Email Verification via OTP**: 6-digit HMAC-SHA256 one-time password delivered via Gmail SMTP.
- **JWT Authentication**: Secure Bearer tokens with `jti` revocation tracking and protected routes.
- **Private Aliases**: Add contacts by email and assign custom display names visible only to you.

---

## 🛠️ Tech Stack & Architecture

```mermaid
flowchart LR
    subgraph Client["Frontend (React 18 + Vite)"]
        UI["UI / PWA Shell"]
        Cache[("LocalStorage Cache")]
        WSClient["WebSocket Client"]
        Axios["Axios REST Client"]
    end

    subgraph Server["Backend (FastAPI)"]
        Router["API Routers"]
        Auth["JWT & OTP Auth"]
        WSManager["WebSocket ConnectionManager"]
        Service["Chat & Contact Services"]
        Repo["SQLAlchemy Repositories"]
    end

    subgraph Database["Database"]
        PG[("PostgreSQL (Neon)")]
    end

    UI <--> Cache
    UI <--> WSClient
    UI <--> Axios

    Axios --> Router
    WSClient <--> WSManager
    Router --> Service
    WSManager --> Service
    Service --> Repo
    Repo --> PG
```

### Backend
- **Framework**: FastAPI (Python 3.13)
- **Database**: PostgreSQL (Neon Serverless DB)
- **ORM & Migrations**: SQLAlchemy 2.0 + Alembic
- **Real-Time**: Native WebSockets with custom room & user-level `ConnectionManager`
- **Security**: Passlib (Bcrypt), PyJWT, Pydantic v2
- **Email Delivery**: Python `smtplib` + Gmail TLS

### Frontend
- **Framework**: React 18 + Vite
- **Routing**: React Router DOM v6
- **Styling**: Vanilla CSS3 (Custom design system, glassmorphism, responsive grid & flexbox)
- **State & Caching**: React Context (`AuthContext`, `ThemeContext`) + LocalStorage
- **PWA**: `vite-plugin-pwa` with Workbox service workers

---

## 📂 Project Directory Structure

```text
├── Backend/
│   ├── alembic/                  # Database migration scripts
│   ├── app/
│   │   ├── core/                 # App configuration, security, dependencies
│   │   ├── db/                   # SQLAlchemy engine & session factory
│   │   ├── models/               # User, OTP, Conversation, Message, Contact
│   │   ├── repositories/         # Database access layer
│   │   ├── routers/              # REST endpoints & WebSocket handlers
│   │   ├── schemas/              # Pydantic request/response models
│   │   ├── services/             # Business logic (Auth, Chat, Contacts, Email)
│   │   └── websockets/           # Live connection manager & broadcast pipelines
│   ├── tests/                    # Pytest automated test suite
│   ├── requirements.txt          # Python dependencies
│   └── .env.example              # Backend environment configuration template
│
├── Frontend/
│   ├── public/                   # Favicons, webmanifest, PWA icons
│   ├── src/
│   │   ├── api/                  # Axios HTTP client & REST modules
│   │   ├── components/           # AudioPlayer, MessageMenu, Reactions, VoiceBar, Navbar
│   │   ├── context/              # AuthContext & ThemeContext
│   │   ├── pages/                # Chat, Dashboard, Login, Signup, Status
│   │   ├── App.css               # Design system & responsive styles
│   │   └── App.jsx               # App shell and routing table
│   ├── package.json              # Frontend dependencies
│   └── vite.config.js            # Vite bundler & PWA configuration
└── README.md
```

---

## 🚀 Getting Started Locally

### Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- PostgreSQL database (or free [Neon](https://neon.tech) database)

---

### 1. Backend Setup

```bash
cd Backend

# Create and activate virtual environment
python -m venv .venv

# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

Edit `.env` with your credentials:
```env
DATABASE_URL=postgresql://user:password@ep-host.neon.tech/neondb?sslmode=require
SECRET_KEY=your_super_secret_jwt_key
ACCESS_TOKEN_EXPIRE_MINUTES=1440
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
EMAIL_FROM=your_email@gmail.com
ALLOWED_ORIGINS=http://localhost:5173
```

Run database migrations and start the server:
```bash
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend will be running at `http://127.0.0.1:8000` (Docs: `http://127.0.0.1:8000/docs`).

---

### 2. Frontend Setup

Open a new terminal window:
```bash
cd Frontend

# Install dependencies
npm install

# Configure environment variables
cp .env.example .env
```

Verify `Frontend/.env`:
```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_WS_BASE_URL=ws://127.0.0.1:8000
```

Start the Vite development server:
```bash
npm run dev
```

Visit `http://localhost:5173` to test the application!

---

## 🧪 Testing

Run backend tests using `pytest`:
```bash
cd Backend
pytest -v
```

Build frontend for production:
```bash
cd Frontend
npm run build
```

---

## 📄 License

This project is licensed under the MIT License.
