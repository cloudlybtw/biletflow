export const money = (value) => `${Number(value).toLocaleString("en-US")} ₸`;
export const navGroups = {
  attendee: [
    ["Overview", "/account"],
    ["My tickets", "/account/tickets"],
    ["My orders", "/account/orders"],
    ["Notifications", "/account/notifications"],
    ["Support", "/account/support"],
    ["Profile settings", "/account/settings"],
  ],
  organizer: [
    ["Overview", "/organizer"],
    ["My events", "/organizer/events"],
    ["Create event", "/organizer/events/new"],
    ["Orders", "/organizer/orders"],
    ["Attendees", "/organizer/attendees"],
    ["Analytics", "/organizer/analytics"],
    ["Campaigns", "/organizer/campaigns"],
    ["History", "/organizer/history"],
    ["Support", "/organizer/support"],
    ["Settings", "/organizer/settings"],
  ],
  admin: [
    ["Overview", "/admin"],
    ["Users", "/admin/users"],
    ["Event moderation", "/admin/events"],
    ["Paid sales", "/admin/activations"],
    ["Orders", "/admin/orders"],
    ["Payments", "/admin/payments"],
    ["Refunds", "/admin/refunds"],
    ["Support", "/admin/support"],
    ["Platform settings", "/admin/settings"],
  ],
};
