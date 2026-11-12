import { useEffect, useRef, useState } from "react";
import Navbar from "../../components/Navbar/Navbar";
import ExperienceHero from "../../components/ExperienceHero/ExperienceHero";
import TicketCarousel from "../../components/TicketCarousel/TicketCarousel";
import { copy, locales, cities, cityLabel } from "../../data/i18n";
import { demoEvents } from "../../data/events";
import { filterEvents, sectionEvents, timezone } from "../../lib/discovery";
import { loadEvents, login } from "../../lib/api";
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
function getLanguage() {
  try {
    return ["en", "ru", "kk"].includes(
      localStorage.getItem("biletflow-language"),
    )
      ? localStorage.getItem("biletflow-language")
      : "ru";
  } catch {
    return "ru";
  }
}
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
  const [lang, setLang] = useState(getLanguage);
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
        if (active) setData(events.length ? { events, state: "live" } : { events: demoEvents, state: "demo" });
      })
      .catch(() => {
        if (active) setData({ events: demoEvents, state: "demo" });
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
    setCollection(null);
  };
  const invalidDates = filters.from && filters.to && filters.to < filters.from;
  const filtered = invalidDates ? [] : filterEvents(data.events, filters);
  const visibleSections = (collection ? [collection] : sections)
    .map((key) => ({ key, events: sectionEvents(filtered, key) }))
    .filter((s) => s.events.length);
  const date = (e) =>
    new Intl.DateTimeFormat(locales[lang], {
      timeZone: timezone,
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date(e.startsAt));
  const price = (e) =>
    e.price === 0
      ? t.freePrice
      : e.price == null
        ? t.unknownPrice
        : `${t.from} ${new Intl.NumberFormat(locales[lang]).format(e.price)} ₸`;
  const viewAll = (key) => {
    setCollection(key);
    document
      .getElementById("collections")
      .scrollIntoView({ behavior: "smooth", block: "start" });
  };
  async function signIn(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setAuth((a) => ({ ...a, busy: true, error: false }));
    try {
      const result = await login(form.get("email"), form.get("password"));
      setAuth({ busy: false, error: false, user: result.user });
    } catch {
      setAuth((a) => ({ ...a, busy: false, error: true }));
    }
  }
  function card(e) {
    return (
      <article className="event-card" key={e.id}>
        <button
          className="event-link"
          onClick={() => setModal({ type: "event", event: e })}
          aria-label={`${e.title}, ${date(e)}, ${price(e)}`}
        >
          <div className="event-image">
            <img
              src={e.image}
              alt=""
              loading="lazy"
              onError={(event) => {
                event.currentTarget.style.visibility = "hidden";
              }}
            />
            <span className="event-badge">{t[e.category]}</span>
            <span className="image-arrow" aria-hidden="true">
              ↗
            </span>
          </div>
          <div className="event-date">{date(e)}</div>
          <h3>{e.title}</h3>
          <p className="event-location">
            {e.venue || t.unknownVenue} ·{" "}
            {cityLabel(e.city, lang) || t.unknownVenue}
          </p>
          <div className="event-bottom">
            <strong className={e.price === 0 ? "free-price" : ""}>
              {price(e)}
            </strong>
            <span>
              {e.demo ? t.demo : "BiletFlow"} <span aria-hidden="true">↗</span>
            </span>
          </div>
        </button>
      </article>
    );
  }
  return (
    <>
      <Navbar
        t={t}
        lang={lang}
        setLang={setLang}
        city={filters.city}
        setCity={(value) => update("city", value)}
        onSignIn={() => setModal({ type: "login" })}
      />
      <main id="home">
        <ExperienceHero
          t={t}
          query={filters.q}
          onQueryChange={(value) => update("q", value)}
          onSearchInteraction={() => setSearchPaused(true)}
          onIntroFinish={setIntroFinished}
          onCreate={() => setModal({ type: "organizer" })}
        />
        <TicketCarousel
          t={t}
          lang={lang}
          events={data.events}
          loading={data.state === "loading"}
          introFinished={introFinished}
          searchPaused={searchPaused}
          onResume={() => setSearchPaused(false)}
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
            <label className="filter-select">
              <span>{t.city}</span>
              <select
                value={filters.city}
                onChange={(e) => update("city", e.target.value)}
              >
                <option value="">{t.allCities}</option>
                {Object.keys(cities).map((c) => (
                  <option key={c} value={c}>
                    {cityLabel(c, lang)}
                  </option>
                ))}
              </select>
            </label>
            <details className="date-filter">
              <summary>
                {t.dates}
                <span aria-hidden="true">⌄</span>
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
            <label className="filter-select category-select">
              <span>{t.category}</span>
              <select
                value={filters.category}
                onChange={(e) => update("category", e.target.value)}
              >
                <option value="">{t.allCategories}</option>
                {[...Object.keys(symbols), "other"].map((c) => (
                  <option key={c} value={c}>
                    {t[c]}
                  </option>
                ))}
              </select>
            </label>
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
            ) : data.state === "demo" ? (
              t.demoNotice
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
                      <span>↗</span>
                    </button>
                  )}
                  {collection && (
                    <span className="result-count">{events.length}</span>
                  )}
                </div>
                <div className="event-grid">
                  {(collection ? events : events.slice(0, 4)).map(card)}
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
                <span>↗</span>
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
      <footer className="page-width">
        <a className="wordmark" href="#home">
          BiletFlow<span className="brand-dot">.</span>
        </a>
        <p>{t.footer}</p>
        <span>{t.timezone}</span>
        <small>© {new Date().getFullYear()} BiletFlow</small>
      </footer>
      {modal && (
        <Modal
          title={
            modal.type === "event"
              ? modal.event.title
              : modal.type === "login"
                ? t.signIn
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
              {!modal.event.demo && <p>{t.noBooking}</p>}
            </>
          )}
          {modal.type === "organizer" && (
            <>
              <p>{t.organizerDetail}</p>
              <button
                className="button button-purple"
                onClick={() => setModal({ type: "login" })}
              >
                {t.signIn} ↗
              </button>
            </>
          )}
          {modal.type === "login" &&
            (auth.user ? (
              <p role="status">
                {t.signedIn} {auth.user.full_name}
              </p>
            ) : (
              <form className="login-form" onSubmit={signIn}>
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
                    autoComplete="current-password"
                    maxLength="1024"
                  />
                </label>
                {auth.error && (
                  <p role="alert" className="error">
                    {t.loginError}
                  </p>
                )}
                <button disabled={auth.busy} className="button button-purple">
                  {auth.busy ? t.working : t.signIn} ↗
                </button>
              </form>
            ))}
        </Modal>
      )}
    </>
  );
}
