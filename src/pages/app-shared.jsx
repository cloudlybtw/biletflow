import { t as translate, useLocale, setLocale, dateTime } from "../lib/locale";
import { useEffect, useState } from "react";
import { money, navGroups } from "./app-data";
import { useSession } from "../lib/session-context";
import { logout } from "../lib/client";
import Dropdown from "../components/Dropdown/Dropdown";
import { languageOptions } from "../data/languages";
export function Link({ to, children, className = "", ...rest }) {
  return (
    <a {...rest} className={className} href={`/#${to}`}>
      {children}
    </a>
  );
}
// contained: align the bar with the 1320px page column (buyer account).
export function Topbar({ contained = false }) {
  const { user } = useSession();
  const locale = useLocale();
  const [error, setError] = useState("");
  const here = typeof location === "undefined" ? "" : location.hash.slice(1);
  const current = (to) =>
    here === to || here.startsWith(`${to}/`) ? "page" : undefined;
  async function signOut() {
    try {
      await logout();
      location.hash = "/login";
    } catch {
      setError("Signed out locally. Server logout could not be confirmed.");
    }
  }
  return (
    <header className={`bf-top ws-top${contained ? " is-contained" : ""}`}>
      <button
        className="bf-skip"
        onClick={() => {
          const main = document.querySelector("main");
          if (main) {
            main.tabIndex = -1;
            main.focus();
          }
        }}
      >
        {translate("Skip to content")}
      </button>
      <a href="/" className="wordmark" aria-label="BiletFlow">
        <span className="brand-icon" aria-hidden="true">
          b<span>f</span>
        </span>
        BiletFlow<span className="brand-dot">.</span>
      </a>
      <nav className="ws-links" aria-label={translate("Workspace")}>
        <Link to="/events">{translate("Explore events")}</Link>
        {user && (
          <>
            <a href="/#/account" aria-current={current("/account")}>
              {translate("My account")}
            </a>
            <a href="/#/organizer" aria-current={current("/organizer")}>
              {translate("Organizer")}
            </a>
            {user.platform_role === "platform_admin" && (
              <a href="/#/admin" aria-current={current("/admin")}>
                {translate("Admin")}
              </a>
            )}
          </>
        )}
      </nav>
      <div className="bf-top-right">
        <Dropdown
          label={translate("Language")}
          value={locale}
          onChange={setLocale}
          display={languageOptions.find((o) => o.value === locale)?.hint}
          options={languageOptions}
        />
        {user ? (
          <>
            <a
              className="ws-bell"
              href="/#/account/notifications"
              aria-label={translate("Notifications")}
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.7"
                aria-hidden="true"
              >
                <path d="M6 9a6 6 0 1 1 12 0c0 6 2 7 2 7H4s2-1 2-7Zm4 10a2 2 0 0 0 4 0" />
              </svg>
            </a>
            <a className="ws-user" href="/#/account">
              <span aria-hidden="true">
                {user.full_name?.trim()?.[0]?.toUpperCase() || "•"}
              </span>
              <span className="ws-user-name">{user.full_name}</span>
            </a>
            <button className="ws-signout" onClick={signOut}>
              {translate("Sign out")}
            </button>
          </>
        ) : (
          <Link to="/login" className="ws-signin">
            {translate("Sign in")}
          </Link>
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
                <button onClick={signOut}>{translate("Sign out")}</button>
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
  // The page heading names the open section; the workspace name sits above it.
  const current = navGroups[role]
    .filter(([, to]) => path === to || path.startsWith(`${to}/`))
    .sort((x, y) => y[1].length - x[1].length)[0];
  const heading =
    current && current[1] !== navGroups[role][0][1] ? current[0] : title;
  useEffect(() => {
    document
      .querySelector(".bf-side-link.active")
      ?.scrollIntoView?.({ block: "nearest", inline: "center" });
  }, [path]);
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
              className={`bf-side-link ${current?.[1] === to ? "active" : ""}`}
            >
              {translate(label)}
            </Link>
          ))}
          <Link to="/events">{translate("Back to events")}</Link>
        </aside>
        <main className="bf-main">
          <div className="bf-page-head">
            <div>
              {heading !== title && (
                <p className="bf-page-kicker">{translate(title)}</p>
              )}
              <h1>{translate(heading)}</h1>
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
    <div className="bf-language">
      <span aria-hidden="true">{translate("Language")}</span>
      <Dropdown
        label={translate("Language")}
        value={locale}
        onChange={setLocale}
        options={languageOptions}
      />
      {/* Hidden native fallback: same state, kept out of the tab order. */}
      <select
        className="bf-language-native"
        aria-hidden="true"
        tabIndex={-1}
        value={locale}
        onChange={(e) => setLocale(e.target.value)}
      >
        {languageOptions.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
