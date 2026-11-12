import Home from "./pages/Home/Home";
import ProductApp from "./pages/ProductApp";
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
  return (
    <SessionProvider>
      {route ? <ProductApp key={route} route={route} /> : <Home />}
    </SessionProvider>
  );
}
