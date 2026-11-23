// Account-scoped so a verification link in another tab can resume onboarding.
const key = (userId) => `biletflow-organizer-draft:${userId}`;
const memory = new Map();
export function organizerDraft(userId) {
  if (!userId) return null;
  try {
    return (
      JSON.parse(localStorage.getItem(key(userId))) ||
      memory.get(userId) ||
      null
    );
  } catch {
    return memory.get(userId) || null;
  }
}
export function saveOrganizerDraft(userId, body) {
  const draft = {
    display_name: body.display_name,
    contact_email: body.contact_email,
  };
  memory.set(userId, draft);
  try {
    localStorage.setItem(key(userId), JSON.stringify(draft));
  } catch {
    /* In-memory fallback. */
  }
}
export function clearOrganizerDraft(userId) {
  memory.delete(userId);
  try {
    localStorage.removeItem(key(userId));
  } catch {
    /* Optional storage. */
  }
}
export function notifyEmailVerified() {
  window.dispatchEvent(new Event("biletflow-session"));
  try {
    localStorage.setItem("biletflow-email-verified", String(Date.now()));
  } catch {
    /* Focus also refreshes the session. */
  }
}
