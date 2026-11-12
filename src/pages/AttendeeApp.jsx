import { useSession } from "../lib/session-context";
import { api, apiPath, download } from "../lib/client";
import { useResource } from "../lib/use-resource";
import { Shell, Link, Stat } from "./app-shared";
import {
  State,
  RemoteTable,
  Form,
  Action,
  SecureImage,
  OrderSummary,
  Details,
} from "./live-shared";
import SupportPanel from "./SupportPanel";
import { Payment } from "./PublicPages";
const orderColumns = [
  ["order_number", "Order"],
  ["status", "Status"],
  ["total_amount", "Total (KZT)"],
  ["created_at", "Created"],
];
function Order({ id }) {
  const resource = useResource(`/orders/${id}`);
  return (
    <State resource={resource}>
      {resource.data && (
        <>
          <OrderSummary order={resource.data} />
          {["pending", "awaiting_payment"].includes(resource.data.status) && (
            <Payment
              key={resource.data.updated_at}
              order={resource.data}
              done={resource.reload}
            />
          )}
        </>
      )}
    </State>
  );
}
function Ticket({ id }) {
  const resource = useResource(`/tickets/${id}`);
  return (
    <State resource={resource}>
      {resource.data && (
        <>
          <h2>{resource.data.event.title}</h2>
          <Details
            value={resource.data}
            fields={[
              ["ticket_code", "Ticket code"],
              ["attendee_name", "Attendee"],
              ["ticket_type_name", "Ticket type"],
              ["status", "Status"],
              ["seat_section_label", "Section"],
              ["seat_row_label", "Row"],
              ["seat_number_label", "Seat"],
            ]}
          />
          <SecureImage
            path={apiPath(resource.data.qr_image_url)}
            alt="Ticket admission QR"
          />
          <Action
            perform={() =>
              download(
                apiPath(resource.data.pdf_url),
                `${resource.data.ticket_code}.pdf`,
              )
            }
          >
            Download A4 ticket
          </Action>
        </>
      )}
    </State>
  );
}
function Profile() {
  const { user } = useSession();
  return (
    <>
      <Form
        initial={user}
        fields={[
          {
            name: "full_name",
            label: "Full name",
            required: true,
            maxLength: 200,
          },
          { name: "phone", label: "Phone", nullable: true },
          {
            name: "locale",
            label: "Language",
            required: true,
            options: [
              ["en", "English"],
              ["ru", "Русский"],
              ["kk", "Қазақша"],
            ],
          },
        ]}
        submit={(body) => api("/me", { method: "PATCH", body })}
        done={() => window.dispatchEvent(new Event("biletflow-session"))}
      />
      <Link to="/forgot-password">Change password</Link>
      {!user.email_verified && (
        <Link to="/verify-email">Verify email to book tickets</Link>
      )}
    </>
  );
}
function Overview() {
  const orders = useResource("/orders", true);
  const tickets = useResource("/tickets", true);
  const { user } = useSession();
  return (
    <>
      <h2>Welcome, {user.full_name}</h2>
      <div className="bf-stats">
        <Stat label="Orders" value={orders.data?.length ?? "…"} />
        <Stat label="Tickets" value={tickets.data?.length ?? "…"} />
      </div>
      <State resource={orders} />
      <State resource={tickets} />
      <Link className="bf-button" to="/events">
        Browse events
      </Link>
    </>
  );
}
export default function AttendeeApp({ path }) {
  const section = path.split("/")[2] || "";
  const id = path.split("/")[3];
  return (
    <Shell
      path={path}
      title={
        {
          tickets: "My tickets",
          orders: "My orders",
          support: "Support",
          settings: "Profile settings",
          notifications: "Notifications",
        }[section] || "Your account"
      }
    >
      {section === "orders" ? (
        id ? (
          <Order id={id} />
        ) : (
          <RemoteTable
            path="/orders"
            columns={orderColumns}
            actions={(row) => (
              <Link to={`/account/orders/${row.id}`}>View order</Link>
            )}
          />
        )
      ) : section === "tickets" ? (
        id ? (
          <Ticket id={id} />
        ) : (
          <RemoteTable
            path="/tickets"
            columns={[
              ["ticket_code", "Ticket"],
              ["attendee_name", "Attendee"],
              ["ticket_type_name", "Type"],
              ["status", "Status"],
            ]}
            actions={(row) => (
              <Link to={`/account/tickets/${row.id}`}>View ticket</Link>
            )}
          />
        )
      ) : section === "notifications" ? (
        <RemoteTable
          poll={15000}
          path="/notifications"
          columns={[
            ["title", "Notification"],
            ["body", "Message"],
            ["read_at", "Read"],
          ]}
          actions={(row, reload) =>
            !row.read_at && (
              <Action
                perform={() =>
                  api(`/notifications/${row.id}/read`, { method: "POST" })
                }
                done={reload}
              >
                Mark read
              </Action>
            )
          }
        />
      ) : section === "support" ? (
        <SupportPanel />
      ) : section === "settings" ? (
        <Profile />
      ) : (
        <Overview />
      )}
    </Shell>
  );
}
