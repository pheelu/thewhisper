import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Link } from "react-router-dom";
import { api, ApiError, WS_BASE } from "../shared/api";
import type { LeaderboardEntry, Me } from "../shared/types";
import { TabBar } from "../components/TabBar";

export function Home() {
  const navigate = useNavigate();
  const [me, setMe] = useState<Me | null>(null);
  const [board, setBoard] = useState<LeaderboardEntry[]>([]);
  const [present, setPresent] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  const loadBoard = useCallback(async () => {
    const res = await api.get<{ items: LeaderboardEntry[] }>("/api/v1/leaderboard");
    setBoard(res.items);
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const meRes = await api.get<Me>("/api/v1/me");
        if (!alive) return;
        setMe(meRes);
        await loadBoard();
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          navigate("/join");
          return;
        }
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [navigate, loadBoard]);

  // WebSocket: aggiornamenti live di classifica e presenze.
  useEffect(() => {
    if (!me) return;
    const ws = new WebSocket(`${WS_BASE}/api/v1/ws`);
    wsRef.current = ws;
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (typeof msg.type === "string" && msg.type.startsWith("gamification.")) {
          void loadBoard();
        } else if (msg.type === "presence.updated") {
          setPresent((msg.payload?.active ?? []).length);
        }
      } catch {
        /* ignora frame non-JSON */
      }
    };
    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping", payload: {} }));
    }, 25000);
    return () => {
      clearInterval(ping);
      ws.close();
    };
  }, [me, loadBoard]);

  async function toggleConsent() {
    if (!me) return;
    const next = !me.participant.is_photographable;
    const p = await api.post<Me["participant"]>("/api/v1/me/consent", { is_photographable: next });
    setMe({ ...me, participant: p });
  }

  async function leave() {
    try {
      await api.post("/api/v1/me/leave");
    } finally {
      navigate("/");
    }
  }

  if (loading) return <main className="screen screen--center">Preparo il salotto…</main>;
  if (!me) return null;

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
        <button className="chip" onClick={toggleConsent}>
          {participant.is_photographable ? "📸 Fotografabile" : "🚫 Non fotografabile"} · tocca per
          cambiare
        </button>
      </section>

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
            <span className="action-card__icon">✎</span>
            Scatta una Whisper
          </Link>
          <Link to="/feed" className="action-card">
            <span className="action-card__icon">🖼</span>
            Sbircia il feed
          </Link>
          <Link to="/profile" className="action-card">
            <span className="action-card__icon">✒︎</span>
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
