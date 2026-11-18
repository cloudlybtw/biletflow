import { useSyncExternalStore } from "react";
const key = "biletflow-city";
let memory = "";
export function getCity() {
  try {
    return window.localStorage.getItem(key) ?? memory;
  } catch {
    return memory;
  }
}
export function setCity(value) {
  memory = value;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* Storage is optional. */
  }
  window.dispatchEvent(new Event(key));
}
function subscribe(listener) {
  window.addEventListener(key, listener);
  window.addEventListener("storage", listener);
  return () => {
    window.removeEventListener(key, listener);
    window.removeEventListener("storage", listener);
  };
}
export function useCity() {
  return [useSyncExternalStore(subscribe, getCity, () => ""), setCity];
}
