# The Whisper — Foundation Tecnica Cross-Cutting

> Documento AUTOREVOLE e VINCOLANTE. Ogni agente di dominio DEVE essere coerente con quanto qui definito. In caso di conflitto tra questo documento e una scelta di dominio, prevale questo documento. Le estensioni di dominio sono ammesse solo se additive e non contraddittorie.

**Stack vincolante:** FastAPI (uv) · Python 3.14 async · PostgreSQL (SQLAlchemy async + Alembic) · WebSocket · S3-compatibile (MinIO in dev) · React + Vite PWA · Accesso QR per-evento + pseudonimo, nessun account permanente.

**Gli 8 domini** poggiano su questa foundation. Nomi canonici usati nel documento: `identity` (foundation: Event/Participant/auth), `profile`, `photo` (Foto Whisper + feed), `discovery` (commenti/indovinelli/scoperta), `dialogue` (chat/inviti/missive), `betting` (scommesse), `gamification` (punti/titoli/premi), `gazette` (gazzettino), `moderation`. La foundation qui descritta vive nel package tecnico condiviso `shared/` + dominio `identity/`.

---

## 1. Struttura cartelle del monorepo

```
the-whisper/
├── README.md
├── docker-compose.yml              # postgres, minio, backend, frontend (dev)
├── .env.example
├── pyproject.toml                  # gestito con uv (workspace)
├── uv.lock
│
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── migrations/                 # Alembic UNICO per tutto il backend
│   │   ├── env.py
│   │   └── versions/
│   │
│   └── src/
│       └── whisper/
│           ├── main.py             # crea FastAPI app, monta i router di dominio, lifespan
│           ├── settings.py         # pydantic-settings, unica sorgente di config/env
│           │
│           ├── shared/             # === FOUNDATION CROSS-CUTTING (no logica di dominio) ===
│           │   ├── core/
│           │   │   ├── entity.py           # BaseEntity (dataclass): id, created_at, updated_at
│           │   │   ├── enums.py            # enum condivisi (EventStatus, ParticipantRole, PointReason...)
│           │   │   ├── errors.py           # gerarchia DomainError + mapping HTTP
│           │   │   ├── clock.py            # Clock protocol (now() aware UTC) — no datetime.now() sparsi
│           │   │   ├── ids.py              # generazione uuid7
│           │   │   └── pagination.py       # Page[T], PageParams (cursor-based)
│           │   │
│           │   └── infrastructure/
│           │       ├── db/
│           │       │   ├── base.py         # DeclarativeBase, naming_convention, TimestampMixin, UUIDMixin
│           │       │   ├── session.py      # async engine, async_sessionmaker, get_session (DI)
│           │       │   └── types.py        # tipi SA riusabili (TZDateTime, CIText...)
│           │       ├── http/
│           │       │   ├── error_handlers.py   # exception handlers -> formato errore standard
│           │       │   ├── deps.py             # dependency: current_participant, current_host, require_role
│           │       │   └── responses.py        # helper envelope/paginazione
│           │       ├── realtime/
│           │       │   ├── hub.py          # WebSocketHub (rooms per-evento)
│           │       │   ├── envelope.py     # schema busta {type,payload,...}
│           │       │   ├── auth.py         # handshake/auth del socket
│           │       │   └── broker.py       # EventBus interno + fan-out (pub verso hub)
│           │       ├── storage/
│           │       │   └── s3.py           # client S3/MinIO, presigned URL
│           │       └── security/
│           │           └── tokens.py       # firma/verifica session token (event-scoped)
│           │
│           ├── identity/           # === DOMINIO FOUNDATION: Event + Participant + auth ===
│           │   ├── core/
│           │   │   ├── entities.py         # Event, Participant (dominio puro)
│           │   │   ├── use_cases.py        # create_event, open/close_event, join_via_qr, ...
│           │   │   ├── repositories.py     # Protocol EventRepository, ParticipantRepository
│           │   │   └── services.py         # regole: validità finestra evento, unicità pseudonimo
│           │   └── infrastructure/
│           │       ├── models.py           # ORM Event, Participant (tabelle `event`, `participant`)
│           │       ├── repositories.py     # impl SQLAlchemy
│           │       └── router.py           # /api/v1/events, /api/v1/join, /api/v1/me
│           │
│           ├── profile/            # gli altri 7 domini seguono lo STESSO schema core/ + infrastructure/
│           │   ├── core/           #   core/: entities, use_cases, repositories(Protocol), services
│           │   └── infrastructure/ #   infrastructure/: models(ORM), repositories(impl), router, ws_handlers
│           ├── photo/
│           ├── discovery/
│           ├── dialogue/
│           ├── betting/
│           ├── gamification/       # OWNER del saldo punti e del ledger (vedi §5)
│           ├── gazette/
│           └── moderation/
│
│       └── tests/
│           ├── conftest.py
│           ├── shared/
│           └── <dominio>/
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── public/                     # manifest PWA, service worker, icons
│   └── src/
│       ├── main.tsx
│       ├── app/                    # routing, providers
│       ├── shared/                 # api client (fetch wrapper), ws client, tipi, envelope, error UI
│       │   ├── api/
│       │   ├── realtime/           # WebSocket client + reconnect
│       │   └── auth/               # gestione sessione/join QR
│       └── features/               # una cartella per dominio, speculare al backend
│           ├── profile/ photo/ discovery/ dialogue/ betting/ gamification/ gazette/ moderation/
│
├── infra/
│   ├── docker/                     # Dockerfile backend, frontend
│   ├── minio/                      # bucket bootstrap, policy
│   ├── postgres/                   # init sql, tuning
│   └── deploy/                     # compose prod, reverse proxy, env
│
└── docs/
    ├── FOUNDATION.md               # questo documento
    ├── adr/                        # Architecture Decision Records
    └── domains/                    # un file per dominio (contratti, eventi WS, tabelle)
```

