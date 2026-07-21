import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../shared/api";

interface CreatedEvent {
  event: { id: string; name: string; status: string; join_code: string };
  join_url: string;
}

function isoLocalPlusHours(hours: number): string {
  return new Date(Date.now() + hours * 3600_000).toISOString();
}

export function Host() {
  const navigate = useNavigate();
  const [name, setName] = useState("Il Ballo dei Bridgerton");
  const [venue, setVenue] = useState("");
  const [secret, setSecret] = useState("");
  const [created, setCreated] = useState<CreatedEvent | null>(null);
  const [opened, setOpened] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<CreatedEvent>("/api/v1/events", {
        name: name.trim(),
        venue_name: venue.trim() || null,
        starts_at: isoLocalPlusHours(-0.1),
        ends_at: isoLocalPlusHours(6),
        timezone: "Europe/Rome",
        host_secret: secret,
        host_pseudonym: "Padrone di Casa",
      });
      setCreated(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore di rete.");
    } finally {
      setBusy(false);
    }
  }

  async function open() {
    if (!created) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/v1/events/${created.event.id}/open`);
      setOpened(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore di rete.");
    } finally {
      setBusy(false);
    }
  }

  if (created) {
    return (
      <main className="screen">
        <header className="topbar">
          <Link to="/" className="topbar__back">
            ‹ home
          </Link>
        </header>
        <div className="crest crest--sm">♛</div>
        <h1 className="title">{created.event.name}</h1>
        <p className="prose prose--sm">
          Stato:{" "}
          <strong style={{ color: opened ? "var(--whisper-gold-soft)" : "var(--whisper-muted)" }}>
            {opened ? "aperta" : "bozza"}
          </strong>
        </p>

        <div className="card card--code">
          <span className="card__label">Codice serata</span>
          <div className="code">{created.event.join_code}</div>
          <img
            className="qr"
            src={`/api/v1/events/${created.event.id}/qr.png`}
            alt="QR della serata"
          />
          <a className="linky" href={created.join_url} target="_blank" rel="noreferrer">
            {created.join_url}
          </a>
        </div>

        {error && <p className="error">{error}</p>}

        <div className="stack">
          {!opened ? (
            <button className="btn btn--gold" onClick={open} disabled={busy}>
              {busy ? "Apro le porte…" : "Apri la serata"}
            </button>
          ) : (
            <button className="btn btn--gold" onClick={() => navigate("/home")}>
              Entra nel salotto
            </button>
          )}
          <Link className="btn btn--ghost" to={`/j/${created.event.join_code}`}>
            Vai alla schermata d'ingresso
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="screen">
      <header className="topbar">
        <Link to="/" className="topbar__back">
          ‹ indietro
        </Link>
      </header>
      <div className="crest crest--sm">♛</div>
      <h1 className="title">Ospita una serata</h1>
      <p className="prose prose--sm">
        Crea il tuo salotto dell'alta società. Otterrai un codice da condividere con gli ospiti.
      </p>

      <form className="form" onSubmit={create}>
        <label className="field">
          <span>Nome della serata</span>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required />
        </label>
        <label className="field">
          <span>Locale (facoltativo)</span>
          <input value={venue} onChange={(e) => setVenue(e.target.value)} maxLength={120} />
        </label>
        <label className="field">
          <span>Segreto organizzatore</span>
          <input
            type="password"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            placeholder="Ti servirà per gestire la serata"
            minLength={4}
            required
          />
        </label>

        {error && <p className="error">{error}</p>}

        <button className="btn btn--gold" type="submit" disabled={busy}>
          {busy ? "Preparo il salotto…" : "Crea la serata"}
        </button>
      </form>
    </main>
  );
}
