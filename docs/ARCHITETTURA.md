# ARCHITETTURA UNIFICATA — The Whisper

> Documento di riconciliazione. Prende la FOUNDATION (autorevole) e i design degli 8 domini e li fonde in **un solo modello implementabile**. Dove foundation e dominio confliggono, prevale la foundation; dove i domini confliggono tra loro, questo documento decide (le decisioni sono elencate in §8). Nomi canonici dei domini: `identity` (foundation), `profile`, `photo`, `discovery`, `dialogue`, `betting`, `gamification`, `gazette`, `moderation`.

**Stack vincolante:** FastAPI (uv) · Python 3.14 async · PostgreSQL ≥15 (SQLAlchemy async + Alembic) · WebSocket · S3/MinIO · React + Vite PWA · accesso QR per-evento + pseudonimo, nessun account permanente.

---

## 1. Panoramica architettura e albero cartelle

### 1.1 Principi

- **Clean architecture per dominio:** ogni dominio ha `core/` (puro: entità, use case, `Protocol` di repository e porte, servizi — nessun import di SQLAlchemy/FastAPI/boto3) e `infrastructure/` (ORM, repository, router, ws_handlers, adapter porte). Dipendenze verso l'interno: `infrastructure → core → shared/core`.
- **Scoping per `event_id`:** ogni tabella di gioco ha `event_id UUID NOT NULL FK→event ON DELETE CASCADE`. Nessun endpoint accetta `event_id`/`participant_id` dal client per dati di gioco: vengono dal token (`SessionContext`).
- **Punti solo via ledger:** `point_ledger` (dominio `gamification`) è l'unica scrittura punti; gli altri domini accreditano via `PointsPort` idempotente.
- **Realtime solo via EventBus:** i use case ritornano `DomainEvent` puri; l'adapter router li traduce in buste WS e li pubblica su `EventBus` **dopo il commit** (persist→publish).
- **Collaborazione cross-dominio via Porte (`Protocol`)**, mai import di `models.py` altrui, mai FK cross-dominio "logiche" (soft-reference con UUID).
- **Alembic unico** per tutto il backend; `Base.metadata` aggrega i modelli di tutti i domini.

### 1.2 Albero definitivo

```
the-whisper/
├── docker-compose.yml            # postgres, minio, backend, frontend (dev)
├── pyproject.toml · uv.lock      # workspace uv
│
├── backend/
│   ├── alembic.ini
│   ├── migrations/               # UNICO albero Alembic (versions/)
│   └── src/whisper/
│       ├── main.py               # crea app, monta i router, lifespan (scheduler+hub)
│       ├── settings.py           # pydantic-settings (unica sorgente env)
│       │
│       ├── shared/               # === FOUNDATION CROSS-CUTTING ===
│       │   ├── core/
│       │   │   ├── entity.py        # BaseEntity, TimestampedEntity
│       │   │   ├── enums.py         # EventStatus, ParticipantRole, ParticipantNobleTitle, PointReason
│       │   │   ├── errors.py        # DomainError + mapping HTTP
│       │   │   ├── clock.py         # Clock protocol (now() aware UTC)
│       │   │   ├── ids.py           # uuid7()
│       │   │   ├── pagination.py    # Page[T], PageParams (cursor/keyset)
│       │   │   └── ports.py         # Protocol condivisi: PointsPort, StatsPort, ErasablePort
│       │   └── infrastructure/
│       │       ├── db/base.py       # DeclarativeBase, naming_convention, UUIDMixin, TimestampMixin, AppendOnlyMixin
│       │       ├── db/session.py    # async engine, sessionmaker, get_session (DI)
│       │       ├── db/types.py      # TZDateTime, CIText, EncryptedBytes (AEAD)
│       │       ├── http/error_handlers.py · deps.py (current_participant, require_role, require_not_sanctioned) · responses.py
│       │       ├── realtime/hub.py · envelope.py · auth.py · broker.py (EventBus)
│       │       ├── storage/s3.py    # presigned PUT/GET, purge per prefisso
│       │       ├── security/tokens.py
│       │       └── scheduler/loop.py # tick asyncio unico; registra job di dominio (vedi §1.3)
│       │
│       ├── identity/    # Event, Participant, auth/join/close, consent write, erase-orchestrator, retention job
│       ├── profile/     # persona nobiliare, reveal-machine, clues, consent-audit, template mistero
│       ├── photo/       # Foto Whisper (ciclo di vita, feed, subject segreto, cacciatore discreto)
│       ├── discovery/   # commenti, guess, discovery_state, Invito al Dialogo
│       ├── dialogue/    # missive mascherate, chat 1:1, reveal, scambio contatti (unica sede contatti reali)
│       ├── betting/     # scommesse orarie, round/opzioni/puntate, scheduler, payout parimutuel
│       ├── gamification/# OWNER point_ledger + score, stat, leaderboard, achievement, premi
│       ├── gazette/     # Il Gazzettino (edizioni snapshot, render S3, link pubblico)
│       └── moderation/  # report, auto-hide, sanzioni, blocchi, cascade consenso, penalità
│           ├── core/            # entities, use_cases, repositories(Protocol), services, ports(Protocol)
│           └── infrastructure/  # models, repositories, router, ws_handlers, port_adapters
│
│   └── tests/  conftest.py · shared/ · <dominio>/
│
├── frontend/  (React + Vite PWA)
│   └── src/
│       ├── app/          # routing, providers
│       ├── shared/       # api client, realtime (ws + reconnect/backoff), auth (join QR/sessione), envelope, error UI
│       └── features/     # profile/ photo/ discovery/ dialogue/ betting/ gamification/ gazette/ moderation/ (speculari al backend)
│
├── infra/  docker/ · minio/ (bucket bootstrap, policy privata) · postgres/ · deploy/
└── docs/   FOUNDATION.md · ARCHITETTURA_UNIFICATA.md · adr/ · domains/ (registro tipi WS)
```

### 1.3 Scheduler unico (`shared/infrastructure/scheduler/loop.py`)

Loop asyncio in-process (MVP single-worker), tick ~60 s, avviato nel lifespan. Ogni dominio registra un **job idempotente** (protetto da advisory lock per-evento per il futuro multi-worker):

| Job | Dominio | Cadenza | Azione |
|---|---|---|---|
| `betting.tick` | betting | 60 s | apre/blocca/risolve round; crea round per cadenza `event.settings.betting` |
| `gazette.interim` | gazette | `interim_cadence_minutes` (def 60) | genera edizione interim |
| `discovery.expire_invites` | discovery | 60 s | `pending → expired` su `expires_at < now()` |
| `photo.cleanup_drafts` | photo | 5 min | elimina bozze non pubblicate > 15 min + oggetti S3 orfani |
| `dialogue.purge_contacts` | dialogue | 10 min | hard-delete `dialogue_contact` con `expires_at < now()` |
| `identity.retention` | identity | 1 h | `DELETE FROM event WHERE retention_until < now()` + purge S3 `events/{event_id}/` |
| `gazette.expire_shares` | gazette | 1 h | revoca `share_slug` scaduti |

Alla **chiusura evento** (`identity.close_event`) l'EventBus pubblica `event.closed`; `gamification.finalize` e `gazette.final` sono innescati come reazione (hook sincrono nell'use case di close, non best-effort).

---

## 2. Schema database unificato

Convenzioni: tabelle `snake_case` **singolari**; ogni tabella ha `id UUID PK` (uuid7), `created_at`/`updated_at TIMESTAMPTZ` (mixin) salvo tabelle **append-only** (`point_ledger`, `stat_signal`, `profile_reveal_signal`, `profile_reveal`, `profile_consent_event`, `moderation_action`) che hanno solo `created_at`. Naming vincoli: `ix_/uq_/fk_/ck_/pk_` deterministici.

### 2.1 Foundation / `identity`

**`event`** (radice/tenant)

| Colonna | Tipo | Note |
|---|---|---|
| id | uuid PK | |
| name / venue_name | text / text NULL | |
| join_code | text NOT NULL | `uq_event_join_code` UNIQUE su `lower(join_code)`, ≥8 char |
| status | `event_status` | NOT NULL DEFAULT 'draft' |
| starts_at / ends_at | timestamptz | `ck_event_window CHECK (ends_at > starts_at)` |
| closed_at | timestamptz NULL | |
| timezone | text NOT NULL DEFAULT 'Europe/Rome' | IANA; solo display/scheduling locale |
| retention_until | timestamptz NULL | default `closed_at + 30gg` |
| host_secret_hash | text NULL | |
| settings | jsonb NOT NULL DEFAULT '{}' | override per-evento (betting, gamification.points, moderation, gazette, reveal) |

