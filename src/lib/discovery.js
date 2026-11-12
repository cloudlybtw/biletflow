export const timezone = "Asia/Almaty";
export function localDay(value) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(value));
  return ["year", "month", "day"]
    .map((k) => parts.find((p) => p.type === k).value)
    .join("-");
}
export function inWeek(event, now = new Date()) {
  const today = localDay(now);
  const midnight = new Date(`${today}T00:00:00+05:00`);
  const day = new Date(`${today}T12:00:00Z`).getUTCDay();
  const end = new Date(+midnight + (8 - (day || 7)) * 86400000);
  return new Date(event.startsAt) >= now && new Date(event.startsAt) < end;
}
export function filterEvents(events, filters) {
  return events.filter(
    (e) =>
      (!filters.q ||
        e.title
          .toLocaleLowerCase()
          .includes(filters.q.trim().toLocaleLowerCase())) &&
      (!filters.city || e.city === filters.city) &&
      (!filters.category || e.category === filters.category) &&
      (!filters.free || e.price === 0) &&
      (!filters.from || localDay(e.startsAt) >= filters.from) &&
      (!filters.to || localDay(e.startsAt) <= filters.to),
  );
}
export function sectionEvents(events, key, now) {
  return [
    ...new Map(
      events
        .filter((e) =>
          key === "week"
            ? inWeek(e, now)
            : key === "free"
              ? e.price === 0
              : e.category === key,
        )
        .map((e) => [e.id, e]),
    ).values(),
  ];
}
