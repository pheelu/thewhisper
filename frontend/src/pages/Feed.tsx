import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { game, type Photo } from "../shared/game";
import { ApiError } from "../shared/api";
import { useWhisperSocket } from "../shared/realtime";
import { TabBar } from "../components/TabBar";

const LIVE = new Set([
  "photo.published",
  "photo.removed",
  "photo.subject_revealed",
  "discovery.photo_solved",
  "discovery.comment_added",
]);

export function Feed() {
  const navigate = useNavigate();
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setPhotos(await game.feed());
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) navigate("/join");
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    void load();
  }, [load]);

  useWhisperSocket((msg) => {
    if (LIVE.has(msg.type)) void load();
  });

  return (
    <main className="screen screen--tabbed">
      <header className="topbar topbar--split">
        <h1 className="title">I Whispers della serata</h1>
        <Link to="/capture" className="pill pill--action">
          + Scatta
        </Link>
      </header>

      {loading && <p className="prose">Sbircio i pettegolezzi…</p>}

      {!loading && photos.length === 0 && (
        <div className="empty">
          <div className="crest crest--sm">🕯</div>
          <p className="prose">
            Ancora nessuna Foto Whisper. Sii il primo Cacciatore: immortala un dettaglio
            intrigante di un ospite consenziente.
          </p>
          <Link to="/capture" className="btn btn--gold">
            Scatta la prima Whisper
          </Link>
        </div>
      )}

      <div className="feed">
        {photos.map((p) => (
          <button key={p.photo_id} className="whisper" onClick={() => navigate(`/photo/${p.photo_id}`)}>
            {p.image_url && <img src={p.image_url} alt={p.mysterious_title} loading="lazy" />}
            <div className="whisper__body">
              <div className="whisper__title">« {p.mysterious_title} »</div>
              <div className="whisper__meta">
                <span>💬 {p.comment_count}</span>
                <span>🎯 {p.correct_guess_count}</span>
                <span className={p.subject_revealed ? "revealed" : "mystery"}>
                  {p.subject_revealed && p.subject
                    ? `Svelato: ${p.subject.pseudonym}`
                    : "Chi sarà mai?"}
                </span>
              </div>
            </div>
          </button>
        ))}
      </div>

      <TabBar />
    </main>
  );
}
