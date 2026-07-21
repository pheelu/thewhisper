import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../shared/api";
import { dialogue, type ConversationDetail } from "../shared/dialogue";
import { useWhisperSocket } from "../shared/realtime";
import { IconMask, IconSend, IconSparkle } from "../components/icons";

export function Chat() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [conv, setConv] = useState<ConversationDetail | null>(null);
  const [body, setBody] = useState("");
  const [contact, setContact] = useState("");
  const [showContactBox, setShowContactBox] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const c = await dialogue.conversation(id);
      setConv(c);
      void dialogue.markRead(id).catch(() => undefined);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) navigate("/join");
      if (err instanceof ApiError && err.status === 404) navigate("/missives");
    }
  }, [id, navigate]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conv?.messages.length]);

  useWhisperSocket((msg) => {
    if (msg.type.startsWith("dialogue.") && msg.payload?.conversation_id === id) void load();
  });

  async function onSend(e: FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await dialogue.sendMessage(id, body.trim());
      setBody("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore.");
    } finally {
      setBusy(false);
    }
  }

  async function onReveal() {
    setBusy(true);
    setError(null);
    try {
      await dialogue.reveal(id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore di rete, riprova.");
    } finally {
      setBusy(false);
    }
  }

  async function onShareContact(e: FormEvent) {
    e.preventDefault();
    if (!contact.trim()) return;
    setBusy(true);
    try {
      await dialogue.setContact(id, contact.trim());
      setShowContactBox(false);
      setContact("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore.");
    } finally {
      setBusy(false);
    }
  }

  if (!conv) return <main className="screen screen--center">Apro la corrispondenza…</main>;

  const sysLabel = (b: string) =>
    b === "identity_revealed" ? (
      <>
        <IconMask /> L'ammiratore ha rivelato la propria identità
      </>
    ) : b === "contact_exchanged" ? (
      <>
        <IconSparkle /> Contatti scambiati!
      </>
    ) : (
      b
    );

  return (
    <main className="screen screen--chat">
      <header className="topbar topbar--split">
        <Link to="/missives" className="topbar__back">
          ‹ missive
        </Link>
        <div className="topbar__event">
          {conv.counterpart_masked && <IconMask />} {conv.counterpart_display}
        </div>
        <span />
      </header>

      {conv.i_am_initiator && !conv.i_am_revealed && (
        <div className="reveal-bar">
          Per l'altro sei «{conv.my_alias}».
          <button className="chip" onClick={onReveal} disabled={busy}>
            Rivela chi sei
          </button>
        </div>
      )}

      <div className="chat">
        {conv.messages.map((m) =>
          m.kind === "system" ? (
            <div key={m.message_id} className="chat__system">
              {sysLabel(m.body)}
            </div>
          ) : (
            <div key={m.message_id} className={"bubble" + (m.mine ? " bubble--mine" : "")}>
              {!m.mine && <div className="bubble__sender">{m.sender_display}</div>}
              {m.body}
            </div>
          ),
        )}
        <div ref={bottomRef} />
      </div>

      {conv.contact_exchanged && conv.contacts && (
        <div className="contacts-box">
          {conv.contacts
            .filter((c) => !c.mine)
            .map((c) => (
              <div key={c.participant_id}>
                <IconSparkle /> {c.contact_type}: <strong>{c.contact_value}</strong>
              </div>
            ))}
        </div>
      )}

      {!conv.contact_exchanged && (
        <div className="contact-cta">
          {conv.my_contact_consent ? (
            <span className="hint">
              Contatto condiviso — in attesa dell'altra parte
              {conv.i_am_initiator && !conv.i_am_revealed ? " (e del tuo reveal)" : ""}…
            </span>
          ) : showContactBox ? (
            <form className="comment-form" onSubmit={onShareContact}>
              <input
                value={contact}
                onChange={(e) => setContact(e.target.value)}
                placeholder="@tuo_instagram"
                maxLength={120}
              />
              <button className="btn btn--ghost" type="submit" disabled={busy}>
                Condividi
              </button>
            </form>
          ) : (
            <button className="chip" onClick={() => setShowContactBox(true)}>
              <IconSparkle /> Proponi scambio contatti
            </button>
          )}
        </div>
      )}

      {error && <p className="error">{error}</p>}

      <form className="comment-form comment-form--sticky" onSubmit={onSend}>
        <input
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Scrivi…"
          maxLength={1000}
        />
        <button className="btn btn--gold btn--send" type="submit" disabled={busy || !body.trim()}>
          <IconSend size="1.15rem" />
        </button>
      </form>
    </main>
  );
}