**Regole strutturali vincolanti:**

- Ogni dominio ha ESATTAMENTE `core/` (puro, nessun import di SQLAlchemy/FastAPI/boto3) e `infrastructure/` (adapter). Le dipendenze puntano verso l'interno: `infrastructure → core → shared/core`. Mai il contrario.
- `core/` definisce i repository come `typing.Protocol`; `infrastructure/repositories.py` li implementa. I use case ricevono i repository per dependency injection, non li istanziano.
- Un solo albero Alembic per l'intero backend (`backend/migrations/`). Le migration importano `Base.metadata` che aggrega i modelli di tutti i domini. Niente migration per-dominio separate.
- I domini NON importano `models.py` di altri domini. La collaborazione cross-dominio avviene via use case/repository esposti dal dominio proprietario, oppure via EventBus (§4).

---

## 2. Entità e tabelle condivise fondanti

### 2.1 Campi base comuni (mixin obbligatori)

Ogni tabella del sistema DEVE includere:

| Colonna | Tipo Postgres | Regola |
|---|---|---|
| `id` | `UUID` PK | UUIDv7 generato applicativamente (ordinabile temporalmente). Default DB `gen_random_uuid()` solo come fallback. |
| `created_at` | `TIMESTAMPTZ NOT NULL` | Default `now()` (UTC). Mai modificato. |
| `updated_at` | `TIMESTAMPTZ NOT NULL` | Default `now()`; aggiornato su ogni UPDATE (evento ORM `onupdate`). |

Implementati come `UUIDMixin` + `TimestampMixin` in `shared/infrastructure/db/base.py`. Naming convention SQLAlchemy obbligatoria (per nomi vincoli deterministici in Alembic):

```
ix_%(table_name)s_%(column_0_name)s
uq_%(table_name)s_%(column_0_name)s
fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s
ck_%(table_name)s_%(constraint_name)s
pk_%(table_name)s
```

### 2.2 Tabella `event`

Rappresenta la serata/evento presso il locale. Radice del contesto dati (tenant logico).

