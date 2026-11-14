import CalendarLinks from "./CalendarLinks";
import SeatMap from "./SeatMap";
import { t as translate, dateTime, getLocale } from "../lib/locale";
import { useState } from "react";
import { api, apiPath, download, login, query } from "../lib/client";
import { useResource } from "../lib/use-resource";
import { useSession } from "../lib/session-context";
import { Topbar, Link, EventCard, LanguagePicker } from "./app-shared";
import { Form, State, Action, OrderSummary, SecureImage } from "./live-shared";
import { money } from "./app-data";
function AuthPage({ path, params }) {
  const next = params.get("next");
  const safeNext =
    next?.startsWith("/") && !next.startsWith("//") ? next : "/account";
  const [message, setMessage] = useState("");
  const loginPage = path === "/login";
  const register = path === "/register";
  const verify = path === "/verify-email";
  const reset = path === "/reset-password";
  const token = params.get("token") || "";
  const fields = verify
    ? token
      ? []
      : [
          {
            name: "token",
            label: translate("Verification token"),
            required: true,
          },
        ]
    : [
        ...(register
          ? [
              {
                name: "full_name",
                label: translate("Full name"),
                required: true,
                maxLength: 200,
              },
              {
                name: "locale",
                label: translate("Language"),
                options: [
                  ["en", "English"],
                  ["kk", "Қазақша"],
                  ["ru", "Русский"],
                ],
                default: "en",
                required: true,
              },
            ]
          : []),
        ...(!reset
          ? [
              {
                name: "email",
                label: translate("Email"),
                type: "email",
                required: true,
              },
            ]
          : []),
        ...(loginPage || register || reset
          ? [
              {
                name: reset ? "new_password" : "password",
                label: reset
                  ? translate("New password")
                  : translate("Password"),
                type: "password",
                autoComplete: loginPage ? "current-password" : "new-password",
                required: true,
                minLength: loginPage ? 1 : 8,
                maxLength: 128,
              },
            ]
          : []),
      ];
  const title = loginPage
    ? translate("Welcome back")
    : register
      ? translate("Create your account")
      : verify
        ? translate("Verify your email")
        : translate("Reset your password");
  return (
    <main className="bf-auth">
      <Link to="/events">BiletFlow</Link>
      <LanguagePicker />
      <div className="bf-auth-card">
        <h1>{title}</h1>
        {message && <p role="status">{translate(message)}</p>}
        <Form
          fields={fields}
          label={loginPage ? translate("Sign in") : title}
          submit={async (body) => {
            if (loginPage) {
              await login(body.email, body.password);
              location.hash = safeNext;
              return;
            }
            if (register) {
              await api("/auth/register", {
                method: "POST",
                auth: false,
                body,
              });
              setMessage(
                "Account created. Check your email for the verification link, then sign in.",
              );
              return;
            }
            if (verify) {
              await api("/auth/verify-email", {
                method: "POST",
                auth: false,
                body: {
                  token: token || body.token,
                },
              });
              window.dispatchEvent(new Event("biletflow-session"));
              setMessage("Email verified. You can now book tickets.");
              return;
            }
            if (reset) {
              await api("/auth/password/reset", {
                method: "POST",
                auth: false,
                body: {
                  ...body,
                  token,
                },
              });
              history.replaceState(null, "", "/#/login");
              window.dispatchEvent(new Event("hashchange"));
              return;
            }
            await api("/auth/password/forgot", {
              method: "POST",
              auth: false,
              body,
            });
            setMessage("If an account exists, a reset link has been sent.");
          }}
        />
        {verify && (
          <Form
            fields={[
              {
                name: "email",
                label: translate("Email"),
                type: "email",
                required: true,
              },
            ]}
            label="Resend verification"
            submit={(body) =>
              api("/auth/verify-email/resend", {
                method: "POST",
                auth: false,
                body,
              })
            }
          />
        )}
        <div className="bf-bridge-links">
          <Link to="/login">{translate("Sign in")}</Link>
          <Link to="/register">{translate("Register")}</Link>
          <Link to="/forgot-password">{translate("Forgot password?")}</Link>
          <Link to="/verify-email">{translate("Verify email")}</Link>
        </div>
      </div>
    </main>
  );
}
function Events() {
  const [filters, setFilters] = useState({});
  const path = "/events?" + query(filters);
  const resource = useResource(path, true);
  const categories = useResource("/event-categories", true);
  return (
    <>
      <h1>{translate("Events for you")}</h1>
      <form
        className="bf-filter-row"
        onSubmit={(event) => {
          event.preventDefault();
          const values = Object.fromEntries(new FormData(event.currentTarget));
          for (const key of ["date_from", "date_to"])
            if (values[key]) values[key] = new Date(values[key]).toISOString();
          setFilters(values);
        }}
      >
        <input
          name="q"
          aria-label={translate("Search")}
          placeholder={translate("Search events")}
        />
        <input
          name="city"
          aria-label={translate("City")}
          placeholder={translate("City")}
        />
        <select name="category_id" aria-label={translate("Category")}>
          <option value="">{translate("All categories")}</option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c[`name_${getLocale()}`] || c.name_en}
            </option>
          ))}
        </select>
        <label>
          {translate("From")}
          <input name="date_from" type="datetime-local" />
        </label>
        <label>
          {translate("Until")}
          <input name="date_to" type="datetime-local" />
        </label>
        <button className="bf-button">{translate("Search")}</button>
      </form>
      <State resource={resource}>
        <div className="bf-event-grid">
          {resource.data?.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>
        {resource.data?.length === 0 && (
          <p>{translate("No upcoming events found.")}</p>
        )}
      </State>
    </>
  );
}
function EventDetail({ slug, id, promo }) {
  const resource = useResource(
    id ? `/events/${id}` : `/events/by-slug/${encodeURIComponent(slug)}`,
  );
  const event = resource.data;
  return (
    <State resource={resource}>
      {event && (
        <>
          <h1>{event.title}</h1>
          <p>{event.description}</p>
          <p>
            {dateTime(event.starts_at, {
              timeZone: event.timezone,
            })}{" "}
            · {event.timezone}
          </p>
          <EventImages id={event.id} />
          <TicketChoices event={event} promo={promo} />
          <CalendarLinks id={event.id} />
          <ReportEvent id={event.id} />
        </>
      )}
    </State>
  );
}
function EventImages({ id }) {
  const images = useResource(`/events/${id}/images`, true);
  return (
    <div className="bf-event-grid">
      {images.data?.map((image) => (
        <SecureImage
          key={image.id}
          path={apiPath(image.url)}
          alt={image.alt_text || translate("Event image")}
        />
      ))}
    </div>
  );
}
function TicketChoices({ event, promo }) {
  const tickets = useResource(`/events/${event.id}/ticket-types`, true);
  return (
    <State resource={tickets}>
      <div className="bf-panel">
        <h2>{translate("Ticket types")}</h2>
        {tickets.data
          ?.filter((t) => !t.is_hidden)
          .map((t) => (
            <div className="bf-ticket-type" key={t.id}>
              <span>
                {t.name} · {money(t.price_amount)} ·{" "}
                {Math.max(
                  0,
                  t.quantity_total - t.quantity_sold - t.quantity_reserved,
                )}{" "}
                {translate("available")}
              </span>
              {event.status === "published" ? (
                <Link
                  className="bf-button"
                  to={`/checkout/${event.id}?ticket=${t.id}&promo=${encodeURIComponent(promo || "")}`}
                >
                  {translate("Choose tickets")}
                </Link>
              ) : (
                <span>
                  {translate("Preview only \u2014 registration is not open.")}
                </span>
              )}
            </div>
          ))}
      </div>
    </State>
  );
}
function Campaign({ token }) {
  const resource = useResource(`/campaign-links/${encodeURIComponent(token)}`);
  return (
    <State resource={resource}>
      {resource.data && (
        <>
          <p role="status">
            {translate("Promotion applied: ")}
            {resource.data.promo_code}
          </p>
          <EventDetail
            slug={resource.data.event_slug}
            promo={resource.data.promo_code}
          />
        </>
      )}
    </State>
  );
}
function Checkout({ id, params }) {
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
  if (order)
    return (
      <>
        <h1>
          {translate("Order ")}
          {order.order_number}
        </h1>
        <OrderSummary order={order} />
        {order.status === "completed" && order.event_id && (
          <CalendarLinks id={order.event_id} />
        )}
        {["pending", "awaiting_payment"].includes(order.status) && (
          <Payment order={order} done={setOrder} />
        )}
      </>
    );
  return (
    <>
      <h1>{translate("Checkout")}</h1>
      <p>
        {translate(
          "Payments are simulated. No real money moves. The final total includes any processing fee calculated by the server.",
        )}
      </p>
      {!user.email_verified && (
        <p role="alert">
          {translate("Verify your email before booking.")}{" "}
          <Link to="/verify-email">{translate("Verify email")}</Link>
        </p>
      )}
      <State resource={tickets}>
        <div className="bf-panel bf-form">
          <label>
            {translate("Ticket type")}
            <select
              value={cart.ticket_type_id}
              onChange={(e) => {
                setCart({
                  ...cart,
                  ticket_type_id: e.target.value,
                });
                setSelectedSeats([]);
                setPreview(null);
              }}
            >
              <option value="">{translate("Choose\u2026")}</option>
              {tickets.data
                ?.filter((t) => !t.is_hidden)
                .map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} · {money(t.price_amount)}
                  </option>
                ))}
            </select>
          </label>
          <label>
            {translate("Quantity")}
            <input
              type="number"
              min="1"
              max="1000"
              disabled={assigned}
              value={assigned ? owned.length : cart.quantity}
              onChange={(e) => {
                setCart({
                  ...cart,
                  quantity: e.target.value,
                });
                setPreview(null);
              }}
            />
          </label>
          <label>
            {translate("Promo code")}
            <input
              value={cart.code}
              onChange={(e) => {
                setCart({
                  ...cart,
                  code: e.target.value,
                });
                setPreview(null);
              }}
            />
          </label>
          <Action
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
            {translate("Check discount")}
          </Action>
          {preview && (
            <p role="status">
              {translate("Discount")}
              {money(preview.discount_amount)}
              {translate(" \xB7 Before fees")} {money(preview.total_amount)}
            </p>
          )}
        </div>
        {assigned && (
          <div className="bf-panel">
            <h2>{translate("Select your seats")}</h2>
            <State resource={seats}>
              <SeatMap
                seats={seats.data || []}
                selected={selectedSeats}
                setSelected={setSelectedSeats}
                ticketTypeId={cart.ticket_type_id}
              />
              <p role="status">
                {translate("Selected total")}:{" "}
                {money(
                  (seats.data || [])
                    .filter((s) => selectedSeats.includes(s.id))
                    .reduce((sum, s) => sum + (s.price_amount || 0), 0),
                )}
              </p>
            </State>
            <Action
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
              {owned.map((hold) => (
                <div key={hold.id}>
                  {translate("Held until")}
                  {dateTime(hold.expires_at)}{" "}
                  <Action
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
                </div>
              ))}
            </State>
          </div>
        )}
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
      </State>
    </>
  );
}
export function Payment({ order, done }) {
  const [payment, setPayment] = useState(
    order.payments?.find((p) => p.status === "initiated") || null,
  );
  return (
    <div className="bf-panel">
      <h2>{translate("Simulated payment")}</h2>
      <p>
        {translate("Payable total:")}
        {money(order.total_amount)}
        {translate(". Reservation expires:")}{" "}
        {order.expires_at ? dateTime(order.expires_at) : "—"}
      </p>
      {!payment || payment.status === "failed" ? (
        <Action
          perform={async () =>
            setPayment(
              await api(`/orders/${order.id}/pay`, {
                method: "POST",
              }),
            )
          }
        >
          {translate("Start payment")}
        </Action>
      ) : (
        ["success", "failure"].map((outcome) => (
          <Action
            key={outcome}
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
  );
}
export default function PublicPages({ route, path }) {
  const params = new URLSearchParams(route.split("?")[1] || "");
  if (
    [
      "/login",
      "/register",
      "/forgot-password",
      "/reset-password",
      "/verify-email",
    ].includes(path)
  )
    return <AuthPage path={path} params={params} />;
  const campaign = params.get("c");
  return (
    <>
      <Topbar />
      <main className="bf-public">
        {path.startsWith("/checkout/") ? (
          <Checkout id={path.split("/")[2]} params={params} />
        ) : campaign ? (
          <Campaign token={campaign} />
        ) : path.startsWith("/preview/") ? (
          <EventDetail id={path.split("/")[2]} />
        ) : path.startsWith("/events/") || path.startsWith("/e/") ? (
          <EventDetail
            slug={decodeURIComponent(path.split("/")[2])}
            promo={params.get("promo")}
          />
        ) : (
          <Events />
        )}
      </main>
    </>
  );
}
function ReportEvent({ id }) {
  const { user } = useSession();
  return user ? (
    <details className="bf-panel">
      <summary>{translate("Report this event")}</summary>
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
  ) : null;
}
