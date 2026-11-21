import { useState } from "react";
import CalendarLinks from "../CalendarLinks";
import SeatMap from "../SeatMap";
import Arrow from "../../components/Icons/Arrow";
import { api } from "../../lib/client";
import { t as translate, dateTime, useLocale } from "../../lib/locale";
import { useResource } from "../../lib/use-resource";
import { useSession } from "../../lib/session-context";
import { Link } from "../app-shared";
import { Form, State, Action, OrderSummary } from "../live-shared";
import "./Checkout.css";

// Checkout (#/checkout/{eventId}): dark DICE style. Left: tickets, seats,
// attendee form. Right: sticky order summary. Request bodies are unchanged.
const locales = { en: "en-GB", ru: "ru-RU", kk: "kk-KZ" };
const text = {
  en: {
    home: "Home",
    checkout: "Checkout",
    demo: "Demo payment: no real money moves.",
    step1: "Tickets",
    step2: "Seats",
    step3: "Your details",
    less: "Fewer tickets",
    more: "More tickets",
    apply: "Apply",
    summary: "Your order",
    subtotal: "Subtotal",
    discount: "Discount",
    total: "Total before fees",
    fees: "Any processing fee is added by the server on the next step.",
    pick: "Pick a ticket type to see the total.",
    left: (n) => `${n} left`,
    soldOut: "Sold out",
    free: "Free",
    seatsHint: "Pick seats on the map, then hold them for your order.",
    held: "Held seats",
    payTitle: "Demo payment",
    payBody:
      "This is a simulated payment. Choose how it ends to test both paths.",
    expires: "Reservation expires",
    payable: "To pay",
  },
  ru: {
    home: "Главная",
    checkout: "Оформление",
    demo: "Демонстрационный платёж: реальные деньги не списываются.",
    step1: "Билеты",
    step2: "Места",
    step3: "Ваши данные",
    less: "Меньше билетов",
    more: "Больше билетов",
    apply: "Применить",
    summary: "Ваш заказ",
    subtotal: "Сумма",
    discount: "Скидка",
    total: "Итого без сборов",
    fees: "Сервисный сбор, если он есть, сервер добавит на следующем шаге.",
    pick: "Выберите тип билета, чтобы увидеть сумму.",
    left: (n) => `Осталось ${n}`,
    soldOut: "Распродано",
    free: "Бесплатно",
    seatsHint: "Выберите места на схеме и забронируйте их для заказа.",
    held: "Забронированные места",
    payTitle: "Демонстрационный платёж",
    payBody:
      "Это имитация оплаты. Выберите результат, чтобы проверить оба сценария.",
    expires: "Бронь до",
    payable: "К оплате",
  },
  kk: {
    home: "Басты бет",
    checkout: "Рәсімдеу",
    demo: "Демо төлем: нақты ақша есептен шығарылмайды.",
    step1: "Билеттер",
    step2: "Орындар",
    step3: "Сіздің деректеріңіз",
    less: "Азырақ билет",
    more: "Көбірек билет",
    apply: "Қолдану",
    summary: "Тапсырысыңыз",
    subtotal: "Сомасы",
    discount: "Жеңілдік",
    total: "Алымсыз жиыны",
    fees: "Қызмет алымы болса, сервер келесі қадамда қосады.",
    pick: "Соманы көру үшін билет түрін таңдаңыз.",
    left: (n) => `${n} қалды`,
    soldOut: "Сатылып кетті",
    free: "Тегін",
    seatsHint: "Схемадан орын таңдап, тапсырысқа брондаңыз.",
    held: "Брондалған орындар",
    payTitle: "Демо төлем",
    payBody: "Бұл төлем имитациясы. Екі нәтижені де тексеріп көріңіз.",
    expires: "Бронь мерзімі",
    payable: "Төлеуге",
  },
};
const tenge = (amount, lang) =>
  `${new Intl.NumberFormat(locales[lang]).format(amount || 0)} ₸`;

