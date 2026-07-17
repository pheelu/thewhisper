import { FormEvent, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { api, ApiError } from "../shared/api";
import { NOBLE_TITLES, type Me } from "../shared/types";

export function Join() {
  const { code } = useParams();
  const navigate = useNavigate();
  const [joinCode, setJoinCode] = useState(code ?? "");
  const [pseudonym, setPseudonym] = useState("");
  const [nobleTitle, setNobleTitle] = useState<string>("");
  const [photographable, setPhotographable] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post<Me>("/api/v1/join", {
        join_code: joinCode.trim(),
        pseudonym: pseudonym.trim(),
        noble_title: nobleTitle || null,
        is_photographable: photographable,
      });
      navigate("/home");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore di rete.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="screen">
      <header className="topbar">
        <Link to="/" className="topbar__back">
          ‹ indietro
        </Link>
      </header>
      <div className="crest crest--sm">✒︎</div>
      <h1 className="title">Presentati alla Società</h1>
      <p className="prose prose--sm">
        Scegli un nome e un titolo. Il tuo vero io resterà un mistero… per ora.
      </p>

      <form className="form" onSubmit={onSubmit}>
        <label className="field">
          <span>Codice della serata</span>
          <input
            value={joinCode}
            onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
            placeholder="Es. HY7YNJET"
            autoCapitalize="characters"
            required
          />
        </label>

        <label className="field">
          <span>Pseudonimo</span>
          <input
            value={pseudonym}
            onChange={(e) => setPseudonym(e.target.value)}
            placeholder="Es. Lady Whistledown"
            maxLength={40}
            required
          />
        </label>

        <label className="field">
          <span>Titolo nobiliare</span>
          <select value={nobleTitle} onChange={(e) => setNobleTitle(e.target.value)}>
            <option value="">— scegli —</option>
            {NOBLE_TITLES.map((t) => (
              <option key={t} value={t}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </option>
            ))}
          </select>
        </label>

        <label className="check">
          <input
            type="checkbox"
            checked={photographable}
            onChange={(e) => setPhotographable(e.target.checked)}
          />
          <span>Accetto di poter essere fotografato/a durante il gioco</span>
        </label>

        {error && <p className="error">{error}</p>}

        <button className="btn btn--gold" type="submit" disabled={busy}>
          {busy ? "Entro nel salotto…" : "Entra nel salotto"}
        </button>
      </form>
    </main>
  );
}
