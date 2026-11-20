import { useState } from "react";
import Arrow from "../../components/Icons/Arrow";
import { menuCategories } from "../../data/categories";
import { copy } from "../../data/i18n";
import { localCategory, publicImage } from "../../lib/api";
import { api, download } from "../../lib/client";
import { useLocale, t as translate, errorText } from "../../lib/locale";
import { useResource } from "../../lib/use-resource";
import { useSession } from "../../lib/session-context";
import { Link } from "../app-shared";
import { Form } from "../live-shared";
import "./EventPage.css";

const locales = { en: "en-GB", ru: "ru-RU", kk: "kk-KZ" };

const text = {
  en: {
    home: "Home",
    getTickets: "Get tickets",
    from: "From",
    free: "Free",
    tickets: "Tickets",
    about: "About",
    whenWhere: "When & where",
    starts: "Starts",
    ends: "Ends",
    venue: "Venue",
    map: "Open in maps",
    refunds: "Refunds",
    calendar: "Add to calendar",
    ics: "Calendar file (.ics)",
    choose: "Choose",
    left: (n) => `${n} left`,
    soldOut: "Sold out",
    salesOpen: (d) => `On sale ${d}`,
    salesEnded: "Sales ended",
    regOpens: (d) => `Registration opens ${d}`,
    regClosed: "Registration is closed",
    paidOff: "Paid tickets are not on sale yet",
    perOrder: (a, b) => `${a}–${b} per order`,
    noTickets: "Tickets are not available yet.",
    preview: "Preview: registration is not open.",
    cancelled: "This event has been cancelled.",
    suspended: "Sales for this event are paused.",
    unlisted: "Unlisted event: only people with the link can see it.",
    private: "Private event.",
    seated: "Reserved seating: you pick seats at checkout.",
    promo: "Promo code applied:",
    report: "Report this event",
    gallery: "Photos",
    loading: "Loading event…",
    retry: "Try again",
    timezone: "Times shown in",
  },
  ru: {
    home: "Главная",
    getTickets: "Купить билет",
    from: "От",
    free: "Бесплатно",
    tickets: "Билеты",
    about: "О событии",
    whenWhere: "Когда и где",
    starts: "Начало",
    ends: "Окончание",
    venue: "Площадка",
    map: "Открыть на карте",
    refunds: "Возврат",
    calendar: "Добавить в календарь",
    ics: "Файл календаря (.ics)",
    choose: "Выбрать",
    left: (n) => `Осталось ${n}`,
    soldOut: "Распродано",
    salesOpen: (d) => `Продажа с ${d}`,
    salesEnded: "Продажа завершена",
    regOpens: (d) => `Регистрация откроется ${d}`,
    regClosed: "Регистрация закрыта",
    paidOff: "Платные билеты пока не продаются",
    perOrder: (a, b) => `${a}–${b} в заказе`,
    noTickets: "Билеты пока недоступны.",
    preview: "Предпросмотр: регистрация не открыта.",
    cancelled: "Событие отменено.",
    suspended: "Продажи на это событие приостановлены.",
    unlisted: "Событие по ссылке: его видят только те, у кого есть ссылка.",
    private: "Закрытое событие.",
    seated: "Места по схеме: выберете их при оформлении.",
    promo: "Промокод применён:",
    report: "Пожаловаться на событие",
    gallery: "Фото",
    loading: "Загружаем событие…",
    retry: "Повторить",
    timezone: "Время указано в поясе",
  },
  kk: {
    home: "Басты бет",
    getTickets: "Билет алу",
    from: "Бастап",
    free: "Тегін",
    tickets: "Билеттер",
    about: "Іс-шара туралы",
    whenWhere: "Қашан және қайда",
    starts: "Басталуы",
    ends: "Аяқталуы",
    venue: "Алаң",
    map: "Картадан ашу",
    refunds: "Қайтару",
    calendar: "Күнтізбеге қосу",
    ics: "Күнтізбе файлы (.ics)",
    choose: "Таңдау",
    left: (n) => `${n} қалды`,
    soldOut: "Сатылып кетті",
    salesOpen: (d) => `Сату ${d} басталады`,
    salesEnded: "Сату аяқталды",
    regOpens: (d) => `Тіркеу ${d} ашылады`,
    regClosed: "Тіркеу жабық",
    paidOff: "Ақылы билеттер әзірге сатылмайды",
    perOrder: (a, b) => `Тапсырыста ${a}–${b}`,
    noTickets: "Билеттер әзірге жоқ.",
    preview: "Алдын ала қарау: тіркеу ашылмаған.",
    cancelled: "Іс-шара тоқтатылды.",
    suspended: "Бұл іс-шараға сату тоқтатылды.",
    unlisted: "Сілтеме арқылы ғана көрінетін іс-шара.",
    private: "Жабық іс-шара.",
    seated: "Орындар схема бойынша: рәсімдеу кезінде таңдайсыз.",
    promo: "Промокод қолданылды:",
    report: "Іс-шара туралы шағым",
    gallery: "Суреттер",
    loading: "Іс-шара жүктелуде…",
    retry: "Қайталау",
    timezone: "Уақыт белдеуі",
  },
};

