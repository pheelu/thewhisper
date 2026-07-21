import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../shared/api";
import { game, type RosterEntry } from "../shared/game";
import type { Me } from "../shared/types";
import { TabBar } from "../components/TabBar";
import { IconCamera } from "../components/icons";

export function Capture() {
  const navigate = useNavigate();
  const [meId, setMeId] = useState<string | null>(null);
  const [roster, setRoster] = useState<RosterEntry[]>([]);
  const [subject, setSubject] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const me = await api.get<Me>("/api/v1/me");
        setMeId(me.participant.id);
        setRoster(await game.roster());
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) navigate("/join");
      }
    })();
  }, [navigate]);

  const targets = useMemo(
    () => roster.filter((r) => r.is_photographable && r.participant_id !== meId),
    [roster, meId],
  );

  function onPick(f: File | undefined) {
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file || !subject) return;
    setBusy(true);
    setError(null);
    try {
      const draft = await game.createDraft(subject, title.trim(), file.type);
      await game.upload(draft.upload_url, file);
      await game.publish(draft.photo_id);
      navigate(`/photo/${draft.photo_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Qualcosa è andato storto.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="screen screen--tabbed">
      <h1 className="title">Diventa Cacciatore</h1>
      <p className="prose prose--sm">
        Immortala un dettaglio intrigante di un ospite <strong>consenziente</strong>, dagli un
        titolo misterioso e pubblicalo. La tua identità resterà segreta.
      </p>

      <form className="form" onSubmit={onSubmit}>
        <label className="field">
          <span>La preda (chi ha acconsentito)</span>
          <select value={subject} onChange={(e) => setSubject(e.target.value)} required>
            <option value="">— scegli un ospite —</option>
            {targets.map((t) => (
              <option key={t.participant_id} value={t.participant_id}>
                {t.pseudonym}
                {t.noble_title ? ` · ${t.noble_title}` : ""}
              </option>
            ))}
          </select>
          {targets.length === 0 && (
            <small className="hint">Nessun ospite fotografabile al momento.</small>
          )}
        </label>

        <label className="capture-tile">
          {preview ? (
            <img src={preview} alt="anteprima" />
          ) : (
            <span className="capture-tile__cta">
              <IconCamera size="1.6rem" /> Tocca per scattare o scegliere
            </span>
          )}
          <input
            type="file"
            accept="image/*"
            capture="environment"
            hidden
            onChange={(e) => onPick(e.target.files?.[0])}
          />
        </label>

        <label className="field">
          <span>Titolo misterioso</span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Es. « Un guanto lasciato cadere »"
            maxLength={120}
            required
          />
        </label>

        {error && <p className="error">{error}</p>}

        <button className="btn btn--gold" type="submit" disabled={busy || !file || !subject}>
          {busy ? "Pubblico la Whisper…" : "Pubblica la Whisper"}
        </button>
      </form>

      <TabBar />
    </main>
  );
}