export function Checkout({ id, params }) {
  const lang = useLocale();
  const t = text[lang];
  const tickets = useResource(`/events/${id}/ticket-types`, true);
  const event = useResource(`/events/${id}`);
  const assigned = event.data?.seating_mode === "assigned";
  const holds = useResource(
    assigned ? `/events/${id}/seat-holds` : null,
    true,
    10000,
  );
  const seats = useResource(
    assigned ? `/events/${id}/seats` : null,
    true,
    10000,
  );
  const [selectedSeats, setSelectedSeats] = useState([]);
  const [cart, setCart] = useState({
    ticket_type_id: params.get("ticket") || "",
    quantity: 1,
    code: params.get("promo") || "",
  });
  const [preview, setPreview] = useState(null);
  const [order, setOrder] = useState(null);
  const { user } = useSession();
  const fields = [
    {
      name: "full_name",
      label: translate("Attendee name"),
      default: user.full_name,
      required: true,
    },
    {
      name: "email",
      label: translate("Attendee email"),
      type: "email",
      default: user.email,
      required: true,
    },
  ];
  const owned = (holds.data || []).filter(
    (hold) => hold.ticket_type_id === cart.ticket_type_id,
  );
  const items = [
    {
      ticket_type_id: cart.ticket_type_id,
      quantity: assigned ? owned.length : Number(cart.quantity),
      ...(assigned
        ? {
            seat_hold_ids: owned.map((hold) => hold.id),
          }
        : {}),
    },
  ];
  const types = (tickets.data || []).filter((x) => !x.is_hidden);
  const chosen = types.find((x) => x.id === cart.ticket_type_id);
  const quantity = items[0].quantity || 0;
  const subtotal = chosen ? chosen.price_amount * quantity : 0;
  const setQuantity = (value) => {
    const max = chosen?.max_per_order || 1000;
    const min = chosen?.min_per_order || 1;
    setCart({ ...cart, quantity: Math.min(max, Math.max(min, value)) });
    setPreview(null);
  };
  const e = event.data;

  if (order)
    return (
      <div className="co">
        <h1 className="co-title">
          {translate("Order ")}
          {order.order_number}
        </h1>
        <div className="co-legacy">
          <OrderSummary order={order} />
          {order.status === "completed" && order.event_id && (
            <CalendarLinks id={order.event_id} />
          )}
          {["pending", "awaiting_payment"].includes(order.status) && (
            <Payment order={order} done={setOrder} />
          )}
        </div>
      </div>
    );

  return (
    <div className="co">
      <nav className="crumbs" aria-label="Breadcrumb">
        <a href="/">{t.home}</a>
        {e && (
          <>
            <span aria-hidden="true">/</span>
            <a href={`/#/events/${e.slug}`}>{e.title}</a>
          </>
        )}
        <span aria-hidden="true">/</span>
        <span aria-current="page">{t.checkout}</span>
      </nav>
      <h1 className="co-title">{translate("Checkout")}</h1>
      <p className="co-demo">{t.demo}</p>
      {!user.email_verified && (
        <p role="alert" className="co-alert">
          {translate("Verify your email before booking.")}{" "}
          <Link to="/verify-email">{translate("Verify email")}</Link>
        </p>
      )}

      <div className="co-grid">
        <div className="co-steps">
          <State resource={tickets}>
            <section className="co-step" aria-labelledby="co-step-1">
              <h2 id="co-step-1">
                <span aria-hidden="true">01</span> {t.step1}
              </h2>
              <fieldset className="co-types">
                <legend className="visually-hidden">
                  {translate("Ticket type")}
                </legend>
                {types.map((type) => {
                  const left = Math.max(
                    0,
                    (type.quantity_total ?? Infinity) -
                      (type.quantity_sold || 0) -
                      (type.quantity_reserved || 0),
                  );
                  return (
                    <label
                      key={type.id}
                      className={`co-type${type.id === cart.ticket_type_id ? " is-on" : ""}${left === 0 ? " is-off" : ""}`}
                    >
                      <input
                        type="radio"
                        name="ticket_type"
                        value={type.id}
                        checked={type.id === cart.ticket_type_id}
                        disabled={left === 0}
                        onChange={() => {
                          setCart({
                            ...cart,
                            ticket_type_id: type.id,
                            quantity: type.min_per_order || 1,
                          });
                          setSelectedSeats([]);
                          setPreview(null);
                        }}
                      />
                      <span className="co-type-name">
                        <strong>{type.name}</strong>
                        {type.description && <small>{type.description}</small>}
                        {Number.isFinite(left) && left <= 20 && (
                          <small className="co-type-left">
                            {left === 0 ? t.soldOut : t.left(left)}
                          </small>
                        )}
                      </span>
                      <span className="co-type-price">
                        {type.price_amount === 0
                          ? t.free
                          : tenge(type.price_amount, lang)}
                      </span>
                    </label>
                  );
                })}
              </fieldset>

              {!assigned && (
                <div className="co-qty">
                  <label htmlFor="co-qty">{translate("Quantity")}</label>
                  <div className="co-stepper">
                    <button
                      type="button"
                      aria-label={t.less}
                      disabled={
                        !chosen || quantity <= (chosen.min_per_order || 1)
                      }
                      onClick={() => setQuantity(quantity - 1)}
                    >
                      −
                    </button>
                    <input
                      id="co-qty"
                      type="number"
                      min={chosen?.min_per_order || 1}
                      max={chosen?.max_per_order || 1000}
                      value={cart.quantity}
                      onChange={(ev) => {
                        setCart({ ...cart, quantity: ev.target.value });
                        setPreview(null);
                      }}
                    />
                    <button
                      type="button"
                      aria-label={t.more}
                      disabled={
                        !chosen || quantity >= (chosen.max_per_order || 1000)
                      }
                      onClick={() => setQuantity(quantity + 1)}
                    >
                      +
                    </button>
                  </div>
                </div>
              )}

              <div className="co-promo">
                <label htmlFor="co-promo">{translate("Promo code")}</label>
                <div>
                  <input
                    id="co-promo"
                    value={cart.code}
                    autoComplete="off"
                    onChange={(ev) => {
                      setCart({ ...cart, code: ev.target.value });
                      setPreview(null);
                    }}
                  />
                  <Action
                    className="co-button co-button-ghost"
                    perform={async () =>
                      setPreview(
                        await api(`/events/${id}/promo/validate`, {
                          method: "POST",
                          auth: false,
                          body: {
                            code: cart.code,
                            items,
                          },
                        }),
                      )
                    }
                  >
                    {t.apply}
                  </Action>
                </div>
              </div>
            </section>

            {assigned && (
              <section className="co-step" aria-labelledby="co-step-2">
                <h2 id="co-step-2">
                  <span aria-hidden="true">02</span> {t.step2}
                </h2>
                <p className="co-muted">{t.seatsHint}</p>
                <div className="co-legacy">
                  <h3 className="visually-hidden">
                    {translate("Select your seats")}
                  </h3>
                  <State resource={seats}>
                    <SeatMap
                      seats={seats.data || []}
                      selected={selectedSeats}
                      setSelected={setSelectedSeats}
                      ticketTypeId={cart.ticket_type_id}
                    />
                    <p role="status" className="co-muted">
                      {translate("Selected total")}:{" "}
                      {tenge(
                        (seats.data || [])
                          .filter((s) => selectedSeats.includes(s.id))
                          .reduce((sum, s) => sum + (s.price_amount || 0), 0),
                        lang,
                      )}
                    </p>
                  </State>
                  <Action
                    className="co-button"
                    perform={() =>
                      api(`/events/${id}/seat-holds`, {
                        method: "POST",
                        body: {
                          ticket_type_id: cart.ticket_type_id,
                          seat_ids: selectedSeats,
                        },
                      })
                    }
                    done={() => {
                      holds.reload();
                      seats.reload();
                      setSelectedSeats([]);
                    }}
                  >
                    {translate("Hold selected seats")}
                  </Action>
                  <State resource={holds}>
                    {owned.length > 0 && (
                      <ul className="co-holds" aria-label={t.held}>
                        {owned.map((hold) => (
                          <li key={hold.id}>
                            <span>
                              {translate("Held until")}{" "}
                              {dateTime(hold.expires_at)}
                            </span>
                            <Action
                              className="co-button co-button-ghost"
                              perform={() =>
                                api(`/events/${id}/seat-holds/${hold.id}`, {
                                  method: "DELETE",
                                })
                              }
                              done={() => {
                                holds.reload();
                                seats.reload();
                              }}
                            >
                              {translate("Release")}
                            </Action>
                          </li>
                        ))}
                      </ul>
                    )}
                  </State>
                </div>
              </section>
            )}

            <section className="co-step" aria-labelledby="co-step-3">
              <h2 id="co-step-3">
                <span aria-hidden="true">{assigned ? "03" : "02"}</span>{" "}
                {t.step3}
              </h2>
              <div className="co-legacy co-form">
                <Form
                  fields={fields}
                  label="Reserve tickets"
                  submit={(body) =>
                    api(`/events/${id}/orders`, {
                      method: "POST",
                      body: {
                        items: items.map((item) => ({
                          ...item,
                          attendees: Array.from(
                            {
                              length: item.quantity,
                            },
                            () => body,
                          ),
                        })),
                        ...(cart.code
                          ? {
                              promo_code: cart.code,
                            }
                          : {}),
                      },
                    })
                  }
                  done={(result) => {
                    location.hash = `/account/orders/${result.id}`;
                  }}
                />
              </div>
            </section>
          </State>
        </div>

        <aside className="co-summary" aria-labelledby="co-summary">
          <h2 id="co-summary">{t.summary}</h2>
          {e && (
            <div className="co-event">
              <strong>{e.title}</strong>
              <span>{dateTime(e.starts_at, { timeZone: e.timezone })}</span>
            </div>
          )}
          {chosen ? (
            <dl>
              <div>
                <dt>
                  {chosen.name} × {quantity}
                </dt>
                <dd>{tenge(subtotal, lang)}</dd>
              </div>
              {preview && (
                <div className="co-discount">
                  <dt>
                    {t.discount}
                    {cart.code ? ` · ${cart.code}` : ""}
                  </dt>
                  <dd>−{tenge(preview.discount_amount, lang)}</dd>
                </div>
              )}
              <div className="co-total">
                <dt>{t.total}</dt>
                <dd>
                  {tenge(preview ? preview.total_amount : subtotal, lang)}
                </dd>
              </div>
            </dl>
          ) : (
            <p className="co-muted">{t.pick}</p>
          )}
          <p className="co-muted co-fees">{t.fees}</p>
        </aside>
      </div>
    </div>
  );
}