const fmt = (value, lang, timeZone, options) =>
  new Intl.DateTimeFormat(locales[lang], {
    timeZone: timeZone || "Asia/Almaty",
    ...options,
  }).format(new Date(value));
const longDate = (v, lang, tz) =>
  fmt(v, lang, tz, { weekday: "short", day: "numeric", month: "long" });
const time = (v, lang, tz) =>
  fmt(v, lang, tz, { hour: "2-digit", minute: "2-digit", hour12: false });
const shortDate = (v, lang, tz) =>
  fmt(v, lang, tz, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
const tenge = (amount, lang) =>
  `${new Intl.NumberFormat(locales[lang]).format(amount)} ₸`;

// Event page: one view for /events/{slug}, /preview/{id} and campaign links.
export default function EventPage({ slug, id, promo }) {
  const lang = useLocale();
  const t = text[lang];
  const resource = useResource(
    id ? `/events/${id}` : `/events/by-slug/${encodeURIComponent(slug)}`,
  );
  const event = resource.data;

  if (resource.loading)
    return (
      <div className="ev-state" role="status">
        <div className="ev-skeleton" aria-hidden="true" />
        <span className="visually-hidden">{t.loading}</span>
      </div>
    );
  if (resource.error)
    return (
      <div className="ev-state" role="alert">
        <p>{errorText(resource.error)}</p>
        <button className="ev-button ev-button-ghost" onClick={resource.reload}>
          {t.retry}
        </button>
      </div>
    );
  if (!event) return null;
  return <EventView event={event} promo={promo} lang={lang} t={t} />;
}

function EventView({ event, promo, lang, t }) {
  const tz = event.timezone;
  const tickets = useResource(`/events/${event.id}/ticket-types`, true);
  const images = useResource(`/events/${event.id}/images`, true);
  const venue = useResource(
    event.venue_id ? `/venues/${event.venue_id}` : null,
  );
  const categories = useResource(
    event.category_id ? "/event-categories" : null,
    true,
  );
  const [imageFailed, setImageFailed] = useState(false);
  // Read the clock once per page view (render must stay pure).
  const [now] = useState(() => Date.now());

  const category = categories.data?.find((c) => c.id === event.category_id);
  const key = category ? localCategory(category.slug) : "other";
  const menu = category && menuCategories.find((c) => c.match.includes(key));
  const categoryName =
    category?.[`name_${lang}`] || category?.name_en || copy[lang][key];
  const sorted = [...(images.data || [])].sort(
    (a, b) => b.is_cover - a.is_cover || a.sort_order - b.sort_order,
  );
  const cover = publicImage(sorted[0]?.url);
  const fallback = `/images/${key === "other" ? "culture" : key}.jpg`;
  const visible = (tickets.data || []).filter((x) => !x.is_hidden);
  const prices = visible.map((x) => x.price_amount);
  const minPrice = prices.length ? Math.min(...prices) : null;
  const priceLabel =
    minPrice == null
      ? null
      : minPrice === 0
        ? t.free
        : `${t.from} ${tenge(minPrice, lang)}`;
  const open = event.status === "published" && !event.is_suspended;
  const regNotYet =
    event.registration_opens_at && new Date(event.registration_opens_at) > now;
  const regClosed =
    event.registration_closes_at &&
    new Date(event.registration_closes_at) < now;
  const place = venue.data
    ? [venue.data.name, venue.data.address_line, venue.data.city]
        .filter(Boolean)
        .join(", ")
    : "";
  const mapUrl = venue.data
    ? venue.data.latitude != null && venue.data.longitude != null
      ? `https://www.google.com/maps/search/?api=1&query=${venue.data.latitude},${venue.data.longitude}`
      : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place)}`
    : null;
  const notices = [
    event.status === "cancelled" && t.cancelled,
    event.status !== "published" && event.status !== "cancelled" && t.preview,
    event.is_suspended && t.suspended,
    event.visibility === "unlisted" && t.unlisted,
    event.visibility === "private" && t.private,
  ].filter(Boolean);

  return (
    <article className="ev-page">
      <nav className="crumbs" aria-label="Breadcrumb">
        <a href="/">{t.home}</a>
        {menu && (
          <>
            <span aria-hidden="true">/</span>
            <a href={`#/category/${menu.slug}`}>{menu.label[lang]}</a>
          </>
        )}
        <span aria-hidden="true">/</span>
        <span aria-current="page">{event.title}</span>
      </nav>

      {notices.map((n) => (
        <p className="ev-notice" role="status" key={n}>
          {n}
        </p>
      ))}
      {promo && (
        <p className="ev-notice ev-notice-hl" role="status">
          {t.promo} <strong>{promo}</strong>
        </p>
      )}

      <header className="ev-hero">
        <div className="ev-cover">
          <img
            src={imageFailed || !cover ? fallback : cover}
            alt={sorted[0]?.alt_text || ""}
            onError={() => setImageFailed(true)}
          />
        </div>
        <div className="ev-summary">
          {categoryName && <span className="ev-tag">{categoryName}</span>}
          <p className="ev-when">
            {longDate(event.starts_at, lang, tz)} ·{" "}
            {time(event.starts_at, lang, tz)}
          </p>
          <h1>{event.title}</h1>
          {venue.data && (
            <p className="ev-where">
              {venue.data.name}
              {venue.data.city ? ` · ${venue.data.city}` : ""}
            </p>
          )}
          <div className="ev-buy">
            {priceLabel && <strong>{priceLabel}</strong>}
            {open && visible.length > 0 && (
              <a className="ev-button" href="#tickets" onClick={jump}>
                {t.getTickets}
                <Arrow size={16} />
              </a>
            )}
          </div>
        </div>
      </header>

      <div className="ev-body">
        <div className="ev-main">
          <section
            id="tickets"
            className="ev-section"
            aria-labelledby="ev-tickets"
          >
            <h2 id="ev-tickets">{t.tickets}</h2>
            {event.seating_mode === "assigned" && (
              <p className="ev-muted">{t.seated}</p>
            )}
            {tickets.loading && <div className="ev-skeleton ev-skeleton-row" />}
            {tickets.error && <p role="alert">{errorText(tickets.error)}</p>}
            {tickets.data && !visible.length && (
              <p className="ev-muted">{t.noTickets}</p>
            )}
            <ul className="ev-tickets">
              {visible.map((ticket) => (
                <TicketRow
                  key={ticket.id}
                  ticket={ticket}
                  event={event}
                  promo={promo}
                  lang={lang}
                  t={t}
                  now={now}
                  blocked={
                    !open
                      ? t.preview
                      : regNotYet
                        ? t.regOpens(
                            shortDate(event.registration_opens_at, lang, tz),
                          )
                        : regClosed
                          ? t.regClosed
                          : null
                  }
                />
              ))}
            </ul>
          </section>

          {event.description && (
            <section className="ev-section" aria-labelledby="ev-about">
              <h2 id="ev-about">{t.about}</h2>
              <p className="ev-description">{event.description}</p>
            </section>
          )}

          {sorted.length > 1 && (
            <section className="ev-section" aria-labelledby="ev-gallery">
              <h2 id="ev-gallery">{t.gallery}</h2>
              <div className="ev-gallery">
                {sorted.slice(1).map((image) => {
                  const src = publicImage(image.url);
                  return src ? (
                    <img
                      key={image.id}
                      src={src}
                      alt={image.alt_text || ""}
                      loading="lazy"
                    />
                  ) : null;
                })}
              </div>
            </section>
          )}

          {event.refund_policy && (
            <section className="ev-section" aria-labelledby="ev-refunds">
              <h2 id="ev-refunds">{t.refunds}</h2>
              <p className="ev-description">{event.refund_policy}</p>
            </section>
          )}

          <ReportEvent id={event.id} label={t.report} />
        </div>

        <aside className="ev-side">
          <section className="ev-card" aria-labelledby="ev-when">
            <h2 id="ev-when">{t.whenWhere}</h2>
            <dl>
              <div>
                <dt>{t.starts}</dt>
                <dd>{shortDate(event.starts_at, lang, tz)}</dd>
              </div>
              {event.ends_at && (
                <div>
                  <dt>{t.ends}</dt>
                  <dd>{shortDate(event.ends_at, lang, tz)}</dd>
                </div>
              )}
              {place && (
                <div>
                  <dt>{t.venue}</dt>
                  <dd>{place}</dd>
                </div>
              )}
            </dl>
            <p className="ev-muted ev-tz">
              {t.timezone} {tz}
            </p>
            {mapUrl && (
              <a
                className="ev-button ev-button-ghost"
                href={mapUrl}
                target="_blank"
                rel="noreferrer"
              >
                {t.map}
                <Arrow size={15} />
              </a>
            )}
          </section>
          <Calendar id={event.id} t={t} />
        </aside>
      </div>

      {open && visible.length > 0 && (
        <div className="ev-sticky">
          <span>{priceLabel}</span>
          <a className="ev-button" href="#tickets" onClick={jump}>
            {t.getTickets}
          </a>
        </div>
      )}
    </article>
  );
}

