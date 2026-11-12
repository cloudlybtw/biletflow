import { useState, useEffect } from "react";
import { api, download } from "../lib/client";
import { useResource } from "../lib/use-resource";
import { Link, Badge } from "./app-shared";

export function State({ resource, children }) {
  if (resource.loading)
    return (
      <p role="status" className="bf-panel">
        Loading…
      </p>
    );
  if (resource.error)
    return (
      <div className="bf-panel" role="alert">
        <p>{resource.error.message}</p>
        <button className="bf-outline-button" onClick={resource.reload}>
          Try again
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
  const [status, setStatus] = useState({ busy: false, error: "", message: "" });
  return (
    <span className="bf-action">
      <button
        className={className}
        disabled={status.busy}
        onClick={async () => {
          if (confirm && !window.confirm(confirm)) return;
          setStatus({ busy: true });
          try {
            await perform();
            setStatus({ message: "Saved." });
            done?.();
          } catch (error) {
            setStatus({ error: error.message });
          }
        }}
      >
        {status.busy ? "Working…" : children}
      </button>
      {status.error && <span role="alert">{status.error}</span>}
      {status.message && <span role="status">{status.message}</span>}
    </span>
  );
}
export function Form({
  fields,
  initial = {},
  submit,
  label = "Save",
  done,
  children,
}) {
  const [status, setStatus] = useState({});
  return (
    <form
      className="bf-panel bf-form"
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
        setStatus({ busy: true });
        try {
          const result = await submit(body, form);
          setStatus({ message: "Saved successfully." });
          done?.(result);
        } catch (error) {
          setStatus({ error: error.message });
        }
      }}
    >
      {fields.map((field) => (
        <label key={field.name}>
          {field.label}
          {field.options ? (
            <SelectInput field={field} initial={initial[field.name]} />
          ) : field.type === "textarea" ? (
            <textarea
              name={field.name}
              defaultValue={initial[field.name] ?? field.default ?? ""}
              required={field.required}
              rows={4}
              maxLength={field.maxLength}
            />
          ) : (
            <input
              name={field.name}
              type={field.type === "integer" ? "number" : field.type || "text"}
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
      {status.error && <p role="alert">{status.error}</p>}
      {status.message && <p role="status">{status.message}</p>}
      <button className="bf-button" disabled={status.busy}>
        {status.busy ? "Saving…" : label}
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
      <option value="">Select…</option>
      {field.options.map((option) => (
        <option key={option[0]} value={option[0]}>
          {option[1]}
        </option>
      ))}
    </select>
  );
}

export function DataTable({ rows = [], columns, actions }) {
  if (!rows.length) return <p className="bf-panel">No records found.</p>;
  return (
    <div className="bf-panel bf-table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map(([key, label]) => (
              <th key={key}>{label}</th>
            ))}
            {actions && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.id || row.key || index}>
              {columns.map(([key, , render]) => (
                <td key={key}>
                  {render ? render(row[key], row) : show(row[key])}
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
function show(value) {
  return value == null
    ? "—"
    : typeof value === "boolean"
      ? value
        ? "Yes"
        : "No"
      : String(value);
}
export function Details({ value, fields }) {
  return (
    <dl className="bf-panel bf-details">
      {fields.map(([key, label]) => (
        <div key={key}>
          <dt>{label}</dt>
          <dd>{show(value?.[key])}</dd>
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
  return <Action perform={() => download(path, name)}>Download CSV</Action>;
}
export function SecureImage({ path, alt }) {
  const [image, setImage] = useState({});
  useEffect(() => {
    let alive = true;
    let url;
    api(path, { raw: true })
      .then((response) => response.blob())
      .then((blob) => {
        url = URL.createObjectURL(blob);
        if (alive) setImage({ path, url });
        else URL.revokeObjectURL(url);
      })
      .catch((error) => {
        if (alive) setImage({ path, error });
      });
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [path]);
  if (image.path !== path) return <p>Loading image…</p>;
  return image.error ? (
    <p role="alert">{image.error.message}</p>
  ) : (
    <img className="bf-secure-image" src={image.url} alt={alt} />
  );
}
export function OrderSummary({ order, managed = false }) {
  return (
    <>
      <Details
        value={order}
        fields={[
          ["order_number", "Order"],
          ["status", "Status"],
          ["subtotal_amount", "Subtotal (KZT)"],
          ["discount_amount", "Discount (KZT)"],
          ["fee_amount", "Processing fee (KZT)"],
          ["total_amount", "Total (KZT)"],
          ["expires_at", "Reservation expires"],
        ]}
      />
      {!managed &&
        order.ticket_ids?.map((id) => (
          <Link
            key={id}
            className="bf-outline-button"
            to={`/account/tickets/${id}`}
          >
            View ticket
          </Link>
        ))}
    </>
  );
}
export function StatusBadge({ value }) {
  return <Badge>{value}</Badge>;
}
