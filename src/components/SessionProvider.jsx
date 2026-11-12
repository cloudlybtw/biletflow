import { useEffect, useState } from "react";
import { api, client } from "../lib/client";
import { SessionContext } from "../lib/session-context";

export default function SessionProvider({ children }) {
  const [session, setSession] = useState({
    user: null,
    loading: client.hasSession(),
    error: "",
  });
  useEffect(() => {
    let generation = 0;
    let alive = true;
    async function restore() {
      const current = ++generation;
      if (!client.hasSession()) {
        setSession({ user: null, loading: false, error: "" });
        return;
      }
      try {
        const user = await api("/me");
        if (alive && generation === current)
          setSession({ user, loading: false, error: "" });
      } catch (error) {
        if (alive && generation === current)
          setSession({ user: null, loading: false, error: error.message });
      }
    }
    restore();
    window.addEventListener("biletflow-session", restore);
    return () => {
      alive = false;
      generation++;
      window.removeEventListener("biletflow-session", restore);
    };
  }, []);
  return <SessionContext value={session}>{children}</SessionContext>;
}