| Colonna | Tipo | Vincoli / Note |
|---|---|---|
| `id` | `UUID` | PK |
| `name` | `TEXT NOT NULL` | Nome serata (es. "Il Ballo dei Bridgerton"). |
| `venue_name` | `TEXT NULL` | Nome locale. |
| `join_code` | `TEXT NOT NULL` | Codice opaco stampato/encodato nel QR. **UNIQUE**. Case-insensitive, alfanumerico, ≥8 char, generato random. |
| `status` | `event_status` (enum) | `NOT NULL DEFAULT 'draft'`. Valori: `draft`, `open`, `closed`, `archived`. |
| `starts_at` | `TIMESTAMPTZ NOT NULL` | Inizio finestra. |
| `ends_at` | `TIMESTAMPTZ NOT NULL` | Fine finestra pianificata. `CHECK (ends_at > starts_at)`. |
| `closed_at` | `TIMESTAMPTZ NULL` | Chiusura effettiva (può anticipare/posticipare `ends_at`). |
| `timezone` | `TEXT NOT NULL DEFAULT 'Europe/Rome'` | IANA TZ. I timestamp restano UTC; la TZ serve solo per display e per scheduling locale (scommesse orarie, gazzettino). |
| `retention_until` | `TIMESTAMPTZ NULL` | Scadenza dati per GDPR (§6). Default: `closed_at + 30 giorni`. |
| `host_secret_hash` | `TEXT NULL` | Hash del PIN/segreto host per la console organizzatore (§3.4). |
| `settings` | `JSONB NOT NULL DEFAULT '{}'` | Config non relazionale (es. cadenza scommesse, feature flags dominio). |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | Mixin. |

**Indici:** `uq_event_join_code` UNIQUE su `lower(join_code)`; `ix_event_status`; `ix_event_retention_until` (parziale `WHERE status='closed'`, per il job di retention).

### 2.3 Tabella `participant`

Sessione di una persona **all'interno di un singolo evento**. Non è un account: esiste solo nel contesto `event`. La stessa persona fisica in due eventi = due `participant` distinti.

| Colonna | Tipo | Vincoli / Note |
|---|---|---|
| `id` | `UUID` | PK. Usato come identificatore pubblico del partecipante nel gioco. |
| `event_id` | `UUID NOT NULL` | **FK → `event.id` ON DELETE CASCADE**. |
| `pseudonym` | `TEXT NOT NULL` | Nome scelto al join. Univoco per-evento. |
| `noble_title` | `participant_noble_title` (enum) NULL | Duca, Duchessa, Conte, Contessa, Barone, Baronessa, Visconte, Viscontessa, Marchese, Marchesa. Assegnato/scelto al join o dal dominio `profile`. |
| `role` | `participant_role` (enum) | `NOT NULL DEFAULT 'guest'`. Valori: `guest`, `host`. (Il "Cacciatore"/"Soggetto" NON sono ruoli persistenti: sono ruoli situazionali per-Whisper, vivono nel dominio `photo`.) |
| `score` | `INTEGER NOT NULL DEFAULT 0` | Saldo punti **denormalizzato** (proiezione del ledger, §5). Fonte di verità = ledger in `gamification`. |
| `is_photographable` | `BOOLEAN NOT NULL DEFAULT false` | Consenso OPT-IN a essere fotografato. **Deve essere `true` esplicitamente** perché il dominio `photo` accetti la persona come Soggetto. |
| `consent_at` | `TIMESTAMPTZ NULL` | Timestamp del consenso opt-in (audit GDPR). |
| `session_token_id` | `UUID NOT NULL` | Identificatore (jti) della sessione corrente; permette revoca. |
| `last_seen_at` | `TIMESTAMPTZ NULL` | Aggiornato dal WS/heartbeat (presence). |
| `left_at` | `TIMESTAMPTZ NULL` | Uscita volontaria; il record resta per integrità referenziale fino a retention. |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | Mixin. |

**Indici / vincoli:**
- `uq_participant_event_pseudonym` UNIQUE su `(event_id, lower(pseudonym))`.
- `ix_participant_event_id` (tutte le query di dominio filtrano per evento).
- `CHECK (role <> 'host' OR is_photographable = false)` opzionale: l'host non partecipa al gioco foto (raccomandato, non obbligatorio).

**Regola di scoping (VINCOLANTE per tutti i domini):** ogni tabella di dominio che riferisce persone o contenuti di gioco DEVE avere una colonna `event_id UUID NOT NULL FK → event.id ON DELETE CASCADE`, anche quando ridondante rispetto a un `participant_id`. Questo garantisce cancellazione GDPR per-evento in un colpo solo e query sempre scopate per tenant. I riferimenti a persone usano `participant_id` (mai identità reale).

