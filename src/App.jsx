import Home from "./pages/Home/Home";
import ProductApp from "./pages/ProductApp";
import { useEffect, useState } from "react";
export default function App() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const update = () => setHash(window.location.hash);
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return hash.startsWith("#/") ? <ProductApp /> : <Home />;
}
