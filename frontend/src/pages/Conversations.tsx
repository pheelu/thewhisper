import { FormEvent, useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../shared/api";
import { dialogue, type ConversationSummary } from "../shared/dialogue";
import { game, type RosterEntry } from "../shared/game";
import type { Me } from "../shared/types";
import { useWhisperSocket } from "../shared/realtime";
import { TabBar } from "../components/TabBar";
import { IconMask, IconSparkle } from "../components/icons";

export function Conversations() {
  const navigate = useNavigate();
  const [meId, setMeId] = useState<string | null>(null);
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [roster, setRoster] = useState<RosterEntry[]>([]);
  const [composing, setComposing] = useState(false);
  const [recipient, setRecipient] = useState("");
  const [body, setBody] = useState("");
  const [sentAlias, setSentAlias] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setItems(await dialogue.conversations());
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) navigate("/join");
    }
  }, [navigate]);

  useEffect(() => {
    (async () => {
      try {
        const me = await api.get<Me>("/api/v1/me");
        setMeId(me.participant.id);
        await load();
        setRoster(await game.roster());
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) navigate("/join");
      }
    })();
  }, [navigate, load]);

  useWhisperSocket((msg) => {
    if (msg.type.startsWith("dialogue.")) void load();
  });

  async function onSend(e: FormEvent) {
    e.preventDefault();
    if (!recipient || !body.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await dialogue.sendMissive(recipient, body.trim());
      setSentAlias(res.your_alias);
      setBody("");
      setRecipient("");
      setComposing(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore.");
    } finally {
      setBusy(false);
    }
  }

  const targets = roster.filter((r) => r.participant_id !== meId);

  return (
    <main className="screen screen--tabbed">
      <header className="topbar topbar--split">
        <h1 className="title">Missive Segrete</h1>
        <button className="pill pill--action" onClick={() => setComposing((v) => !v)}>
          {composing ? "chiudi" : "＋ Nuova missiva"}
        </button>
      </header>

      {sentAlias && (
        <p className="success">
          Missiva consegnata. Per il destinatario sei «{sentAlias}» — finché non ti rivelerai.
        </p>
      )}

      {composing && (
        <form className="form guess-box" onSubmit={onSend}>
          <label className="field">
            <span>Al nobile…</span>
            <select value={recipient} onChange={(e) => setRecipient(e.target.value)} required>
              <option value="">— scegli il destinatario —</option>
              {targets.map((t) => (
                <option key={t.participant_id} value={t.participant_id}>
                  {t.pseudonym}
                  {t.noble_title ? ` · ${t.noble_title}` : ""}
                </option>
              ))}
            </select>
            {targets.length === 0 && (
              <small className="hint">Nessun altro nobile in sala al momento.</small>
            )}
          </label>
          <label className="field">
            <span>La tua missiva (firmata con uno pseudonimo misterioso)</span>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Vi ho notato dall'altro lato del salotto…"
              maxLength={1000}
              rows={3}
              required
            />
          </label>
          {error && <p className="error">{error}</p>}
          <button className="btn btn--gold" type="submit" disabled={busy}>
            {busy ? "Sigillo la missiva…" : "Invia in segreto"}
          </button>
        </form>
      )}

      <ul className="convlist">
        {items.map((c) => (
          <li key={c.conversation_id}>
            <button className="convitem" onClick={() => navigate(`/chat/${c.conversation_id}`)}>
              <div className="convitem__row">
                <span className="convitem__name">
                  {c.counterpart.is_masked && <IconMask />}{" "}
                  {c.counterpart.display_name}
                  {c.counterpart.noble_title && <em> · {c.counterpart.noble_title}</em>}
                </span>
                {c.unread_count > 0 && <span className="badge">{c.unread_count}</span>}
              </div>
              <div className="convitem__preview">
                {c.contact_exchanged && (
                  <>
                    <IconSparkle /> contatti scambiati ·{" "}
                  </>
                )}
                {c.last_body ?? "…"}
              </div>
            </button>
          </li>
        ))}
        {items.length === 0 && !composing && (
          <li className="board__empty" style={{ listStyle: "none" }}>
            Nessuna missiva… per ora. Osa: scrivi a qualcuno che ti incuriosisce.
          </li>
        )}
      </ul>

      <TabBar />
    </main>
  );
}
