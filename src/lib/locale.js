import { useSyncExternalStore } from "react";
import messages from "../locales/product.json";

export const locales = { en: "en-GB", ru: "ru-RU", kk: "kk-KZ" };
let memoryLocale = "en";
export function getLocale() {
  try {
    const value = window.localStorage.getItem("biletflow-language");
    return locales[value] ? value : memoryLocale;
  } catch {
    return memoryLocale;
  }
}
export function setLocale(value) {
  if (!locales[value]) return;
  memoryLocale = value;
  try {
    window.localStorage.setItem("biletflow-language", value);
  } catch {
    /* Optional storage. */
  }
  if (typeof document !== "undefined") document.documentElement.lang = value;
  if (typeof window !== "undefined")
    window.dispatchEvent(new Event("biletflow-language"));
}
function subscribe(listener) {
  window.addEventListener("biletflow-language", listener);
  window.addEventListener("storage", listener);
  return () => {
    window.removeEventListener("biletflow-language", listener);
    window.removeEventListener("storage", listener);
  };
}
export function useLocale() {
  return useSyncExternalStore(subscribe, getLocale, () => "en");
}
export function t(value) {
  if (typeof value !== "string") return value;
  const key = value.trim();
  const translated = messages[key]?.[getLocale()] || key;
  return (
    (value.startsWith(" ") ? " " : "") +
    translated +
    (value.endsWith(" ") ? " " : "")
  );
}
export function dateTime(value, options = {}) {
  return new Intl.DateTimeFormat(locales[getLocale()], {
    dateStyle: "medium",
    timeStyle: "short",
    ...options,
  }).format(new Date(value));
}
export function number(value) {
  return new Intl.NumberFormat(locales[getLocale()]).format(Number(value));
}
export function errorText(error) {
  if (getLocale() === "en")
    return error.message || "Unable to complete this action.";
  const code = error.code || "";
  const known = {
    INVALID_CREDENTIALS: "Invalid email or password.",
    ACCOUNT_SUSPENDED: "This account is suspended.",
    VALIDATION_ERROR: "Check the entered details.",
    EMAIL_NOT_VERIFIED: "Verify your email address to continue.",
    UNAUTHORIZED: "Sign in again to continue.",
    TOKEN_EXPIRED: "Sign in again to continue.",
    FORBIDDEN: "This action is not permitted.",
    SOLD_OUT: "Tickets are sold out.",
    RATE_LIMITED: "Too many attempts. Try again later.",
    SEAT_UNAVAILABLE: "The selected seat is no longer available.",
  };
  const message =
    known[code] ||
    (code.startsWith("PROMO_")
      ? "The promo code is unavailable."
      : error.message);
  if (getLocale() === "en" || messages[message]) return t(message);
  return `${t("Unable to complete this action.")} ${code ? `(${code})` : ""}`;
}
