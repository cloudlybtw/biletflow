import { useEffect, useState } from "react";
import Navbar from "../../components/Navbar/Navbar";
import EventCard from "../../components/EventCard/EventCard";
import Arrow from "../../components/Icons/Arrow";
import Dropdown from "../../components/Dropdown/Dropdown";
import {
  EventCardSkeleton,
  EmptyState,
  ErrorState,
  NotFound,
} from "../../components/States/States";
import {
  formatEventDate,
  formatEventPrice,
} from "../../components/EventCard/format";
import { categoryBySlug, menuCategories } from "../../data/categories";
import { cities, cityLabel } from "../../data/i18n";
import { loadEvents } from "../../lib/api";
import { useCity } from "../../lib/city";
import { localDay } from "../../lib/discovery";
import { useLocale } from "../../lib/locale";
import "../Home/Home.css";
import "./Category.css";

const PAGE = 12;

const text = {
  en: {
    home: "Home",
    events: "events",
    allEvents: "All events",
    search: "Search",
    results: "Results for",
    city: "City",
    allCities: "All cities",
    when: "When",
    sort: "Sort",
    any: "Any date",
    today: "Today",
    tomorrow: "Tomorrow",
    weekend: "Weekend",
    week: "This week",
    month: "This month",
    free: "Free only",
    byDate: "Soonest first",
    cheap: "Price: low to high",
    pricey: "Price: high to low",
    next: "Next up",
    tickets: "Get tickets",
    more: "Show more",
    shown: (a, b) => `Showing ${a} of ${b}`,
    emptyTitle: "No events match",
    emptyBody: "Try another date or city, or clear the filters.",
    clear: "Clear filters",
    explore: "Explore other categories",
    intro: {
      concerts:
        "Live music across Kazakhstan: big arena shows, club nights, jazz and open-air festivals.",
      default: "Everything coming up in this category, soonest first.",
      all: "Every upcoming event on BiletFlow, soonest first.",
    },
  },
  ru: {
    home: "Главная",
    events: "событий",
    allEvents: "Все события",
    search: "Поиск",
    results: "Результаты по запросу",
    city: "Город",
    allCities: "Все города",
    when: "Когда",
    sort: "Сортировка",
    any: "Любая дата",
    today: "Сегодня",
    tomorrow: "Завтра",
    weekend: "Выходные",
    week: "Эта неделя",
    month: "Этот месяц",
    free: "Бесплатно",
    byDate: "Сначала ближайшие",
    cheap: "Сначала дешевле",
    pricey: "Сначала дороже",
    next: "Ближайшее",
    tickets: "Купить билет",
    more: "Показать ещё",
    shown: (a, b) => `Показано ${a} из ${b}`,
    emptyTitle: "Ничего не нашлось",
    emptyBody: "Попробуйте другую дату или город либо сбросьте фильтры.",
    clear: "Сбросить фильтры",
    explore: "Другие категории",
    intro: {
      concerts:
        "Живая музыка по всему Казахстану: большие шоу на аренах, клубные вечера, джаз и фестивали под открытым небом.",
      default: "Все ближайшие события этой категории.",
      all: "Все предстоящие события на BiletFlow, сначала ближайшие.",
    },
  },
  kk: {
    home: "Басты бет",
    events: "іс-шара",
    allEvents: "Барлық іс-шаралар",
    search: "Іздеу",
    results: "Іздеу нәтижелері:",
    city: "Қала",
    allCities: "Барлық қалалар",
    when: "Қашан",
    sort: "Сұрыптау",
    any: "Кез келген күн",
    today: "Бүгін",
    tomorrow: "Ертең",
    weekend: "Демалыс",
    week: "Осы апта",
    month: "Осы ай",
    free: "Тек тегін",
    byDate: "Алдымен жақындары",
    cheap: "Алдымен арзандары",
    pricey: "Алдымен қымбаттары",
    next: "Ең жақыны",
    tickets: "Билет алу",
    more: "Тағы көрсету",
    shown: (a, b) => `${b} ішінен ${a} көрсетілді`,
    emptyTitle: "Ештеңе табылмады",
    emptyBody: "Басқа күнді немесе қаланы таңдаңыз не сүзгілерді тазалаңыз.",
    clear: "Сүзгілерді тазалау",
    explore: "Басқа санаттар",
    intro: {
      concerts:
        "Қазақстан бойынша тірі музыка: аренадағы үлкен шоулар, клуб кештері, джаз және ашық аспан астындағы фестивальдер.",
      default: "Осы санаттағы жақын іс-шаралардың бәрі.",
      all: "BiletFlow-дағы барлық алдағы іс-шаралар.",
    },
  },
};