Indici: `ix_event_status`, `ix_event_retention_until WHERE status='closed'`.

**`participant`** (sessione persona-in-evento; NON un account)

| Colonna | Tipo | Note |
|---|---|---|
| id | uuid PK | identificatore pubblico di gioco |
| event_id | uuid NOT NULL | FK→event CASCADE |
| pseudonym | text NOT NULL | |
| noble_title | `participant_noble_title` NULL | |
| role | `participant_role` | NOT NULL DEFAULT 'guest' |
| score | integer NOT NULL DEFAULT 0 | **proiezione** del ledger |
| is_photographable | boolean NOT NULL DEFAULT false | opt-in esplicito |
| consent_at | timestamptz NULL | |
| consent_revoked_at | timestamptz NULL | *(additivo)* ultimo revoke |
| session_token_id | uuid NOT NULL | jti sessione corrente (revoca) |
| last_seen_at / left_at | timestamptz NULL | presence / uscita |

Indici/vincoli: `uq_participant_event_pseudonym` UNIQUE `(event_id, lower(pseudonym))`; `ix_participant_event_id`; `ck_participant_host_not_photographable CHECK (role<>'host' OR is_photographable=false)`.

> Sessione = JWT HS256 (cookie `httpOnly` primario, `Bearer` fallback/WS). Nessuna tabella sessione: la revoca avviene rigenerando `session_token_id` e verificando `jti` + `event.status`.

### 2.2 `profile`

**`participant_profile`** (1:1 con participant)

id · event_id(FK CASCADE) · **participant_id** uuid NOT NULL `uq_participant_profile_participant_id` UNIQUE (FK CASCADE) · secret_template_id uuid NULL (FK→profile_secret_template SET NULL) · secret_text text NULL · motto/house_name/bio text NULL · avatar_seed text NOT NULL · accent_color text NULL `CHECK (~ '^#[0-9a-fA-F]{6}$')` · clues jsonb NOT NULL DEFAULT '[]' (`[{id,type,label,reveal_order,sensitive}]`) · reveal_stage `profile_reveal_stage` NOT NULL DEFAULT 'concealed' · reveal_score int NOT NULL DEFAULT 0 CHECK≥0 · is_complete bool NOT NULL DEFAULT false · completed_at/disclosed_publicly_at timestamptz NULL.
Indici: `ix_participant_profile_event_id`, `ix_participant_profile_reveal_stage (event_id, reveal_stage)`.

**`profile_reveal_signal`** *(append-only, idempotente; analogo del ledger per la reveal)*
id · event_id · subject_participant_id (FK CASCADE) · signal_kind text · weight int CHECK>0 · source_domain text · source_ref text · idempotency_key text.
Indici: `uq_profile_reveal_signal_event_idem UNIQUE (event_id, idempotency_key)`, `ix_..._subject`.

**`profile_reveal`** *(append-only; sblocco per-osservatore)*
id · event_id · subject_participant_id · viewer_participant_id · clue_id uuid NULL · reveal_kind `profile_reveal_kind` · source `profile_reveal_source`.
Indici: `uq_profile_reveal_viewer_subject_clue UNIQUE (event_id, viewer_participant_id, subject_participant_id, clue_id) NULLS NOT DISTINCT`, `ix_..._viewer`, `ix_..._subject`.

**`profile_consent_event`** *(append-only, audit GDPR)*
id · event_id · participant_id · previous_value bool NULL · new_value bool · actor_participant_id · source text ('self'|'host'|'erase').
Indice: `ix_profile_consent_event_participant (event_id, participant_id, created_at DESC)`.

**`profile_secret_template`** *(reference globale, NO event_id, esente da retention)*
id · code text `uq` UNIQUE · label text · category text NULL · default_clues jsonb · is_active bool.

### 2.3 `photo`

**`photo`** (Foto Whisper)

| Colonna | Tipo | Note |
|---|---|---|
| id · event_id | uuid | FK→event CASCADE |
| hunter_participant_id | uuid NOT NULL | Cacciatore — **mai in feed/broadcast** |
| subject_participant_id | uuid NOT NULL | Soggetto (risposta segreta); `is_photographable=true` alla creazione |
| mysterious_title | text NOT NULL | `CHECK 1..120` |
| storage_key | text NOT NULL | `uq_photo_storage_key`; `events/{event_id}/photos/{photo_id}` |
| content_type | text NOT NULL DEFAULT 'image/jpeg' | `CHECK IN (jpeg,png,webp)` |
| byte_size/width/height/blurhash | int/int/int/text NULL | `CHECK byte_size ≤ 10MB` |
| status | `photo_status` | NOT NULL DEFAULT 'draft' |
| subject_revealed | bool NOT NULL DEFAULT false | + revealed_at (`CHECK` coerente) |
| published_at/removed_at | timestamptz NULL | |
| removed_reason | `photo_removal_reason` NULL | non esposto in chiaro |
| removed_by_participant_id | uuid NULL | FK SET NULL |
| comment_count/correct_guess_count | int NOT NULL DEFAULT 0 | denormalizzati (feed), aggiornati da discovery via `PhotoPort` |
| retention_until | timestamptz NULL | `min(event.retention_until, closed_at+7gg)` |

Indici: `ix_photo_feed (event_id,status,published_at DESC,id DESC)`, `ix_photo_hunter`, `ix_photo_subject`, `ix_photo_retention_until WHERE retention_until IS NOT NULL`, `ck_photo_hunter_not_subject CHECK (hunter<>subject)`.

> **Nota di riconciliazione:** i commenti NON stanno più qui. `whisper_comment` è di `discovery` (§2.4). `photo` conserva solo i contatori denormalizzati per il feed.

### 2.4 `discovery`

**`whisper_comment`** (owner unico dei commenti)
id · event_id · photo_id (FK→photo CASCADE) · author_participant_id uuid NULL (FK CASCADE; NULL=tombstone erase) · body text `CHECK btrim 1..500` · status `comment_status` NOT NULL DEFAULT 'visible' · removed_at timestamptz NULL.
Indici: `ix_whisper_comment_event_photo_created (event_id,photo_id,created_at DESC,id DESC)`, `ix_whisper_comment_author`.

**`whisper_guess`**
id · event_id · photo_id · guesser_participant_id · guessed_subject_participant_id · is_correct bool NOT NULL · guess_rank int NULL CHECK(>0).
Indici: `uq_whisper_guess_photo_guesser_candidate UNIQUE (photo_id,guesser_participant_id,guessed_subject_participant_id)`, `ix_..._photo_guesser`, `ix_..._photo_correct (photo_id) WHERE is_correct`, `ix_..._event`.

**`whisper_discovery_state`** (proiezione 1:1 per foto)
id · event_id · photo_id `uq` UNIQUE · total_guess_count/correct_guess_count int DEFAULT 0 CHECK≥0 · first_correct_guesser_id uuid NULL (FK SET NULL) · solved_at timestamptz NULL · reveal_state `discovery_reveal_state` NOT NULL DEFAULT 'hidden' · revealed_at timestamptz NULL · reveal_message text NULL CHECK(≤280).
Indici: `ix_..._event`, `ix_..._event_solved (event_id, solved_at)`.

**`whisper_invite`** (artefatto "Invito al Dialogo")
id · event_id · photo_id · inviter_participant_id (il Soggetto) · invitee_participant_id `CHECK (<>inviter)` · context `invite_context` · status `invite_status` NOT NULL DEFAULT 'pending' · message text NULL CHECK(≤280) · expires_at timestamptz NULL (def `now()+2h`, ≤ `event.ends_at`) · responded_at timestamptz NULL · chat_id uuid NULL (soft-ref a `conversation.id`).
Indici: `uq_whisper_invite_photo_inviter_invitee UNIQUE (photo_id,inviter,invitee)`, `ix_..._event_invitee_status`, `ix_..._event_inviter`, `ix_..._expires (expires_at) WHERE status='pending'`.

### 2.5 `dialogue`

**`conversation`**
id · event_id · initiator_id · recipient_id `CHECK(<>)` · initiator_mask_id/recipient_mask_id uuid NULL (FK→dialogue_mask SET NULL) · origin `conversation_origin` · source_ref jsonb NULL (`{photo_id, comment_id?}`) · status `conversation_status` NOT NULL DEFAULT 'active' · initiator_revealed/recipient_revealed bool DEFAULT false (monotoni) · initiator_contact_consent/recipient_contact_consent bool DEFAULT false · contact_exchanged_at timestamptz NULL · first_reply_awarded bool DEFAULT false · last_message_at · initiator_last_read_at/recipient_last_read_at timestamptz NULL.
Indici: `ix_conversation_initiator (event_id,initiator_id,last_message_at DESC)`, `ix_conversation_recipient (…)`, `uq_conversation_pair_origin UNIQUE (event_id,initiator_id,recipient_id,origin) WHERE origin='dialogue_invite'`.

