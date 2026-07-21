import { Routes, Route } from "react-router-dom";
import { Landing } from "./pages/Landing";
import { Join } from "./pages/Join";
import { Host } from "./pages/Host";
import { Home } from "./pages/Home";
import { Feed } from "./pages/Feed";
import { Capture } from "./pages/Capture";
import { PhotoDetail } from "./pages/PhotoDetail";
import { ProfileEdit } from "./pages/ProfileEdit";
import { Conversations } from "./pages/Conversations";
import { Chat } from "./pages/Chat";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/host" element={<Host />} />
      <Route path="/join" element={<Join />} />
      <Route path="/j/:code" element={<Join />} />
      <Route path="/home" element={<Home />} />
      <Route path="/feed" element={<Feed />} />
      <Route path="/capture" element={<Capture />} />
      <Route path="/photo/:id" element={<PhotoDetail />} />
      <Route path="/profile" element={<ProfileEdit />} />
      <Route path="/missives" element={<Conversations />} />
      <Route path="/chat/:id" element={<Chat />} />
    </Routes>
  );
}
