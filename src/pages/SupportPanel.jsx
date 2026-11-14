import { t as translate, dateTime } from "../lib/locale";
import { useState } from "react";
import { api, apiPath, download } from "../lib/client";
import { useResource } from "../lib/use-resource";
import { useSession } from "../lib/session-context";
import { Form, State, DataTable, Action, Details } from "./live-shared";
const categories = [
  "ticket_delivery",
  "payment",
  "refund",
  "seating",
  "event_information",
  "check_in",
  "account",
  "technical",
].map((value) => [value, value]);
export default function SupportPanel({
  inbox = "/support/cases",
  staff = false,
  organizer = false,
  eventId = null,
}) {
  const cases = useResource(inbox, true, 10000);
  const [selected, setSelected] = useState(null);
  const orders = useResource(!staff && !organizer ? "/orders" : null, true);
  if (selected)
    return (
      <>
        <button className="bf-outline-button" onClick={() => setSelected(null)}>
          {translate("Back to cases")}
        </button>
        <Thread key={selected} id={selected} staff={staff} eventId={eventId} />
      </>
    );
  return (
    <>
      <State resource={cases}>
        <DataTable
          rows={cases.data || []}
          columns={[
            ["case_number", translate("Case")],
            ["subject", translate("Subject")],
            ["status", translate("Status")],
            ["last_message_at", translate("Last update")],
          ]}
          actions={(row) => (
            <button
              className="bf-outline-button"
              onClick={() => setSelected(row.id)}
            >
              {translate("Open conversation")}
            </button>
          )}
        />
      </State>
      {!staff && (
        <>
          <h2>{translate("Open a support case")}</h2>
          <Form
            fields={[
              {
                name: "subject",
                label: translate("Subject"),
                required: true,
                maxLength: 200,
              },
              {
                name: "category",
                label: translate("Category"),
                options: categories,
                required: true,
              },
              ...(!organizer
                ? [
                    {
                      name: "order_id",
                      label: translate("Related order"),
                      required: true,
                      options: (orders.data || []).map((order) => [
                        order.id,
                        order.order_number,
                      ]),
                    },
                  ]
                : []),
              {
                name: "body",
                label: translate("Message"),
                type: "textarea",
                required: true,
                maxLength: 10000,
              },
            ]}
            label="Send request"
            submit={(body) =>
              api("/support/cases", {
                method: "POST",
                body: {
                  ...body,
                  case_type: organizer ? "organizer" : "attendee",
                  ...(eventId
                    ? {
                        event_id: eventId,
                      }
                    : {}),
                },
              })
            }
            done={(result) => setSelected(result.id)}
          />
        </>
      )}
    </>
  );
}
function Thread({ id, staff, eventId }) {
  const detail = useResource(`/support/cases/${id}`);
  const messages = useResource(`/support/cases/${id}/messages`, true, 5000);
  const attachments = useResource(
    `/support/cases/${id}/attachments`,
    true,
    10000,
  );
  const { user } = useSession();
  const people = useResource(
    staff ? (eventId ? `/events/${eventId}/staff` : "/admin/users") : null,
    true,
  );
  const options = [
    [user.id, `${user.full_name} (me)`],
    ...(people.data || [])
      .filter((p) => (p.user_id || p.id) !== user.id)
      .map((p) => [
        p.user_id || p.id,
        p.full_name || `${p.role} · ${p.user_id.slice(0, 8)}`,
      ]),
  ];
  return (
    <>
      <State resource={detail}>
        {detail.data && (
          <Details
            value={detail.data}
            fields={[
              ["case_number", translate("Case")],
              ["subject", translate("Subject")],
              ["status", translate("Status")],
              ["category", translate("Category")],
            ]}
          />
        )}
      </State>
      {staff && (
        <details className="bf-panel">
          <summary>{translate("Escalate to platform support")}</summary>
          {detail.data?.escalated_at ? (
            <p>
              {translate("Escalated: ")}
              {detail.data.escalation_reason}
            </p>
          ) : (
            <Form
              fields={[
                {
                  name: "reason",
                  label: translate("Escalation reason"),
                  type: "textarea",
                  required: true,
                  maxLength: 2000,
                },
              ]}
              label="Escalate"
              submit={(body) =>
                api(`/support/cases/${id}/escalate`, {
                  method: "POST",
                  body,
                })
              }
              done={detail.reload}
            />
          )}
        </details>
      )}
      <State resource={messages}>
        <div className="bf-panel bf-chat">
          {messages.data?.map((message) => (
            <div
              className={`bf-bubble ${message.is_internal_note ? "bf-note" : ""}`}
              key={message.id}
            >
              <strong>
                {message.is_internal_note
                  ? translate("Internal note")
                  : translate(message.sender_role)}
              </strong>
              <p>{message.body}</p>
              <small>{dateTime(message.created_at)}</small>
            </div>
          ))}
        </div>
      </State>
      <Form
        fields={[
          {
            name: "body",
            label: translate("Reply"),
            type: "textarea",
            required: true,
            maxLength: 10000,
          },
          ...(staff
            ? [
                {
                  name: "is_internal_note",
                  label: translate("Internal note (staff only)"),
                  type: "checkbox",
                },
              ]
            : []),
        ]}
        label="Send message"
        submit={async (body, form) => {
          const message = await api(`/support/cases/${id}/messages`, {
            method: "POST",
            body,
          });
          const file = form.elements.screenshot.files[0];
          if (file) {
            try {
              const data = new FormData();
              data.append("file", file);
              await api(
                `/support/cases/${id}/messages/${message.id}/attachments`,
                {
                  method: "POST",
                  body: data,
                },
              );
            } catch (error) {
              messages.reload();
              throw new Error(
                `Message sent, but screenshot failed: ${error.message}`,
                {
                  cause: error,
                },
              );
            }
          }
          return message;
        }}
        done={() => {
          messages.reload();
          attachments.reload();
        }}
      >
        <label>
          {translate("Screenshot (optional, PNG/JPEG/WebP)")}
          <input
            type="file"
            name="screenshot"
            accept="image/png,image/jpeg,image/webp"
          />
        </label>
      </Form>
      <State resource={attachments}>
        {attachments.data?.map((attachment) => (
          <Action
            key={attachment.id}
            perform={() =>
              download(apiPath(attachment.file_url), attachment.filename)
            }
          >
            {translate("Download screenshot \xB7")}{" "}
            {dateTime(attachment.created_at)}
          </Action>
        ))}
      </State>
      {staff && (
        <>
          <Form
            fields={[
              {
                name: "status",
                label: translate("Case status"),
                required: true,
                options: [
                  "open",
                  "in_progress",
                  "waiting_for_customer",
                  "resolved",
                ].map((s) => [s, s.replaceAll("_", " ")]),
              },
            ]}
            submit={(body) =>
              api(`/support/cases/${id}/status`, {
                method: "PATCH",
                body,
              })
            }
            done={detail.reload}
          />
          <Form
            fields={[
              {
                name: "assigned_to_user_id",
                label: translate("Assign to staff member"),
                required: true,
                options,
              },
            ]}
            submit={(body) =>
              api(`/support/cases/${id}/assignment`, {
                method: "PATCH",
                body,
              })
            }
            done={detail.reload}
          />
          <Action
            perform={() =>
              api(`/support/cases/${id}/assignment`, {
                method: "PATCH",
                body: {
                  assigned_to_user_id: null,
                },
              })
            }
            done={detail.reload}
          >
            {translate("Unassign")}
          </Action>
        </>
      )}
    </>
  );
}
