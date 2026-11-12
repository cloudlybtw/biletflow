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
        <Link to="/events">Explore events</Link>
        {user ? (
          <>
            <Link to="/account/notifications">Notifications</Link>
            <Link to="/account">{user.full_name}</Link>
            <Link to="/organizer">Organizer</Link>
            {user.platform_role === "platform_admin" && (
              <Link to="/admin">Admin</Link>
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
              Sign out
            </button>
          </>
        ) : (
          <Link to="/login">Sign in</Link>
        )}
        <details className="bf-mobile-nav">
          <summary>Menu</summary>
          <nav aria-label="Workspace navigation">
            <Link to="/events">Explore events</Link>
            {user ? (
              <>
                <Link to="/account">My account</Link>
                <Link to="/account/notifications">Notifications</Link>
                <Link to="/organizer">Organizer workspace</Link>
                {user.platform_role === "platform_admin" && (
                  <Link to="/admin">Platform admin</Link>
                )}
              </>
            ) : (
              <>
                <Link to="/login">Sign in</Link>
                <Link to="/register">Register</Link>
              </>
            )}
          </nav>
        </details>
        {error && <span role="alert">{error}</span>}
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
          <div className="bf-side-label">{role.toUpperCase()}</div>
          {navGroups[role].map(([label, to]) => (
            <Link
              key={to}
              to={to}
              className={`bf-side-link ${path === to ? "active" : ""}`}
            >
              {label}
            </Link>
          ))}
          <Link to="/events">Back to events</Link>
        </aside>
        <main className="bf-main">
          <div className="bf-page-head">
            <div>
              <h1>{title}</h1>
              {subtitle && <p>{subtitle}</p>}
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
      <span>{label}</span>
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
        <span>{event.category || "Event"}</span>
      </div>
      <div className="bf-event-info">
        <small>
          {new Date(event.startsAt || event.starts_at).toLocaleString()}
        </small>
        <h3>{event.title}</h3>
        <p>{event.venue || event.city || ""}</p>
        {event.price != null && (
          <strong>
            {event.price === 0 ? "Free" : `From ${money(event.price)}`}
          </strong>
        )}
      </div>
    </Link>
  );
}
