import { NavLink } from "react-router-dom";
import { IconCamera, IconCrown, IconFeed, IconMissive, IconQuill } from "./icons";

const tabs = [
  { to: "/home", label: "Salotto", Icon: IconCrown },
  { to: "/feed", label: "Feed", Icon: IconFeed },
  { to: "/capture", label: "Scatta", Icon: IconCamera },
  { to: "/missives", label: "Missive", Icon: IconMissive },
  { to: "/profile", label: "Profilo", Icon: IconQuill },
];

export function TabBar() {
  return (
    <nav className="tabbar">
      {tabs.map(({ to, label, Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) => "tabbar__item" + (isActive ? " tabbar__item--active" : "")}
        >
          <Icon size="1.3rem" className="tabbar__icon" />
          <span className="tabbar__label">{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