### 2.4 Regole di dominio foundation (in `identity/core`)

- Un `participant` può fotografare/essere fotografato solo mentre `event.status = 'open'` e `now()` ∈ [`starts_at`, `ends_at`/`closed_at`].
- La chiusura evento (`close_event`) setta `status='closed'`, `closed_at=now()`, calcola `retention_until`, revoca tutte le sessioni.

---

## 3. Modello di autenticazione / sessione

Nessun account permanente. La sessione è **event-scoped**: un token valido identifica un `participant` dentro un `event` e scade con la chiusura dell'evento.

### 3.1 Flusso di join via QR

1. Il QR stampato al tavolo codifica un URL frontend: `https://app.thewhisper/j/{join_code}`.
2. La PWA legge `join_code`, mostra la schermata di ingresso (pseudonimo, titolo nobiliare, e **checkbox opt-in "Accetto di poter essere fotografato/a"**).
3. La PWA chiama `POST /api/v1/join`:

```json
{
  "join_code": "A7KD9QZ2",
  "pseudonym": "Lady Whistledown",
  "noble_title": "baronessa",
  "is_photographable": true
}
```

4. Il backend valida: evento esiste e `status='open'`, finestra temporale valida, pseudonimo libero per-evento. Crea il `participant`, emette il **session token**, imposta il cookie e ritorna il profilo:

```json
{
  "participant": { "id": "…", "pseudonym": "…", "noble_title": "baronessa", "role": "guest", "score": 0 },
  "event": { "id": "…", "name": "…", "status": "open", "timezone": "Europe/Rome" }
}
```

### 3.2 Session token — formato e trasporto

