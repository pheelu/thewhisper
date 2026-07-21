import { FormEvent, useCallback, useEffect, useState } from "react";
import { ApiError } from "../shared/api";
import { bets, type BetRound } from "../shared/bets";
import { game, type RosterEntry } from "../shared/game";
import { useWhisperSocket } from "../shared/realtime";
import { IconDice, IconTrophy } from "./icons";

function countdown(toIso: string): string {
  const ms = new Date(toIso).getTime() - Date.now();
  if (ms <= 0) return "0:00";
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function BetCard({ meId }: { meId: string }) {
  const [round, setRound] = useState<BetRound | null>(null);
  const [roster, setRoster] = useState<RosterEntry[]>([]);
  const [candidate, setCandidate] = useState("");
  const [amount, setAmount] = useState(10);
  const [tick, setTick] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await bets.current();
      setRound(res.round);
    } catch {
      /* scommesse non disponibili: nascondi la card */
    }
  }, []);

  useEffect(() => {
    void load();
    void game.roster().then(setRoster).catch(() => undefined);
    const t = setInterval(() => setTick((v) => v + 1), 1000);
    return () => clearInterval(t);
  }, [load]);

  // ogni 30s circa ricontrolla lo stato (le transizioni possono avvenire server-side)
  useEffect(() => {
    if (tick > 0 && tick % 30 === 0) void load();
  }, [tick, load]);

  useWhisperSocket((msg) => {
    if (msg.type.startsWith("betting.")) void load();
  });

  if (!round) return null;

  const targets = roster.filter((r) => r.participant_id !== meId);

  async function onStake(e: FormEvent) {
    e.preventDefault();
    if (!round || !candidate) return;
    setBusy(true);
    setError(null);
    try {
      await bets.stake(round.round_id, candidate, amount);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore.");
    } finally {
      setBusy(false);
    }
  }

  async function onCancel() {
    if (!round?.my_stake) return;
    setBusy(true);
    try {
      await bets.cancel(round.my_stake.stake_id);
      await load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="bet-card">
      <div className="bet-card__head">
        <span className="bet-card__label">
          <IconDice /> Scommessa dell'Alta Società
        </span>
        {round.status === "open" && (
          <span className="bet-card__timer">chiude tra {countdown(round.closes_at)}</span>
        )}
        {round.status === "locked" && (
          <span className="bet-card__timer">esito tra {countdown(round.measurement_end)}</span>
        )}
      </div>
      <h3 className="bet-card__title">{round.title}</h3>
      <p className="prose prose--sm">{round.prompt}</p>

      {round.total_pool > 0 && (
        <div className="bet-card__pool">Montepremi: <strong>{round.total_pool}</strong> punti</div>
      )}

      {round.pools.length > 0 && (
        <ul className="bet-pools">
          {round.pools.slice(0, 5).map((p) => (
            <li key={p.participant_id}>
              <span>{p.pseudonym}</span>
              <span>{p.pool} pt</span>
            </li>
          ))}
        </ul>
      )}

      {round.my_stake ? (
        <div className="bet-mine">
          Hai puntato <strong>{round.my_stake.amount}</strong> su{" "}
          <strong>{round.my_stake.candidate_pseudonym}</strong>
          {round.my_stake.status === "won" && (
            <span className="success">
              {" "}
              — hai vinto {round.my_stake.payout}! <IconTrophy />
            </span>
          )}
          {round.my_stake.status === "lost" && <span className="error"> — sfortuna…</span>}
          {round.my_stake.status === "refunded" && <span> — rimborsata</span>}
          {round.status === "open" && (
            <button className="chip" onClick={onCancel} disabled={busy}>
              Annulla
            </button>
          )}
        </div>
      ) : round.status === "open" ? (
        <form className="bet-form" onSubmit={onStake}>
          <select value={candidate} onChange={(e) => setCandidate(e.target.value)} required>
            <option value="">— su chi punti? —</option>
            {targets.map((t) => (
              <option key={t.participant_id} value={t.participant_id}>
                {t.pseudonym}
              </option>
            ))}
          </select>
          <input
            type="number"
            min={round.min_stake}
            max={round.max_stake}
            value={amount}
            onChange={(e) => setAmount(Number(e.target.value))}
          />
          <button className="btn btn--gold" type="submit" disabled={busy || !candidate}>
            Punta
          </button>
        </form>
      ) : (
        <p className="hint">Puntate chiuse — si attende l'esito…</p>
      )}

      {error && <p className="error">{error}</p>}
    </section>
  );
}
