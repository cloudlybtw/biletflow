import { useState } from "react";
import { api, apiPath, download, query } from "../lib/client";
import { useResource } from "../lib/use-resource";
import { Shell, Link, Stat } from "./app-shared";
import {
  Form,
  State,
  Action,
  DataTable,
  RemoteTable,
  Details,
  Export,
  SecureImage,
  OrderSummary,
} from "./live-shared";
import SupportPanel from "./SupportPanel";

const ticketFields = [
  { name: "name", label: "Ticket name", required: true },
  {
    name: "description",
    label: "Description",
    type: "textarea",
    nullable: true,
  },
  {
    name: "price_amount",
    label: "Price (whole KZT)",
    type: "integer",
    min: 0,
    default: 0,
    required: true,
  },
  {
    name: "quantity_total",
    label: "Capacity",
    type: "integer",
    min: 0,
    required: true,
  },
  {
    name: "min_per_order",
    label: "Minimum per order",
    type: "integer",
    min: 1,
    default: 1,
    required: true,
  },
  {
    name: "max_per_order",
    label: "Maximum per order",
    type: "integer",
    min: 1,
    default: 10,
    required: true,
  },
  {
    name: "sales_start_at",
    label: "Sales start (local time)",
    type: "datetime-local",
    nullable: true,
  },
  {
    name: "sales_end_at",
    label: "Sales end (local time)",
    type: "datetime-local",
    nullable: true,
  },
  { name: "is_hidden", label: "Hide ticket type", type: "checkbox" },
];
function EventForm({ event, done }) {
  const venues = useResource("/venues", true),
    categories = useResource("/event-categories", true);
  return (
    <Form
      key={event?.updated_at || "new"}
      initial={event}
      fields={[
        { name: "title", label: "Event title", required: true, maxLength: 200 },
        {
          name: "description",
          label: "Description",
          type: "textarea",
          nullable: true,
        },
        {
          name: "starts_at",
          label: "Starts (local time)",
          type: "datetime-local",
          required: true,
        },
        {
          name: "ends_at",
          label: "Ends (local time)",
          type: "datetime-local",
          required: true,
        },
        {
          name: "seating_mode",
          label: "Seating",
          default: "general_admission",
          required: true,
          options: [
            ["general_admission", "General admission"],
            ["assigned", "Assigned seats (venue required)"],
          ],
        },
        {
          name: "timezone",
          label: "Event timezone",
          default: "Asia/Almaty",
          required: true,
        },
        {
          name: "venue_id",
          label: "Venue",
          nullable: true,
          options: (venues.data || []).map((v) => [
            v.id,
            `${v.name}, ${v.city}`,
          ]),
        },
        {
          name: "category_id",
          label: "Category",
          nullable: true,
          options: (categories.data || []).map((c) => [c.id, c.name_en]),
        },
        {
          name: "visibility",
          label: "Visibility",
          default: "public",
          required: true,
          options: ["public", "unlisted", "private"].map((v) => [v, v]),
        },
        {
          name: "capacity",
          label: "Event capacity (optional)",
          type: "integer",
          min: 1,
          nullable: true,
        },
        {
          name: "registration_opens_at",
          label: "Registration opens (local time)",
          type: "datetime-local",
          nullable: true,
        },
        {
          name: "registration_closes_at",
          label: "Registration closes (local time)",
          type: "datetime-local",
          nullable: true,
        },
        {
          name: "refund_policy",
          label: "Refund policy",
          type: "textarea",
          nullable: true,
        },
      ]}
      label={event ? "Save event" : "Create draft"}
      submit={(body) =>
        api(event ? `/events/${event.id}` : "/events", {
          method: event ? "PATCH" : "POST",
          body,
        })
      }
      done={done}
    />
  );
}
function TicketTypes({ base }) {
  const resource = useResource(`${base}/ticket-types`, true);
  const [edit, setEdit] = useState(null);
  return (
    <>
      <State resource={resource}>
        <DataTable
          rows={resource.data || []}
          columns={[
            ["name", "Ticket"],
            ["price_amount", "Price (KZT)"],
            ["quantity_total", "Capacity"],
            ["quantity_sold", "Sold"],
            ["quantity_reserved", "Reserved"],
            ["is_hidden", "Hidden"],
          ]}
          actions={(row) => (
            <button className="bf-outline-button" onClick={() => setEdit(row)}>
              Edit
            </button>
          )}
        />
      </State>
      <SeatConfiguration base={base} tickets={resource.data || []} />
      <h2>Inventory by ticket type</h2>
      <RemoteTable
        path={`${base}/inventory`}
        columns={[
          ["name", "Ticket type"],
          ["available", "Available"],
          ["reserved", "Reserved"],
          ["sold", "Sold"],
          ["refunded", "Refunded"],
          ["cancelled", "Cancelled"],
          ["checked_in", "Checked in"],
        ]}
      />
      <h2>{edit ? "Edit ticket type" : "Add ticket type"}</h2>
      <Form
        key={edit?.id || "new"}
        fields={ticketFields}
        initial={edit || {}}
        submit={(body) =>
          api(
            edit ? `${base}/ticket-types/${edit.id}` : `${base}/ticket-types`,
            { method: edit ? "PATCH" : "POST", body },
          )
        }
        done={() => {
          setEdit(null);
          resource.reload();
        }}
      />
      {edit && <button onClick={() => setEdit(null)}>Cancel edit</button>}
    </>
  );
}
function Images({ base }) {
  const resource = useResource(`${base}/images`, true);
  return (
    <>
      <State resource={resource}>
        <div className="bf-event-grid">
          {resource.data?.map((image) => (
            <div className="bf-panel" key={image.id}>
              <SecureImage
                path={apiPath(image.url)}
                alt={image.alt_text || "Event image"}
              />
              <p>{image.is_cover ? "Cover image" : ""}</p>
              <Action
                perform={() =>
                  api(`${base}/images/${image.id}`, {
                    method: "PATCH",
                    body: { is_cover: true },
                  })
                }
                done={resource.reload}
              >
                Set cover
              </Action>
              <Action
                confirm="Delete this image?"
                perform={() =>
                  api(`${base}/images/${image.id}`, { method: "DELETE" })
                }
                done={resource.reload}
              >
                Delete
              </Action>
            </div>
          ))}
        </div>
      </State>
      <Form
        fields={[
          { name: "alt_text", label: "Image description" },
          { name: "is_cover", label: "Use as cover", type: "checkbox" },
        ]}
        label="Upload image"
        submit={(body, form) => {
          const data = new FormData();
          data.append("file", form.elements.file.files[0]);
          data.append("is_cover", String(body.is_cover));
          data.append("alt_text", body.alt_text || "");
          return api(`${base}/images`, { method: "POST", body: data });
        }}
        done={resource.reload}
      >
        <label>
          Image file
          <input
            name="file"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            required
          />
        </label>
      </Form>
    </>
  );
}
function Staff({ base }) {
  const resource = useResource(`${base}/staff`, true);
  return (
    <>
      <State resource={resource}>
        <DataTable
          rows={resource.data || []}
          columns={[
            ["user_id", "Staff member"],
            ["role", "Role"],
            ["revoked_at", "Revoked"],
          ]}
          actions={(row) =>
            !row.revoked_at && (
              <Action
                confirm="Revoke this staff assignment?"
                perform={() =>
                  api(`${base}/staff/${row.id}`, { method: "DELETE" })
                }
                done={resource.reload}
              >
                Revoke
              </Action>
            )
          }
        />
      </State>
      <Form
        fields={[
          {
            name: "email",
            label: "Staff email",
            type: "email",
            required: true,
          },
          {
            name: "role",
            label: "Role",
            options: ["event_admin", "support_agent", "co_organizer"].map(
              (r) => [r, r.replaceAll("_", " ")],
            ),
            required: true,
          },
        ]}
        label="Assign staff"
        submit={(body) => api(`${base}/staff`, { method: "POST", body })}
        done={resource.reload}
      />
    </>
  );
}
function Activation({ base }) {
  const resource = useResource(`${base}/paid-sales/checklist`);
  const [payment, setPayment] = useState(null);
  return (
    <>
      <p>Identity checks, payouts, and activation payments are simulated.</p>
      <State resource={resource}>
        {resource.data && (
          <>
            <Details
              value={resource.data}
              fields={[
                ["has_paid_ticket_type", "Paid ticket type"],
                ["identity_verified", "Identity verified"],
                ["payout_account_active", "Active payout account"],
                ["terms_accepted", "Terms accepted"],
                ["fee_amount", "Activation fee (KZT)"],
                ["fee_paid", "Fee paid"],
                ["paid_sales_status", "Paid sales"],
              ]}
            />
            <Action
              perform={() =>
                api(`${base}/paid-sales/terms`, {
                  method: "POST",
                  body: { accepted: true },
                })
              }
              done={resource.reload}
            >
              Accept paid-sales terms
            </Action>
            <Action
              perform={async () =>
                setPayment(
                  await api(`${base}/paid-sales/pay`, { method: "POST" }),
                )
              }
            >
              Start activation payment
            </Action>
            {payment &&
              ["success", "failure"].map((outcome) => (
                <Action
                  key={outcome}
                  perform={() =>
                    api(`/payments/${payment.id}/simulate`, {
                      method: "POST",
                      body: { outcome },
                    })
                  }
                  done={resource.reload}
                >
                  Simulate {outcome}
                </Action>
              ))}
            <Action
              perform={() =>
                api(`${base}/paid-sales/activate`, { method: "POST", body: {} })
              }
              done={resource.reload}
            >
              Activate paid sales
            </Action>
            <p>
              <Link to="/organizer/settings">
                Manage identity and payout account
              </Link>
            </p>
          </>
        )}
      </State>
    </>
  );
}
function Campaigns({ base }) {
  const resource = useResource(`${base}/campaigns`, true),
    tickets = useResource(`${base}/ticket-types`, true);
  const [selected, setSelected] = useState(null);
  const fields = [
    { name: "name", label: "Campaign name", required: true },
    {
      name: "discount_type",
      label: "Discount type",
      required: true,
      options: [
        ["percent", "Percent"],
        ["fixed", "Fixed amount (KZT)"],
      ],
    },
    {
      name: "discount_value",
      label: "Discount value",
      type: "integer",
      min: 1,
      required: true,
    },
    {
      name: "starts_at",
      label: "Starts (local time)",
      type: "datetime-local",
      nullable: true,
    },
    {
      name: "ends_at",
      label: "Ends (local time)",
      type: "datetime-local",
      nullable: true,
    },
    {
      name: "max_redemptions",
      label: "Maximum redemptions",
      type: "integer",
      min: 1,
      nullable: true,
    },
    {
      name: "ticket_type_ids",
      label: "Eligible ticket types (none means all)",
      multiple: true,
      options: (tickets.data || []).map((t) => [t.id, t.name]),
    },
    ...(!selected
      ? [{ name: "code", label: "Custom promo code (optional)" }]
      : []),
  ];
  return (
    <>
      <State resource={resource}>
        <DataTable
          rows={resource.data || []}
          columns={[
            ["name", "Campaign"],
            ["discount_type", "Discount"],
            ["discount_value", "Value"],
            ["redemption_count", "Claims"],
            ["status", "Status"],
          ]}
          actions={(row) => (
            <>
              <button
                className="bf-outline-button"
                onClick={() => setSelected(row)}
              >
                Manage
              </button>
              {["activate", "disable"].map((action) => (
                <Action
                  key={action}
                  perform={() =>
                    api(`${base}/campaigns/${row.id}/${action}`, {
                      method: "POST",
                    })
                  }
                  done={resource.reload}
                >
                  {action}
                </Action>
              ))}
              <Action
                confirm="Delete this draft campaign?"
                perform={() =>
                  api(`${base}/campaigns/${row.id}`, { method: "DELETE" })
                }
                done={resource.reload}
              >
                Delete draft
              </Action>
            </>
          )}
        />
      </State>
      <h2>{selected ? "Edit campaign" : "Create campaign"}</h2>
      <Form
        key={selected?.id || "new"}
        fields={fields}
        initial={selected || {}}
        submit={(body) =>
          api(
            selected ? `${base}/campaigns/${selected.id}` : `${base}/campaigns`,
            { method: selected ? "PATCH" : "POST", body },
          )
        }
        done={() => {
          setSelected(null);
          resource.reload();
        }}
      />
      {selected && (
        <>
          <button onClick={() => setSelected(null)}>New campaign</button>
          <CampaignQR
            base={`${base}/campaigns/${selected.id}`}
            codes={selected.promo_codes}
          />
        </>
      )}
    </>
  );
}
function CampaignQR({ base, codes }) {
  const resource = useResource(`${base}/qr`, true);
  const campaign = useResource(base);
  const currentCodes = campaign.data?.promo_codes || codes || [];
  return (
    <>
      <h2>Promo codes</h2>
      {currentCodes.map((c) => (
        <p key={c.id}>{c.code}</p>
      ))}
      <Form
        fields={[
          { name: "code", label: "Custom code (leave blank to generate)" },
        ]}
        label="Add promo code"
        submit={(body) => api(`${base}/promo-codes`, { method: "POST", body })}
        done={() => {
          campaign.reload();
          resource.reload();
        }}
      />
      <Form
        fields={[
          {
            name: "promo_code_id",
            label: "Promo code for this QR",
            options: currentCodes.map((code) => [code.id, code.code]),
          },
        ]}
        label="Create campaign QR"
        submit={(body) => api(`${base}/qr`, { method: "POST", body })}
        done={resource.reload}
      />
      <State resource={resource}>
        {resource.data?.map((qr) => (
          <div className="bf-panel" key={qr.id}>
            <p>PROMO · {qr.scan_count} scans</p>
            <a href={qr.target_url}>{qr.target_url}</a>
            <SecureImage
              path={apiPath(qr.image_url)}
              alt="Campaign promo QR (not admission)"
            />
            <Action
              perform={() =>
                download(apiPath(qr.image_url), "campaign-promo.png")
              }
            >
              Download promo QR
            </Action>
          </div>
        ))}
      </State>
    </>
  );
}
function Orders({ base }) {
  const [id, setId] = useState(null),
    [filters, setFilters] = useState({});
  const resource = useResource(`${base}/orders?${query(filters)}`, true);
  return (
    <>
      <Form
        fields={[
          { name: "q", label: "Search buyer or order" },
          {
            name: "status",
            label: "Status",
            options: [
              "pending",
              "completed",
              "cancelled",
              "expired",
              "refunded",
            ].map((s) => [s, s]),
          },
        ]}
        label="Search orders"
        submit={async (body) => setFilters(body)}
      />
      <State resource={resource}>
        <DataTable
          rows={resource.data || []}
          columns={[
            ["order_number", "Order"],
            ["buyer_name", "Buyer"],
            ["total_amount", "Total (KZT)"],
            ["status", "Status"],
          ]}
          actions={(row) => (
            <button className="bf-outline-button" onClick={() => setId(row.id)}>
              View order
            </button>
          )}
        />
      </State>
      {id && (
        <ManagedOrder key={id} base={base} id={id} done={resource.reload} />
      )}
    </>
  );
}
function ManagedOrder({ base, id, done }) {
  const resource = useResource(`${base}/orders/${id}`);
  return (
    <State resource={resource}>
      {resource.data && (
        <>
          <OrderSummary order={resource.data} managed />
          {resource.data.status === "completed" && (
            <Form
              fields={[
                {
                  name: "reason",
                  label: "Cancellation / refund reason",
                  required: true,
                  maxLength: 2000,
                },
              ]}
              label={
                resource.data.total_amount
                  ? "Issue full simulated refund"
                  : "Cancel free registration"
              }
              submit={async (body) => {
                if (
                  !window.confirm(
                    "Invalidate every ticket and return inventory for this order?",
                  )
                )
                  throw new Error("Cancelled.");
                return api(
                  `${base}/orders/${id}/${resource.data.total_amount ? "refunds" : "cancel"}`,
                  { method: "POST", body },
                );
              }}
              done={() => {
                resource.reload();
                done();
              }}
            />
          )}
        </>
      )}
    </State>
  );
}
function Analytics({ base }) {
  const tickets = useResource(`${base}/ticket-types`, true);
  const [filters, setFilters] = useState({});
  const suffix = "?" + query(filters);
  const summary = useResource(`${base}/analytics/summary${suffix}`);
  const reports = [
    ["sales/daily", "Sales by day", [["day", "Day"]]],
    [
      "sales/ticket-types",
      "Sales by ticket type",
      [["ticket_type_name", "Ticket type"]],
    ],
    [
      "campaigns",
      "Campaigns",
      [
        ["campaign_name", "Campaign"],
        ["redemptions", "Redemptions"],
      ],
    ],
    ["promo-codes", "Promo codes", [["promo_code", "Code"]]],
  ];
  return (
    <>
      <p>All financial figures are simulated KZT.</p>
      <Form
        fields={[
          {
            name: "date_from",
            label: "From (local time)",
            type: "datetime-local",
          },
          {
            name: "date_to",
            label: "Until (local time)",
            type: "datetime-local",
          },
          {
            name: "ticket_type_id",
            label: "Ticket type",
            options: (tickets.data || []).map((t) => [t.id, t.name]),
          },
        ]}
        submit={async (body) => setFilters(body)}
        label="Apply filters"
      />
      <State resource={summary}>
        {summary.data && (
          <Details
            value={summary.data}
            fields={[
              ["capacity", "Capacity"],
              ["sold", "Sold"],
              ["reserved", "Reserved"],
              ["remaining", "Remaining"],
              ["percent_sold", "Sold %"],
              ["gross_amount", "Gross (KZT)"],
              ["discount_amount", "Discounts (KZT)"],
              ["refund_amount", "Refunds (KZT)"],
              ["net_amount", "Net (KZT)"],
              ["fee_amount", "Processing fees (KZT)"],
              ["estimated_payout_amount", "Estimated payout (KZT)"],
              ["checked_in", "Checked in"],
              ["absent", "Absent"],
              ["check_in_percent", "Attendance %"],
            ]}
          />
        )}
      </State>
      <Export path={`${base}/analytics/summary.csv${suffix}`} />
      {reports.map(([path, label, columns]) => (
        <section key={path}>
          <h2>{label}</h2>
          <RemoteTable
            path={`${base}/analytics/${path}${suffix}`}
            columns={[
              ...columns,
              ["gross_amount", "Gross (KZT)"],
              ["discount_amount", "Discount (KZT)"],
              ["net_amount", "Net (KZT)"],
              ["fee_amount", "Processing fees (KZT)"],
              ["estimated_payout_amount", "Estimated payout (KZT)"],
            ]}
          />
          <Export
            path={`${base}/analytics/${path}.csv${suffix}`}
            name={`${path.replaceAll("/", "-")}.csv`}
          />
        </section>
      ))}
    </>
  );
}
function History({ base }) {
  const [filters, setFilters] = useState({});
  return (
    <>
      <Form
        fields={[
          {
            name: "date_from",
            label: "From (local time)",
            type: "datetime-local",
          },
          {
            name: "date_to",
            label: "Until (local time)",
            type: "datetime-local",
          },
          { name: "action_type", label: "Action type" },
        ]}
        submit={async (body) => setFilters(body)}
        label="Filter activity"
      />
      <RemoteTable
        path={`${base}/history?${query(filters)}`}
        columns={[
          ["occurred_at", "Time"],
          ["actor_name", "Actor"],
          ["action_type", "Action"],
          ["summary", "Summary"],
        ]}
      />
    </>
  );
}
function Settings() {
  const profile = useResource("/organizers/me"),
    payout = useResource("/organizers/me/payout-accounts", true);
  return (
    <>
      <h2>Organizer profile</h2>
      <State resource={profile}>
        {profile.data && (
          <Form
            initial={profile.data}
            fields={[
              { name: "display_name", label: "Organizer name", required: true },
              {
                name: "contact_email",
                label: "Contact email",
                type: "email",
                required: true,
              },
              { name: "contact_phone", label: "Contact phone", nullable: true },
              {
                name: "description",
                label: "Description",
                type: "textarea",
                nullable: true,
              },
            ]}
            submit={(body) => api("/organizers/me", { method: "PATCH", body })}
            done={profile.reload}
          />
        )}
      </State>
      <Action
        perform={() =>
          api("/organizers/me/identity-verification", { method: "POST" })
        }
        done={profile.reload}
      >
        Simulate identity verification
      </Action>
      <h2>Simulated payout accounts</h2>
      <State resource={payout}>
        <DataTable
          rows={payout.data || []}
          columns={[
            ["account_holder_name", "Holder"],
            ["external_account_ref", "Account"],
            ["status", "Status"],
            ["is_default", "Default"],
          ]}
          actions={(row) => (
            <Action
              perform={() =>
                api(`/organizers/me/payout-accounts/${row.id}/default`, {
                  method: "POST",
                })
              }
              done={payout.reload}
            >
              Set default
            </Action>
          )}
        />
      </State>
      <Form
        fields={[
          {
            name: "account_holder_name",
            label: "Account holder",
            required: true,
          },
          {
            name: "external_account_ref",
            label: "Simulated IBAN / account reference",
            required: true,
          },
        ]}
        label="Add payout account"
        submit={(body) =>
          api("/organizers/me/payout-accounts", { method: "POST", body })
        }
        done={payout.reload}
      />
    </>
  );
}
function EventWorkspace({ id, tab = "details" }) {
  const base = `/events/${id}`;
  const resource = useResource(base);
  const event = resource.data;
  return (
    <>
      <State resource={resource}>
        {event && (
          <>
            <h2>{event.title}</h2>
            <p>
              {event.status} · Paid sales: {event.paid_sales_status}
            </p>
            <Link to={`/preview/${event.id}`}>Preview event</Link>
            <div className="bf-actions">
              {["publish", "unpublish", "cancel", "duplicate"].map((action) => (
                <Action
                  key={action}
                  confirm={
                    action === "cancel"
                      ? "Cancel this event, invalidate tickets and simulate refunds for all buyers?"
                      : null
                  }
                  perform={async () => {
                    const result = await api(`${base}/${action}`, {
                      method: "POST",
                    });
                    if (action === "duplicate")
                      location.hash = `/organizer/events/${result.id}`;
                  }}
                  done={resource.reload}
                >
                  {action}
                </Action>
              ))}
              {event.status === "draft" && (
                <Action
                  confirm="Delete this draft?"
                  perform={() => api(base, { method: "DELETE" })}
                  done={() => {
                    location.hash = "/organizer/events";
                  }}
                >
                  Delete draft
                </Action>
              )}
            </div>
          </>
        )}
      </State>
      <nav className="bf-event-subnav">
        {[
          "details",
          "tickets",
          "images",
          "staff",
          "activation",
          "payouts",
          "campaigns",
          "orders",
          "attendees",
          "analytics",
          "history",
          "support",
        ].map((t) => (
          <Link
            key={t}
            className={tab === t ? "bf-button" : ""}
            to={`/organizer/events/${id}/${t}`}
          >
            {t}
          </Link>
        ))}
      </nav>
      {tab === "details" ? (
        event && <EventForm event={event} done={resource.reload} />
      ) : tab === "tickets" ? (
        <TicketTypes base={base} />
      ) : tab === "images" ? (
        <Images base={base} />
      ) : tab === "staff" ? (
        <Staff base={base} />
      ) : tab === "activation" ? (
        <Activation base={base} />
      ) : tab === "payouts" ? (
        <Payouts base={base} />
      ) : tab === "campaigns" ? (
        <Campaigns base={base} />
      ) : tab === "orders" ? (
        <Orders base={base} />
      ) : tab === "analytics" ? (
        <Analytics base={base} />
      ) : tab === "history" ? (
        <History base={base} />
      ) : tab === "support" ? (
        <SupportPanel inbox={`${base}/support/cases`} staff eventId={id} />
      ) : (
        <>
          <RemoteTable
            path={`${base}/tickets`}
            columns={[
              ["ticket_code", "Ticket"],
              ["attendee_name", "Attendee"],
              ["ticket_type_name", "Type"],
              ["status", "Status"],
              ["checked_in_at", "Checked in"],
            ]}
          />
          <h2>Refund history</h2>
          <RemoteTable
            path={`${base}/refunds`}
            columns={[
              ["order_id", "Order"],
              ["amount", "Amount (KZT)"],
              ["status", "Status"],
            ]}
          />
          <h2>Scan history</h2>
          <RemoteTable
            path={`${base}/checkin/records`}
            columns={[
              ["scanned_at", "Time"],
              ["result", "Result"],
              ["action", "Action"],
            ]}
          />
        </>
      )}
    </>
  );
}
export default function OrganizerApp({ path }) {
  const events = useResource("/events/my", true);
  const parts = path.split("/");
  const section = parts[2] || "";
  const id = section === "events" && parts[3] !== "new" ? parts[3] : null;
  const [chosen, setChosen] = useState("");
  const content = id ? (
    <EventWorkspace key={`${id}/${parts[4]}`} id={id} tab={parts[4]} />
  ) : section === "events" && parts[3] === "new" ? (
    <EventForm
      done={(event) => {
        location.hash = `/organizer/events/${event.id}`;
      }}
    />
  ) : section === "settings" ? (
    <Settings />
  ) : section === "support" ? (
    <SupportPanel organizer />
  ) : ["orders", "attendees", "analytics", "campaigns", "history"].includes(
      section,
    ) ? (
    <>
      <label>
        Event
        <select value={chosen} onChange={(e) => setChosen(e.target.value)}>
          <option value="">Choose an event…</option>
          {events.data?.map((event) => (
            <option key={event.id} value={event.id}>
              {event.title}
            </option>
          ))}
        </select>
      </label>
      {chosen && (
        <EventWorkspace key={chosen + section} id={chosen} tab={section} />
      )}
    </>
  ) : (
    <>
      <div className="bf-stats">
        <Stat label="My events" value={events.data?.length ?? "…"} />
      </div>
      <State resource={events}>
        <DataTable
          rows={events.data || []}
          columns={[
            ["title", "Event"],
            ["classification", "Period"],
            ["status", "Status"],
            ["starts_at", "Starts"],
          ]}
          actions={(event) => (
            <Link to={`/organizer/events/${event.id}`}>Manage event</Link>
          )}
        />
      </State>
      <Link className="bf-button" to="/organizer/events/new">
        Create event
      </Link>
    </>
  );
  return (
    <Shell role="organizer" path={path} title="Organizer workspace">
      {content}
    </Shell>
  );
}

