import { t as translate } from "../lib/locale";
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
              ["ticket_code", translate("Ticket code")],
              ["attendee_name", translate("Attendee")],
              ["ticket_type_name", translate("Ticket type")],
              ["status", translate("Status")],
              ["seat_section_label", translate("Section")],
              ["seat_row_label", translate("Row")],
              ["seat_number_label", translate("Seat")],
            ]}
          />
          <SecureImage
            path={apiPath(resource.data.qr_image_url)}
            alt={translate("Ticket admission QR")}
          />
          <Action
            perform={() =>
              download(
                apiPath(resource.data.pdf_url),
                `${resource.data.ticket_code}.pdf`,
              )
            }
          >
            {translate("Download A4 ticket")}
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
      <Link to="/forgot-password">{translate("Change password")}</Link>
      {!user.email_verified && (
        <Link to="/verify-email">
          {translate("Verify email to book tickets")}
        </Link>
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
      <h2>
        {translate("Welcome, ")}
        {user.full_name}
      </h2>
      <div className="bf-stats">
        <Stat label="Orders" value={orders.data?.length ?? "…"} />
        <Stat label="Tickets" value={tickets.data?.length ?? "…"} />
      </div>
      <State resource={orders} />
      <State resource={tickets} />
      <Link className="bf-button" to="/events">
        {translate("Browse events")}
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
          tickets: translate("My tickets"),
          orders: translate("My orders"),
          support: translate("Support"),
          settings: translate("Profile settings"),
          notifications: translate("Notifications"),
        }[section] || translate("Your account")
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
              <Link to={`/account/orders/${row.id}`}>
                {translate("View order")}
              </Link>
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
              ["ticket_code", translate("Ticket")],
              ["attendee_name", translate("Attendee")],
              ["ticket_type_name", translate("Type")],
              ["status", translate("Status")],
            ]}
            actions={(row) => (
              <Link to={`/account/tickets/${row.id}`}>
                {translate("View ticket")}
              </Link>
            )}
          />
        )
      ) : section === "notifications" ? (
        <RemoteTable
          poll={15000}
          path="/notifications"
          columns={[
            ["title", translate("Notification")],
            ["body", translate("Message")],
            ["read_at", translate("Read")],
          ]}
          actions={(row, reload) =>
            !row.read_at && (
              <Action
                perform={() =>
                  api(`/notifications/${row.id}/read`, {
                    method: "POST",
                  })
                }
                done={reload}
              >
                {translate("Mark read")}
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