- **Formato:** JWT firmato HS256 (segreto in `settings`). Claim: `sub` = `participant_id`, `eid` = `event_id`, `role`, `jti` = `session_token_id`, `iat`, `exp`.
- **`exp`:** allineato a `event.ends_at + margine` (default 6h). Alla chiusura evento la sessione è invalidata a prescindere dall'`exp`, verificando `jti == participant.session_token_id` e `event.status != 'closed'`.
- **Trasporto primario: cookie `httpOnly`** `whisper_session`, `Secure`, `SameSite=Lax`, `Path=/`. Scelta obbligatoria per la PWA web (mitiga XSS token theft, sopravvive ai refresh, ininfluente per l'utente).
- **Trasporto alternativo (fallback):** header `Authorization: Bearer <jwt>` accettato dagli stessi endpoint, per test/tool e per il WebSocket dove il cookie non fosse disponibile. Il cookie ha precedenza se entrambi presenti.
- **CSRF:** essendo `SameSite=Lax` + API JSON con `Content-Type: application/json`, il rischio è basso; per mutazioni cross-site si applica double-submit token solo se in futuro servisse embedding cross-origin. Non richiesto nel MVP.

### 3.3 Identificazione del Participant nelle richieste

- Dependency FastAPI `current_participant` in `shared/infrastructure/http/deps.py`:
  1. estrae il token (cookie → poi bearer),
  2. verifica firma/scadenza,
  3. carica `participant` + `event`,
  4. verifica `jti == participant.session_token_id`, `event.status ∈ {open, closed}` (closed permette sola lettura del gazzettino), `participant.left_at IS NULL`,
  5. inietta un oggetto `SessionContext { participant_id, event_id, role }`.
- **Tutti** i router di dominio dipendono da `current_participant`. **Ogni** query di dominio DEVE filtrare per `event_id = context.event_id`. Nessun endpoint accetta `event_id` dal client per dati di gioco: viene dal token. Questo previene cross-tenant leakage by design.
- `require_role('host')` per gli endpoint della console organizzatore.

### 3.4 Ruolo host / organizzatore del locale

- L'host è un `participant` con `role='host'`, creato tramite un flusso separato: `POST /api/v1/events` (crea evento in `draft`) e `POST /api/v1/events/{id}/host-session` che richiede `host_secret` (verificato contro `host_secret_hash`). Ottiene un session token con `role='host'`.
- Capacità host: aprire/chiudere l'evento, vedere metriche aggregate, gestire premi del locale, agire da moderatore (rimozione foto, ban partecipante). L'host **non** partecipa al gioco foto e non vede identità reali oltre a quanto il gioco già espone.
- La creazione dell'evento e la generazione del `join_code`/QR sono operazioni host (o di un backoffice fuori scope MVP che usa gli stessi endpoint).

### 3.5 Endpoint foundation canonici

| Metodo | Path | Auth | Scopo |
|---|---|---|---|
| `POST` | `/api/v1/events` | host bootstrap | Crea evento (draft). |
| `POST` | `/api/v1/events/{id}/open` | host | Apre l'evento. |
| `POST` | `/api/v1/events/{id}/close` | host | Chiude, revoca sessioni, calcola retention. |
| `POST` | `/api/v1/events/{id}/host-session` | host_secret | Ottiene token host. |
| `GET` | `/api/v1/events/{id}` | any (scoped) | Stato evento pubblico. |
| `POST` | `/api/v1/join` | pubblico + join_code | Crea participant + sessione. |
| `GET` | `/api/v1/me` | participant | Contesto sessione corrente. |
| `POST` | `/api/v1/me/leave` | participant | Uscita volontaria. |
| `WS` | `/api/v1/ws` | participant (token) | Canale realtime (§4). |

---

## 4. Trasporto realtime (WebSocket hub)

Un unico endpoint WebSocket `/api/v1/ws`. Il realtime è **cross-dominio**: i domini pubblicano eventi, l'hub li instrada ai socket dell'evento giusto.

### 4.1 Autenticazione del socket

- Il client apre `wss://…/api/v1/ws`. Il cookie `httpOnly` viaggia automaticamente nell'handshake; in fallback il client invia il primo frame `{"type":"auth","payload":{"token":"<jwt>"}}` entro 5s.
- L'hub valida il token con la STESSA logica di `current_participant`. Se invalido/scaduto/evento chiuso → chiusura con close code `4401` (unauthorized) / `4403` / `4404`.
- Ottenuto `SessionContext`, il socket viene registrato nella **room** dell'evento.

### 4.2 Rooms e hub

- Una **room per evento**: `room_key = event_id`. Tutti i partecipanti di un evento condividono la room. Non esistono room cross-evento (isolamento tenant anche sul realtime).
- `WebSocketHub` (in `shared/infrastructure/realtime/hub.py`) mantiene in memoria: `rooms: dict[event_id, dict[participant_id, set[WebSocket]]]` (un partecipante può avere più tab). API interna:
  - `broadcast(event_id, message)` → tutti i socket della room.
  - `send_to_participant(event_id, participant_id, message)` → recapito mirato (missive segrete, chat, notifiche punti).
  - `presence(event_id)` → participant_id attivi.
- **Scalabilità:** nel MVP l'hub è in-process (single worker). L'astrazione `broker` consente in futuro un backend Redis pub/sub senza toccare i domini. I domini NON parlano mai direttamente ai WebSocket: pubblicano su `EventBus`.

### 4.3 Formato messaggi — busta standard

Ogni messaggio (server→client e client→server) è una busta JSON:

```json
{
  "type": "photo.published",
  "payload": { "...": "..." },
  "event_id": "…",
  "message_id": "uuid",
  "ts": "2026-07-17T20:14:03.120Z"
}
```

- `type`: stringa `"<dominio>.<evento>"` in `snake_case` dopo il punto (namespaced per dominio). Registro dei tipi mantenuto in `docs/domains/`. Esempi: `photo.published`, `discovery.comment_added`, `discovery.subject_guessed`, `dialogue.missive_received`, `dialogue.chat_opened`, `betting.round_opened`, `betting.round_settled`, `gamification.points_awarded`, `gamification.badge_unlocked`, `moderation.photo_removed`, `presence.updated`, `event.closed`.
- `payload`: object; schema definito dal dominio proprietario del `type`. **Mai** contenere identità reali/contatti se non a valle di un consenso di dominio (dialogue).
- Frame di sistema: `auth`, `ping`/`pong` (heartbeat ogni 25s), `error` (`{type:"error", payload:{code,message}}`).

### 4.4 Come i domini pubblicano eventi

- `shared/infrastructure/realtime/broker.py` espone `EventBus` con `publish(RealtimeEvent)`. Un use case di dominio, dopo aver committato la sua transazione, chiama l'EventBus (via dependency, mai import diretto dell'hub nel `core/`).
- **Ordine obbligatorio:** persistere (commit DB) → poi pubblicare sul realtime. Il realtime è best-effort/effimero; la fonte di verità è il DB. I client che si (ri)connettono ricostruiscono lo stato via REST, poi ricevono aggiornamenti incrementali via WS.
- **Contratto `core` puro:** i use case restituiscono una lista di `DomainEvent` (dataclass in `core/`); è l'adapter in `infrastructure/router.py` a tradurli in buste realtime e a chiamare l'EventBus. Così `core/` resta senza dipendenze I/O.

