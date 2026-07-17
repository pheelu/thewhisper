import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../shared/api";
import { game, type MyProfile } from "../shared/game";
import type { Me } from "../shared/types";
import { TabBar } from "../components/TabBar";

export function ProfileEdit() {
  const navigate = useNavigate();
  const [me, setMe] = useState<Me | null>(null);
  const [profile, setProfile] = useState<MyProfile | null>(null);
  const [secret, setSecret] = useState("");
  const [motto, setMotto] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [m, p] = await Promise.all([api.get<Me>("/api/v1/me"), game.myProfile()]);
        setMe(m);
        setProfile(p);
        setSecret(p.secret_text ?? "");
        setMotto(p.motto ?? "");
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) navigate("/join");
      }
    })();
  }, [navigate]);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const p = await game.updateProfile({ secret_text: secret.trim(), motto: motto.trim() });
      setProfile(p);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore.");
    } finally {
      setBusy(false);
    }
  }

  if (!me || !profile) return <main className="screen screen--center">Carico il profilo…</main>;

  const title = me.participant.noble_title
    ? me.participant.noble_title.charAt(0).toUpperCase() + me.participant.noble_title.slice(1)
    : "Nobile";

  return (
    <main className="screen screen--tabbed">
      <div className="hero-card hero-card--sm">
        <div className="hero-card__title">{title}</div>
        <div className="hero-card__name">{me.participant.pseudonym}</div>
        <div className="hero-card__score">
          <span>{me.participant.score}</span> punti · {profile.is_complete ? "profilo completo ✓" : "profilo incompleto"}
        </div>
      </div>

      <p className="prose prose--sm">
        Un buon nobile custodisce un <strong>segreto</strong>. Scrivine uno intrigante: verrà
        svelato solo se sceglierai di rivelarti. Completa il profilo per guadagnare punti.
      </p>

      <form className="form" onSubmit={onSave}>
        <label className="field">
          <span>Il tuo motto</span>
          <input
            value={motto}
            onChange={(e) => setMotto(e.target.value)}
            placeholder="Es. Chi sussurra, regna"
            maxLength={140}
          />
        </label>
        <label className="field">
          <span>Il tuo segreto</span>
          <textarea
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            placeholder="Es. Scrivo poesie segrete a mezzanotte…"
            maxLength={280}
            rows={3}
          />
        </label>

        {error && <p className="error">{error}</p>}
        {saved && <p className="success">Profilo aggiornato ✓</p>}

        <button className="btn btn--gold" type="submit" disabled={busy}>
          {busy ? "Salvo…" : "Salva il profilo"}
        </button>
      </form>

      <TabBar />
    </main>
  );
}
