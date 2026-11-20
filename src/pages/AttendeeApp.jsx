import CalendarLinks from "./CalendarLinks";
import { t as translate, useLocale, errorText } from "../lib/locale";
import { useSession } from "../lib/session-context";
import { api, apiPath, download } from "../lib/client";
import { useResource } from "../lib/use-resource";
import { Topbar, Link } from "./app-shared";
import { State, Form, Action, SecureImage, OrderSummary } from "./live-shared";
import Arrow from "../components/Icons/Arrow";
import SupportPanel from "./SupportPanel";
import { Payment } from "./PublicPages";
import "./Account.css";

// Buyer account: dark, DICE-style. Tabs on top instead of the workspace
// sidebar; tickets as cards with QR; orders and notifications as lists.
const locales = { en: "en-GB", ru: "ru-RU", kk: "kk-KZ" };
const text = {
  en: {
    hi: "Hi,",
    tabs: {
      "": "Overview",
      tickets: "My tickets",
      orders: "Orders",
      notifications: "Notifications",
      support: "Support",
      settings: "Settings",
    },
    account: "Account",
    upcoming: "Upcoming",
    past: "Past",
    tickets: "Tickets",
    orders: "Orders",
    unread: "Unread",
    nextUp: "Next up",
    noTickets: "No tickets yet",
    noTicketsBody: "Find something to go to: your tickets will appear here.",
    browse: "Browse events",
    open: "Open ticket",
    all: "All tickets",
    seat: "Seat",
    row: "Row",
    section: "Section",
    type: "Ticket type",
    attendee: "Attendee",
    code: "Ticket code",
    when: "When",
    where: "Where",
    pdf: "Download PDF",
    showQr: "Show this QR code at the entrance.",
    noOrders: "No orders yet",
    order: "Order",
    view: "View",
    noNotes: "No notifications",
    noNotesBody: "Order, ticket and support updates will show up here.",
    markRead: "Mark read",
    back: "Back",
    password: "Change password",
    verify: "Verify email to book tickets",
    status: {
      valid: "Valid",
      checked_in: "Checked in",
      cancelled: "Cancelled",
      refunded: "Refunded",
      pending: "Pending",
      awaiting_payment: "Awaiting payment",
      paid: "Paid",
      completed: "Completed",
      partially_refunded: "Partly refunded",
      expired: "Expired",
    },
  },
  ru: {
    hi: "Привет,",
    tabs: {
      "": "Обзор",
      tickets: "Мои билеты",
      orders: "Заказы",
      notifications: "Уведомления",
      support: "Поддержка",
      settings: "Настройки",
    },
    account: "Аккаунт",
    upcoming: "Предстоящие",
    past: "Прошедшие",
    tickets: "Билеты",
    orders: "Заказы",
    unread: "Непрочитанные",
    nextUp: "Ближайшее",
    noTickets: "Билетов пока нет",
    noTicketsBody: "Выберите событие: купленные билеты появятся здесь.",
    browse: "Смотреть афишу",
    open: "Открыть билет",
    all: "Все билеты",
    seat: "Место",
    row: "Ряд",
    section: "Сектор",
    type: "Тип билета",
    attendee: "Участник",
    code: "Код билета",
    when: "Когда",
    where: "Где",
    pdf: "Скачать PDF",
    showQr: "Покажите этот QR-код на входе.",
    noOrders: "Заказов пока нет",
    order: "Заказ",
    view: "Открыть",
    noNotes: "Уведомлений нет",
    noNotesBody: "Здесь появятся новости о заказах, билетах и обращениях.",
    markRead: "Прочитано",
    back: "Назад",
    password: "Сменить пароль",
    verify: "Подтвердите почту, чтобы покупать билеты",
    status: {
      valid: "Действует",
      checked_in: "Использован",
      cancelled: "Отменён",
      refunded: "Возвращён",
      pending: "В обработке",
      awaiting_payment: "Ждёт оплаты",
      paid: "Оплачен",
      completed: "Завершён",
      partially_refunded: "Частичный возврат",
      expired: "Истёк",
    },
  },
  kk: {
    hi: "Сәлем,",
    tabs: {
      "": "Шолу",
      tickets: "Билеттерім",
      orders: "Тапсырыстар",
      notifications: "Хабарландырулар",
      support: "Қолдау",
      settings: "Баптаулар",
    },
    account: "Аккаунт",
    upcoming: "Алдағы",
    past: "Өткен",
    tickets: "Билеттер",
    orders: "Тапсырыстар",
    unread: "Оқылмаған",
    nextUp: "Ең жақыны",
    noTickets: "Әзірге билет жоқ",
    noTicketsBody: "Іс-шара таңдаңыз: сатып алған билеттер осында шығады.",
    browse: "Афишаны көру",
    open: "Билетті ашу",
    all: "Барлық билеттер",
    seat: "Орын",
    row: "Қатар",
    section: "Сектор",
    type: "Билет түрі",
    attendee: "Қатысушы",
    code: "Билет коды",
    when: "Қашан",
    where: "Қайда",
    pdf: "PDF жүктеу",
    showQr: "Кіреберісте осы QR-кодты көрсетіңіз.",
    noOrders: "Әзірге тапсырыс жоқ",
    order: "Тапсырыс",
    view: "Ашу",
    noNotes: "Хабарландыру жоқ",
    noNotesBody: "Тапсырыс, билет және өтініш жаңалықтары осында шығады.",
    markRead: "Оқылды",
    back: "Артқа",
    password: "Құпиясөзді өзгерту",
    verify: "Билет алу үшін поштаны растаңыз",
    status: {
      valid: "Жарамды",
      checked_in: "Пайдаланылды",
      cancelled: "Тоқтатылды",
      refunded: "Қайтарылды",
      pending: "Өңделуде",
      awaiting_payment: "Төлем күтілуде",
      paid: "Төленді",
      completed: "Аяқталды",
      partially_refunded: "Ішінара қайтарылды",
      expired: "Мерзімі өтті",
    },
  },
};

