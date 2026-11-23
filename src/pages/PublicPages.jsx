import EmailVerification from "./EmailVerification";
import { t as translate, useLocale } from "../lib/locale";
import { useState } from "react";
import { api, login } from "../lib/client";
import { useResource } from "../lib/use-resource";
import { Link, LanguagePicker } from "./app-shared";
import SiteHeader from "../components/Navbar/Navbar";
import EventPage from "./Event/EventPage";
import { Checkout, Payment } from "./Checkout/Checkout";
import { NotFound } from "../components/States/States";
import { Form, State } from "./live-shared";
function AuthPage({ path, params }) {
  const next = params.get("next");
  const safeNext =
    next?.startsWith("/") && !next.startsWith("//") ? next : "/account";
  const [message, setMessage] = useState("");
  const keepNext = next ? `?next=${encodeURIComponent(safeNext)}` : "";
  const locale = useLocale();
  const loginPage = path === "/login";
  const register = path === "/register";
  const verify = path === "/verify-email";
  const reset = path === "/reset-password";
  const token = params.get("token") || "";
  const fields = [
    ...(register
      ? [
          {
            name: "full_name",
            label: translate("Full name"),
            required: true,
            maxLength: 200,
          },
        ]
      : []),
    ...(!reset
      ? [
          {
            name: "email",
            label: translate("Email"),
            type: "email",
            required: true,
          },
        ]
      : []),
    ...(loginPage || register || reset
      ? [
          {
            name: reset ? "new_password" : "password",
            label: reset ? translate("New password") : translate("Password"),
            type: "password",
            autoComplete: loginPage ? "current-password" : "new-password",
            required: true,
            minLength: loginPage ? 1 : 8,
            maxLength: 128,
          },
        ]
      : []),
  ];
  const title = loginPage
    ? translate("Welcome back")
    : register
      ? translate("Create your account")
      : verify
        ? translate("Verify your email")
        : translate("Reset your password");
  if (verify)
    return (
      <main className="bf-auth auth auth-verification">
        <section
          className="bf-auth-card verification-card"
          aria-label={translate("Verify your email")}
        >
          <a href="/" className="wordmark" aria-label="BiletFlow">
            <span className="brand-icon" aria-hidden="true">
              b<span>f</span>
            </span>
            BiletFlow<span className="brand-dot">.</span>
          </a>
          <EmailVerification token={token} next={safeNext} />
        </section>
      </main>
    );
  const art = authArt[locale] || authArt.en;
  return (
    <main className="bf-auth auth">
      <aside className="auth-art" aria-hidden="true">
        <p className="auth-art-line">
          {art.line1}
          <br />
          <em>{art.line2}</em>
        </p>
        <span className="auth-art-sticker">{art.sticker}</span>
      </aside>
      <div className="auth-side">
        <div className="bf-auth-top">
          <a href="/" className="wordmark" aria-label="BiletFlow">
            <span className="brand-icon" aria-hidden="true">
              b<span>f</span>
            </span>
            BiletFlow<span className="brand-dot">.</span>
          </a>
          <LanguagePicker />
        </div>
        <div className="bf-auth-card">
          {(loginPage || register) && (
            <nav className="auth-switch" aria-label={translate("Account")}>
              <a
                href={`/#/login${keepNext}`}
                aria-current={loginPage ? "page" : undefined}
              >
                {translate("Sign in")}
              </a>
              <a
                href={`/#/register${keepNext}`}
                aria-current={register ? "page" : undefined}
              >
                {translate("Register")}
              </a>
            </nav>
          )}
          <h1>{title}</h1>
          {message && <p role="status">{translate(message)}</p>}
          {verify ? (
            <EmailVerification token={token} next={safeNext} />
          ) : (
            <Form
              fields={fields}
              label={loginPage ? translate("Sign in") : title}
              submit={async (body) => {
                if (loginPage) {
                  await login(body.email, body.password);
                  location.hash = safeNext;
                  return;
                }
                if (register) {
                  await api("/auth/register", {
                    method: "POST",
                    auth: false,
                    body: { ...body, locale },
                  });
                  // The API does not sign in on register, but unverified accounts may
                  // sign in, so do it now and land on the account page.
                  try {
                    await login(body.email, body.password);
                  } catch {
                    setMessage(
                      "Account created. Check your email for the verification link, then sign in.",
                    );
                    return;
                  }
                  location.hash = safeNext;
                  return;
                }
                if (reset) {
                  await api("/auth/password/reset", {
                    method: "POST",
                    auth: false,
                    body: {
                      ...body,
                      token,
                    },
                  });
                  history.replaceState(null, "", "/#/login");
                  window.dispatchEvent(new Event("hashchange"));
                  return;
                }
                await api("/auth/password/forgot", {
                  method: "POST",
                  auth: false,
                  body,
                });
                setMessage("If an account exists, a reset link has been sent.");
              }}
            />
          )}
          <div className="bf-bridge-links">
            {!loginPage && !register && (
              <Link to="/login">{translate("Sign in")}</Link>
            )}
            {path !== "/forgot-password" && (
              <Link to="/forgot-password">{translate("Forgot password?")}</Link>
            )}
            {!verify && (
              <Link to="/verify-email">{translate("Verify email")}</Link>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
// Big type on the left of the sign-in pages (decorative).
const authArt = {
  en: {
    line1: "Your next",
    line2: "night out.",
    sticker: "Tickets · QR · Kazakhstan",
  },
  ru: {
    line1: "Следующий",
    line2: "вечер — ваш.",
    sticker: "Билеты · QR · Казахстан",
  },
  kk: {
    line1: "Келесі кеш",
    line2: "сіздікі.",
    sticker: "Билеттер · QR · Қазақстан",
  },
};
function Campaign({ token }) {
  const resource = useResource(`/campaign-links/${encodeURIComponent(token)}`);
  return (
    <State resource={resource}>
      {resource.data && (
        <>
          <p role="status">
            {translate("Promotion applied: ")}
            {resource.data.promo_code}
          </p>
          <EventPage
            slug={resource.data.event_slug}
            promo={resource.data.promo_code}
          />
        </>
      )}
    </State>
  );
}
export default function PublicPages({ route, path }) {
  const params = new URLSearchParams(route.split("?")[1] || "");
  if (
    [
      "/login",
      "/register",
      "/forgot-password",
      "/reset-password",
      "/verify-email",
    ].includes(path)
  )
    return <AuthPage path={path} params={params} />;
  const campaign = params.get("c");
  return (
    <>
      <SiteHeader />
      <main className="bf-public">
        {path.startsWith("/checkout/") ? (
          <Checkout id={path.split("/")[2]} params={params} />
        ) : campaign ? (
          <Campaign token={campaign} />
        ) : path.startsWith("/preview/") ? (
          <EventPage id={path.split("/")[2]} />
        ) : path.startsWith("/events/") || path.startsWith("/e/") ? (
          <EventPage
            slug={decodeURIComponent(path.split("/")[2])}
            promo={params.get("promo")}
          />
        ) : (
          <NotFound />
        )}
      </main>
    </>
  );
}
// Account order page imports Payment from here.
export { Payment };