function Payouts({ base }) {
  const resource = useResource(`${base}/payouts`, true);
  return (
    <>
      <h2>Simulated payouts</h2>
      <p>
        Academic demo only. No real money moves. Request a payout after the
        event ends.
      </p>
      <Action
        perform={() => api(`${base}/payouts`, { method: "POST" })}
        done={resource.reload}
      >
        Request simulated payout
      </Action>
      <State resource={resource}>
        <DataTable
          rows={resource.data || []}
          columns={[
            ["id", "Reference"],
            ["amount", "Amount (KZT)"],
            ["status", "Status"],
            ["note", "Note"],
          ]}
        />
      </State>
    </>
  );
}

function SeatConfiguration({ base, tickets }) {
  const event = useResource(base);
  const venue = useResource(
    event.data?.seating_mode === "assigned" && event.data?.venue_id
      ? `/venues/${event.data.venue_id}`
      : null,
  );
  const prices = useResource(
    event.data?.seating_mode === "assigned" ? `${base}/seat-prices` : null,
  );
  if (event.data?.seating_mode !== "assigned") return null;
  const seats = (venue.data?.sections || []).flatMap((section) =>
    section.rows.flatMap((row) =>
      row.seats.map((seat) => [
        seat.id,
        `${section.name} ${row.label} ${seat.seat_number}`,
      ]),
    ),
  );
  return (
    <section className="bf-panel">
      <h2>Seat pricing and availability</h2>
      <State resource={prices}>
        {prices.data?.map((category) => (
          <Form
            key={`${category.price_category_id}-${category.ticket_type_id}`}
            fields={[
              {
                name: "ticket_type_id",
                label: category.name,
                nullable: true,
                options: tickets
                  .filter((t) => !t.is_hidden)
                  .map((t) => [t.id, `${t.name} · ${t.price_amount} KZT`]),
              },
            ]}
            initial={category}
            submit={(body) =>
              api(`${base}/seat-prices/${category.price_category_id}`, {
                method: "PATCH",
                body,
              })
            }
            done={prices.reload}
          />
        ))}
      </State>
      <Form
        fields={[
          { name: "seat_id", label: "Seat", required: true, options: seats },
          { name: "blocked", label: "Block seat", type: "checkbox" },
          { name: "reason", label: "Reason", required: true, maxLength: 500 },
        ]}
        label="Update seat availability"
        submit={({ seat_id, ...body }) =>
          api(`${base}/seats/${seat_id}/block`, { method: "PATCH", body })
        }
      />
    </section>
  );
}
