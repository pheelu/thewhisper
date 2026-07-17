export function Landing() {
  return (
    <main className="landing">
      <div className="landing__crest">✒︎</div>
      <p className="landing__eyebrow">L'Alta Società vi attende</p>
      <h1 className="landing__title">The Whisper</h1>
      <p className="landing__subtitle">Il gioco del mistero e del corteggiamento</p>
      <p className="landing__body">
        Scansiona il QR all'ingresso del locale per entrare nel salotto, scegliere
        il tuo titolo nobiliare e iniziare a raccogliere pettegolezzi.
      </p>
      <button className="landing__cta" disabled>
        In arrivo — scansiona il QR all'evento
      </button>
    </main>
  );
}