// Simulated payment block, used here and on the account order page.
export function Payment({ order, done }) {
  const lang = useLocale();
  const t = text[lang];
  const [payment, setPayment] = useState(
    order.payments?.find((p) => p.status === "initiated") || null,
  );
  return (
    <section className="co-pay" aria-labelledby={`co-pay-${order.id}`}>
      <span className="co-pay-tag">{t.demo}</span>
      <h2 id={`co-pay-${order.id}`}>{t.payTitle}</h2>
      <p className="co-muted">{t.payBody}</p>
      <dl>
        <div>
          <dt>{t.payable}</dt>
          <dd className="co-pay-total">{tenge(order.total_amount, lang)}</dd>
        </div>
        <div>
          <dt>{t.expires}</dt>
          <dd>{order.expires_at ? dateTime(order.expires_at) : "—"}</dd>
        </div>
      </dl>
      <div className="co-pay-actions">
        {!payment || payment.status === "failed" ? (
          <Action
            className="co-button"
            perform={async () =>
              setPayment(
                await api(`/orders/${order.id}/pay`, {
                  method: "POST",
                }),
              )
            }
          >
            {translate("Start payment")}
            <Arrow size={15} />
          </Action>
        ) : (
          ["success", "failure"].map((outcome) => (
            <Action
              key={outcome}
              className={`co-button${outcome === "failure" ? " co-button-ghost" : ""}`}
              perform={async () => {
                const result = await api(`/payments/${payment.id}/simulate`, {
                  method: "POST",
                  body: {
                    outcome,
                  },
                });
                setPayment(result);
                done(await api(`/orders/${order.id}`));
              }}
            >
              {translate("Simulate")} {translate(outcome)}
            </Action>
          ))
        )}
      </div>
    </section>
  );
}
