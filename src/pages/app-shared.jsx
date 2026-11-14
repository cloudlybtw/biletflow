import { t as translate, useLocale, setLocale, dateTime } from "../lib/locale";
import { useState } from "react";
import { money, navGroups } from "./app-data";
import { useSession } from "../lib/session-context";
import { logout } from "../lib/client";
export function Link({ to, children, className = "" }) {
  return (
    <a className={className} href={`/#${to}`}>
      {children}
    </a>
  );
}
export function Topbar() {
  const { user } = useSession();
  const [error, setError] = useState("");
  return (
    <header className="bf-top">
      <a href="/" className="bf-brand">
        biletflow<span>.</span>
      </a>
      <div className="bf-top-right">
        <LanguagePicker />
        <Link to="/events">{translate("Explore events")}</Link>
        {user ? (
          <>
            <Link to="/account/notifications">
              {translate("Notifications")}
            </Link>
            <Link to="/account">{user.full_name}</Link>
            <Link to="/organizer">{translate("Organizer")}</Link>
            {user.platform_role === "platform_admin" && (
              <Link to="/admin">{translate("Admin")}</Link>
            )}
            <button
              onClick={async () => {
                try {
                  await logout();
                  location.hash = "/login";
                } catch {
                  setError(
                    "Signed out locally. Server logout could not be confirmed.",
                  );
                }
              }}
            >
              {translate("Sign out")}
            </button>
          </>
        ) : (
          <Link to="/login">{translate("Sign in")}</Link>
        )}
        <details className="bf-mobile-nav">
          <summary>{translate("Menu")}</summary>
          <nav aria-label={translate("Workspace navigation")}>
            <Link to="/events">{translate("Explore events")}</Link>
            {user ? (
              <>
                <Link to="/account">{translate("My account")}</Link>
                <Link to="/account/notifications">
                  {translate("Notifications")}
                </Link>
                <Link to="/organizer">{translate("Organizer workspace")}</Link>
                {user.platform_role === "platform_admin" && (
                  <Link to="/admin">{translate("Platform admin")}</Link>
                )}
              </>
            ) : (
              <>
                <Link to="/login">{translate("Sign in")}</Link>
                <Link to="/register">{translate("Register")}</Link>
              </>
            )}
          </nav>
        </details>
        {error && <span role="alert">{translate(error)}</span>}
      </div>
    </header>
  );
}
export function Shell({ role = "attendee", path, title, subtitle, children }) {
  return (
    <>
      <Topbar />
      <div className="bf-shell">
        <aside className="bf-side">
          <div className="bf-side-label">{translate(role)}</div>
          {navGroups[role].map(([label, to]) => (
            <Link
              key={to}
              to={to}
              className={`bf-side-link ${path === to ? "active" : ""}`}
            >
              {translate(label)}
            </Link>
          ))}
          <Link to="/events">{translate("Back to events")}</Link>
        </aside>
        <main className="bf-main">
          <div className="bf-page-head">
            <div>
              <h1>{translate(title)}</h1>
              {subtitle && <p>{translate(subtitle)}</p>}
            </div>
          </div>
          {children}
        </main>
      </div>
    </>
  );
}
export function Stat({ label, value }) {
  return (
    <div className="bf-stat">
      <span>{translate(label)}</span>
      <strong>{value}</strong>
    </div>
  );
}
export function Badge({ children }) {
  return (
    <span
      className={`bf-badge ${String(children).toLowerCase().replaceAll(" ", "-")}`}
    >
      {children}
    </span>
  );
}
export function EventCard({ event }) {
  return (
    <Link
      to={`/events/${encodeURIComponent(event.slug)}`}
      className="bf-event-card"
    >
      <div className="bf-event-image">
        <img src={event.image || "/images/culture.jpg"} alt="" />
        <span>{event.category || translate("Event")}</span>
      </div>
      <div className="bf-event-info">
        <small>{dateTime(event.startsAt || event.starts_at)}</small>
        <h3>{event.title}</h3>
        <p>{event.venue || event.city || ""}</p>
        {event.price != null && (
          <strong>
            {event.price === 0
              ? translate("Free")
              : `From ${money(event.price)}`}
          </strong>
        )}
      </div>
    </Link>
  );
}
export function LanguagePicker() {
  const locale = useLocale();
  return (
    <label className="bf-language">
      {translate("Language")}
      <select value={locale} onChange={(e) => setLocale(e.target.value)}>
        <option value="kk">Қазақша</option>
        <option value="ru">Русский</option>
        <option value="en">English</option>
      </select>
    </label>
  );
}
