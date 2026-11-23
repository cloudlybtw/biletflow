import { useEffect, useState } from "react";
import { api } from "../lib/client";
import { useSession } from "../lib/session-context";
import { t, errorText } from "../lib/locale";
import { organizerDraft, notifyEmailVerified } from "../lib/organizer-draft";
import { Form } from "./live-shared";
import { Link } from "./app-shared";

export default function EmailVerification({ token, next }) {
  const { user, loading } = useSession();
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [sendError, setSendError] = useState(null);
  const [sending, setSending] = useState(false);
  const [delivery, setDelivery] = useState(null);
  const [now, setNow] = useState(Date.now);
  const userId = user?.id;
  const draft = organizerDraft(user?.id);
  const organizer = next === "/organizer" || Boolean(draft);
  const differentContact =
    draft?.contact_email &&
    draft.contact_email.toLowerCase() !== user?.email?.toLowerCase();
  const status = delivery || user;
  const sent = Boolean(status?.verification_email_sent_at);
  const remaining =
    Math.max(
      0,
      Math.ceil(
        (Date.parse(status?.verification_email_resend_at) - now) / 1000,
      ),
    ) || 0;

  useEffect(() => {
    if (!remaining) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [remaining]);

  useEffect(() => {
    if (!token || loading) return;
    let active = true;
    api("/auth/verify-email", { method: "POST", auth: false, body: { token } })
      .then((verifiedUser) => {
        if (!active) return;
        setResult(verifiedUser);
        notifyEmailVerified();
        // A fresh tab may not share sessionStorage. Resume through sign-in in that case.
        if (
          organizerDraft(verifiedUser.id) &&
          (!userId || userId === verifiedUser.id)
        ) {
          history.replaceState(
            null,
            "",
            userId ? "/#/organizer" : "/#/login?next=%2Forganizer",
          );
          window.dispatchEvent(new Event("hashchange"));
        }
      })
      .catch((failure) => {
        if (active) setError(failure);
      });
    return () => {
      active = false;
    };
  }, [token, loading, userId]);

  useEffect(() => {
    if (user?.email_verified && organizer && !token)
      location.hash = "/organizer";
  }, [user?.email_verified, organizer, token]);

  if (loading) return <p role="status">{t("Restoring your session…")}</p>;
  if (result || user?.email_verified)
    return (
      <div className="auth-done">
        <p role="status">{t("Email verified. You can now book tickets.")}</p>
        <Link className="bf-button" to={organizer ? "/organizer" : "/account"}>
          {t(organizer ? "Become an organizer" : "My account")}
        </Link>
      </div>
    );
  return (
    <div className="bf-verification">
      <h1>{t(sent ? "Check your inbox" : "Verify your account email")}</h1>
      {user &&
        (sent ? (
          <p role="status">
            {t(
              organizer
                ? "We sent a link to {email}. Follow it to continue creating your profile."
                : "We sent a verification link to {email}.",
            ).replace("{email}", user.email)}
          </p>
        ) : (
          <p className="bf-verification-email">{user.email}</p>
        ))}
      {differentContact && (
        <p className="bf-verification-note">
          {t(
            "Your organizer contact email may differ from your account email.",
          )}
        </p>
      )}
      {token && !error && <p role="status">{t("Verifying your email…")}</p>}
      {(error || sendError) && (
        <p role="alert">{errorText(sendError || error)}</p>
      )}
      {user ? (
        <>
          <button
            className="bf-button"
            disabled={sending || remaining > 0}
            onClick={async () => {
              setSending(true);
              setSendError(null);
              try {
                await api("/auth/verify-email/resend", {
                  method: "POST",
                  body: { email: user.email },
                });
                const refreshed = await api("/me");
                setDelivery(refreshed);
                setNow(Date.now());
                window.dispatchEvent(new Event("biletflow-session"));
              } catch (failure) {
                setSendError(failure);
              } finally {
                setSending(false);
              }
            }}
          >
            {sending
              ? t("Sending email…")
              : remaining > 0
                ? t("Resend in {seconds} s").replace("{seconds}", remaining)
                : sendError
                  ? t("Try again")
                  : t(sent ? "Resend email" : "Send email")}
          </button>
        </>
      ) : !token || error ? (
        <Form
          fields={[
            { name: "email", label: "Email", type: "email", required: true },
          ]}
          label="Send verification email"
          submit={async (body) => {
            await api("/auth/verify-email/resend", {
              method: "POST",
              auth: false,
              body,
            });
          }}
        />
      ) : null}
    </div>
  );
}
