import { t, number } from "../lib/locale";
export default function SeatMap({
  seats,
  selected,
  setSelected,
  ticketTypeId,
}) {
  const xs = [...new Set(seats.map((s) => s.x))].sort((a, b) => a - b);
  const ys = [...new Set(seats.map((s) => s.y))].sort((a, b) => a - b);
  return (
    <>
      <p className="bf-seat-legend">
        {[
          "available",
          "selected",
          "held",
          "sold",
          "unavailable",
          "accessible",
        ].map((state) => (
          <span key={state} data-state={state}>
            {t(state)}
          </span>
        ))}
      </p>
      <div
        className="bf-seat-scroll"
        role="region"
        aria-label={t("Select your seats")}
        tabIndex={0}
      >
        <div
          className="bf-spatial-seats"
          style={{
            gridTemplateColumns: `repeat(${Math.max(xs.length, 1)}, minmax(76px,1fr))`,
          }}
        >
          {seats.map((seat) => {
            const checked = selected.includes(seat.id);
            const state = checked ? "selected" : seat.status;
            const disabled =
              seat.status !== "available" ||
              seat.ticket_type_id !== ticketTypeId;
            return (
              <label
                key={seat.id}
                data-state={state}
                style={{
                  gridColumn: xs.indexOf(seat.x) + 1,
                  gridRow: ys.indexOf(seat.y) + 1,
                }}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={disabled}
                  onChange={(e) =>
                    setSelected(
                      e.target.checked
                        ? [...selected, seat.id]
                        : selected.filter((id) => id !== seat.id),
                    )
                  }
                />
                <span>
                  {seat.section} {seat.row} {seat.number}
                </span>
                <small>
                  {t(state)}
                  {seat.held_by_me ? ` · ${t("Your hold")}` : ""}
                  {seat.accessible ? ` · ♿ ${t("accessible")}` : ""}
                </small>
                <small>
                  {seat.category_name} ·{" "}
                  {seat.price_amount == null
                    ? "—"
                    : `${number(seat.price_amount)} ₸`}
                </small>
              </label>
            );
          })}
        </div>
      </div>
    </>
  );
}
