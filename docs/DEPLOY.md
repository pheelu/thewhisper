# Deploy — The Whisper (Render + Supabase)

Architettura di produzione (evento singolo, minima manutenzione):

```
[ Browser PWA ] ──HTTPS──> [ Render: 1 web service Docker ]
                              ├─ FastAPI (API + WebSocket)
                              └─ serve la PWA buildata (single origin)
                                     │
                         ┌───────────┴───────────┐
                   [ Supabase Postgres ]   [ Supabase Storage (foto) ]
```

- **Un solo servizio** su Render (Docker) che serve sia le API sia la PWA → un URL, un certificato HTTPS, nessun problema di cookie/CORS.
- **Dati su Supabase**: Postgres (con backup) + Storage S3-compatibile per le foto.
- **HTTPS automatico** (necessario: la fotocamera nel browser funziona solo in HTTPS).

---

## 1. Supabase (dati)

1. Crea un progetto su <https://supabase.com> (regione **EU**, es. Frankfurt, per GDPR). Salva la **password del database**.
2. **Connection string** — *Project Settings → Database → Connection string*:
   - Scegli **Session pooler** (porta `5432`) — supporta i prepared statement, nessuna config extra.
   - Copia la stringa e trasformala per asyncpg sostituendo il prefisso:
     ```
     postgresql+asyncpg://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres
     ```
     → questo è il valore di **`DATABASE_URL`**.
   - *(Se preferisci il **Transaction pooler**, porta `6543`: allora imposta anche `DB_DISABLE_PREPARED_STATEMENTS=true`.)*
3. **Storage** — *Storage → New bucket*: nome **`whisper-photos`**, **Private**.
4. **Chiavi S3** — *Project Settings → Storage → S3 Access Keys → New access key*. Annota `access key` e `secret`. L'endpoint è:
   ```
   https://<ref>.supabase.co/storage/v1/s3
   ```
   La **region** è quella del progetto (es. `eu-central-1`).
5. **CORS del bucket** (serve per l'upload diretto dal browser): in *Storage → Policies/Settings* consenti `PUT`/`GET` dall'origine del tuo sito Render (`https://the-whisper.onrender.com`).
   *Se l'upload dal browser viene bloccato dalla CORS, si passa in 10 minuti a un upload lato server (proxy) — chiedimelo.*

Env risultanti da Supabase:
| Variabile | Valore |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres.<ref>:<pwd>@...pooler.supabase.com:5432/postgres` |
| `S3_ENDPOINT_URL` | `https://<ref>.supabase.co/storage/v1/s3` |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | dalle S3 Access Keys |
| `S3_BUCKET` | `whisper-photos` |
| `S3_REGION` | es. `eu-central-1` |
| `S3_PUBLIC_URL` | `https://<ref>.supabase.co/storage/v1/object/public/whisper-photos` |

---

## 2. Render (compute)

1. Vai su <https://render.com> → **New → Blueprint** e collega il repo GitHub `pheelu/thewhisper`. Render legge [`render.yaml`](../render.yaml) e crea il web service.
2. Nella dashboard del servizio, **Environment**, imposta le variabili `sync: false` (quelle prese da Supabase al punto 1). `SECRET_KEY` è generata da Render, `SESSION_COOKIE_SECURE=true` è già impostata.
3. **Deploy**. Il container, all'avvio, applica le migrazioni (`alembic upgrade head`) e avvia il server. Il primo build richiede qualche minuto.
4. Apri l'URL (`https://the-whisper.onrender.com`) → vedi la landing. Verifica `…/health` → `{"status":"ok"}` e `…/docs` per le API.

> **Custom domain / QR**: puoi collegare un dominio in *Settings → Custom Domains*. Il QR della serata punterà a quell'URL (`https://tuodominio/j/<codice>`).

---

## 3. Uso e manutenzione

- **Aggiornare l'app**: `git push` su `main` → Render ridispiega da solo (le migrazioni girano automaticamente).
- **Backup**: automatici su Supabase (piano free: point-in-time limitato; per eventi importanti fai un dump manuale da *Database → Backups*).
- **Retention/GDPR**: i dati di una serata sono già progettati per essere cancellati dopo l'evento (job di retention). Le foto stanno sotto `events/{event_id}/...` così il purge le raggiunge tutte.
- **Costi**: piano free per uso occasionale ≈ 0 €. Nota: sul free tier **Render** e **Supabase** vanno in pausa dopo inattività e si risvegliano da soli (qualche secondo di attesa al primo accesso). Per una serata importante, valuta il piano Starter (~7 €/mese) per evitare il cold start.

## 4. Troubleshooting rapido
- **Errore prepared statement / `DuplicatePreparedStatement`** → stai usando il Transaction pooler: imposta `DB_DISABLE_PREPARED_STATEMENTS=true` (oppure passa al Session pooler).
- **La fotocamera non parte** → serve HTTPS (Render lo dà; su dominio custom attendi l'emissione del certificato).
- **Upload foto bloccato (CORS)** → configura la CORS del bucket (punto 1.5) o passa all'upload lato server.
- **La PWA non si aggiorna** → è un service worker: hard refresh o attendi l'auto-update.