**`dialogue_message`**
id · event_id · conversation_id (FK CASCADE) · sender_id · sender_masked bool DEFAULT true · sender_mask_id uuid NULL · kind `message_kind` DEFAULT 'text' · system_event text NULL · body text `CHECK (kind='system' OR char_length 1..1000)` · read_at/deleted_at timestamptz NULL.
Indice: `ix_dialogue_message_conversation (conversation_id,created_at DESC,id DESC)`.

**`dialogue_mask`**
id · event_id · participant_id (owner, **mai** verso counterpart) · alias text `CHECK 2..40` · generated bool DEFAULT true.
Indici: `uq_dialogue_mask_event_alias UNIQUE (event_id, lower(alias))`, `ix_..._participant`.

**`dialogue_contact`** (UNICA sede contatti reali, cifrata)
id · event_id · conversation_id · participant_id (owner) · revealed_to_id · contact_type `dialogue_contact_type` · contact_value_enc bytea NOT NULL (AEAD) · expires_at timestamptz NOT NULL (`min(event.retention_until, now()+7gg)`).
Indici: `uq_dialogue_contact_owner UNIQUE (conversation_id,participant_id,contact_type)`, `ix_..._expires`, `ix_..._event`.

**`dialogue_preference`**
participant_id PK (FK CASCADE) · event_id · accept_missives_from `missive_policy` DEFAULT 'anyone'.

> **Rimosso:** `dialogue_block` (i blocchi sono in `moderation.participant_block`, §2.9). Il blocco a livello conversazione resta come `conversation.status='blocked'`, ma la tabella dei blocchi è unica.

### 2.6 `betting`

**`bet_template`** *(reference globale, NO event_id, esente retention)*
id · code `uq` · title/prompt text · resolution_rule `bet_resolution_rule` · subject_type `bet_subject_type` · stake_mode `bet_stake_mode` DEFAULT 'parimutuel' · option_source `bet_option_source` · betting_seconds int DEFAULT 900 · measurement_seconds int DEFAULT 3600 · min_stake int DEFAULT 5 · max_stake int DEFAULT 100 CHECK(≥min) · fixed_reward int NULL · config jsonb · is_active bool.

**`bet_round`** (snapshot immutabile del template + macchina a stati)
id · event_id · template_id (FK RESTRICT) · snapshot: template_code/title/prompt/resolution_rule/stake_mode/min_stake/max_stake/fixed_reward/config · status `bet_round_status` DEFAULT 'scheduled' · opens_at · closes_at `CHECK(>opens_at)` · measurement_start · measurement_end `CHECK(>start)` · resolves_at (=measurement_end) · total_pool int DEFAULT 0 CHECK≥0 · stake_count int DEFAULT 0 · winning_option_ids uuid[] NULL · winning_metric jsonb NULL · settled_at timestamptz NULL · void_reason text NULL · settlement_idempotency_key text NULL `uq` UNIQUE.
Indici: `ix_bet_round_event_status`, `ix_bet_round_resolves_at WHERE status IN ('open','locked')`, `uq_bet_round_one_active (event_id) WHERE status IN ('open','locked')`.

**`bet_option`**
id · event_id · round_id (FK CASCADE) · label text · subject_participant_id uuid NULL (FK CASCADE) · subject_photo_id uuid NULL (soft-ref) · meta jsonb · pool int DEFAULT 0 CHECK≥0 · final_metric numeric NULL · is_winner bool DEFAULT false.
Indici: `uq_bet_option_round_participant (round_id,subject_participant_id) WHERE NOT NULL`, `uq_bet_option_round_photo (round_id,subject_photo_id) WHERE NOT NULL`, `ix_..._round`.

**`bet_stake`**
id · event_id · round_id · option_id · participant_id · amount int CHECK>0 · status `bet_stake_status` DEFAULT 'placed' · payout int DEFAULT 0 CHECK≥0 · stake_ledger_key text (`bet_staked:{stake_id}`) · payout_ledger_key text NULL · placed_at · settled_at timestamptz NULL.
Indici: `uq_bet_stake_round_participant (round_id,participant_id) WHERE status<>'void'`, `ix_..._option`, `ix_..._round`, `ix_..._participant`.

### 2.7 `gamification` (OWNER dell'economia punti)

**`point_ledger`** *(append-only, UNICA fonte di verità dei punti)*

| Colonna | Tipo | Note |
|---|---|---|
| id · event_id · participant_id | uuid | FK CASCADE |
| delta | integer NOT NULL | `CHECK (delta<>0)` |
| reason | `point_reason` NOT NULL | |
| source_domain | text NOT NULL | audit |
| idempotency_key | text NOT NULL | |
| metadata | jsonb NOT NULL DEFAULT '{}' | `{photo_id,bet_id,...}` |
| created_at | timestamptz | *(no updated_at)* |

Indici: **`uq_point_ledger_event_idem UNIQUE (event_id, idempotency_key)`**, `ix_..._event_participant`, `ix_..._event_reason`, `ix_..._event_created_at`.

**`stat_signal`** *(append-only, idempotente; metriche di gioco non-punto)*
id · event_id · participant_id · signal `stat_signal_kind` · idempotency_key text · metadata jsonb.
Indice: `uq_stat_signal_event_idem UNIQUE (event_id, idempotency_key)`, `ix_..._event_participant`, `ix_..._event_signal`.

**`participant_stat`** (proiezione, stessa transazione di `stat_signal`)
id · event_id · participant_id `uq (event_id,participant_id)` · photos_created · photos_as_subject · correct_guesses_made · correct_guesses_received · comments_made · comments_received · bets_placed · bets_won · missives_sent · missives_replied · dialogues_opened (int DEFAULT 0) · last_scoring_at timestamptz NULL.
Indice: `ix_participant_stat_event_subject (event_id, photos_as_subject DESC)`.

**`achievement`** *(catalogo statico, NO event_id, esente retention)*
id · code `uq` · name/description · category `achievement_category` · trigger_type `achievement_trigger` · stat_key text NULL · threshold_value int NULL · target_rank int NULL DEFAULT 1 · bonus_points int DEFAULT 0 · is_title bool DEFAULT true · active bool.

**`participant_achievement`**
id · event_id · participant_id · achievement_id (FK RESTRICT) · unlocked_at · context jsonb · ledger_id uuid NULL (FK→point_ledger).
Indice: `uq_participant_achievement UNIQUE (event_id,participant_id,achievement_id)`, `ix_..._event_ach`.

**`prize`**
id · event_id · name/description · kind `prize_kind` · award_mode `prize_award_mode` DEFAULT 'manual' · rank_from/rank_to int NULL `CHECK(rank_to≥rank_from)` · threshold_points int NULL · quantity int NULL CHECK>0 · awarded_count int DEFAULT 0 · status `prize_status` DEFAULT 'draft' · created_by uuid.
Indice: `ix_prize_event_status`.

**`prize_award`**
id · event_id · prize_id · participant_id · status `prize_award_status` DEFAULT 'pending' · redemption_code text `uq globale` · rank_at_award int NULL · awarded_by/redeemed_by uuid NULL · awarded_at · redeemed_at timestamptz NULL.
Indici: `uq_prize_award_redemption_code`, `uq_prize_award_prize_participant (event_id,prize_id,participant_id)`, `ix_..._event_participant`.

### 2.8 `gazette`

**`gazette_edition`**
id · event_id · kind `gazette_edition_kind` · status `gazette_edition_status` DEFAULT 'pending' · sequence int DEFAULT 1 · period_start/period_end `CHECK(>)` · title text · summary text NULL · generated_by `gazette_generated_by` · generated_at/published_at timestamptz NULL · share_slug text NULL (≥16 char) · share_expires_at timestamptz NULL (≤ retention_until) · render_key text NULL (`events/{event_id}/gazette/{edition_id}.{ext}`) · render_format `gazette_render_format` NULL · stats jsonb · idempotency_key text · error jsonb NULL.
Indici: `uq_gazette_edition_event_idem UNIQUE (event_id, idempotency_key)`, `uq_gazette_edition_event_kind_seq UNIQUE (event_id,kind,sequence)`, `uq_gazette_edition_share_slug UNIQUE lower(share_slug)`, `ix_..._event_status`, `ix_..._share_slug WHERE share_slug IS NOT NULL`.

