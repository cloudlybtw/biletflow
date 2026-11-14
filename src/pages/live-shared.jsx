import { t as translate, dateTime, number, errorText } from "../lib/locale";
import { useState, useEffect, useId } from "react";
import { api, download } from "../lib/client";
import { useResource } from "../lib/use-resource";
import { Link, Badge } from "./app-shared";
export function State({ resource, children }) {
  if (resource.loading)
    return (
      <p role="status" className="bf-panel">
        {translate("Loading\u2026")}
      </p>
    );
  if (resource.error)
    return (
      <div className="bf-panel" role="alert">
        <p>{errorText(resource.error)}</p>
        <button className="bf-outline-button" onClick={resource.reload}>
          {translate("Try again")}
        </button>
      </div>
    );
  return children;
}
export function Action({
  children,
  perform,
  done,
  confirm,
  className = "bf-outline-button",
}) {
  const [status, setStatus] = useState({
    busy: false,
    error: "",
    message: "",
  });
  return (
    <span className="bf-action">
      <button
        className={className}
        disabled={status.busy}
        onClick={async () => {
          if (confirm && !window.confirm(translate(confirm))) return;
          setStatus({
            busy: true,
          });
          try {
            await perform();
            setStatus({
              message: "Saved.",
            });
            done?.();
          } catch (error) {
            setStatus({
              error: error,
            });
          }
        }}
      >
        {status.busy ? translate("Working\u2026") : children}
      </button>
      {status.error && <span role="alert">{errorText(status.error)}</span>}
      {status.message && <span role="status">{translate(status.message)}</span>}
    </span>
  );
}
export function Form({
  fields,
  initial = {},
  submit,
  label = translate("Save"),
  done,
  children,
}) {
  const [status, setStatus] = useState({});
  const feedbackId = useId();
  return (
    <form
      className="bf-panel bf-form"
      aria-busy={Boolean(status.busy)}
      onSubmit={async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const values = new FormData(form);
        const body = {};
        for (const field of fields) {
          const value = values.get(field.name);
          if (field.multiple)
            body[field.name] = values.getAll(field.name).filter(Boolean);
          else if (field.type === "checkbox") body[field.name] = value === "on";
          else if (value !== "" && value != null)
            body[field.name] = ["number", "integer"].includes(field.type)
              ? Number(value)
              : field.type === "datetime-local"
                ? new Date(value).toISOString()
                : value;
          else if (field.nullable) body[field.name] = null;
        }
        setStatus({
          busy: true,
        });
        try {
          const result = await submit(body, form);
          setStatus({
            message: "Saved successfully.",
          });
          done?.(result);
        } catch (error) {
          setStatus({
            error: error,
          });
        }
      }}
    >
      {fields.map((field) => (
        <label key={field.name}>
          {translate(field.label)}
          {field.options ? (
            <SelectInput field={field} initial={initial[field.name]} />
          ) : field.type === "textarea" ? (
            <textarea
              name={field.name}
              aria-describedby={status.error ? feedbackId : undefined}
              defaultValue={initial[field.name] ?? field.default ?? ""}
              required={field.required}
              rows={4}
              maxLength={field.maxLength}
            />
          ) : (
            <input
              name={field.name}
              type={field.type === "integer" ? "number" : field.type || "text"}
              aria-describedby={status.error ? feedbackId : undefined}
              autoComplete={
                field.autoComplete ||
                {
                  full_name: "name",
                  email: "email",
                  phone: "tel",
                  password: "current-password",
                  new_password: "new-password",
                }[field.name]
              }
              defaultValue={
                field.type === "checkbox"
                  ? undefined
                  : field.type === "datetime-local" && initial[field.name]
                    ? localTime(initial[field.name])
                    : (initial[field.name] ?? field.default ?? "")
              }
              defaultChecked={
                field.type === "checkbox"
                  ? Boolean(initial[field.name])
                  : undefined
              }
              required={field.required}
              min={field.min}
              max={field.max}
              minLength={field.minLength}
              maxLength={field.maxLength}
              step={field.step || (field.type === "number" ? "any" : undefined)}
            />
          )}
        </label>
      ))}
      {children}
      {status.error && (
        <p id={feedbackId} role="alert">
          {errorText(status.error)}
        </p>
      )}
      {status.message && <p role="status">{translate(status.message)}</p>}
      <button className="bf-button" disabled={status.busy}>
        {status.busy ? translate("Saving\u2026") : label}
      </button>
    </form>
  );
}
function localTime(value) {
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
function SelectInput({ field, initial }) {
  const [value, setValue] = useState(
    initial ?? field.default ?? (field.multiple ? [] : ""),
  );
  return (
    <select
      name={field.name}
      multiple={field.multiple}
      value={value}
      required={field.required}
      onChange={(event) =>
        setValue(
          field.multiple
            ? Array.from(event.target.selectedOptions, (option) => option.value)
            : event.target.value,
        )
      }
    >
      <option value="">{translate("Select\u2026")}</option>
      {field.options.map((option) => (
        <option key={option[0]} value={option[0]}>
          {translate(option[1])}
        </option>
      ))}
    </select>
  );
}
export function DataTable({ rows = [], columns, actions }) {
  if (!rows.length)
    return <p className="bf-panel">{translate("No records found.")}</p>;
  return (
    <div className="bf-panel bf-table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map(([key, label]) => (
              <th key={key}>{translate(label)}</th>
            ))}
            {actions && <th>{translate("Actions")}</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.id || row.key || index}>
              {columns.map(([key, , render]) => (
                <td key={key}>
                  {render ? render(row[key], row) : show(row[key], key)}
                </td>
              ))}
              {actions && (
                <td>
                  <div className="bf-actions">{actions(row)}</div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function show(value, key = "") {
  if (
    value != null &&
    /(_at|expires)$/.test(key) &&
    !Number.isNaN(Date.parse(value))
  )
    return dateTime(value);
  if (typeof value === "number") return number(value);
  if (
    [
      "status",
      "sender_role",
      "case_type",
      "category",
      "platform_role",
    ].includes(key)
  )
    return translate(value);
  return value == null
    ? "—"
    : typeof value === "boolean"
      ? value
        ? translate("Yes")
        : translate("No")
      : String(value);
}
export function Details({ value, fields }) {
  return (
    <dl className="bf-panel bf-details">
      {fields.map(([key, label]) => (
        <div key={key}>
          <dt>{translate(label)}</dt>
          <dd>{show(value?.[key], key)}</dd>
        </div>
      ))}
    </dl>
  );
}
export function RemoteTable({ path, columns, actions, poll = 0 }) {
  const resource = useResource(path, true, poll);
  return (
    <State resource={resource}>
      <DataTable
        rows={resource.data || []}
        columns={columns}
        actions={actions ? (row) => actions(row, resource.reload) : null}
      />
    </State>
  );
}
export function Export({ path, name = "report.csv" }) {
  return (
    <Action perform={() => download(path, name)}>
      {translate("Download CSV")}
    </Action>
  );
}
export function SecureImage({ path, alt }) {
  const [image, setImage] = useState({});
  useEffect(() => {
    let alive = true;
    let url;
    api(path, {
      raw: true,
    })
      .then((response) => response.blob())
      .then((blob) => {
        url = URL.createObjectURL(blob);
        if (alive)
          setImage({
            path,
            url,
          });
        else URL.revokeObjectURL(url);
      })
      .catch((error) => {
        if (alive)
          setImage({
            path,
            error,
          });
      });
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [path]);
  if (image.path !== path) return <p>{translate("Loading image\u2026")}</p>;
  return image.error ? (
    <p role="alert">{errorText(image.error)}</p>
  ) : (
    <img className="bf-secure-image" src={image.url} alt={translate(alt)} />
  );
}
export function OrderSummary({ order, managed = false }) {
  return (
    <>
      <Details
        value={order}
        fields={[
          ["order_number", translate("Order")],
          ["status", translate("Status")],
          ["subtotal_amount", translate("Subtotal (KZT)")],
          ["discount_amount", translate("Discount (KZT)")],
          ["fee_amount", translate("Processing fee (KZT)")],
          ["total_amount", translate("Total (KZT)")],
          ["expires_at", translate("Reservation expires")],
        ]}
      />
      {!managed &&
        order.ticket_ids?.map((id) => (
          <Link
            key={id}
            className="bf-outline-button"
            to={`/account/tickets/${id}`}
          >
            {translate("View ticket")}
          </Link>
        ))}
    </>
  );
}
export function StatusBadge({ value }) {
  return <Badge>{value}</Badge>;
}
