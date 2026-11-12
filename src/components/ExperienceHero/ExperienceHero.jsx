import { useEffect, useRef, useState } from "react";
import "./ExperienceHero.css";
const scenes = [
  { image: "music", label: "LIVE / ALMATY", title: "Concerts", side: "concert" },
  { image: "hero", label: "OPEN AIR / QAZAQSTAN", title: "Festivals", side: "festival" },
  { image: "theatre", label: "ON STAGE / ASTANA", title: "Theatre", side: "theatre" },
  { image: "culture", label: "TOGETHER / QAZAQSTAN", title: "Culture", side: "culture" },
];
const sessionKey = "biletflow-original-hero-intro";
let seenInMemory = false;
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function introSeen() {
  try { return seenInMemory || sessionStorage.getItem(sessionKey) === "seen"; }
  catch { return seenInMemory; }
}
export default function ExperienceHero({ t, query, onQueryChange, onCreate, onSearchInteraction, onIntroFinish }) {
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
    <div className="experience-art" aria-hidden="true">
      {scenes.map((scene) => <div className={`experience-card scene-${scene.side}`} key={scene.side}><img src={`/images/${scene.image}.jpg`} alt="" fetchPriority="high" /><div className="scene-caption"><small>{scene.label}</small><strong>{scene.title}</strong><span>↗</span></div></div>)}
      <div className="opening-ticket"><div className="ticket-body"><span className="ticket-brand">BiletFlow<span>✳</span></span><small>ONE TICKET. A WORLD OUT THERE.</small><strong>GO FEEL<br />SOMETHING.</strong><span className="ticket-footer">QAZAQSTAN <span>YOUR NEXT MEMORY ↗</span></span></div><div className="ticket-stub"><span>YOUR NEXT MEMORY</span><i /><small>BF — 001</small></div><span className="tear-thread" /></div>
    </div>
    <div className="experience-content" onFocus={() => setFinished(true)}>
      <p className="experience-kicker">BiletFlow <span> / {t.eyebrow}</span></p>
      <h1 id="experience-title" lang="en">Life happens<br /><em>out there.</em></h1>
      <p className="experience-subtitle">{t.intro}</p>
      <form className="experience-search" onSubmit={discover} onFocus={onSearchInteraction} role="search" aria-label={t.discover}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></svg><input ref={searchRef} type="search" aria-label={t.search} placeholder={t.search} value={query} onChange={(e) => onQueryChange(e.target.value)} /><button type="submit" aria-label={t.explore}>↗</button></form>
      <div className="experience-actions"><a href="#discover" onClick={discover}>{t.explore} <span aria-hidden="true">↗</span></a><button onClick={onCreate}>{t.create}</button></div>
    </div>
    <span className="experience-coordinate" aria-hidden="true">43.2389° N · 76.8897° E</span><span className="experience-note" aria-hidden="true">YOUR CITY. YOUR PEOPLE. YOUR NEXT MEMORY.</span>
    {!finished && <button ref={skipRef} className="intro-skip" onClick={() => { setFinished(true); searchRef.current?.focus(); }}>{t.skipIntro} ↗</button>}
  </section>;
}