**`gazette_section`**
id · event_id · edition_id (FK CASCADE) · kind `gazette_section_kind` · position int · title · subtitle text NULL · body jsonb.
Indici: `uq_gazette_section_edition_kind UNIQUE (edition_id,kind)`, `uq_gazette_section_edition_position UNIQUE (edition_id,position)`.

**`gazette_entry`**
id · event_id · edition_id · section_id (FK CASCADE) · position int · participant_id uuid NULL (FK SET NULL) · photo_id uuid NULL (soft-ref) · display_name_snapshot text · title_snapshot text NULL · value_label text NULL · metric_value numeric NULL · rank int NULL · metadata jsonb.
Indici: `ix_gazette_entry_edition (edition_id,section_id,position)`, `ix_gazette_entry_participant WHERE participant_id IS NOT NULL`, `ix_gazette_entry_photo WHERE photo_id IS NOT NULL`.

### 2.9 `moderation`

**`content_report`** (riferimento polimorfo cross-dominio, no FK sul contenuto)
id · event_id · reporter_participant_id uuid NULL (NOT NULL alla creazione; NULL su erase) · content_type `report_content_type` · content_id uuid · content_owner_participant_id uuid NULL (FK CASCADE; **solo host**) · reason `report_reason` · note text NULL CHECK(≤500) · content_snapshot jsonb NULL · status `report_status` DEFAULT 'pending' · resolved_by_participant_id uuid NULL · resolution_note text NULL · resolved_at timestamptz NULL.
Indici: `uq_content_report_content_reporter UNIQUE (event_id,content_type,content_id,reporter_participant_id)`, `ix_..._event_status`, `ix_..._content (event_id,content_type,content_id)`, `ix_..._owner`.

**`moderation_action`** *(append-only, audit)*
id · event_id · actor_type `mod_actor_type` · actor_participant_id uuid NULL · action `moderation_action_type` · content_type NULL · content_id uuid NULL · target_participant_id uuid NULL · report_id uuid NULL (FK SET NULL) · reason text NULL · metadata jsonb.
Indici: `ix_moderation_action_event_created (event_id,created_at DESC)`, `ix_..._content`, `ix_..._target`.

**`participant_sanction`**
id · event_id · participant_id · sanction_type `sanction_type` · reason text NULL · issued_by uuid NULL · report_id uuid NULL · starts_at · expires_at/lifted_at timestamptz NULL · lifted_by uuid NULL.
Indici: `uq_participant_sanction_active_ban (event_id,participant_id) WHERE sanction_type='ban' AND lifted_at IS NULL`, `ix_..._participant`.

**`participant_block`** (owner UNICO dei blocchi, ex `dialogue_block`)
id · event_id · blocker_participant_id · blocked_participant_id `CHECK(<>)`.
Indici: `uq_participant_block_pair UNIQUE (event_id,blocker,blocked)`, `ix_..._blocker`, `ix_..._blocked`.

### 2.10 ENUM condivisi (`shared/core/enums.py`)

```
EventStatus            = draft | open | closed | archived
ParticipantRole        = guest | host
ParticipantNobleTitle  = duca|duchessa|conte|contessa|barone|baronessa|visconte|viscontessa|marchese|marchesa
PointReason (canonico, esteso in modo ADDITIVO via PR su questo file):
   photo_created | subject_guessed | photo_solved | hunter_guess_bonus |
   profile_completed | missive_replied | dialogue_opened | dialogue_matched |
   bet_staked | bet_won | bet_refunded | badge_bonus | gazette_feature |
   moderation_penalty | manual_host | reversal
   # riservati/opzionali (default off): wrong_guess_penalty, false_report_penalty
```

**ENUM di dominio** (nel `core/` del dominio proprietario, stesse convenzioni):
`profile_reveal_stage`, `profile_reveal_kind`, `profile_reveal_source` · `photo_status`, `photo_removal_reason` · `comment_status(visible|hidden|removed)`, `discovery_reveal_state`, `invite_context`, `invite_status` · `conversation_origin`, `conversation_status`, `message_kind`, `dialogue_contact_type`, `missive_policy` · `bet_resolution_rule`, `bet_subject_type`, `bet_stake_mode`, `bet_option_source`, `bet_round_status`, `bet_stake_status` · `stat_signal_kind`, `achievement_category`, `achievement_trigger`, `prize_kind`, `prize_award_mode`, `prize_status`, `prize_award_status` · `gazette_edition_kind`, `gazette_edition_status`, `gazette_generated_by`, `gazette_render_format`, `gazette_section_kind` · `report_content_type`, `report_reason`, `report_status`, `mod_actor_type`, `moderation_action_type`, `sanction_type`.

### 2.11 Un solo ledger, accredito idempotente

`gamification/core` espone **`PointsPort`**; nessun altro dominio scrive `point_ledger` o `participant.score`.

```python
class PointsPort(Protocol):
    async def award_points(self, *, event_id, participant_id, delta, reason,
                           source_domain, idempotency_key, metadata=None) -> LedgerResult: ...
    async def get_balance(self, *, event_id, participant_id) -> int: ...
```

**Transazione atomica** (una sola):
1. `INSERT INTO point_ledger (...) ON CONFLICT (event_id, idempotency_key) DO NOTHING`.
2. Se ha inserito: `UPDATE participant SET score = score + :delta` (e `last_scoring_at=now()` su `participant_stat` se `delta>0`).
3. Commit → poi `EventBus.publish(points_awarded, leaderboard_updated)`.

`idempotency_key` è **deterministica sull'evento di business** (tabella §5). Un secondo award con la stessa chiave è no-op: sicuro per retry, redelivery WS e job ripetuti. Il saldo canonico è ricalcolabile con `SELECT sum(delta) … GROUP BY participant_id`; la leaderboard legge `participant.score`. Le correzioni sono **righe compensative** `reason=reversal` (mai UPDATE/DELETE).

Le metriche non-punto seguono lo stesso pattern con **`StatsPort.record_signal`** (idempotente su `stat_signal`) e, per la meccanica di scoperta, **`ProfileRevealPort.register_signal`** (idempotente su `profile_reveal_signal`).

---

## 3. Contratto API REST consolidato

Prefisso `/api/v1`. Auth: **P**=participant, **H**=host, **PUB**=public. Nessun `event_id` in path per dati di gioco (dal token).

### identity (foundation)
| M | Path | Auth | Scopo |
|---|---|---|---|
| POST | /events | H bootstrap | crea evento (draft) |
| POST | /events/{id}/open · /close | H | apre / chiude (revoca sessioni, retention) |
| POST | /events/{id}/host-session | host_secret | token host |
| GET | /events/{id} | P/H | stato evento |
| POST | /join | PUB+join_code | crea participant + sessione |
| GET | /me · POST /me/leave | P | contesto / uscita |
| **POST** | **/me/consent** | P | **opt-in/revoca fotografabilità (canonico, qui)** |
| POST | /me/erase | P | orchestratore cancellazione (chiama ErasablePort di tutti i domini) |
| WS | /ws | P (token) | canale realtime |