### 4.5 Riconnessione

- Il client implementa reconnect con backoff esponenziale (1s → max 30s) + jitter. Alla riconnessione: ri-auth automatica (cookie) e **resync REST** dei domini visibili (feed foto, scommessa aperta, saldo punti). Nessuna garanzia di replay dei messaggi persi via WS: lo stato mancante si recupera via REST (idempotente).
- Chiusura pulita su `event.closed` (close code `4000`): il client mostra il gazzettino finale e smette di riconnettersi.

---

## 5. Convenzioni trasversali

### 5.1 Naming

- **Tabelle:** `snake_case`, **singolare** (`event`, `participant`, `photo`, `whisper_comment`, `bet`, `point_ledger`). Colonne FK: `<referenced_table>_id`.
- **Enum Postgres:** `snake_case` con prefisso semantico (`event_status`, `participant_role`, `point_reason`). Definiti una volta in `shared/core/enums.py` (Python `enum.StrEnum`) e mappati a tipi ENUM Postgres nativi.
- **Endpoint REST:** prefisso `/api/v1`, risorse **plurali** kebab/snake coerente (`/api/v1/photos`, `/api/v1/bets`, `/api/v1/missives`). Verbi via metodo HTTP; azioni non-CRUD come sotto-risorsa (`POST /api/v1/photos/{id}/guesses`). Nessun `event_id` in path per dati di gioco (viene dal token).
- **Tipi WS:** `<dominio>.<evento>` (§4.3).

### 5.2 Formato errori API (obbligatorio)

Tutte le risposte di errore usano lo stesso envelope (HTTP status coerente):

```json
{
  "error": {
    "code": "participant.pseudonym_taken",
    "message": "Questo pseudonimo è già in uso in questa serata.",
    "details": { "field": "pseudonym" },
    "request_id": "…"
  }
}
```

