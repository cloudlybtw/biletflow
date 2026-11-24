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
    let returning = null;
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
        if (!alive || generation !== current) return;
        // A background refresh that hits a network blip keeps the signed-in
        // user (and any half-filled form); only auth failures sign out.
        setSession((previous) =>
          previous.user && ![401, 403].includes(error.status)
            ? previous
            : { user: null, loading: false, error: error.message },
        );
      }
    }
    // Switching back to the tab fires both focus and visibilitychange:
    // one /me request covers both.
    const onReturn = () => {
      if (returning) return;
      returning = restore().finally(() => {
        returning = null;
      });
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") onReturn();
    };
    const onStorage = (event) => {
      if (event.key === "biletflow-email-verified") restore();
    };
    window.addEventListener("focus", onReturn);
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("storage", onStorage);
    restore();
    window.addEventListener("biletflow-session", restore);
    return () => {
      alive = false;
      generation++;
      window.removeEventListener("focus", onReturn);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("biletflow-session", restore);
    };
  }, []);
  return <SessionContext value={session}>{children}</SessionContext>;
}
