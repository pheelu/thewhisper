import { Routes, Route } from "react-router-dom";
import { Landing } from "./pages/Landing";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      {/* Le rotte di gioco (join, feed, profilo, chat, scommesse...) verranno
          aggiunte man mano che i domìni vengono implementati. */}
    </Routes>
  );
}
