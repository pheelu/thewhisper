import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../shared/api";
import type { LeaderboardEntry, Me } from "../shared/types";
import { useWhisperSocket } from "../shared/realtime";
import { TabBar } from "../components/TabBar";
import { BetCard } from "../components/BetCard";
import { IconCamera, IconCameraOff, IconFeed, IconQuill } from "../components/icons";

export function Home() {
  const navigate = useNavigate();
  const [me, setMe] = useState<Me | null>(null);
  const [board, setBoard] = useState<LeaderboardEntry[]>([]);
  const [present, setPresent] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadAll = useCallback(async () => {
    try {
      setLoadError(null);
      const [meRes, boardRes] = await Promise.all([
        api.get<Me>("/api/v1/me"),
        api.get<{ items: LeaderboardEntry[] }>("/api/v1/leaderboard"),
      ]);
      setMe(meRes);
      setBoard(boardRes.items);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        navigate("/join");
        return;
      }
      setLoadError(err instanceof ApiError ? err.message : "Problema di connessione.");
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  useWhisperSocket(
    (msg) => {
      if (msg.type.startsWith("gamification.")) {
        // aggiorna classifica E il proprio punteggio nella hero-card
        void loadAll();
      } else if (msg.type === "presence.updated") {
        setPresent((msg.payload?.active as string[] | undefined)?.length ?? 0);
      }
    },
    { onConnect: () => void loadAll() },
  );

  async function toggleConsent() {
    if (!me || busy) return;
    const next = !me.participant.is_photographable;
    setBusy(true);
    try {
      const p = await api.post<Me["participant"]>("/api/v1/me/consent", {
        is_photographable: next,
      });
      setMe({ ...me, participant: p });
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Errore di rete, riprova.");
    } finally {
      setBusy(false);
    }
  }

  async function leave() {
    try {
      await api.post("/api/v1/me/leave");
    } catch {
      /* comunque si esce */
    } finally {
      navigate("/");
    }
  }

  if (loading) return <main className="screen screen--center">Preparo il salotto…</main>;

  if (!me) {
    return (
      <main className="screen screen--center">
        <p className="error">{loadError ?? "Impossibile caricare il salotto."}</p>
        <button className="btn btn--gold" onClick={() => void loadAll()}>
          Riprova
        </button>
      </main>
    );
  }

  const { participant, event } = me;
  const title = participant.noble_title
    ? participant.noble_title.charAt(0).toUpperCase() + participant.noble_title.slice(1)
    : "Nobile";

  return (
    <main className="screen screen--tabbed">
      <header className="topbar topbar--split">
        <div>
          <div className="topbar__event">{event.name}</div>
          {event.venue_name && <div className="topbar__venue">{event.venue_name}</div>}
        </div>
        <div className="pill">● {present} in sala</div>
      </header>

      <section className="hero-card">
        <div className="hero-card__title">{title}</div>
        <div className="hero-card__name">{participant.pseudonym}</div>
        <div className="hero-card__score">
          <span>{participant.score}</span> punti pettegolezzo
        </div>
        <button className="chip" onClick={toggleConsent} disabled={busy}>
          {participant.is_photographable ? (
            <>
              <IconCamera /> Fotografabile
            </>
          ) : (
            <>
              <IconCameraOff /> Non fotografabile
            </>
          )}{" "}
          · tocca per cambiare
        </button>
      </section>

      {loadError && <p className="error">{loadError}</p>}

      {participant.role === "guest" && <BetCard meId={participant.id} />}

      <section>
        <h2 className="section-title">Classifica dell'Alta Società</h2>
        <ol className="board">
          {board.map((e) => (
            <li key={e.participant_id} className={e.participant_id === participant.id ? "me" : ""}>
              <span className="board__rank">{e.rank}</span>
              <span className="board__name">
                {e.pseudonym}
                {e.noble_title && <em> · {e.noble_title}</em>}
              </span>
              <span className="board__score">{e.score}</span>
            </li>
          ))}
          {board.length === 0 && <li className="board__empty">Ancora nessun punteggio…</li>}
        </ol>
      </section>

      <section>
        <h2 className="section-title">Che cosa desideri fare?</h2>
        <div className="actions">
          <Link to="/capture" className="action-card">
            <IconCamera size="1.5rem" className="action-card__icon" />
            Scatta una Whisper
          </Link>
          <Link to="/feed" className="action-card">
            <IconFeed size="1.5rem" className="action-card__icon" />
            Sbircia il feed
          </Link>
          <Link to="/profile" className="action-card">
            <IconQuill size="1.5rem" className="action-card__icon" />
            Il tuo segreto
          </Link>
        </div>
      </section>

      <button className="btn btn--ghost" onClick={leave}>
        Lascia la serata
      </button>

      <TabBar />
    </main>
  );
}
