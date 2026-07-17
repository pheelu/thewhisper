# The Whisper 🎭

> Il Gioco del Mistero e del Corteggiamento — un social game real-time per aperitivi ed eventi, in stile *Bridgerton*.

Il locale diventa un salotto dell'alta società: i partecipanti sono **nobili**, i pettegolezzi sono **Whispers**. Si entra scansionando un QR, si sceglie un titolo nobiliare e un segreto, si scattano foto misteriose (solo a chi acconsente), si prova a indovinare i "Soggetti", si scommette e ci si scambia missive segrete.

## Stack

| Livello    | Tecnologia                                             |
|------------|--------------------------------------------------------|
| Frontend   | React + Vite, PWA mobile-first                         |
| Backend    | FastAPI (Python 3.14, async), gestito con **uv**       |
| Database   | PostgreSQL (SQLAlchemy async + Alembic)                |
| Realtime   | WebSocket (per-evento)                                 |
| Storage    | S3-compatibile (MinIO in dev)                          |
| Scheduler  | APScheduler (scommesse orarie, gazzettino)             |

## Principi

- **Accesso per-evento**: QR code + pseudonimo. Nessun account permanente; la sessione vive nel contesto di un evento.
- **Consenso opt-in totale**: si può fotografare *solo* chi ha accettato di essere fotografabile. GDPR-first.
- **Clean architecture**: ogni dominio ha `core/` (logica di dominio pura) e `infrastructure/` (I/O, persistenza). Le dipendenze puntano verso l'interno.

## Domìni

`profiles` · `whispers` · `discovery` · `messaging` · `bets` · `gamification` · `gazette` · `moderation`

## Sviluppo locale

```bash
# 1. Infrastruttura (Postgres + MinIO)
cp .env.example .env
docker compose up -d

# 2. Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# 3. Frontend
cd frontend
npm install
npm run dev
```

Documentazione di progetto in [`docs/`](./docs).

---
🤖 Generated with [Claude Code](https://claude.com/claude-code)
