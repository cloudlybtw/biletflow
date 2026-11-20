import Home from "./pages/Home/Home";
import ProductApp from "./pages/ProductApp";
import Category from "./pages/Category/Category";
import SiteFooter from "./components/SiteFooter/SiteFooter";
import SessionProvider from "./components/SessionProvider";
import { useEffect, useState } from "react";
function currentRoute() {
  return window.location.hash.startsWith("#/")
    ? window.location.hash.slice(1)
    : window.location.pathname !== "/"
      ? window.location.pathname + window.location.search
      : null;
}
export default function App() {
  const [route, setRoute] = useState(currentRoute);
  useEffect(() => {
    const update = () => setRoute(currentRoute());
    window.addEventListener("hashchange", update);
    window.addEventListener("popstate", update);
    return () => {
      window.removeEventListener("hashchange", update);
      window.removeEventListener("popstate", update);
    };
  }, []);
  const path = route?.split("?")[0];
  // Listing pages (category, all events, search) share the dark Category page.
  const category =
    path?.startsWith("/category/") || path === "/events" || path === "/search";
  // New page starts at the top; filter changes (same path, new ?query) keep the scroll.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [path]);
  // Discovery pages (home, listings, event pages) are dark (DICE-style);
  // workspace, checkout and form pages stay light.
  const eventPage =
    /^\/(events|e|preview)\/./.test(path || "") ||
    new URLSearchParams(route?.split("?")[1] || "").has("c");
  // The buyer account is customer-facing, so it is dark too.
  const account = /^\/account(\/|$)/.test(path || "");
  const dark = !route || category || eventPage || account;
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);
  return (
    <SessionProvider>
      {category ? (
        <Category key={route.split("?")[0]} route={route} />
      ) : route ? (
        <ProductApp key={route} route={route} />
      ) : (
        <Home />
      )}
      <SiteFooter />
    </SessionProvider>
  );
}
