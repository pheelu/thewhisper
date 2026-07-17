import { useNavigate } from "react-router-dom";

export function Landing() {
  const navigate = useNavigate();
  return (
    <main className="screen screen--center">
      <div className="crest">✒︎</div>
      <p className="eyebrow">L'Alta Società vi attende</p>
      <h1 className="display">The Whisper</h1>
      <p className="subtitle">Il gioco del mistero e del corteggiamento</p>
      <p className="prose">
        Scansiona il QR all'ingresso del locale — oppure entra col codice della serata —
        scegli il tuo titolo nobiliare e inizia a raccogliere pettegolezzi.
      </p>
      <div className="stack">
        <button className="btn btn--gold" onClick={() => navigate("/join")}>
          Entra in una serata
        </button>
        <button className="btn btn--ghost" onClick={() => navigate("/host")}>
          Crea una serata (organizzatore)
        </button>
      </div>
    </main>
  );
}
