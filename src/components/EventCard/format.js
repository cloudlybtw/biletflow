import { copy, locales } from "../../data/i18n";
import { timezone } from "../../lib/discovery";
export const formatEventDate = (event, lang) =>
  new Intl.DateTimeFormat(locales[lang], {
    timeZone: timezone,
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(event.startsAt));
export const formatEventPrice = (event, lang) => {
  const t = copy[lang];
  return event.price === 0
    ? t.freePrice
    : event.price == null
      ? t.unknownPrice
      : `${t.from} ${new Intl.NumberFormat(locales[lang]).format(event.price)} ₸`;
};
