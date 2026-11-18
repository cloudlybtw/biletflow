import Arrow from "../Icons/Arrow";
import { Fragment, useEffect, useRef, useState } from "react";
import { menuCategories } from "../../data/categories";
import { useLocale } from "../../lib/locale";
import TiltedCard, { TiltedCardLayer } from "../TiltedCard/TiltedCard";
import { cityLabel, locales } from "../../data/i18n";
import { timezone } from "../../lib/discovery";
import { formatEventPrice } from "../EventCard/format";
import "./ExperienceHero.css";
const scenes = [
  { image: "music", label: "LIVE / ALMATY", title: "Concerts", side: "concert", prefer: ["music"] },
  { image: "hero", label: "OPEN AIR / QAZAQSTAN", title: "Festivals", side: "festival", prefer: ["campus", "other", "workshop", "music"] },
  { image: "theatre", label: "ON STAGE / ASTANA", title: "Theatre", side: "theatre", prefer: ["culture"] },
  { image: "culture", label: "TOGETHER / QAZAQSTAN", title: "Culture", side: "culture", prefer: ["comedy", "culture", "sport"] },
];
const sessionKey = "biletflow-original-hero-intro";
let seenInMemory = false;
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function introSeen() {
  try { return seenInMemory || sessionStorage.getItem(sessionKey) === "seen"; }
  catch { return seenInMemory; }
}
const backText = {
  en: { date: "Date", time: "Time", place: "Place", price: "Price", details: "Event details", none: "Next event is announced soon", browse: "Browse events" },
  ru: { date: "Дата", time: "Время", place: "Место", price: "Цена", details: "Подробнее", none: "Ближайшее событие скоро анонсируем", browse: "К афише" },
  kk: { date: "Күні", time: "Уақыты", place: "Орны", price: "Бағасы", details: "Толығырақ", none: "Жақын арада жарияланады", browse: "Афишаға" },
};
const zone = { timeZone: timezone };
// The soonest upcoming event for each tile, never the same event twice.
function pickEvents(events) {
  const now = Date.now();
  const upcoming = events.filter((e) => new Date(e.startsAt) >= now);
  const used = new Set();
  return scenes.map((scene) => {
    const found = scene.prefer
      .map((c) => upcoming.find((e) => e.category === c && !used.has(e.id)))
      .find(Boolean);
    if (found) used.add(found.id);
    return found || null;
  });
}
function TileBack({ event, scene, onDetails }) {
  const lang = useLocale();
  const b = backText[lang];
  if (!event)
    return (
      <div className="flip-back">
        <small>{scene.title}</small>
        <p className="flip-none">{b.none}</p>
        <a className="flip-action" href="#discover" onClick={(e) => e.stopPropagation()}>
          {b.browse} <Arrow size={15} />
        </a>
      </div>
    );
  const start = new Date(event.startsAt);
  const date = new Intl.DateTimeFormat(locales[lang], { ...zone, weekday: "short", day: "numeric", month: "long" }).format(start);
  const time = new Intl.DateTimeFormat(locales[lang], { ...zone, hour: "2-digit", minute: "2-digit", hour12: false }).format(start);
  const place = [event.venue, cityLabel(event.city, lang)].filter(Boolean).join(", ");
  return (
    <div className="flip-back">
      <small>{scene.title}</small>
      <h3>{event.title}</h3>
      <dl>
        <div><dt>{b.date}</dt><dd>{date}</dd></div>
        <div><dt>{b.time}</dt><dd>{time}</dd></div>
        {place && <div><dt>{b.place}</dt><dd>{place}</dd></div>}
        <div><dt>{b.price}</dt><dd>{formatEventPrice(event, lang)}</dd></div>
      </dl>
      <button
        className="flip-action"
        onClick={(e) => {
          e.stopPropagation();
          onDetails?.(event);
        }}
      >
        {b.details} <Arrow size={15} />
      </button>
    </div>
  );
}
// Headline words rise one by one (CSS stagger via --i). Visible text is unchanged.
function Words({ text, start = 0 }) {
  return text.split(" ").map((word, i) => (
    <Fragment key={word + i}>
      {i > 0 && " "}
      <span className="word">
        <span style={{ "--i": start + i }}>{word}</span>
      </span>
    </Fragment>
  ));
}
function Marquee() {
  const lang = useLocale();
  const items = menuCategories.map((c) => c.label[lang]);
  const row = (hidden) => (
    <ul className="marquee-row" aria-hidden={hidden || undefined}>
      {items.map((label) => (
        <li key={label}>{label}</li>
      ))}
    </ul>
  );
  return (
    <div className="experience-marquee" aria-hidden="true">
      <div className="marquee-track">{row(true)}{row(true)}</div>
    </div>
  );
}
export default function ExperienceHero({ t, query, onQueryChange, onCreate, onSearchInteraction, onIntroFinish, events = [], onDetails }) {
  const picks = pickEvents(events);
  const [finished, setFinished] = useState(() => reducedMotion() || introSeen());
  const searchRef = useRef(null);
  const skipRef = useRef(null);
  useEffect(() => {
    if (finished) {
      seenInMemory = true;
      try { sessionStorage.setItem(sessionKey, "seen"); } catch { /* Storage is optional. */ }
      onIntroFinish(true);
      return;
    }
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const finish = () => {
      if (document.activeElement === skipRef.current) searchRef.current?.focus();
      setFinished(true);
    };
    const changed = () => { if (preference.matches) finish(); };
    const timer = setTimeout(finish, 2800);
    preference.addEventListener("change", changed);
    return () => { clearTimeout(timer); preference.removeEventListener("change", changed); };
  }, [finished, onIntroFinish]);
  function discover(event) {
    event.preventDefault(); setFinished(true); onSearchInteraction();
    document.getElementById("discover")?.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
  }
  return <section className={`experience-hero${finished ? " is-settled" : ""}`} aria-labelledby="experience-title">
    <div className="experience-glow" aria-hidden="true" />
    <div className="experience-art">
      {scenes.map((scene, i) => (
        <div className={`experience-card scene-${scene.side}`} key={scene.side}>
          <TiltedCard
            imageSrc={`/images/${scene.image}.jpg`}
            altText=""
            captionText={scene.title}
            containerWidth="100%"
            containerHeight="100%"
            imageWidth="100%"
            imageHeight="100%"
            radius={6}
            rotateAmplitude={12}
            scaleOnHover={1.04}
            glare={0.45}
            glareColor="#f2ef1d"
            shadow={0.6}
            floating
            gyroscope={false}
            showTooltip={false}
            introDelay={i * 120}
            backContent={<TileBack event={picks[i]} scene={scene} onDetails={onDetails} />}
          >
            <TiltedCardLayer depth={26}>
              <div className="scene-caption">
                <small>{scene.label}</small>
                <strong>{scene.title}</strong>
              </div>
              <span className="flip-hint" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square"><path d="M4 12a8 8 0 0 1 14-5.3M20 12a8 8 0 0 1-14 5.3M18 3v4h-4M6 21v-4h4" /></svg>
              </span>
            </TiltedCardLayer>
          </TiltedCard>
        </div>
      ))}
      <div className="opening-ticket"><div className="ticket-body"><span className="ticket-brand">BiletFlow<span>✳</span></span><small>ONE TICKET. A WORLD OUT THERE.</small><strong>GO FEEL<br />SOMETHING.</strong><span className="ticket-footer">QAZAQSTAN <span>YOUR NEXT MEMORY ↗</span></span></div><div className="ticket-stub"><span>YOUR NEXT MEMORY</span><i /><small>BF — 001</small></div><span className="tear-thread" /></div>
    </div>
    <div className="experience-content" onFocus={() => setFinished(true)}>
      <h1 id="experience-title" lang="en"><Words text="Life happens" /><br /><em><Words text="out there." start={2} /></em></h1>
      <p className="experience-subtitle">{t.intro}</p>
      <form className="experience-search" onSubmit={discover} onFocus={onSearchInteraction} role="search" aria-label={t.discover}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></svg><input ref={searchRef} type="search" aria-label={t.search} placeholder={t.search} value={query} onChange={(e) => onQueryChange(e.target.value)} /><button type="submit" aria-label={t.explore}><Arrow size={20} /></button></form>
      <div className="experience-actions"><a href="#discover" onClick={discover}>{t.explore} <Arrow size={17} /></a><button onClick={onCreate}>{t.create}</button></div>
    </div>
    <span className="experience-coordinate" aria-hidden="true">43.2389° N · 76.8897° E</span><span className="experience-note" aria-hidden="true">YOUR CITY. YOUR PEOPLE. YOUR NEXT MEMORY.</span>
    {!finished && <button ref={skipRef} className="intro-skip" onClick={() => { setFinished(true); searchRef.current?.focus(); }}>{t.skipIntro} ↗</button>}
  <Marquee />
  </section>;
}