const ranges = ["any", "today", "tomorrow", "weekend", "week", "month"];

// Day keys (YYYY-MM-DD, Almaty time) for each quick range.
function rangeBounds(range, now = new Date()) {
  const today = localDay(now);
  const shift = (days) =>
    localDay(new Date(+new Date(`${today}T12:00:00+05:00`) + days * 86400000));
  const weekday = new Date(`${today}T12:00:00+05:00`).getUTCDay() || 7;
  if (range === "today") return [today, today];
  if (range === "tomorrow") return [shift(1), shift(1)];
  if (range === "weekend")
    return weekday >= 6
      ? [today, shift(7 - weekday)]
      : [shift(6 - weekday), shift(7 - weekday)];
  if (range === "week") return [today, shift(7 - weekday)];
  if (range === "month") return [today, `${today.slice(0, 7)}-31`];
  return null;
}

function readParams(route) {
  const params = new URLSearchParams(route.split("?")[1] || "");
  return {
    when: ranges.includes(params.get("when")) ? params.get("when") : "any",
    sort: ["date", "cheap", "pricey"].includes(params.get("sort"))
      ? params.get("sort")
      : "date",
    free: params.get("free") === "1",
    q: (params.get("q") || "").trim(),
  };
}

export default function Category({ route }) {
  const lang = useLocale();
  const t = text[lang];
  // One listing for /category/{slug}, /events (everything) and /search?q=.
  const path = route.split("?")[0];
  const searching = path === "/search";
  const slug = path.startsWith("/category/") ? path.split("/")[2] : "";
  const category = slug ? categoryBySlug(slug) : null;
  const missing = slug && !category;
  const [city, setCity] = useCity();
  const [data, setData] = useState({ events: [], state: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [limit, setLimit] = useState(PAGE);
  const filters = readParams(route);

  const heading = category
    ? category.label[lang]
    : searching
      ? filters.q
        ? `“${filters.q}”`
        : t.search
      : t.allEvents;
  useEffect(() => {
    if (!missing) document.title = `${heading} | BiletFlow`;
  }, [missing, heading]);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    loadEvents(controller.signal)
      .then((events) => active && setData({ events, state: "live" }))
      .catch(() => active && setData({ events: [], state: "error" }));
    return () => {
      active = false;
      controller.abort();
    };
  }, [attempt]);

  const setFilter = (key, value) => {
    const next = { ...filters, [key]: value };
    const params = new URLSearchParams();
    if (next.when !== "any") params.set("when", next.when);
    if (next.sort !== "date") params.set("sort", next.sort);
    if (next.free) params.set("free", "1");
    if (next.q) params.set("q", next.q);
    const qs = params.toString();
    history.replaceState(null, "", `#${path}${qs ? `?${qs}` : ""}`);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    setLimit(PAGE);
  };

  const inCategory = data.events.filter((e) => {
    if (category && !category.match.includes(e.category)) return false;
    if (!filters.q) return true;
    const q = filters.q.toLocaleLowerCase();
    return [e.title, e.venue, e.description].some((v) =>
      v?.toLocaleLowerCase().includes(q),
    );
  });

  const results = (() => {
    const bounds = rangeBounds(filters.when);
    const list = inCategory.filter((e) => {
      if (city && e.city !== city) return false;
      if (filters.free && e.price !== 0) return false;
      if (bounds) {
        const day = localDay(e.startsAt);
        if (day < bounds[0] || day > bounds[1]) return false;
      }
      return true;
    });
    const price = (e) => (e.price == null ? Infinity : e.price);
    if (filters.sort === "cheap") list.sort((a, b) => price(a) - price(b));
    if (filters.sort === "pricey")
      list.sort((a, b) => (b.price ?? -1) - (a.price ?? -1));
    return list;
  })();

  if (missing)
    return (
      <>
        <Navbar />
        <main className="page-width">
          <NotFound />
        </main>
      </>
    );

  const open = (event) => window.location.assign(`#/events/${event.slug}`);
  const featured = filters.sort === "date" ? results[0] : null;
  const grid = featured ? results.slice(1) : results;
  const visible = grid.slice(0, limit);
  const filtered = filters.when !== "any" || filters.free || city;
  const clearUrl = `#${path}${filters.q ? `?q=${encodeURIComponent(filters.q)}` : ""}`;

  return (
    <>
      <Navbar />
      <main className="category-page page-width">
        <nav className="crumbs" aria-label="Breadcrumb">
          <a href="/">{t.home}</a>
          <span aria-hidden="true">/</span>
          {searching && <span>{t.search}</span>}
          {searching && <span aria-hidden="true">/</span>}
          <span aria-current="page">
            {category
              ? category.label[lang]
              : searching
                ? filters.q || t.search
                : t.allEvents}
          </span>
        </nav>
        <header className="category-head">
          <h1 className={searching ? "is-query" : undefined}>
            {heading}
            {data.state === "live" && (
              <sup aria-label={`${results.length} ${t.events}`}>
                {results.length}
              </sup>
            )}
          </h1>
          <p>
            {searching && filters.q
              ? `${t.results} “${filters.q}”`
              : category
                ? t.intro[slug] || t.intro.default
                : t.intro.all}
          </p>
        </header>

        <div className="category-filters">
          <div className="chip-row" role="group" aria-label={t.when}>
            {ranges.map((r) => (
              <button
                key={r}
                aria-pressed={filters.when === r}
                onClick={() => setFilter("when", r)}
              >
                {t[r]}
              </button>
            ))}
            <button
              aria-pressed={filters.free}
              onClick={() => setFilter("free", !filters.free)}
            >
              {t.free}
            </button>
          </div>
          <div className="select-row">
            <Dropdown
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
            <Dropdown
              label={t.sort}
              value={filters.sort}
              onChange={(value) => setFilter("sort", value)}
              icon={<span className="dropdown-prefix">{t.sort}</span>}
              options={[
                { value: "date", label: t.byDate },
                { value: "cheap", label: t.cheap },
                { value: "pricey", label: t.pricey },
              ]}
            />
          </div>
        </div>

        {data.state === "loading" && <EventCardSkeleton count={8} />}
        {data.state === "error" && (
          <ErrorState
            onRetry={() => {
              setData({ events: [], state: "loading" });
              setAttempt((n) => n + 1);
            }}
          />
        )}
        {data.state === "live" && !results.length && (
          <EmptyState
            title={t.emptyTitle}
            body={t.emptyBody}
            action={filtered ? t.clear : undefined}
            onAction={() => {
              setCity("");
              history.replaceState(null, "", clearUrl);
              window.dispatchEvent(new HashChangeEvent("hashchange"));
            }}
          />
        )}

        {featured && (
          <button className="spotlight" onClick={() => open(featured)}>
            <div className="spotlight-image">
              <img src={featured.image} alt="" />
            </div>
            <div className="spotlight-body">
              <span className="spotlight-tag">{t.next}</span>
              <h2>{featured.title}</h2>
              <dl>
                <div>
                  <dt className="visually-hidden">Date</dt>
                  <dd>{formatEventDate(featured, lang)}</dd>
                </div>
                <div>
                  <dt className="visually-hidden">Place</dt>
                  <dd>
                    {[featured.venue, cityLabel(featured.city, lang)]
                      .filter(Boolean)
                      .join(" · ")}
                  </dd>
                </div>
              </dl>
              <div className="spotlight-foot">
                <strong>{formatEventPrice(featured, lang)}</strong>
                <span className="spotlight-cta">
                  {t.tickets}
                  <Arrow size={16} />
                </span>
              </div>
            </div>
          </button>
        )}

        {visible.length > 0 && (
          <div className="event-grid category-grid">
            {visible.map((e) => (
              <EventCard key={e.id} event={e} lang={lang} onOpen={open} />
            ))}
          </div>
        )}

        {grid.length > visible.length && (
          <div className="more-row">
            <p>
              {t.shown(visible.length + (featured ? 1 : 0), results.length)}
            </p>
            <button
              className="button button-purple"
              onClick={() => setLimit((n) => n + PAGE)}
            >
              {t.more}
            </button>
          </div>
        )}

        <section className="explore" aria-labelledby="explore-title">
          <h2 id="explore-title">{t.explore}</h2>
          <ul>
            {menuCategories
              .filter((c) => c.slug !== slug)
              .map((c) => (
                <li key={c.slug}>
                  <a href={`#/category/${c.slug}`}>
                    {c.label[lang]}
                    <Arrow size={18} />
                  </a>
                </li>
              ))}
          </ul>
        </section>
      </main>
    </>
  );
}
