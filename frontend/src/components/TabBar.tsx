import { NavLink } from "react-router-dom";

const tabs = [
  { to: "/home", label: "Salotto", icon: "♛" },
  { to: "/feed", label: "Feed", icon: "🖼" },
  { to: "/capture", label: "Scatta", icon: "✎" },
  { to: "/profile", label: "Profilo", icon: "✒︎" },
];

export function TabBar() {
  return (
    <nav className="tabbar">
      {tabs.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          className={({ isActive }) => "tabbar__item" + (isActive ? " tabbar__item--active" : "")}
        >
          <span className="tabbar__icon">{t.icon}</span>
          <span className="tabbar__label">{t.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