### profile
`GET/PUT /profiles/me` · `GET /profiles/{participant_id}` · `GET /profiles` (roster paginato) · `PATCH /profiles/me/pseudonym` (delega a identity; 409 taken / 403 rename_locked via `PhotoPort.is_published_subject` / 429) · `PATCH /profiles/me/title` · `POST /profiles/me/disclose` (targeted|public) · `GET /profiles/me/reveals` · `GET /profiles/secret-templates` · `GET /profiles/titles`. Tutti **P**.
> **Rimosso** `POST /me/consent` da profile (owner = identity; profile ne registra solo l'audit via subscription).

### photo
`POST /photos` (crea draft + presigned PUT) · `POST /photos/{id}/publish` · `GET /photos` (feed) · `GET /photos/{id}` · `GET /photos/mine` · `GET /photos/of-me` · **`POST /photos/{id}/reveal`** (owner del reveal Soggetto) · `DELETE /photos/{id}` (hunter|subject|host; removed_reason dal ruolo, include il "takedown" del Soggetto). Tutti **P** (delete anche **H**).
> **Rimossi** da photo: `/photos/{id}/comments` (→ discovery), `/comments/{id}` (→ discovery), `/photos/{id}/report` (→ moderation).

### discovery
`POST /photos/{photo_id}/comments` · `GET /photos/{photo_id}/comments` · `DELETE /comments/{comment_id}` (autore) · `POST /photos/{photo_id}/guesses` · `GET /photos/{photo_id}/guesses/me` · `GET /photos/{photo_id}/discovery` · `POST /photos/{photo_id}/invites` · `GET /invites` · `POST /invites/{id}/accept|decline|cancel`. Tutti **P**.
> **Rimosso** `POST /photos/{photo_id}/reveal` da discovery (owner = photo; discovery aggiorna `discovery_state.reveal_state` reagendo a `photo.subject_revealed`).

### dialogue
`POST /missives` · `GET /conversations` · `GET /conversations/{id}` · `GET/POST /conversations/{id}/messages` · `POST /conversations/{id}/read` · `POST /conversations/{id}/reveal` · `POST/DELETE /conversations/{id}/contact-consent` · `GET /conversations/{id}/contacts` · `GET/POST /masks` · `PUT /me/dialogue-preference`. Tutti **P**.
> **Rimossi** da dialogue: `POST /conversations/invite` (l'invito è di discovery; dialogue lo apre via `DialoguePort.open_conversation_from_invite`, use-case interno), `POST /conversations/{id}/block` + `/blocks` (→ moderation; `/conversations/{id}/block` resta come thin-wrapper che chiama `BlockPort` e setta `status='blocked'`), `POST /conversations/{id}/report` (→ moderation).

### betting
`GET /bets/rounds` · `GET /bets/rounds/current` · `GET /bets/rounds/{id}` · `POST /bets/rounds/{id}/stakes` · `DELETE /bets/stakes/{id}` · `GET /bets/stakes/mine` · `GET /bets/rounds/{id}/results` (P). `GET /bets/templates` · `POST /bets/rounds` · `POST /bets/rounds/{id}/open|lock|settle|void` · `PATCH /bets/config` (H).

### gamification
`GET /leaderboard` · `GET /me/points` · `GET /achievements` · `GET /me/achievements` · `GET /prizes` · `GET /me/prizes` (P). `POST /prizes` · `PATCH /prizes/{id}` · `POST /prizes/{id}/awards` · `POST /prize-awards/{id}/redeem|revoke` · `POST /points/adjustments` · `POST /events/{id}/gamification/finalize` · `GET /host/leaderboard` (H).

### gazette
`GET /gazette/editions` · `GET /gazette/editions/latest` · `GET /gazette/editions/{id}` · `GET /gazette/editions/{id}/render` (P). `POST /gazette/editions` · `POST /gazette/editions/{id}/publish|regenerate` · `POST/DELETE /gazette/editions/{id}/share` (H). **`GET /gazette/shared/{share_slug}` (PUB, rate-limited)**.

### moderation
**`POST /reports`** (P, polimorfo: content_type+content_id) · `GET /blocks` · `POST /blocks` · `DELETE /blocks/{blocked_participant_id}` (P). `GET /reports` · `GET /reports/{id}` · `POST /reports/{id}/claim|resolve` · `POST /participants/{id}/sanctions` · `GET /participants/{id}/sanctions` · `POST /sanctions/{id}/lift` · `GET /moderation/actions` (H).
> **Rimossi** `POST /photos/{id}/takedown` (= `DELETE /photos/{id}` da Soggetto) e `POST /me/consent` (→ identity; moderation esegue solo il cascade via port).

**Collisioni risolte:** `/photos/{id}/comments`, `/comments/{id}` → discovery · `/photos/{id}/reveal` → photo · report (photo/dialogue/moderation) → `/reports` moderation · blocchi (dialogue/moderation) → moderation · consenso (identity/profile/moderation) → identity · invito (discovery/dialogue) → discovery (dialogue interno).

---

## 4. Catalogo eventi realtime (WebSocket)

Busta standard `{type, payload, event_id, message_id, ts}`. `type = "<dominio>.<evento>"`. Ordine: **persist→publish**. Broadcast = tutta la room evento; Mirato = `send_to_participant`. **Mai** identità reali/contatti/Cacciatore nei broadcast.

| type | dir | recapito | payload (sintesi) | trigger |
|---|---|---|---|---|
| **sistema** | | | | |
| auth / ping / pong / error | c↔s | — | frame di sistema (heartbeat 25 s) | handshake / keepalive |
| presence.updated | s→c | broadcast | `{active:[participant_id]}` | heartbeat/join/leave |
| event.closed | s→c | broadcast | `{event_id}` (close code 4000) | chiusura evento |
| **profile** | | | | |
| profile.updated | s→c | broadcast | campi pubblici (pseudonym?,noble_title?,motto?,accent_color?…) | PUT profile / patch pseudonym/title |
| profile.clue_revealed | s→c | broadcast | `{subject_participant_id,clue_id,clue_type,clue_label,reveal_order,reveal_stage}` | soglia clue globale superata |
| profile.reveal_advanced | s→c | broadcast | `{subject_participant_id,reveal_stage,reveal_score,visible_clue_count}` | transizione stato reveal |
| profile.identity_disclosed | s→c | targeted/broadcast | `{subject_participant_id,scope,to_participant_id?}` | POST /profiles/me/disclose |
| profile.consent_changed | s→c | mirato (interessato+host) | `{participant_id,is_photographable}` | POST /me/consent |
| **photo** | | | | |
| photo.published | s→c | broadcast | `{photo_id,mysterious_title,image_url,blurhash,published_at,comment_count:0,correct_guess_count:0}` | publish |
| photo.of_you_published | s→c | mirato (Soggetto) | `{photo_id,mysterious_title,image_url,published_at}` | publish |
| photo.subject_revealed | s→c | broadcast | `{photo_id,subject:{participant_id,pseudonym,noble_title},revealed_at,message?}` | POST /photos/{id}/reveal |
| photo.removed | s→c | broadcast | `{photo_id}` (nessun motivo/attore) | delete/takedown/consent-cascade/**uphold moderazione** |
| photo.hidden | s→c | broadcast | `{photo_id}` | foto → under_review (report/soglia) |
| **discovery** | | | | |
| discovery.comment_added | s→c | broadcast | `{photo_id,comment_id,author_participant_id,author_pseudonym,body,created_at,comment_count}` | nuovo commento |
| discovery.guess_result | s→c | mirato (guesser) | `{photo_id,guess_id,is_correct,guess_rank?,attempts_left,points_awarded}` | POST guess |
| discovery.photo_solved | s→c | broadcast | `{photo_id,solved_at,correct_guess_count}` | primo guess corretto |
| discovery.subject_guessed | s→c | mirato (Cacciatore + Soggetto) | `{photo_id,correct_guess_count,latest_guess_rank}` | guess corretto |
| discovery.invite_received | s→c | mirato (invitato) | `{invite_id,photo_id,context,message?,inviter_participant_id,inviter_pseudonym,expires_at}` | POST invite |
| discovery.invite_answered | s→c | mirato (inviter) | `{invite_id,photo_id,status,chat_id?}` | accept/decline |
| discovery.invite_expired | s→c | mirato (inviter+invitee) | `{invite_id,photo_id}` | job scadenza |
| **dialogue** | | | | |
| dialogue.missive_received | s→c | mirato (destinatario) | `{conversation_id,message_id,sender_display,preview?,origin:'missive',ts}` (mai participant_id se mascherato) | POST /missives |
| dialogue.chat_opened | s→c | mirato (target) | `{conversation_id,origin:'dialogue_invite',source_ref,initiator_display}` | invito accettato |
| dialogue.message_received | s→c | mirato (counterpart) | `{conversation_id,message_id,sender_display,kind,body,ts}` | POST message |
| dialogue.message_read | s→c | mirato (mittente) | `{conversation_id,reader_display,read_at}` | POST read |
| dialogue.revealed | s→c | mirato (counterpart) | `{conversation_id,participant_id,pseudonym,noble_title}` | POST reveal |
| dialogue.contact_consent_updated | s→c | mirato | `{conversation_id,participant_display,consented,pending}` (no contatto) | consenso parziale |
| dialogue.contact_exchanged | s→c | mirato (2 parti) | `{conversation_id,contacts:[{participant_display,contact_type,contact_value}]}` | doppio consenso + entrambi rivelati |
| dialogue.typing | c↔s | mirato | `{conversation_id,sender_display?}` (effimero) | typing |
| **betting** | | | | |
| betting.round_scheduled/opened/locked | s→c | broadcast | round + opzioni/pool/tempi | transizioni round |
| betting.pool_updated | s→c | broadcast (throttled) | `{round_id,total_pool,stake_count,options:[{id,pool,implied_odds}]}` (mai CHI) | variazione pool |
| betting.stake_confirmed | s→c | mirato | `{round_id,stake_id,option_id,amount,new_score}` | piazzamento |
| betting.round_settled | s→c | broadcast | `{round_id,winning_options,tie,total_pool,winning_pool}` | settle |
| betting.payout_received | s→c | mirato | `{round_id,stake_id,result,payout,profit,new_score}` | settle |
| betting.round_voided / refund_issued | s→c | broadcast / mirato | void + refund | void/cancel |
| **gamification** | | | | |
| gamification.points_awarded | s→c | mirato (beneficiario) | `{delta,new_score,reason,source_domain,ref,ts}` | dopo award_points |
| gamification.leaderboard_updated | s→c | broadcast (debounce ~750ms) | `{generation,top:[…],changed:[…]}` | variazione saldo |
| gamification.badge_unlocked | s→c | mirato | `{achievement,bonus_points,context,ts}` | sblocco |
| gamification.badge_announced | s→c | broadcast (solo is_title) | `{achievement,participant:{participant_id,pseudonym,noble_title}}` | sblocco titolo |
| gamification.prize_awarded | s→c | mirato | `{prize_award_id,prize,redemption_code,ts}` | assegnazione premio |
| **gazette** | | | | |
| gazette.edition_ready | s→c | mirato (host) | `{edition_id,kind,sequence,title,generated_at}` | edizione ready |
| gazette.published | s→c | broadcast | `{edition_id,kind,title,summary,published_at,share_url?,cover_photo_url?}` | pubblicazione |
| gazette.generation_failed | s→c | mirato (host) | `{edition_id,kind,error_code}` | fallimento |
| gazette.final_ready | s→c | broadcast | `{edition_id,title,share_url}` | finale a chiusura (prima del close 4000) |
| **moderation** | | | | |
| moderation.report_queued | s→c | mirato (host) | `{report_id,content_type,content_id,content_owner_participant_id,reason,distinct_reporters,auto_hidden}` (unico con owner) | nuova report / soglia |
| moderation.report_ack | s→c | mirato (reporter) | `{report_id,status:'received'}` | POST /reports |
| moderation.content_hidden / content_restored / content_removed | s→c | broadcast | `{content_type,content_id}` (non-foto) | auto-hide/dismiss/uphold |
| moderation.participant_sanctioned | s→c | mirato (sanzionato) | `{sanction_type,reason?,expires_at?}` (ban → close 4403) | sanzione |

**Duplicati risolti:** commenti → `discovery.comment_added` (rimosso `comment_added` di photo) · reveal Soggetto → `photo.subject_revealed` (rimosso `discovery.subject_revealed`) · rimozione foto → **`photo.removed`** unico (la moderazione la scatena via `PhotoPort.remove`; `moderation.photo_removed` della foundation è soddisfatto da `photo.removed`) · `moderation.content_*` solo per contenuti **non-foto** · blocchi → `dialogue.blocked` rimosso (nessuna notifica al bloccato; il blocker sincronizza multi-tab via resync REST).

---

## 5. Point economy (tabella unica)

Tutti gli accrediti passano da `PointsPort.award_points`. Costanti in `event.settings.gamification.points` (override per-evento). Segno: + accredito, − addebito.

| Azione | Dominio owner | Δ default | reason | idempotency_key |
|---|---|---|---|---|
| Pubblicare Foto Whisper | photo | **+5** | photo_created | `photo_created:{photo_id}` |
| Indovinare il Soggetto (guesser) | discovery | **+25/20/15/10** per rank 1/2/3/≥4 | subject_guessed | `subject_guessed:{photo_id}:{guesser_id}` |
| Prima foto risolta (Cacciatore, one-shot) | discovery | **+20** | photo_solved | `photo_solved:{photo_id}` |
| Bonus popolarità Cacciatore (per indovino distinto, cap 10) | discovery | **+3** | hunter_guess_bonus | `hunter_guess_bonus:{photo_id}:{guesser_id}` |
| Profilo completo (1 volta) | profile | **+5** | profile_completed | `profile_completed:{participant_id}` |
| Missiva che genera risposta (all'iniziatore, 1×conv) | dialogue | **+10** | missive_replied | `missive_replied:{conversation_id}` |
| Chat aperta da invito accettato (ciascuna parte) | dialogue | **+10** | dialogue_opened | `dialogue_opened:{conversation_id}:{role}` |
| Scambio contatti riuscito (ciascuna parte) | dialogue | **+15** | dialogue_matched | `dialogue_matched:{conversation_id}:{participant_id}` |
| Piazzamento puntata (escrow) | betting | **−amount** | bet_staked | `bet_staked:{stake_id}` |
| Vincita round (parimutuel/fixed) | betting | **+payout** | bet_won | `bet_won:{stake_id}` |
| Rimborso (void/no-winner/cancel pre-lock) | betting | **+amount** | bet_refunded | `bet_refunded:{stake_id}` |
| Sblocco achievement/titolo con bonus | gamification | **+bonus_points** | badge_bonus | `badge:{achievement_id}:{participant_id}` |
| Featured nella nightly_final (#1 headline / altre / titolo / desiderato) | gazette | **+50 / +20 / +30 / +40** | gazette_feature | `gazette_feature:{edition_id}:{participant_id}:{section_kind}` |
| Penalità contenuto rimosso su uphold | moderation | **−80/−50/−40/−30/−20** per reason | moderation_penalty | `moderation_penalty:{content_type}:{content_id}` |
| Rettifica manuale host | gamification | **±delta** | manual_host | chiave esplicita dal client |
| Storno contenuto moderato | gamification | **−delta_originale** | reversal | `reversal:{ledger_id}` |

**Regole trasversali:**
- **Payout parimutuel:** `total_pool = Σ amount (non-void)`; `winning_pool = Σ amount sulle opzioni vincenti (array, pareggi inclusi)`; `payout_i = floor(amount_i · total_pool·(1−rake) / winning_pool)` (rake default 0). **Remainder** = `total_pool − Σ payout_i` assegnato alla prima stake vincente (`ORDER BY placed_at,id`) per conservare i punti. `winning_pool=0` o `stake_count < min_participants` → **void + refund totale**.
- **fixed_reward:** nessun escrow; ogni predizione corretta riceve `fixed_reward` (`bet_won`), finanziato dalla casa.
- **Idempotenza settlement:** `bet_round.settlement_idempotency_key = 'bet_settle:{round_id}'` UNIQUE; secondo settle = no-op.
- **Storno su moderazione:** su rimozione di un contenuto già premiato, `gamification` emette righe `reversal` (chiave `reversal:{ledger_id}`) per gli accrediti collegati via `metadata.photo_id` e decrementa i contatori via `stat_signal(content_removed)`. Il ledger resta append-only.
- `gazette`/`gamification` non riaccreditano i punti di top_players/badges/bets (già contabilizzati): niente doppia contabilità.
- Le penalità possono portare `score` sotto zero: **saldi negativi consentiti** (coerente con la natura sommativa del ledger); la leaderboard mostra il valore reale. `betting` blocca la puntata se `amount > get_balance()`.

---

## 6. Macchine a stati chiave

### 6.1 Foto Whisper (`photo.status`)
```
draft ─publish(hunter, upload S3 verificato, consenso valido)→ published
draft ─timeout/annullo─→ removed
published ─report/soglia─→ under_review ─host restore─→ published
                                        ─host reject──→ removed
published ─(subject_request|hunter_deleted|consent_revoked|host_action|moderation uphold)→ removed
published ─chiusura evento (post gazzettino)→ archived
removed = terminale (oggetto S3 purgato)
```
Guardie: transizioni illegali → `409 photo.invalid_transition`. Gate consenso ri-verificato al publish (`409 photo.subject_consent_revoked`). Gate finestra (`event.status='open'` e `starts_at ≤ now ≤ coalesce(closed_at, ends_at)`) → fuori finestra `410 event.closed`. Ogni ingresso in `published` accredita `photo_created` (idempotente). Ogni uscita dal feed → broadcast `photo.removed`/`photo.hidden`.

### 6.2 Scommessa (`bet_round.status` + `bet_stake.status`)
```
round:  scheduled ─now≥opens_at→ open ─now≥closes_at→ locked ─now≥resolves_at→ resolving → settled
        (qualsiasi stato pre-settled) ─host/void condizioni─→ void
stake:  placed ─settlement→ won | lost
        placed ─cancel pre-lock→ void        placed ─void round→ refunded
```
Transizioni idempotenti, protette da advisory lock per-round (multi-worker). `open→locked` chiude le puntate; misurazione `[measurement_start, measurement_end)` con `measurement_start ≥ closes_at` (bet-before-outcome). Solo `won`/`refunded` generano accredito. Escrow al `placed`, payout/refund al `settled`/`void`.

### 6.3 Chat / rivelazione / contatti (`conversation`)
```
origine:  missive | dialogue_invite | direct
reveal (per lato, MONOTONO):  false → true  (irreversibile) → message system + dialogue.revealed
contatto (doppio opt-in):  consent(side) richiede side_revealed=true
   exchange SSE (init_consent ∧ recip_consent ∧ init_revealed ∧ recip_revealed)
       → contact_exchanged_at=now(); 2× dialogue_contact (AEAD, expires_at=min(retention, now+7g))
       → message system 'contact_exchanged' + dialogue.contact_exchanged + award dialogue_matched
stato:  active ─block→ blocked ─unblock→ active ;  {active,blocked} ─event.close→ closed (read-only)
```
Ponte con discovery: `whisper_invite: pending → accepted` (emette `DiscoveryInviteAccepted`) → dialogue apre la conversation via `DialoguePort.open_conversation_from_invite` e ritorna `chat_id` che discovery salva. Contatti reali: **solo** in `dialogue_contact`, cifrati, mai in broadcast, revocabili (`DELETE /contact-consent` = hard-delete).

### 6.4 Consenso fotografabilità (`participant.is_photographable`)
```
join(is_photographable) ──→ [true: consent_at=now]  |  [false]
POST /me/consent {true}  → is_photographable=true, consent_at=now, profile_consent_event(+)
POST /me/consent {false} → is_photographable=false, consent_revoked_at=now
        ├─ profile_consent_event(new=false, source='self'|'host'|'erase')
        ├─ photo.on_consent_revoked(participant): foto attive con subject=me → removed(consent_revoked) → photo.removed
        └─ photo rifiuta nuove Whisper con subject=me
host: può forzare solo → false (tutela). Reveal-stage profilo è indipendente e MONOTONO (concealed→hinted→unmasked, mai regressione).
```
Reveal profilo: `concealed (reveal_score<3) → hinted (≥3) → unmasked (disclosed_publicly_at set)`. Nessun unmask automatico (solo auto-svelamento del Soggetto). Clue globali visibili = `min(len(clues), floor(reveal_score/3))`; clue `sensitive` richiedono `identity_disclosed` verso il viewer.

*(Macchine minori: report `pending→under_review→upheld|dismissed`; achievement `locked→unlocked`; prize `draft→active→archived` + award `pending→redeemed|revoked`; gazette edition `pending→generating→ready→published`/`failed`/`superseded`; invite `pending→accepted|declined|cancelled|expired`.)*

---

## 7. Flusso GDPR / consenso end-to-end

**Principi:** minimizzazione, opt-in totale, retention per-evento, diritto alla cancellazione, discrezione (foundation §6).

1. **Opt-in all'ingresso (join):** la PWA mostra la checkbox "Accetto di poter essere fotografato/a". `POST /join` crea il `participant` con `is_photographable` e, se true, `consent_at`. Nessun dato reale raccolto: solo pseudonimo per-evento.
2. **Gate fotografabilità:** `photo` accetta un Soggetto **solo** se `is_photographable=true ∧ consent_at IS NOT NULL`, verificato al draft **e** ri-verificato al publish. I bersagli delle scommesse su partecipanti sono filtrati sugli opt-in.
3. **Revoca consenso:** `POST /me/consent {false}` (identity) → cascade `photo.on_consent_revoked` rimuove le foto attive del Soggetto (`removed_reason=consent_revoked`, hard-delete S3) senza svelare il Cacciatore; `profile_consent_event` traccia previous/new/actor/source.
4. **Segnalazione + rimozione rapida:** `POST /reports` (moderation) → auto-hide su soglia `distinct_reporters ≥ threshold` o `reason ∈ {non_consensual_subject, nudity_explicit}` → `photo.hidden`/`moderation.content_hidden`. Il Soggetto ritratto rimuove la propria foto con `DELETE /photos/{id}` (senza review né penalità al Cacciatore). Uphold host → `PhotoPort.remove` + penalità `moderation_penalty` + `reversal` degli accrediti collegati.
5. **Discrezione (§6.5):** `hunter_participant_id`, `content_owner_participant_id`, mask→participant, contatti reali **mai** nei broadcast; visibili solo all'interessato e all'host per moderazione. Le Missive Segrete non entrano nel gazzettino.
6. **Contatti reali:** unica sede `dialogue_contact` (AEAD, `expires_at=min(retention, now+7g)`, job di purge dedicato), creati solo dopo doppio opt-in + entrambe le identità di gioco rivelate; revocabili in ogni momento.
7. **Retention per-evento:** alla chiusura `retention_until = closed_at + 30gg` (foto/chat più brevi, ≤ evento). Il job `identity.retention` esegue `DELETE FROM event` → CASCADE su tutte le tabelle di gioco + purge S3 `events/{event_id}/`. Le tabelle reference (`profile_secret_template`, `bet_template`, `achievement`) non hanno `event_id` e sono esenti.
8. **Diritto alla cancellazione:** `POST /me/erase` (o azione host) → `identity` orchestra chiamando in sequenza `ErasablePort.erase_participant(event_id, participant_id)` di ogni dominio:
   - photo: foto come Cacciatore/Soggetto → removed + purge S3;
   - discovery: commenti/guess dell'utente e guess che lo indicano come candidato → delete; `first_correct_guesser_id`/invite → SET NULL/delete;
   - dialogue: messaggi → tombstone (`deleted_at`, body redatto, display '[cancellato]'); mask → delete; `dialogue_contact` (owner o revealed_to) → hard-delete; conversation → anonimizzata;
   - gamification: righe ledger/stat/achievement dell'utente → hard-delete; prize_award pending → revoca; ricalcolo/broadcast leaderboard;
   - gazette: `gazette_entry.participant_id=NULL`, `display_name_snapshot`→tombstone ('Un misterioso nobile'), purge render S3 che lo citano, revoca share_slug interessati;
   - moderation: reporter/owner/target/actor → NULL, `content_snapshot` svuotati, blocchi/sanzioni cancellati; `moderation_action` conserva solo action+timestamp per dimostrabilità;
   - profile: `participant_profile` + `profile_reveal` (viewer/subject) delete, `profile_reveal_signal` anonimizzato/cancellato.
9. **Audit minimo:** consensi, chiusure, erase, rettifiche, riscatti premio tracciati (timestamp+attore) senza dati personali; log senza token né contatti.

---

## 8. Incoerenze trovate e risoluzioni

| # | Incoerenza tra domini | Risoluzione |
|---|---|---|
| 1 | `whisper_comment` definito in **photo** e **discovery**; tipo WS `comment_added` (photo) vs `discovery.comment_added` (foundation) | Tabella + endpoint + evento → **discovery**. Photo conserva solo `comment_count` denormalizzato aggiornato via `PhotoPort`. |
| 2 | `POST /photos/{id}/reveal` in **photo** e **discovery** (e disclosure in **profile**) | Reveal Soggetto-su-foto → **photo** (`subject_revealed`, evento `photo.subject_revealed`). Discovery aggiorna `discovery_state` reagendo all'evento. Profile mantiene `disclose` (targeted/public) come reveal a livello *persona*, distinto. |
| 3 | "Invito al Dialogo": `whisper_invite`+`/invites` (discovery) vs `conversation origin=dialogue_invite`+`/conversations/invite` (dialogue) | Artefatto/endpoint invito → **discovery**. Su accept emette `DiscoveryInviteAccepted`; **dialogue** apre la chat via `DialoguePort.open_conversation_from_invite` (use-case interno, no REST pubblico). |
| 4 | Blocchi in **dialogue** (`dialogue_block`, `/blocks`) e **moderation** (`participant_block`, `/blocks`) | Owner unico → **moderation** (`participant_block`, `/blocks`, `BlockPort`). Dialogue consulta `BlockPort`; `/conversations/{id}/block` resta wrapper che setta `conversation.status='blocked'`. |
| 5 | Consenso `POST /me/consent` reclamato da identity, profile, moderation | Endpoint + write `is_photographable/consent_at` → **identity**. Profile registra l'audit (`profile_consent_event`), photo/moderation eseguono il cascade, via porte/eventi. |
| 6 | Report: `/photos/{id}/report` (photo), `/conversations/{id}/report` (dialogue), `/reports` (moderation) | Unico `POST /reports` polimorfo → **moderation**. Gli altri rimossi. |
| 7 | Takedown foto: `/photos/{id}/takedown` (moderation) vs `DELETE /photos/{id}` (photo) | Unico `DELETE /photos/{id}` → **photo**, `removed_reason` derivato dal ruolo (subject/hunter/host). |
| 8 | Punti indovino: 15/14/13… (photo) vs 25/20/15/10 (discovery) vs 20+10 (gamification) | Owner del gioco di scoperta = **discovery**: **25/20/15/10** per rank. Formule di photo/gamification scartate. |
| 9 | Bonus Cacciatore: `photo_guess_bonus` +5 cap 25 (photo) vs `photo_solved`+20 & `hunter_guess_bonus`+3 (discovery) vs +15 cap 60 (gamification) | Adottato lo schema **discovery**: `photo_solved` +20 one-shot + `hunter_guess_bonus` +3/indovino (cap 10). Rimossi gli altri. |
| 10 | `photo_created`: +10 (photo) vs +5 (gamification) | **+5** (anti-farming; la creatività paga via guess/scommesse/gazzettino). |
| 11 | `missive_replied`: +10 (dialogue) vs +5 (gamification) | **+10** (owner dialogue). Valori comunque override in `event.settings`. |
| 12 | Ricompensa dialogo: `dialogue_opened` +25/+10 (gamification) vs `dialogue_matched` +15 (dialogue) | Entrambe come momenti distinti: **`dialogue_opened` +10/parte** (chat aperta da invito) e **`dialogue_matched` +15/parte** (contatti scambiati). |
| 13 | Naming reason betting: `bet_stake/bet_refund` (gamification) vs `bet_staked/bet_refunded` (betting) | Canonici → **`bet_staked` / `bet_won` / `bet_refunded`**, chiavi su `{stake_id}`. |
| 14 | Reason `correct_guess` (gamification) duplicato di `subject_guessed` (foundation) | Rimosso `correct_guess`. Guesser → `subject_guessed`; hunter → `photo_solved`/`hunter_guess_bonus`. |
| 15 | `comment_status`: visible|removed (photo) vs visible|hidden|deleted (discovery) | Unificato → **`visible|hidden|removed`** (`deleted` fuso in `removed`; `hidden`=moderazione reversibile). |
| 16 | Rimozione foto WS: `photo.removed` vs `moderation.photo_removed` | Unico **`photo.removed`**; la moderazione lo scatena via `PhotoPort.remove`. `moderation.content_*` solo per non-foto. |
| 17 | Payout parimutuel: senza rake (betting) vs con rake (gamification) | Formula con `rake` **default 0** (compatibile con betting) + remainder al primo vincitore. |
| 18 | Due "signal ledger" (`profile_reveal_signal` vs `stat_signal`) sugli stessi eventi di business | Mantenuti **entrambi** (bounded context distinti: reveal-mechanic vs stats/achievement/betting/gazette). Emessi via porte idempotenti separate; nessuna doppia contabilità perché non toccano il point_ledger. |
| 19 | Contatori `correct_guess_count` su `photo` e su `whisper_discovery_state` | Fonte di verità = righe `whisper_guess`. Entrambe le colonne sono proiezioni aggiornate nella stessa transazione (photo via `PhotoPort`). |
| 20 | `titoli-achievement` vs `noble_title` del profilo | Layer separati: `noble_title` è cosmetico/di profilo; gli achievement `is_title` sono riconoscimenti di gamification. Nessuna sovrapposizione di dato. |
| 21 | `weekly_digest` cross-evento vs scoping per-evento | MVP: **solo digest per-evento**. Il cross-venue (store anonimizzato fuori dal CASCADE) è rimandato/segnalato come open question di prodotto. |
| 22 | PointReason estesi in modo divergente | Un **unico enum canonico** (§2.10) con estensioni additive via PR: `photo_solved, hunter_guess_bonus, profile_completed, dialogue_opened, dialogue_matched, bet_staked, bet_refunded, gazette_feature, moderation_penalty, reversal`. |
| 23 | Scheduler duplicati (betting, gazette, retention, cleanup, purge, invite-expiry) | Un **unico loop** in `shared/scheduler` con job registrati per dominio (§1.3). |

---

## 9. Piano di build in fasi

Legenda dipendenze: → "dipende da". Ogni fase è deployabile e testabile.

### Fase 0 — Scheletro & foundation runnable
`shared/` completo: `entity`, `enums` (EventStatus/ParticipantRole/ParticipantNobleTitle/PointReason), `errors`+handlers, `clock`, `ids(uuid7)`, `pagination`, `db/base`(mixin, naming_convention), `db/session`, `http/deps`, `realtime/hub+envelope+broker`, `storage/s3`, `security/tokens`, `scheduler/loop`. `main.py`+lifespan, `settings`, Alembic init, docker-compose (postgres+minio). **Deliverable:** app che parte, health-check, migration base.

### Fase 1 — Core loop giocabile (foundation + join→profilo→foto→feed→guess→punti)
Ordine e dipendenze:
1. **identity** — `event`, `participant`, `POST /events`+open/close+host-session, `POST /join`, `GET /me`, WS auth/room, `POST /me/consent`. *(nessuna dipendenza)*
2. **gamification (nucleo punti)** — `point_ledger` + `participant.score` + **`PointsPort.award_points`/`get_balance`** + `GET /leaderboard` + `gamification.points_awarded`/`leaderboard_updated`. → identity. *(sblocca tutti gli accrediti)*
3. **profile** — `participant_profile`, `PUT/GET /profiles/me`, `GET /profiles/{id}` (filtrato), roster, `secret-templates`/`titles`, `profile_completed` via PointsPort. → identity, gamification.
4. **photo** — `photo`, presigned PUT/publish, feed, `/photos/mine|of-me`, `/photos/{id}/reveal`, `DELETE`, gate consenso, `SubjectResolverPort`/`PhotoPort`, `photo_created`. → identity, gamification, storage.
5. **discovery** — `whisper_comment`, `whisper_guess`, `whisper_discovery_state`, guessing + anti-abuso, accrediti `subject_guessed`/`photo_solved`/`hunter_guess_bonus`, aggiornamento contatori photo via PhotoPort, `StatsPort.record_signal` + `ProfileRevealPort.register_signal`. → photo, gamification, profile.

**Deliverable Fase 1:** un partecipante entra col QR, crea il profilo, un altro pubblica una Whisper, il feed la mostra, si commenta/indovina, i punti scorrono, la leaderboard si aggiorna in realtime. **Core loop completo.**

### Fase 2 — Social & intrigo
6. **dialogue** — conversation/message/mask/contact/preference, missive mascherate, reveal, doppio opt-in contatti (AEAD), `missive_replied`/`dialogue_matched`, purge contatti. → identity, gamification, moderation(BlockPort, se pronto — altrimenti stub).
7. **discovery: Invito al Dialogo** — `whisper_invite` + `/invites` + `DiscoveryInviteAccepted` → `DialoguePort.open_conversation_from_invite`; `dialogue_opened`. → discovery, dialogue.
8. **stat/participant_stat completi** in gamification (alimentano achievement/gazette/betting). → domini emittenti.

### Fase 3 — Meta-gioco
9. **betting** — template/round/option/stake, scheduler tick, payout parimutuel/void/fixed, read-ports (`PhotoStatsPort`/`DiscoveryStatsPort`/`DialogueStatsPort`), `bet_staked/won/refunded`. → gamification (PointsPort/get_balance), photo/discovery/dialogue (stats), scheduler.
10. **gamification: achievement & premi** — `achievement`(seed), `participant_achievement`, threshold live + ranking in `finalize`, `prize`/`prize_award`, hook `event.closed`. → participant_stat.

### Fase 4 — Sicurezza, editoriale, conformità
11. **moderation** — `content_report`, auto-hide, `moderation_action`, `participant_sanction`, **`participant_block`** (owner), `BlockPort`/`SanctionPort`/`require_not_sanctioned`, cascade consenso, `moderation_penalty`+`reversal`. → identity(revoke sessione), photo/discovery/dialogue/profile (ContentPort), gamification (PointsPort). *(retrofit di `BlockPort` in dialogue/photo/discovery)*
12. **gazette** — edizioni/section/entry, read-ports (Leaderboard/Badge/PhotoStats/DiscoveryStats/BettingRecap/Presence), render S3, link pubblico, `gazette_feature`, job interim + hook `event.closed`→final. → tutti i domini sorgente (read-only), gamification (PointsPort).

### Fase 5 — Hardening
Retention job end-to-end + purge S3; erase orchestrator (`POST /me/erase` → tutte le `ErasablePort`); rate limiting; EXIF strip/re-encode/blurhash pipeline (worker); reconnection/resync FE; osservabilità; multi-worker (advisory lock scheduler, EventBus Redis pub/sub dietro `broker`).

**Dipendenze critiche (grafo sintetico):** `identity → gamification(PointsPort) → {profile, photo}`; `photo → discovery`; `discovery ↔ dialogue (invito)`; `{photo,discovery,dialogue} → betting/gazette (read-ports)`; `moderation` trasversale (ports verso tutti i domini content-owning); `gamification.finalize`/`gazette.final` innescati da `identity.close_event`.