- `code`: stringa stabile `"<dominio>.<slug>"`, machine-readable, NON localizzata. Mapping `DomainError → (http_status, code)` centralizzato in `shared/core/errors.py` + handler in `shared/infrastructure/http/error_handlers.py`.
- Status usati: `400` validazione, `401` non autenticato, `403` ruolo/consenso mancante, `404` non trovato o fuori scope evento, `409` conflitto (es. pseudonimo, doppio settle), `410` evento chiuso, `422` payload malformato (default FastAPI, riformattato nell'envelope), `429` rate limit.
- I domini sollevano solo sottoclassi di `DomainError`; nessun `HTTPException` grezza nei `core/`.

### 5.3 Paginazione

- **Cursor-based** (keyset), non offset. Query param: `?limit=<1..100, default 20>&cursor=<opaque>`. Ordine default: `created_at DESC, id DESC`.
- Risposta:

```json
{
  "items": [ … ],
  "page": { "next_cursor": "…|null", "limit": 20 }
}
```

- `Page[T]` / `PageParams` in `shared/core/pagination.py`; helper di serializzazione in `shared/infrastructure/http/responses.py`.

### 5.4 Gestione punti — ledger unico, idempotente (VINCOLANTE)

Per evitare **doppia contabilità**, i punti hanno UNA sola fonte di verità.

- Il dominio **`gamification`** possiede la tabella append-only `point_ledger`. Nessun altro dominio scrive `participant.score` né una propria contabilità punti.

**Tabella `point_ledger`:**

| Colonna | Tipo | Note |
|---|---|---|
| `id` | `UUID` PK | |
| `event_id` | `UUID NOT NULL` | FK → event, CASCADE. |
| `participant_id` | `UUID NOT NULL` | FK → participant, CASCADE. Beneficiario. |
| `delta` | `INTEGER NOT NULL` | Positivo o negativo (`CHECK (delta <> 0)`). |
| `reason` | `point_reason` (enum) | `photo_created`, `subject_guessed`, `bet_won`, `missive_replied`, `badge_bonus`, `manual_host`, … |
| `source_domain` | `TEXT NOT NULL` | Dominio emittente (audit). |
| `idempotency_key` | `TEXT NOT NULL` | **UNIQUE per-evento** (`uq_point_ledger_event_idem` su `(event_id, idempotency_key)`). |
| `metadata` | `JSONB` | Riferimenti (es. `photo_id`, `bet_id`). |
| `created_at` | `TIMESTAMPTZ` | |

- **API interna (unica via di accreditamento):** use case `award_points(event_id, participant_id, delta, reason, source_domain, idempotency_key, metadata)`. Gli altri domini lo invocano tramite la porta `PointsPort` (Protocol esposto da `gamification/core`), **non** scrivendo la tabella.
- **Idempotenza:** l'`idempotency_key` è deterministica sull'evento di business che genera i punti (es. `"subject_guessed:{photo_id}:{guesser_id}"`, `"bet_won:{bet_id}:{participant_id}"`). Un secondo award con la stessa chiave → INSERT in conflitto → no-op (nessun doppio accredito). Questo rende sicuri retry, redelivery WS e job ripetuti.
- **Saldo:** `participant.score` è una **proiezione** aggiornata nella STESSA transazione dell'insert nel ledger (`UPDATE participant SET score = score + :delta`). In caso di dubbio, il saldo canonico si ricalcola con `SELECT sum(delta) … GROUP BY participant_id`. La leaderboard legge `participant.score`.
- Le classifiche/badge/premi e il gazzettino derivano dal ledger; non introducono contatori paralleli.

### 5.5 Timestamp / timezone

- **Tutto in UTC** nel DB (`TIMESTAMPTZ`), sempre timezone-aware in Python. Vietato `datetime.now()` naive: usare `Clock.now()` (aware UTC) da `shared/core/clock.py`.
- Serializzazione API/WS: ISO-8601 con suffisso `Z` (es. `2026-07-17T20:14:03.120Z`).
- La conversione a orario locale (per display e per scheduling delle scommesse orarie / cadenza gazzettino) usa `event.timezone`. La logica di dominio ragiona in UTC; solo la presentazione e i cron per-evento usano la TZ locale.

### 5.6 Enum condivisi (`shared/core/enums.py`)

Definiti una sola volta, importati dai domini (mai ridefiniti):

- `EventStatus`: `draft | open | closed | archived`
- `ParticipantRole`: `guest | host`
- `ParticipantNobleTitle`: `duca | duchessa | conte | contessa | barone | baronessa | visconte | viscontessa | marchese | marchesa`
- `PointReason`: enumerazione centrale estesa in modo additivo dai domini via PR su questo file.

Gli enum specifici di un dominio (es. `PhotoStatus`, `BetStatus`) vivono nel `core/` del dominio, ma seguono le stesse convenzioni di naming.

---

## 6. Vincoli GDPR trasversali (obbligatori per ogni dominio)

Principi: **minimizzazione, opt-in totale, retention per-evento, diritto alla cancellazione, discrezione**. Ogni dominio è responsabile di rispettarli sui propri dati.

### 6.1 Minimizzazione dei dati

- Non si raccolgono dati identificativi reali. L'unico identificativo è lo **pseudonimo** per-evento; il `participant_id` è la chiave tecnica. Niente nome reale, email, telefono obbligatori.
- Contatti reali (Instagram/telefono) esistono **solo** nel dominio `dialogue`, **solo dopo** consenso esplicito bidirezionale (invito al dialogo accettato), cifrati/limitati e cancellati con l'evento. Nessun altro dominio li memorizza o li mette in payload REST/WS.
- Le foto Whisper sono su S3 con chiavi opache namespaced per evento (`events/{event_id}/photos/{photo_id}`), accesso via presigned URL a scadenza breve, bucket privato.

### 6.2 Consenso opt-in (fotografabilità)

- Una persona è Soggetto fotografabile **solo** se `participant.is_photographable = true` (impostato esplicitamente, `consent_at` registrato). Il dominio `photo` DEVE verificare questo flag prima di accettare/pubblicare una Whisper che la riguarda.
- Revoca del consenso: `POST /api/v1/me/consent {is_photographable:false}` è sempre disponibile; da quel momento non si possono pubblicare nuove foto sul partecipante e le foto esistenti che lo ritraggono possono essere rimosse su richiesta (§6.4).

### 6.3 Retention limitata all'evento

- I dati di gioco (foto, commenti, missive, chat, scommesse, ledger) hanno vita legata all'evento. Alla chiusura si calcola `event.retention_until` (default `closed_at + 30 giorni`; le foto/chat possono avere retention più breve, es. 7 giorni, definita dal dominio ma mai superiore a quella dell'evento).
- Un **job di retention** (schedulato, in `identity`/backoffice) elimina in hard-delete i dati degli eventi con `retention_until < now()`: `DELETE FROM event` con `ON DELETE CASCADE` che propaga a tutte le tabelle di dominio (grazie alla regola `event_id … ON DELETE CASCADE` del §2.3) + purge degli oggetti S3 con prefisso `events/{event_id}/`.
- Ogni dominio DEVE quindi: (a) avere `event_id` con FK CASCADE, (b) registrare eventuali artefatti esterni (S3) sotto il prefisso dell'evento così che il purge li raggiunga.

