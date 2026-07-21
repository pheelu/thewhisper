import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../shared/api";
import {
  game,
  type Comment,
  type GuessResult,
  type Photo,
  type RosterEntry,
} from "../shared/game";
import type { Me } from "../shared/types";
import { useWhisperSocket } from "../shared/realtime";

export function PhotoDetail() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [meId, setMeId] = useState<string | null>(null);
  const [photo, setPhoto] = useState<Photo | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [roster, setRoster] = useState<RosterEntry[]>([]);
  const [amSubject, setAmSubject] = useState(false);
  const [amHunter, setAmHunter] = useState(false);
  const [isHost, setIsHost] = useState(false);
  const [myCorrect, setMyCorrect] = useState(false);
  const [attemptsLeft, setAttemptsLeft] = useState(3);
  const [result, setResult] = useState<GuessResult | null>(null);
  const [commentBody, setCommentBody] = useState("");
  const [candidate, setCandidate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refreshPhoto = useCallback(async () => {
    try {
      setPhoto(await game.photo(id));
      setComments(await game.comments(id));
    } catch {
      /* la foto potrebbe essere stata rimossa */
    }
  }, [id]);

  useEffect(() => {
    (async () => {
      try {
        const [me, ph, cm, rt, mg, ofMe, mine] = await Promise.all([
          api.get<Me>("/api/v1/me"),
          game.photo(id),
          game.comments(id),
          game.roster(),
          game.myGuesses(id),
          game.ofMe().catch(() => [] as Photo[]),
          game.mine().catch(() => [] as Photo[]),
        ]);
        setMeId(me.participant.id);
        setIsHost(me.participant.role === "host");
        setPhoto(ph);
        setComments(cm);
        setRoster(rt);
        setMyCorrect(mg.some((g) => g.is_correct));
        setAttemptsLeft(Math.max(0, 3 - mg.length));
        setAmSubject(ofMe.some((p) => p.photo_id === id));
        setAmHunter(mine.some((p) => p.photo_id === id));
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) navigate("/join");
      }
    })();
  }, [id, navigate]);

  useWhisperSocket((msg) => {
    if (msg.payload?.photo_id === id) void refreshPhoto();
  });

  async function onComment(e: FormEvent) {
    e.preventDefault();
    if (!commentBody.trim()) return;
    setBusy(true);
    try {
      await game.addComment(id, commentBody.trim());
      setCommentBody("");
      setComments(await game.comments(id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore.");
    } finally {
      setBusy(false);
    }
  }

  async function onGuess() {
    if (!candidate) return;
    setBusy(true);
    setError(null);
    try {
      const r = await game.guess(id, candidate);
      setResult(r);
      setAttemptsLeft(r.attempts_left);
      if (r.is_correct) setMyCorrect(true);
      setCandidate("");
      await refreshPhoto();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore.");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    const msg = amSubject
      ? "Vuoi far rimuovere questa foto che ti ritrae?"
      : "Vuoi rimuovere questa foto?";
    if (!window.confirm(msg)) return;
    setBusy(true);
    try {
      await api.del(`/api/v1/photos/${id}`);
      navigate("/feed");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore.");
      setBusy(false);
    }
  }

  async function onReveal() {
    setBusy(true);
    try {
      setPhoto(await game.reveal(id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore.");
    } finally {
      setBusy(false);
    }
  }

  if (!photo) return <main className="screen screen--center">Carico la Whisper…</main>;

  const others = roster.filter((r) => r.participant_id !== meId);
  const canGuess = !myCorrect && !amSubject && attemptsLeft > 0;

  return (
    <main className="screen">
      <header className="topbar">
        <Link to="/feed" className="topbar__back">
          ‹ feed
        </Link>
      </header>

      {photo.image_url && <img className="detail-img" src={photo.image_url} alt={photo.mysterious_title} />}
      <h1 className="detail-title">« {photo.mysterious_title} »</h1>
      <div className="detail-meta">
        {photo.subject_revealed && photo.subject ? (
          <span className="revealed">Il Soggetto era {photo.subject.pseudonym} 🎭</span>
        ) : (
          <span className="mystery">Chi sarà il misterioso Soggetto?</span>
        )}
        <span>🎯 {photo.correct_guess_count} indovinati</span>
      </div>

      {amSubject && !photo.subject_revealed && (
        <button className="btn btn--gold" onClick={onReveal} disabled={busy}>
          Sei tu il Soggetto? Rivelati
        </button>
      )}

      {!photo.subject_revealed && (
        <section className="guess-box">
          <h2 className="section-title">Indovina il Soggetto</h2>
          {myCorrect ? (
            <p className="prose success">Hai indovinato! Che fiuto. 🎉</p>
          ) : amSubject ? (
            <p className="prose prose--sm">Sei tu il Soggetto: goditi il mistero altrui.</p>
          ) : canGuess ? (
            <div className="guess-row">
              <select value={candidate} onChange={(e) => setCandidate(e.target.value)}>
                <option value="">— chi è? —</option>
                {others.map((r) => (
                  <option key={r.participant_id} value={r.participant_id}>
                    {r.pseudonym}
                  </option>
                ))}
              </select>
              <button className="btn btn--gold" onClick={onGuess} disabled={busy || !candidate}>
                Indovina
              </button>
              <small className="hint">{attemptsLeft} tentativi rimasti</small>
            </div>
          ) : (
            <p className="prose prose--sm">Tentativi esauriti per questa Whisper.</p>
          )}
          {result && !result.is_correct && (
            <p className="error">Non è lui/lei… riprova! ({result.attempts_left} rimasti)</p>
          )}
          {result?.is_correct && (
            <p className="success">Esatto! +{result.points_awarded} punti (rango {result.guess_rank}).</p>
          )}
        </section>
      )}

      <section>
        <h2 className="section-title">Pettegolezzi</h2>
        <ul className="comments">
          {comments.map((c) => (
            <li key={c.comment_id}>
              <strong>{c.author_pseudonym ?? "Anonimo"}</strong> {c.body}
            </li>
          ))}
          {comments.length === 0 && <li className="muted">Ancora nessun commento…</li>}
        </ul>
        <form className="comment-form" onSubmit={onComment}>
          <input
            value={commentBody}
            onChange={(e) => setCommentBody(e.target.value)}
            placeholder="Sussurra qualcosa…"
            maxLength={500}
          />
          <button className="btn btn--ghost" type="submit" disabled={busy}>
            Invia
          </button>
        </form>
      </section>

      {error && <p className="error">{error}</p>}

      {(amSubject || amHunter || isHost) && (
        <button className="btn btn--ghost btn--danger" onClick={onDelete} disabled={busy}>
          {amSubject ? "🚫 Rimuovi questa foto (sei tu il Soggetto)" : "🗑 Rimuovi questa foto"}
        </button>
      )}
    </main>
  );
}
