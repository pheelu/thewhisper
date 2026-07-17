import { Routes, Route } from "react-router-dom";
import { Landing } from "./pages/Landing";
import { Join } from "./pages/Join";
import { Host } from "./pages/Host";
import { Home } from "./pages/Home";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/host" element={<Host />} />
      <Route path="/join" element={<Join />} />
      <Route path="/j/:code" element={<Join />} />
      <Route path="/home" element={<Home />} />
    </Routes>
  );
}
