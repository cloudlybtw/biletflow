// Menu categories modelled on ticketon.kz. The API only knows the seed
// categories (sport, music, culture, comedy, workshop, campus, other), so each
// menu entry lists which of those it shows. Edit the `match` lists to retune.
export const menuCategories = [
  {
    slug: "concerts",
    match: ["music"],
    label: { en: "Concerts", ru: "Концерты", kk: "Концерттер" },
  },
  {
    slug: "theatres",
    match: ["culture"],
    label: { en: "Theatre", ru: "Театры", kk: "Театрлар" },
  },
  {
    slug: "stand-up",
    match: ["comedy"],
    label: { en: "Stand-up", ru: "Юмор", kk: "Юмор" },
  },
  {
    slug: "museums",
    match: ["culture"],
    label: {
      en: "Museums & exhibitions",
      ru: "Музеи и выставки",
      kk: "Мұражайлар мен көрмелер",
    },
  },
  {
    slug: "children",
    match: ["workshop"],
    label: { en: "Kids", ru: "Детям", kk: "Балаларға" },
  },
  {
    slug: "sports",
    match: ["sport"],
    label: { en: "Sport", ru: "Спорт", kk: "Спорт" },
  },
  {
    slug: "entertainment",
    match: ["other", "campus"],
    label: {
      en: "Entertainment",
      ru: "Досуг и развлечения",
      kk: "Демалыс және ойын-сауық",
    },
  },
  {
    slug: "shows",
    match: ["other"],
    label: { en: "Shows", ru: "Шоу", kk: "Шоулар" },
  },
  {
    slug: "knowledge-skills",
    match: ["workshop", "campus"],
    label: {
      en: "Knowledge & skills",
      ru: "Знания и навыки",
      kk: "Білім және дағды",
    },
  },
];
export const categoryBySlug = (slug) =>
  menuCategories.find((c) => c.slug === slug);
export const eventsInCategory = (events, slug) => {
  const match = categoryBySlug(slug)?.match || [];
  return events.filter((e) => match.includes(e.category));
};
