import { useEffect, useRef, useState } from "react";
import { heroCopy, heroThemes, showcaseEvents } from "../../data/hero";
import { cityLabel, locales } from "../../data/i18n";
import "./TicketCarousel.css";
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export default function TicketCarousel({ t, lang, events, loading, introFinished, searchPaused, onResume, onDetails }) {
  const [category, setCategory] = useState("upcoming");
  const [playing, setPlaying] = useState(() => !reducedMotion());
  const filtered = showcaseEvents(events, category);
  // A new inventory/category resets only the track; it never changes discovery filters.
  const inventoryKey = `${category}:${filtered.map((event) => event.id).join(",")}`;
  const h = heroCopy[lang];
  return <section className="ticket-showcase" aria-labelledby="showcase-title">
    <h2 id="showcase-title" className="showcase-heading">{h.showcase}</h2>
    <EventTrack key={inventoryKey} {...{ t, lang, h, category, playing, setPlaying, introFinished, searchPaused, onResume, onDetails, loading }} events={filtered} onCategory={(key) => { setPlaying(false); setCategory(key); }} />
    <p className="showcase-note">{events.some((event) => event.demo) ? t.demoNotice : t.timezone}</p>
  </section>;
}

function EventTrack({ t, lang, h, category, playing, setPlaying, introFinished, searchPaused, onResume, onDetails, loading, events, onCategory }) {
  const [reduced, setReduced] = useState(reducedMotion);
  const [slide, setSlide] = useState({ index: 0, target: null, direction: 1 });
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [hidden, setHidden] = useState(() => document.hidden);
  const touch = useRef(null);
  const count = events.length;
  const wrap = (index) => (index + count) % count;
  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const changed = () => { setReduced(preference.matches); if (preference.matches) setPlaying(false); };
    const visibility = () => setHidden(document.hidden);
    preference.addEventListener("change", changed);
    document.addEventListener("visibilitychange", visibility);
    return () => { preference.removeEventListener("change", changed); document.removeEventListener("visibilitychange", visibility); };
  }, [setPlaying]);
  useEffect(() => {
    if (slide.target === null) return;
    const timer = setTimeout(() => setSlide((s) => ({ ...s, index: s.target, target: null })), reduced ? 0 : 720);
    return () => clearTimeout(timer);
  }, [slide.target, reduced]);
  useEffect(() => {
    if (count < 2 || !introFinished || reduced || !playing || searchPaused || hovered || focused || hidden || slide.target !== null) return;
    const timer = setTimeout(() => setSlide((s) => ({ ...s, target: (s.index + 1) % count, direction: 1 })), 7000);
    return () => clearTimeout(timer);
  }, [count, introFinished, reduced, playing, searchPaused, hovered, focused, hidden, slide]);
  function navigate(direction) {
    setPlaying(false);
    if (count < 2 || slide.target !== null) return;
    setSlide({ ...slide, target: wrap(slide.index + direction), direction });
  }
  const active = slide.target ?? slide.index;
  const running = playing && !reduced && !searchPaused;
  function ticket(index, slot) {
    const event = events[index];
    const theme = heroThemes.find((item) => item.category === event.category) || heroThemes[0];
    const date = new Intl.DateTimeFormat(locales[lang], { timeZone: "Asia/Almaty", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(event.startsAt));
    const price = event.price == null ? t.unknownPrice : event.price === 0 ? t.freePrice : `${t.from} ${new Intl.NumberFormat(locales[lang]).format(event.price)} ₸`;
    const current = slot === 0;
    return <article key={slot} className={`event-ticket theme-${theme.key}`} style={{ "--slot": slot }} inert={!current || slide.target !== null} aria-hidden={!current || slide.target !== null} aria-label={event.title}>
      <div className="event-ticket-body">
        <img key={event.image} className="ticket-photo" src={event.image} alt="" loading="lazy" onError={(e) => { e.currentTarget.style.opacity = 0; }} />
        <div className="ticket-shade" />
        <div className="ticket-editorial">
          <div className="ticket-topline"><span>BiletFlow<span aria-hidden="true"> ✳</span></span><span>{event.demo ? t.demo : t.live}</span></div>
          <div className="ticket-story"><p className="ticket-category">{t[event.category] || t.other}</p><h3 className="ticket-headline">{event.title}</h3><p className="ticket-description">{event.description || h[theme.description]}</p></div>
          <div className="ticket-bottom"><p>{cityLabel(event.city, lang)}<span>{event.venue || t.unknownVenue}</span></p><button onClick={() => { setPlaying(false); onDetails(event); }}>{t.details} <span aria-hidden="true">↗</span></button></div>
        </div>
      </div>
      <aside className="event-ticket-stub"><span className="stub-brand">BiletFlow / {String(index + 1).padStart(2, "0")}</span><span className="stub-star" aria-hidden="true">✳</span><div className="stub-meta"><strong>{date}</strong><span>{cityLabel(event.city, lang)}</span><strong>{price}</strong></div><div><svg className="preview-barcode" viewBox="0 0 150 34" aria-hidden="true">{Array.from({ length: 38 }, (_, i) => <rect key={i} x={i * 4} width={i % 3 === 0 ? 3 : 1} height={34} fill="currentColor" />)}</svg><small>{h.preview}</small></div></aside>
    </article>;
  }
  return <div className="ticket-carousel" role="region" aria-roledescription="carousel" aria-label={h.showcase} onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} onFocusCapture={() => setFocused(true)} onBlurCapture={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setFocused(false); }}>
    <div className="carousel-toolbar"><div className="carousel-categories" aria-label={t.category}>{heroThemes.map((theme) => <button key={theme.key} aria-pressed={category === theme.key} onClick={() => onCategory(theme.key)}>{h[theme.key]}</button>)}</div><div className="carousel-navigation"><span aria-live="off">{count ? String(active + 1).padStart(2, "0") : "00"}<span> / {String(count).padStart(2, "0")}</span></span><button disabled={count < 2} aria-label={h.previous} onClick={() => navigate(-1)}>←</button><button disabled={count < 2} aria-label={h.next} onClick={() => navigate(1)}>→</button><button aria-label={running ? h.pause : h.play} aria-pressed={running} disabled={reduced || count < 2} onClick={() => { setPlaying(!running); onResume(); }}>{running ? "Ⅱ" : "▷"}</button></div></div>
    {count ? <div className="ticket-viewport" onTouchStart={(e) => { const p = e.touches[0]; touch.current = { x: p.clientX, y: p.clientY }; }} onTouchCancel={() => { touch.current = null; }} onTouchEnd={(e) => { if (!touch.current) return; const p = e.changedTouches[0]; const dx = p.clientX - touch.current.x; const dy = p.clientY - touch.current.y; touch.current = null; if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy) * 1.4) navigate(dx < 0 ? 1 : -1); }}>
      <div className={`ticket-track ${slide.target !== null ? "is-moving" : ""}`} style={{ "--travel": slide.target === null ? 0 : -slide.direction }}>{(count > 1 ? [-1, 0, 1] : [0]).map((slot) => ticket(wrap(slide.index + slot), slot))}</div>
    </div> : <div className="showcase-empty" role="status"><h3>{loading ? t.loading : t.empty}</h3>{!loading && <p>{h.emptyCategory}</p>}</div>}
  </div>;
}
