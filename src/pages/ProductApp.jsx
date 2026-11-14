import { useLocale, setLocale, t as translate } from "../lib/locale";
import { useEffect } from "react";
import PublicPages from "./PublicPages";
import AttendeeApp from "./AttendeeApp";
import OrganizerApp from "./OrganizerApp";
import PlatformAdminApp from "./PlatformAdminApp";
import { useSession } from "../lib/session-context";
import { Link, Topbar } from "./app-shared";
import { Form } from "./live-shared";
import { api } from "../lib/client";
import "./ProductApp.css";
export default function ProductApp({ route }) {
  const { user, loading, error } = useSession();
  const locale = useLocale();
  useEffect(() => {
    if (user?.locale) setLocale(user.locale);
  }, [user?.locale]);
  const path = route.split("?")[0];
  useEffect(() => {
    document.documentElement.lang = locale;
    const titles = {
      "/login": "Sign in",
      "/register": "Create your account",
      "/forgot-password": "Reset your password",
      "/verify-email": "Verify your email",
    };
    document.title = `${translate(titles[path] || "BiletFlow")} | BiletFlow`;
    if (typeof window.requestAnimationFrame !== "function") return;
    const frame = window.requestAnimationFrame(() => {
      const heading = document.querySelector("main h1");
      if (heading) {
        heading.tabIndex = -1;
        heading.focus({ preventScroll: true });
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [path, locale, loading]);
  const protectedRoute = [
    "/account",
    "/organizer",
    "/admin",
    "/checkout",
    "/preview",
  ].some((prefix) => path.startsWith(prefix));
  if (protectedRoute && loading)
    return <p role="status">{translate("Restoring your session\u2026")}</p>;
  if (protectedRoute && !user)
    return (
      <>
        <Topbar />
        <main className="bf-public">
          <h1>{translate("Sign in to continue")}</h1>
          {error && <p role="alert">{error}</p>}
          <Link
            className="bf-button"
            to={`/login?next=${encodeURIComponent(route)}`}
          >
            {translate("Sign in")}
          </Link>
        </main>
      </>
    );
  if (path.startsWith("/admin") && user.platform_role !== "platform_admin")
    return (
      <>
        <Topbar />
        <p role="alert" className="bf-panel">
          {translate("Platform administrator access is required.")}
        </p>
      </>
    );
  if (path.startsWith("/organizer") && !user.is_organizer)
    return (
      <>
        <Topbar />
        <main className="bf-public">
          <h1>{translate("Become an organizer")}</h1>
          <Form
            fields={[
              {
                name: "display_name",
                label: translate("Organizer name"),
                required: true,
              },
              {
                name: "contact_email",
                label: translate("Contact email"),
                type: "email",
                required: true,
              },
            ]}
            initial={{
              contact_email: user.email,
            }}
            submit={(body) =>
              api("/organizers/me", {
                method: "POST",
                body,
              })
            }
            done={() => window.dispatchEvent(new Event("biletflow-session"))}
            label="Create organizer profile"
          />
        </main>
      </>
    );
  if (path.startsWith("/account")) return <AttendeeApp path={path} />;
  if (path.startsWith("/organizer")) return <OrganizerApp path={path} />;
  if (path.startsWith("/admin")) return <PlatformAdminApp path={path} />;
  return <PublicPages route={route} path={path} />;
}
