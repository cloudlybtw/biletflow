import { cities } from "../data/i18n.js";
import { all, apiBase } from "./client.js";
export { apiBase, login } from "./client.js";
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
// Seed category slug -> local key used for labels and fallback images.
export const localCategory = (slug) => categoryMap[slug] || "other";
// Public image URL: relative API paths get the API origin; anything else
// that is not http(s) is dropped so callers fall back to a stock image.
export function publicImage(url) {
  let image = url;
  if (image?.startsWith("/"))
    image = new URL(apiBase, window.location.origin).origin + image;
  return image && /^https?:\/\//i.test(image) ? image : null;
}
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
        const category = localCategory(
          categories.find((c) => c.id === e.category_id)?.slug,
        );
        const cover = images.find((i) => i.is_cover) || images[0];
        const prices = tickets
          .filter((t) => !t.is_hidden && t.currency === "KZT")
          .map((t) => t.price_amount);
        const image = publicImage(cover?.url);
        return {
          id: e.id,
          slug: e.slug,
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