// In-page jump without touching the hash (the hash holds the route).
function jump(e) {
  e.preventDefault();
  document
    .getElementById("tickets")
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function TicketRow({ ticket, event, promo, lang, t, blocked, now }) {
  const tz = event.timezone;
  const left = Math.max(
    0,
    ticket.quantity_total - ticket.quantity_sold - ticket.quantity_reserved,
  );
  const status =
    blocked ||
    (left === 0
      ? t.soldOut
      : ticket.sales_start_at && new Date(ticket.sales_start_at) > now
        ? t.salesOpen(shortDate(ticket.sales_start_at, lang, tz))
        : ticket.sales_end_at && new Date(ticket.sales_end_at) < now
          ? t.salesEnded
          : ticket.price_amount > 0 &&
              event.paid_sales_status &&
              event.paid_sales_status !== "active"
            ? t.paidOff
            : null);
  return (
    <li className={`ev-ticket${status ? " is-off" : ""}`}>
      <div className="ev-ticket-info">
        <h3>{ticket.name}</h3>
        {ticket.description && <p>{ticket.description}</p>}
        <small>
          {status ||
            [
              left <= 20 ? t.left(left) : null,
              ticket.max_per_order
                ? t.perOrder(ticket.min_per_order || 1, ticket.max_per_order)
                : null,
            ]
              .filter(Boolean)
              .join(" · ")}
        </small>
      </div>
      <strong className="ev-ticket-price">
        {ticket.price_amount === 0 ? t.free : tenge(ticket.price_amount, lang)}
      </strong>
      {!status && (
        <Link
          className="ev-button"
          to={`/checkout/${event.id}?ticket=${ticket.id}&promo=${encodeURIComponent(promo || "")}`}
        >
          {t.choose}
        </Link>
      )}
    </li>
  );
}

function Calendar({ id, t }) {
  const links = useResource(`/events/${id}/calendar-links`);
  if (!links.data) return null;
  return (
    <section className="ev-card" aria-labelledby="ev-cal">
      <h2 id="ev-cal">{t.calendar}</h2>
      <div className="ev-cal-links">
        <a href={links.data.google} target="_blank" rel="noreferrer">
          Google Calendar
        </a>
        <a href={links.data.outlook} target="_blank" rel="noreferrer">
          Outlook
        </a>
        <button
          onClick={() => download(`/events/${id}/calendar.ics`, "event.ics")}
        >
          {t.ics}
        </button>
      </div>
    </section>
  );
}

function ReportEvent({ id, label }) {
  const { user } = useSession() || {};
  if (!user) return null;
  return (
    <details className="ev-report">
      <summary>{label}</summary>
      <Form
        fields={[
          {
            name: "reason",
            label: translate("Report reason"),
            type: "textarea",
            required: true,
            maxLength: 2000,
          },
        ]}
        label="Send report"
        submit={(body) =>
          api(`/events/${id}/reports`, {
            method: "POST",
            body,
          })
        }
      />
    </details>
  );
}
