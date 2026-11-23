import { useLocale, errorText } from "../../lib/locale";
import { api } from "../../lib/client";
import { useEffect, useRef, useState } from "react";
import Arrow from "../../components/Icons/Arrow";
import Navbar from "../../components/Navbar/Navbar";
import ExperienceHero from "../../components/ExperienceHero/ExperienceHero";
import TicketCarousel from "../../components/TicketCarousel/TicketCarousel";
import EventCard from "../../components/EventCard/EventCard";
import Dropdown from "../../components/Dropdown/Dropdown";
import {
  formatEventDate,
  formatEventPrice,
} from "../../components/EventCard/format";
import { useCity } from "../../lib/city";
import { copy, cities, cityLabel } from "../../data/i18n";
import { filterEvents, sectionEvents } from "../../lib/discovery";
import { loadEvents, login } from "../../lib/api";
import { useSession } from "../../lib/session-context";
import "./Home.css";
const initialFilters = {
  q: "",
  city: "",
  category: "",
  from: "",
  to: "",
  free: false,
};
const sections = [
  "week",
  "music",
  "sport",
  "culture",
  "comedy",
  "workshop",
  "campus",
  "free",
  "other",
];
const symbols = {
  sport: "◉",
  music: "♫",
  culture: "◈",
  comedy: "☺",
  workshop: "✳",
  campus: "↗",
};
function Modal({ children, title, onClose, t }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement;
    dialog.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      aria-labelledby="modal-title"
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <button className="modal-close" onClick={onClose} aria-label={t.close}>
        ×
      </button>
      <h2 id="modal-title">{title}</h2>
      {children}
    </dialog>
  );
}
export default function Home() {
  const session = useSession();
  const lang = useLocale();
  const [city, setCity] = useCity();
  const [filters, setFilters] = useState(initialFilters);
  const [searchPaused, setSearchPaused] = useState(false);
  const [introFinished, setIntroFinished] = useState(false);
  const [data, setData] = useState({ events: [], state: "loading" });
  const [collection, setCollection] = useState(null);
  const [modal, setModal] = useState(null);
  const [auth, setAuth] = useState({ busy: false, error: false, user: null });
  const t = copy[lang];
  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      localStorage.setItem("biletflow-language", lang);
    } catch {
      /* Storage is optional. */
    }
  }, [lang]);
  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    let active = true;
    loadEvents(controller.signal)
      .then((events) => {
        if (active) setData({ events, state: "live" });
      })
      .catch(() => {
        if (active) setData({ events: [], state: "error" });
      })
      .finally(() => clearTimeout(timeout));
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timeout);
    };
  }, []);
  const update = (key, value) => setFilters((f) => ({ ...f, [key]: value }));
  const reset = () => {
    setFilters(initialFilters);
    setCity("");
    setCollection(null);
  };
  const invalidDates = filters.from && filters.to && filters.to < filters.from;
  const filtered = invalidDates
    ? []
    : filterEvents(data.events, { ...filters, city });
  const visibleSections = (collection ? [collection] : sections)
    .map((key) => ({ key, events: sectionEvents(filtered, key) }))
    .filter((s) => s.events.length);
  const date = (e) => formatEventDate(e, lang);
  const price = (e) => formatEventPrice(e, lang);
  const viewAll = (key) => {
    setCollection(key);
    document
      .getElementById("collections")
      .scrollIntoView({ behavior: "smooth", block: "start" });
  };
  // One handler for both modal modes. Register does not sign in on the API,
  // so sign in right after it (unverified accounts may sign in).
  async function signIn(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const email = form.get("email");
    const password = form.get("password");
    setAuth((a) => ({ ...a, busy: true, error: false }));
    try {
      if (modal?.type === "register")
        await api("/auth/register", {
          method: "POST",
          auth: false,
          body: {
            email,
            password,
            full_name: form.get("full_name"),
            locale: lang,
          },
        });
      const result = await login(email, password);
      setAuth({ busy: false, error: false, user: result.user });
      location.hash = "/account";
    } catch (error) {
      setAuth((a) => ({
        ...a,
        busy: false,
        error: error?.status ? errorText(error) : t.loginError,
      }));
    }
  }
  const openAuth = (type) => {
    setAuth((a) => ({ ...a, error: false }));
    setModal({ type });
  };
  return (
    <>
      <Navbar
        onSignIn={() =>
          session.user ? (location.hash = "/account") : openAuth("login")
        }
      />
      <main id="home">
        <ExperienceHero
          t={t}
          query={filters.q}
          onQueryChange={(value) => update("q", value)}
          onSearchInteraction={() => setSearchPaused(true)}
          onIntroFinish={setIntroFinished}
          onCreate={() => setModal({ type: "organizer" })}
          events={data.events}
          onDetails={(event) => setModal({ type: "event", event })}
        />
        <TicketCarousel
          t={t}
          lang={lang}
          events={data.events}
          loading={data.state === "loading"}
          introFinished={introFinished}
          searchPaused={searchPaused}
          onDetails={(event) => setModal({ type: "event", event })}
        />
        <section
          id="discover"
          className="discovery page-width"
          aria-label={t.discover}
        >
          <div className="discovery-intro">
            <h2>
              {t.discover}
              <span className="small-spark" aria-hidden="true">
                ✳
              </span>
            </h2>
            <p>{t.sectionNote}</p>
          </div>
          <form
            className="filter-bar"
            onSubmit={(e) => e.preventDefault()}
            aria-label={t.discover}
          >
            <label className="search-field">
              <svg
                width="19"
                height="19"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                aria-hidden="true"
              >
                <circle cx="10.5" cy="10.5" r="6.5" />
                <path d="m16 16 5 5" />
              </svg>
              <input
                type="search"
                aria-label={t.search}
                placeholder={t.search}
                onFocus={() => setSearchPaused(true)}
                value={filters.q}
                onChange={(e) => update("q", e.target.value)}
              />
            </label>
            <div className="filter-select">
              <Dropdown
                variant="stacked"
                align="left"
                label={t.city}
                value={city}
                onChange={setCity}
                icon={<span className="dropdown-prefix">{t.city}</span>}
                options={[
                  { value: "", label: t.allCities },
                  ...Object.keys(cities).map((c) => ({
                    value: c,
                    label: cityLabel(c, lang),
                  })),
                ]}
              />
            </div>
            <details className="date-filter">
              <summary>
                {t.dates}
                <svg
                  width="10"
                  height="6"
                  viewBox="0 0 10 6"
                  fill="none"
                  aria-hidden="true"
                >
                  <path
                    d="m1 1 4 4 4-4"
                    stroke="currentColor"
                    strokeWidth="1.6"
                  />
                </svg>
                {(filters.from || filters.to) && <i />}
              </summary>
              <div className="date-popover">
                <label>
                  {t.fromDate}
                  <input
                    type="date"
                    value={filters.from}
                    onChange={(e) => update("from", e.target.value)}
                  />
                </label>
                <label>
                  {t.toDate}
                  <input
                    type="date"
                    value={filters.to}
                    min={filters.from}
                    onChange={(e) => update("to", e.target.value)}
                  />
                </label>
              </div>
            </details>
            <div className="filter-select category-select">
              <Dropdown
                variant="stacked"
                align="left"
                label={t.category}
                value={filters.category}
                onChange={(value) => update("category", value)}
                icon={<span className="dropdown-prefix">{t.category}</span>}
                options={[
                  { value: "", label: t.allCategories },
                  ...[...Object.keys(symbols), "other"].map((c) => ({
                    value: c,
                    label: t[c],
                  })),
                ]}
              />
            </div>
            <label className="free-toggle">
              <input
                type="checkbox"
                checked={filters.free}
                onChange={(e) => update("free", e.target.checked)}
              />
              <span>{t.freeOnly}</span>
            </label>
            <button className="reset-button" type="button" onClick={reset}>
              {t.reset}
            </button>
          </form>
          <div className="category-tabs" aria-label={t.category}>
            <button
              className={!filters.category ? "selected" : ""}
              onClick={() => update("category", "")}
            >
              {t.allCategories}
            </button>
            {Object.entries(symbols).map(([key, symbol]) => (
              <button
                key={key}
                className={filters.category === key ? "selected" : ""}
                onClick={() =>
                  update("category", filters.category === key ? "" : key)
                }
              >
                <span aria-hidden="true">{symbol}</span>
                {t[key]}
              </button>
            ))}
          </div>
          <div className="catalog-status" role="status">
            {data.state === "loading" ? (
              t.loading
            ) : data.state === "error" ? (
              "Unable to load events. Please try again."
            ) : (
              <>
                {t.live} · {filtered.length} {t.count}
              </>
            )}
          </div>
          {invalidDates && (
            <p role="alert" className="error">
              {t.dateError}
            </p>
          )}
          <div id="collections" aria-busy={data.state === "loading"}>
            {collection && (
              <button className="back-link" onClick={() => setCollection(null)}>
                ← {t.back}
              </button>
            )}
            {visibleSections.map(({ key, events }, index) => (
              <section
                className="event-section"
                key={key}
                aria-labelledby={`heading-${key}`}
              >
                <div className="section-header">
                  <div>
                    <div className="section-heading">
                      <span className="section-number">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <h2 id={`heading-${key}`}>{t[key]}</h2>
                      {key === "week" && <span className="live-dot" />}
                    </div>
                    {key === "week" && <p>{t.weekNote}</p>}
                  </div>
                  {!collection && (
                    <button className="view-all" onClick={() => viewAll(key)}>
                      {t.all}
                      <Arrow size={17} />
                    </button>
                  )}
                  {collection && (
                    <span className="result-count">{events.length}</span>
                  )}
                </div>
                <div className="event-grid">
                  {(collection ? events : events.slice(0, 4)).map((e) => (
                    <EventCard
                      key={e.id}
                      event={e}
                      lang={lang}
                      onOpen={(event) => setModal({ type: "event", event })}
                    />
                  ))}
                </div>
              </section>
            ))}
            {!visibleSections.length && data.state !== "loading" && (
              <div className="empty-state">
                <span aria-hidden="true">⌕</span>
                <h2>{t.empty}</h2>
                <p>{t.emptyBody}</p>
                <button className="button button-purple" onClick={reset}>
                  {t.reset}
                </button>
              </div>
            )}
          </div>
        </section>
        <section className="organizer-section" id="organizers">
          <div className="page-width organizer-inner">
            <div>
              <p className="eyebrow">BILETFLOW / {t.organizers}</p>
              <h2>{t.organizerTitle}</h2>
              <p>{t.organizerBody}</p>
              <button
                className="button button-purple"
                onClick={() => setModal({ type: "organizer" })}
              >
                {t.create}
                <Arrow size={17} />
              </button>
            </div>
            <div className="organizer-art" aria-hidden="true">
              <span>✳</span>
              <p>
                TOGETHER
                <br />
                IS BETTER.
              </p>
            </div>
          </div>
        </section>
      </main>
      {modal && (
        <Modal
          title={
            modal.type === "event"
              ? modal.event.title
              : modal.type === "login"
                ? t.signIn
                : modal.type === "register"
                  ? t.createAccount
                  : t.organizerInfo
          }
          onClose={() => setModal(null)}
          t={t}
        >
          {modal.type === "event" && (
            <>
              <img className="detail-image" src={modal.event.image} alt="" />
              <p className="detail-caption">
                {modal.event.demo || modal.event.illustrative
                  ? t.illustration
                  : ""}
              </p>
              <p className="event-date">
                {date(modal.event)} · {t.timezone}
              </p>
              <p>
                {modal.event.venue || t.unknownVenue} ·{" "}
                {cityLabel(modal.event.city, lang)}
              </p>
              <p>
                <strong>{price(modal.event)}</strong>
              </p>
              <p className="detail-notice">
                {modal.event.demo ? t.demoDetail : modal.event.description}
              </p>
              {!modal.event.demo && (
                <a
                  className="button button-purple"
                  href={`/#/events/${modal.event.slug}`}
                >
                  {t.discover} →
                </a>
              )}
            </>
          )}
          {modal.type === "organizer" && (
            <>
              <p>{t.organizerDetail}</p>
              <button
                className="button button-purple"
                onClick={() => openAuth("login")}
              >
                {t.signIn} <Arrow size={17} />
              </button>
            </>
          )}
          {(modal.type === "login" || modal.type === "register") &&
            (auth.user ? (
              <p role="status">
                {t.signedIn} {auth.user.full_name}
              </p>
            ) : (
              <form className="login-form" onSubmit={signIn} key={modal.type}>
                {modal.type === "register" && (
                  <label>
                    {t.fullName}
                    <input
                      required
                      name="full_name"
                      autoComplete="name"
                      maxLength="200"
                    />
                  </label>
                )}
                <label>
                  {t.email}
                  <input
                    required
                    name="email"
                    type="email"
                    autoComplete="email"
                  />
                </label>
                <label>
                  {t.password}
                  <input
                    required
                    name="password"
                    type="password"
                    autoComplete={
                      modal.type === "register"
                        ? "new-password"
                        : "current-password"
                    }
                    minLength={modal.type === "register" ? 8 : undefined}
                    maxLength={modal.type === "register" ? 128 : 1024}
                  />
                </label>
                {modal.type === "register" && (
                  <p className="login-hint">{t.passwordHint}</p>
                )}
                {auth.error && (
                  <p role="alert" className="error">
                    {auth.error === true ? t.loginError : auth.error}
                  </p>
                )}
                <button disabled={auth.busy} className="button button-purple">
                  {auth.busy
                    ? t.working
                    : modal.type === "register"
                      ? t.createAccount
                      : t.signIn}{" "}
                  <Arrow size={17} />
                </button>
                <p className="login-switch">
                  {modal.type === "register" ? t.haveAccount : t.noAccount}{" "}
                  <button
                    type="button"
                    onClick={() =>
                      openAuth(modal.type === "register" ? "login" : "register")
                    }
                  >
                    {modal.type === "register" ? t.signIn : t.createAccount}
                  </button>
                </p>
              </form>
            ))}
        </Modal>
      )}
    </>
  );
}
