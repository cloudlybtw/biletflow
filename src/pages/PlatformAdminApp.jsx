import { useState } from "react";
import { api, query } from "../lib/client";
import { useResource } from "../lib/use-resource";
import { Shell, Link } from "./app-shared";
import { State, Form, Action, DataTable, Details, Export } from "./live-shared";
import SupportPanel from "./SupportPanel";
const columns = {
  users: [
    ["full_name", "Name"],
    ["email", "Email"],
    ["platform_role", "Role"],
    ["status", "Status"],
  ],
  events: [
    ["title", "Event"],
    ["status", "Status"],
    ["paid_sales_status", "Paid sales"],
    ["is_suspended", "Suspended"],
  ],
  orders: [
    ["order_number", "Order"],
    ["buyer_name", "Buyer"],
    ["total_amount", "Total (KZT)"],
    ["status", "Status"],
  ],
  payments: [
    ["purpose", "Purpose"],
    ["amount", "Amount (KZT)"],
    ["status", "Status"],
    ["failure_reason", "Failure"],
  ],
  refunds: [
    ["order_id", "Order"],
    ["amount", "Refund (KZT)"],
    ["status", "Status"],
    ["reason", "Reason"],
  ],
  activations: [
    ["event_id", "Event"],
    ["status", "Status"],
    ["fee_amount", "Fee (KZT)"],
    ["activated_at", "Activated"],
  ],
};
function Settings() {
  const resource = useResource("/admin/settings");
  const fields = [
    {
      name: "activation_fee_kzt",
      label: "Activation fee (whole KZT)",
      type: "integer",
      min: 0,
      required: true,
    },
    {
      name: "processing_fee_percent",
      label: "Processing fee (%)",
      type: "number",
      min: 0,
      max: 100,
      required: true,
    },
    {
      name: "order_hold_minutes",
      label: "Order hold (minutes)",
      type: "integer",
      min: 1,
      max: 10080,
      required: true,
    },
    {
      name: "seat_hold_minutes",
      label: "Seat hold (minutes)",
      type: "integer",
      min: 1,
      max: 10080,
      required: true,
    },
  ];
  return (
    <State resource={resource}>
      {resource.data && (
        <Form
          fields={fields}
          initial={Object.fromEntries(
            resource.data.map((row) => [row.key, row.value]),
          )}
          submit={(body) => api("/admin/settings", { method: "PATCH", body })}
          done={resource.reload}
        />
      )}
    </State>
  );
}
function Resource({ kind }) {
  const [filters, setFilters] = useState({});
  const [selected, setSelected] = useState(null);
  const path = `/admin/${kind}?${query(filters)}`;
  const resource = useResource(path, true);
  const detail = useResource(selected ? `/admin/${kind}/${selected}` : null);
  return (
    <>
      <p>Financial amounts are simulated KZT.</p>
      <Form
        fields={[
          { name: "q", label: "Search" },
          { name: "status", label: "Status" },
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
          ...(kind === "payments"
            ? [
                {
                  name: "purpose",
                  label: "Payment purpose",
                  options: [
                    ["ticket_purchase", "Ticket order"],
                    ["activation_fee", "Activation fee"],
                  ],
                },
              ]
            : []),
        ]}
        label="Search"
        submit={async (body) => setFilters(body)}
      />
      <Export
        path={`/admin/${kind}/export.csv?${query(filters)}`}
        name={`${kind}.csv`}
      />
      <State resource={resource}>
        <DataTable
          rows={resource.data || []}
          columns={columns[kind]}
          actions={(row) => (
            <button
              className="bf-outline-button"
              onClick={() => setSelected(row.id)}
            >
              Details
            </button>
          )}
        />
      </State>
      {selected && (
        <State resource={detail}>
          {detail.data && (
            <>
              <Details
                value={detail.data}
                fields={[
                  ["id", "Reference"],
                  ...columns[kind],
                  ...(["users", "events"].includes(kind)
                    ? []
                    : [
                        ["created_at", "Created"],
                        ["processed_at", "Processed"],
                      ]),
                ]}
              />
              {["users", "events"].includes(kind) && (
                <Moderation
                  kind={kind}
                  record={detail.data}
                  done={() => {
                    detail.reload();
                    resource.reload();
                  }}
                />
              )}
              {kind === "activations" && (
                <Moderation
                  kind="events"
                  record={{ id: detail.data.event_id }}
                  done={detail.reload}
                />
              )}
            </>
          )}
        </State>
      )}
    </>
  );
}
function Moderation({ kind, record, done }) {
  const [reason, setReason] = useState("");
  const base = `/admin/${kind}/${record.id}`;
  return (
    <div className="bf-panel bf-form">
      <label>
        Moderation reason
        <input
          required
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength="1000"
        />
      </label>
      <Action
        confirm="Suspend this account or event? This stops the affected actions."
        perform={() =>
          api(`${base}/suspend`, { method: "POST", body: { reason } })
        }
        done={done}
      >
        Suspend
      </Action>
      <Action
        perform={() => api(`${base}/unsuspend`, { method: "POST" })}
        done={done}
      >
        Restore
      </Action>
      {kind === "events" && (
        <>
          <Action
            confirm="Suspend paid ticket sales?"
            perform={() =>
              api(`${base}/paid-sales/suspend`, {
                method: "POST",
                body: { reason },
              })
            }
            done={done}
          >
            Suspend paid sales
          </Action>
          <Action
            perform={() =>
              api(`${base}/paid-sales/unsuspend`, { method: "POST" })
            }
            done={done}
          >
            Restore paid sales
          </Action>
        </>
      )}
    </div>
  );
}
export default function PlatformAdminApp({ path }) {
  const kind = path.split("/")[2];
  return (
    <Shell role="admin" path={path} title="Platform administration">
      {kind === "settings" || kind === "reports" ? (
        <Settings />
      ) : kind === "support" ? (
        <SupportPanel inbox="/admin/support/cases" staff />
      ) : columns[kind] ? (
        <Resource key={kind} kind={kind} />
      ) : (
        <div className="bf-panel">
          <h2>Operations</h2>
          <p>
            Search retained records, moderate events and users, and manage
            platform settings.
          </p>
          {Object.keys(columns).map((k) => (
            <p key={k}>
              <Link to={`/admin/${k}`}>{k}</Link>
            </p>
          ))}
        </div>
      )}
    </Shell>
  );
}
