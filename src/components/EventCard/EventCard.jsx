import Arrow from "../Icons/Arrow";
import { copy, cityLabel } from "../../data/i18n";
import { formatEventDate, formatEventPrice } from "./format";
// Card styles (.event-card, .event-link, .event-image, ...) live in Home.css.
export default function EventCard({ event, lang, onOpen }) {
  const t = copy[lang];
  const date = formatEventDate(event, lang);
  const price = formatEventPrice(event, lang);
  return (
    <article className="event-card">
      <button
        className="event-link"
        onClick={() => onOpen(event)}
        aria-label={`${event.title}, ${date}, ${price}`}
      >
        <div className="event-image">
          <img
            src={event.image}
            alt=""
            loading="lazy"
            onError={(e) => {
              e.currentTarget.style.visibility = "hidden";
            }}
          />
          <span className="event-badge">{t[event.category] || t.other}</span>
          <span className="image-arrow">
            <Arrow size={16} />
          </span>
        </div>
        <div className="event-date">{date}</div>
        <h3>{event.title}</h3>
        <p className="event-location">
          {event.venue || t.unknownVenue} ·{" "}
          {cityLabel(event.city, lang) || t.unknownVenue}
        </p>
        <div className="event-bottom">
          <strong className={event.price === 0 ? "free-price" : ""}>
            {price}
          </strong>
          <span>
            {event.demo ? t.demo : "BiletFlow"}{" "}
            <Arrow size={15} />
          </span>
        </div>
      </button>
    </article>
  );
}