### 6.4 Diritto alla cancellazione e rimozione rapida

- **Cancellazione partecipante:** `POST /api/v1/me/erase` (o azione host) esegue la rimozione/anonimizzazione dei dati riferiti a quel `participant_id` in tutti i domini. Meccanismo: ogni dominio espone un handler `erase_participant(event_id, participant_id)` (porta `ErasablePort` in `shared/core`) che l'orchestratore di `identity` invoca in sequenza. Foto in cui la persona è Soggetto → rimosse; commenti/missive → anonimizzati (`participant_id` → tombstone) o cancellati; ledger → il partecipante viene scollegato mantenendo aggregati anonimi se necessari per il gazzettino già emesso.
- **Rimozione rapida della propria foto:** il Soggetto ritratto può chiedere la rimozione immediata di una Whisper che lo riguarda; il dominio `photo`/`moderation` la esegue senza esporre l'identità del Cacciatore (discrezione, §6.5). Rimozione = soft-delete immediato lato feed + hard-delete dell'oggetto S3 entro il ciclo di retention breve.
- **Segnalazione/moderazione:** il dominio `moderation` fornisce `report` su qualunque contenuto; una foto segnalata è nascosta rapidamente dal feed in attesa di revisione host.

### 6.5 Discrezione (identità del Cacciatore)

- L'identità reale del Cacciatore non è mai in chiaro nei payload verso altri partecipanti. Il collegamento Cacciatore↔foto è dato minimizzato: visibile solo al diretto interessato e all'host per moderazione, mai nel feed pubblico né nei messaggi WS di broadcast. Le buste realtime broadcast usano solo `participant_id`/pseudonimi, mai contatti o riferimenti che deanonimizzino.

### 6.6 Audit minimo

- Consensi (`consent_at`), chiusure evento, cancellazioni ed erase sono tracciati (timestamp + attore) per dimostrabilità GDPR, senza raccogliere dati personali aggiuntivi. Log applicativi non contengono contatti reali né token.

---

**Fine documento foundation.** Gli 8 domini estendono questa base restando entro: clean architecture `core/`+`infrastructure/`, scoping per `event_id`, punti solo via `point_ledger`/`PointsPort`, realtime solo via `EventBus`+busta standard, errori nell'envelope standard, e conformità GDPR (opt-in, retention per-evento, erase, discrezione).