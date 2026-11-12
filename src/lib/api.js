import { cities } from "../data/i18n.js";
export const apiBase = (import.meta.env?.VITE_API_BASE_URL || "/api/v1").replace(
  /\/$/,
  "",
);
async function get(path, signal) {
  const response = await fetch(`${apiBase}${path}`, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`API ${response.status}`);
  return response.json();
}
async function all(path, signal) {
  const items = [];
  for (let offset = 0; ; offset += 100) {
    const page = await get(
      `${path}${path.includes("?") ? "&" : "?"}limit=100&offset=${offset}`,
      signal,
    );
    if (!Array.isArray(page.items) || !Number.isInteger(page.total))
      throw new Error("Invalid page");
    items.push(...page.items);
    if (items.length >= page.total || !page.items.length) return items;
  }
}
const categoryMap = {
  sport: "sport",
  sports: "sport",
  football: "sport",
  music: "music",
  concert: "music",
  concerts: "music",
  theatre: "culture",
  culture: "culture",
  art: "culture",
  comedy: "comedy",
  "stand-up": "comedy",
  standup: "comedy",
  workshop: "workshop",
  workshops: "workshop",
  community: "workshop",
  education: "workshop",
  campus: "campus",
  student: "campus",
  students: "campus",
};
export async function loadEvents(signal) {
  const [events, venues, categories] = await Promise.all([
    all("/events", signal),
    all("/venues", signal),
    all("/event-categories", signal),
  ]);
  const result = [];
  // Bound fan-out; never silently drop later API pages.
  for (let index = 0; index < events.length; index += 6) {
    const group = await Promise.all(
      events.slice(index, index + 6).map(async (e) => {
        const [tickets, images] = await Promise.all([
          all(`/events/${e.id}/ticket-types`, signal),
          all(`/events/${e.id}/images`, signal),
        ]);
        const venue = venues.find((v) => v.id === e.venue_id);
        const city =
          Object.keys(cities).find(
            (k) => k === venue?.city || cities[k].includes(venue?.city),
          ) ||
          venue?.city ||
          "";
        const category =
          categoryMap[categories.find((c) => c.id === e.category_id)?.slug] ||
          "other";
        const cover = images.find((i) => i.is_cover) || images[0];
        const prices = tickets
          .filter((t) => !t.is_hidden && t.currency === "KZT")
          .map((t) => t.price_amount);
        let image = cover?.url;
        if (image?.startsWith("/"))
          image = new URL(apiBase, window.location.origin).origin + image;
        if (image && !/^https?:\/\//i.test(image)) image = null;
        return {
          id: e.id,
          title: e.title,
          description: e.description,
          startsAt: e.starts_at,
          city,
          venue: venue?.name,
          category,
          price: prices.length ? Math.min(...prices) : null,
          image:
            image ||
            `/images/${category === "other" ? "culture" : category}.jpg`,
          illustrative: !image,
          demo: false,
        };
      }),
    );
    result.push(...group);
  }
  return result
    .filter((e) => new Date(e.startsAt) >= new Date())
    .sort((a, b) => new Date(a.startsAt) - new Date(b.startsAt));
}
export async function login(email, password) {
  const response = await fetch(`${apiBase}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw new Error("Login failed");
  return response.json();
}