const fmt = (value, lang, tz, options) =>
  value
    ? new Intl.DateTimeFormat(locales[lang], {
        timeZone: tz || "Asia/Almaty",
        ...options,
      }).format(new Date(value))
    : "—";
const dayMonth = (v, lang, tz) => ({
  day: fmt(v, lang, tz, { day: "numeric" }),
  month: fmt(v, lang, tz, { month: "short" }).replace(".", ""),
});
const dateTime = (v, lang, tz) =>
  fmt(v, lang, tz, {
    weekday: "short",
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
const tenge = (amount, lang) =>
  `${new Intl.NumberFormat(locales[lang]).format(amount || 0)} ₸`;
const isUpcoming = (ticket) =>
  new Date(ticket.event?.ends_at || ticket.event?.starts_at) >= new Date();

function StatusChip({ status, t }) {
  return (
    <span className={`acc-chip is-${status}`}>
      {t.status[status] || status}
    </span>
  );
}

function Empty({ title, body, action }) {
  return (
    <div className="acc-empty">
      <h2>{title}</h2>
      {body && <p>{body}</p>}
      {action}
    </div>
  );
}

function ListState({ resource, children }) {
  if (resource.loading)
    return <div className="acc-skeleton" role="status" aria-busy="true" />;
  if (resource.error)
    return (
      <div className="acc-empty" role="alert">
        <p>{errorText(resource.error)}</p>
        <button
          className="acc-button acc-button-ghost"
          onClick={resource.reload}
        >
          {translate("Try again")}
        </button>
      </div>
    );
  return children;
}

function TicketCard({ ticket, lang, t }) {
  const e = ticket.event || {};
  const { day, month } = dayMonth(e.starts_at, lang, e.timezone);
  const seat = [
    ticket.seat_section_label,
    ticket.seat_row_label && `${t.row} ${ticket.seat_row_label}`,
    ticket.seat_number_label && `${t.seat} ${ticket.seat_number_label}`,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <li>
      <a
        className={`acc-ticket${ticket.status === "valid" ? "" : " is-off"}`}
        href={`/#/account/tickets/${ticket.id}`}
      >
        <div className="acc-ticket-date" aria-hidden="true">
          <strong>{day}</strong>
          <span>{month}</span>
        </div>
        <div className="acc-ticket-body">
          <h3>{e.title}</h3>
          <p>
            {fmt(e.starts_at, lang, e.timezone, {
              weekday: "short",
              hour: "2-digit",
              minute: "2-digit",
              hour12: false,
            })}
            {e.venue_name ? ` · ${e.venue_name}` : ""}
            {e.venue_city ? `, ${e.venue_city}` : ""}
          </p>
          <p className="acc-ticket-meta">
            {ticket.ticket_type_name}
            {seat ? ` · ${seat}` : ""}
          </p>
        </div>
        <div className="acc-ticket-stub">
          <StatusChip status={ticket.status} t={t} />
          <span className="acc-ticket-open">
            {t.open}
            <Arrow size={14} />
          </span>
        </div>
      </a>
    </li>
  );
}

function Tickets({ lang, t }) {
  const tickets = useResource("/tickets", true);
  const list = [...(tickets.data || [])].sort(
    (a, b) => new Date(a.event?.starts_at) - new Date(b.event?.starts_at),
  );
  const upcoming = list.filter(isUpcoming);
  const past = list.filter((x) => !isUpcoming(x)).reverse();
  return (
    <ListState resource={tickets}>
      {!list.length ? (
        <Empty
          title={t.noTickets}
          body={t.noTicketsBody}
          action={
            <a className="acc-button" href="/#/events">
              {t.browse}
              <Arrow size={15} />
            </a>
          }
        />
      ) : (
        [
          [t.upcoming, upcoming],
          [t.past, past],
        ]
          .filter(([, items]) => items.length)
          .map(([title, items]) => (
            <section className="acc-section" key={title}>
              <h2 className="acc-label">
                {title} <span>{items.length}</span>
              </h2>
              <ul className="acc-tickets">
                {items.map((ticket) => (
                  <TicketCard
                    key={ticket.id}
                    ticket={ticket}
                    lang={lang}
                    t={t}
                  />
                ))}
              </ul>
            </section>
          ))
      )}
    </ListState>
  );
}

function Ticket({ id, lang, t }) {
  const resource = useResource(`/tickets/${id}`);
  const ticket = resource.data;
  const e = ticket?.event || {};
  return (
    <>
      <Link className="acc-back" to="/account/tickets">
        ← {t.all}
      </Link>
      <State resource={resource}>
        {ticket && (
          <article className="acc-pass">
            <div className="acc-pass-main">
              <StatusChip status={ticket.status} t={t} />
              <h2>{e.title}</h2>
              <dl>
                <div>
                  <dt>{t.when}</dt>
                  <dd>{dateTime(e.starts_at, lang, e.timezone)}</dd>
                </div>
                <div>
                  <dt>{t.where}</dt>
                  <dd>
                    {[e.venue_name, e.venue_address, e.venue_city]
                      .filter(Boolean)
                      .join(", ") || "—"}
                  </dd>
                </div>
                <div>
                  <dt>{t.attendee}</dt>
                  <dd>{ticket.attendee_name}</dd>
                </div>
                <div>
                  <dt>{t.type}</dt>
                  <dd>{ticket.ticket_type_name}</dd>
                </div>
                {ticket.seat_number_label && (
                  <div>
                    <dt>{t.seat}</dt>
                    <dd>
                      {[
                        ticket.seat_section_label,
                        ticket.seat_row_label &&
                          `${t.row} ${ticket.seat_row_label}`,
                        `${t.seat} ${ticket.seat_number_label}`,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </dd>
                  </div>
                )}
              </dl>
              <Action
                className="acc-button"
                perform={() =>
                  download(apiPath(ticket.pdf_url), `${ticket.ticket_code}.pdf`)
                }
              >
                {t.pdf}
              </Action>
            </div>
            <div className="acc-pass-qr">
              <SecureImage
                path={apiPath(ticket.qr_image_url)}
                alt={translate("Ticket admission QR")}
              />
              <code>{ticket.ticket_code}</code>
              <p>{t.showQr}</p>
            </div>
          </article>
        )}
      </State>
    </>
  );
}

function Orders({ lang, t }) {
  const orders = useResource("/orders", true);
  const list = [...(orders.data || [])].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at),
  );
  return (
    <ListState resource={orders}>
      {!list.length ? (
        <Empty
          title={t.noOrders}
          action={
            <a className="acc-button" href="/#/events">
              {t.browse}
            </a>
          }
        />
      ) : (
        <ul className="acc-rows">
          {list.map((order) => (
            <li key={order.id}>
              <a className="acc-row" href={`/#/account/orders/${order.id}`}>
                <div>
                  <strong>
                    {t.order} {order.order_number}
                  </strong>
                  <small>
                    {fmt(order.placed_at || order.created_at, lang, null, {
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                    })}
                  </small>
                </div>
                <StatusChip status={order.status} t={t} />
                <strong className="acc-row-amount">
                  {tenge(order.total_amount, lang)}
                </strong>
                <span className="acc-row-go" aria-hidden="true">
                  <Arrow size={16} />
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </ListState>
  );
}

function Order({ id, t }) {
  const resource = useResource(`/orders/${id}`);
  return (
    <>
      <Link className="acc-back" to="/account/orders">
        ← {t.tabs.orders}
      </Link>
      <div className="acc-legacy">
        <State resource={resource}>
          {resource.data && (
            <>
              <OrderSummary order={resource.data} />
              {resource.data.status === "completed" &&
                resource.data.event_id && (
                  <CalendarLinks id={resource.data.event_id} />
                )}
              {["pending", "awaiting_payment"].includes(
                resource.data.status,
              ) && (
                <Payment
                  key={resource.data.updated_at}
                  order={resource.data}
                  done={resource.reload}
                />
              )}
            </>
          )}
        </State>
      </div>
    </>
  );
}

function Notifications({ lang, t }) {
  const notes = useResource("/notifications", true, 15000);
  const list = notes.data || [];
  return (
    <ListState resource={notes}>
      {!list.length ? (
        <Empty title={t.noNotes} body={t.noNotesBody} />
      ) : (
        <ul className="acc-rows">
          {list.map((note) => (
            <li
              key={note.id}
              className={`acc-note${note.read_at ? "" : " is-new"}`}
            >
              <span className="acc-dot" aria-hidden="true" />
              <div>
                <strong>{note.title}</strong>
                <p>{note.body}</p>
                <small>
                  {fmt(note.created_at, lang, null, {
                    day: "numeric",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                    hour12: false,
                  })}
                </small>
              </div>
              {!note.read_at && (
                <Action
                  className="acc-button acc-button-ghost"
                  perform={() =>
                    api(`/notifications/${note.id}/read`, { method: "POST" })
                  }
                  done={notes.reload}
                >
                  {t.markRead}
                </Action>
              )}
            </li>
          ))}
        </ul>
      )}
    </ListState>
  );
}

function Profile({ t }) {
  const { user } = useSession();
  return (
    <div className="acc-legacy acc-narrow">
      <Form
        initial={user}
        fields={[
          {
            name: "full_name",
            label: translate("Full name"),
            required: true,
            maxLength: 200,
          },
          {
            name: "phone",
            label: translate("Phone"),
            nullable: true,
          },
          {
            name: "locale",
            label: translate("Language"),
            required: true,
            options: [
              ["en", "English"],
              ["ru", "Русский"],
              ["kk", "Қазақша"],
            ],
          },
        ]}
        submit={(body) =>
          api("/me", {
            method: "PATCH",
            body,
          })
        }
        done={() => window.dispatchEvent(new Event("biletflow-session"))}
      />
      <div className="acc-links">
        <Link to="/forgot-password">{t.password}</Link>
        {!user.email_verified && <Link to="/verify-email">{t.verify}</Link>}
      </div>
    </div>
  );
}

function Overview({ lang, t }) {
  const orders = useResource("/orders", true);
  const tickets = useResource("/tickets", true);
  const upcoming = (tickets.data || [])
    .filter((x) => x.status === "valid" && isUpcoming(x))
    .sort(
      (a, b) => new Date(a.event?.starts_at) - new Date(b.event?.starts_at),
    );
  const stats = [
    [t.upcoming, tickets.data ? upcoming.length : "…", "/account/tickets"],
    [t.tickets, tickets.data?.length ?? "…", "/account/tickets"],
    [t.orders, orders.data?.length ?? "…", "/account/orders"],
  ];
  return (
    <>
      <div className="acc-stats">
        {stats.map(([label, value, to]) => (
          <a key={label} className="acc-stat" href={`/#${to}`}>
            <strong>{value}</strong>
            <span>{label}</span>
          </a>
        ))}
      </div>
      {(orders.error || tickets.error) && (
        <p role="alert" className="acc-alert">
          {errorText(orders.error || tickets.error)}
        </p>
      )}
      <section className="acc-section">
        <h2 className="acc-label">{t.nextUp}</h2>
        {tickets.loading ? (
          <div className="acc-skeleton" aria-busy="true" />
        ) : upcoming.length ? (
          <ul className="acc-tickets">
            {upcoming.slice(0, 3).map((ticket) => (
              <TicketCard key={ticket.id} ticket={ticket} lang={lang} t={t} />
            ))}
          </ul>
        ) : (
          <Empty
            title={t.noTickets}
            body={t.noTicketsBody}
            action={
              <Link className="acc-button" to="/events">
                {translate("Browse events")}
              </Link>
            }
          />
        )}
      </section>
    </>
  );
}

export default function AttendeeApp({ path }) {
  const lang = useLocale();
  const t = text[lang];
  const { user } = useSession();
  const section = path.split("/")[2] || "";
  const id = path.split("/")[3];
  const title =
    section === "" ? (
      <>
        {t.hi} <em>{user?.full_name?.split(" ")[0] || ""}</em>
      </>
    ) : (
      t.tabs[section] || t.tabs[""]
    );
  return (
    <>
      <Topbar contained />
      <main className="acc page-width">
        <header className="acc-head">
          <p className="acc-kicker">{t.account}</p>
          <h1>{title}</h1>
        </header>
        <nav className="acc-tabs" aria-label={t.account}>
          {Object.entries(t.tabs).map(([key, label]) => (
            <a
              key={key}
              href={`/#/account${key ? `/${key}` : ""}`}
              aria-current={section === key ? "page" : undefined}
            >
              {label}
            </a>
          ))}
        </nav>
        <div className="acc-content">
          {section === "orders" ? (
            id ? (
              <Order id={id} t={t} />
            ) : (
              <Orders lang={lang} t={t} />
            )
          ) : section === "tickets" ? (
            id ? (
              <Ticket id={id} lang={lang} t={t} />
            ) : (
              <Tickets lang={lang} t={t} />
            )
          ) : section === "notifications" ? (
            <Notifications lang={lang} t={t} />
          ) : section === "support" ? (
            <div className="acc-legacy">
              <SupportPanel />
            </div>
          ) : section === "settings" ? (
            <Profile t={t} />
          ) : (
            <Overview lang={lang} t={t} />
          )}
        </div>
      </main>
    </>
  );
}
