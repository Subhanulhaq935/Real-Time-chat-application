# 💬 Real-Time Chat Application

A modern, responsive real-time 1-on-1 chatting platform built with **FastAPI**, **PostgreSQL (Neon)**, **WebSockets**, and **React (Vite)**. Features a WhatsApp-inspired dark interface, live typing/messaging, single & double blue ticks read receipts, and private contact management.

---

## 🚀 Key Features

- **Real-Time Bidirectional Messaging**: Sub-millisecond messaging via WebSockets with persistent PostgreSQL storage.
- **WhatsApp-Style Read Receipts**:
  - `✓` Single gray tick: Message sent/delivered.
  - `✓✓` Double cyan/blue tick: Seen/read in real-time.
- **Live Unread Badges**: Real-time unread message counter pills (`1`, `2`, `3`...) on the sidebar that update without page reload.
- **Private Contacts & Aliases**: Search registered users by email and assign private custom names invisible to others.
- **Full Responsiveness**: Seamless transitions between mobile full-screen view (with `←` back arrow navigation), tablet split-screen, and desktop layouts.
- **Secure Authentication**:
  - Email verification with HMAC-SHA256 6-digit OTP delivered via Gmail SMTP.
  - JWT tokens with `jti` revocation tracking and HttpOnly cookie support.
  - Eye toggle password visibility on signup and login.
- **Layered Architecture**: Decoupled repository, service, and router patterns with full Alembic migration history.

---

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.13)
- **Database**: PostgreSQL (Neon Serverless DB)
- **ORM & Migrations**: SQLAlchemy 2.0 & Alembic
- **Real-Time**: Native WebSockets with custom `ConnectionManager` (room + user streams)
- **Security**: Passlib (Bcrypt), PyJWT, Pydantic v2
- **Email Service**: Python `smtplib` + Gmail TLS

### Frontend
- **Framework**: React 18 + Vite
- **Routing**: React Router DOM v6
- **Styling**: Vanilla CSS with modern WhatsApp Dark aesthetic & responsive design
- **State Management**: React Context (`AuthContext`)

---

## 📂 Project Structure

```text
├── Backend/
│   ├── alembic/              # Database migration versions
│   ├── app/
│   │   ├── core/             # Configuration, security, dependencies
│   │   ├── db/               # SQLAlchemy engine & session
│   │   ├── models/           # User, OTP, Conversation, Message, Contact
│   │   ├── repositories/     # Data access layer
│   │   ├── routers/          # REST & WebSocket API endpoints
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # Business logic (Auth, Chat, Contacts, Email)
│   │   └── websockets/       # ConnectionManager & broadcasting
│   ├── tests/                # Automated pytest test suite
│   ├── requirements.txt      # Python dependencies
│   └── .env.example          # Backend environment template
│
├── Frontend/
│   ├── public/               # Favicons, webmanifest
│   ├── src/
│   │   ├── api/              # Axios HTTP & REST clients
│   │   ├── components/       # Navbar, ProtectedRoute, Modals
│   │   ├── context/          # AuthContext
│   │   ├── pages/            # Chat, Dashboard, Login, Signup, Status
│   │   ├── App.css           # Responsive chat & dashboard styles
│   │   └── App.jsx           # App shell and routing
│   ├── package.json          # Frontend dependencies
│   └── vite.config.js        # Vite & PWA configuration
└── README.md
```

---

## ⚡ Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/Subhanulhaq935/Real-Time-chat-application.git
cd Real-Time-chat-application
```

### 2. Backend Setup
```bash
cd Backend
python -m venv .venv

# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Fill in your DATABASE_URL, SECRET_KEY, and SMTP credentials in .env

# Run database migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Frontend Setup
```bash
cd ../Frontend
npm install
npm run dev
```

Visit `http://localhost:5173` to start chatting!

---

## 🧪 Testing

Run backend automated test suite:
```bash
cd Backend
pytest -v
```

