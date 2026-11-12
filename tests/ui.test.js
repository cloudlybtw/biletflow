import test, { before, after } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { createServer } from "vite";
import React, { act } from "react";

let server,
  root,
  dom,
  PublicPages,
  ProductApp,
  OrganizerApp,
  AttendeeApp,
  SessionProvider,
  apiClient,
  SessionContext;
const requests = [];
const user = {
  id: "user-1",
  full_name: "Dana",
  email: "dana@example.com",
  email_verified: true,
  is_organizer: true,
  platform_role: "attendee",
};
const event = {
  id: "event-1",
  slug: "demo-event",
  title: "Live event",
  description: "Live description",
  starts_at: "2026-12-01T12:00:00Z",
  ends_at: "2026-12-01T15:00:00Z",
  timezone: "Asia/Almaty",
  seating_mode: "general_admission",
  status: "published",
};
let handle;
before(async () => {
  dom = new JSDOM(
    '<!doctype html><html><body><div id="root"></div></body></html>',
    { url: "http://localhost/" },
  );
  for (const key of [
    "window",
    "document",
    "location",
    "history",
    "FormData",
    "Event",
    "sessionStorage",
  ])
    globalThis[key] = dom.window[key];
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  globalThis.dispatchEvent = dom.window.dispatchEvent.bind(dom.window);
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url, options });
    return handle(url, options);
  };
  const { createRoot } = await import("react-dom/client");
  root = createRoot(document.getElementById("root"));
  server = await createServer({
    server: { middlewareMode: true, hmr: false, ws: false, watch: null },
    appType: "custom",
  });
  PublicPages = (await server.ssrLoadModule("/src/pages/PublicPages.jsx"))
    .default;
  ProductApp = (await server.ssrLoadModule("/src/pages/ProductApp.jsx"))
    .default;
  AttendeeApp = (await server.ssrLoadModule("/src/pages/AttendeeApp.jsx"))
    .default;
  OrganizerApp = (await server.ssrLoadModule("/src/pages/OrganizerApp.jsx"))
    .default;
  SessionProvider = (
    await server.ssrLoadModule("/src/components/SessionProvider.jsx")
  ).default;
  apiClient = await server.ssrLoadModule("/src/lib/client.js");
  SessionContext = (await server.ssrLoadModule("/src/lib/session-context.js"))
    .SessionContext;
});
after(async () => {
  await act(() => root.unmount());
  await server.close();
  dom.window.close();
});
function json(body, status = 200) {
  return new Response(body == null ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
async function render(Component, props, sessionUser = user) {
  requests.length = 0;
  await act(async () => {
    root.render(
      React.createElement(
        SessionContext.Provider,
        { value: { user: sessionUser, loading: false } },
        React.createElement(Component, props),
      ),
    );
    await new Promise((resolve) => setTimeout(resolve, 15));
  });
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 15));
  });
}
async function submit(form) {
  await act(async () => {
    form.dispatchEvent(
      new dom.window.Event("submit", { bubbles: true, cancelable: true }),
    );
    await new Promise((resolve) => setTimeout(resolve, 15));
  });
}
function fill(form, values) {
  for (const [name, value] of Object.entries(values))
    form.elements.namedItem(name).value = value;
}

test("signed-out purchase and admin role routes are gated", async () => {
  handle = () => {
    throw new Error("Unexpected protected request");
  };
  await render(ProductApp, { route: "/checkout/event-1" }, null);
  assert.match(document.body.textContent, /Sign in to continue/);
  await render(ProductApp, { route: "/admin/users" }, user);
  assert.match(document.body.textContent, /administrator access is required/);
  assert.equal(requests.length, 0);
});
test("login submits credentials and never navigates after rejected authentication", async () => {
  handle = (url, options) => {
    assert.equal(url, "/api/v1/auth/login");
    assert.deepEqual(JSON.parse(options.body), {
      email: "dana@example.com",
      password: "wrong",
    });
    return json(
      {
        error: { message: "Invalid credentials.", code: "INVALID_CREDENTIALS" },
      },
      401,
    );
  };
  location.hash = "/login";
  await render(PublicPages, { path: "/login", route: "/login" });
  const form = document.querySelector("form");
  fill(form, { email: user.email, password: "wrong" });
  await submit(form);
  assert.match(document.body.textContent, /Invalid credentials/);
  assert.equal(location.hash, "#/login");
});
test("checkout creates a real order with selected type, promo, and attendees", async () => {
  let created = false;
  handle = (url, options) => {
    if (url.includes("/ticket-types"))
      return json({
        items: [
          {
            id: "type-1",
            name: "General",
            price_amount: 1000,
            quantity_total: 10,
            quantity_sold: 0,
            quantity_reserved: 0,
            is_hidden: false,
          },
        ],
        total: 1,
      });
    if (url === "/api/v1/events/event-1") return json(event);
    if (url === "/api/v1/events/event-1/orders") {
      assert.equal(options.method, "POST");
      assert.deepEqual(JSON.parse(options.body), {
        items: [
          {
            ticket_type_id: "type-1",
            quantity: 1,
            attendees: [{ full_name: "Guest", email: "guest@example.com" }],
          },
        ],
        promo_code: "DEMO15",
      });
      created = true;
      return json(
        { id: "order-1", order_number: "BF-1", status: "pending" },
        201,
      );
    }
    throw new Error(`Unexpected ${url}`);
  };
  await render(PublicPages, {
    path: "/checkout/event-1",
    route: "/checkout/event-1?ticket=type-1&promo=DEMO15",
  });
  const form = document.querySelector("form");
  assert.ok(form);
  fill(form, { full_name: "Guest", email: "guest@example.com" });
  await submit(form);
  assert.equal(created, true);
  assert.equal(location.hash, "#/account/orders/order-1");
});
test("organizer creation persists a draft and opens the returned event", async () => {
  let saved = false;
  handle = (url, options) => {
    if (options.method === "POST" && url === "/api/v1/events") {
      const body = JSON.parse(options.body);
      assert.equal(body.title, "Real workshop");
      assert.equal(body.visibility, "public");
      assert.equal(body.seating_mode, "general_admission");
      assert.match(body.starts_at, /Z$/);
      saved = true;
      return json({ ...event, id: "created-event" }, 201);
    }
    if (
      url.startsWith("/api/v1/events/my") ||
      url.startsWith("/api/v1/venues") ||
      url.startsWith("/api/v1/event-categories")
    )
      return json({ items: [], total: 0 });
    throw new Error(`Unexpected ${url}`);
  };
  await render(OrganizerApp, { path: "/organizer/events/new" });
  const form = document.querySelector("form");
  fill(form, {
    title: "Real workshop",
    starts_at: "2026-12-01T12:00",
    ends_at: "2026-12-01T14:00",
  });
  await submit(form);
  assert.equal(saved, true);
  assert.equal(location.hash, "#/organizer/events/created-event");
});
test("public event detail uses server data and links to the actual checkout", async () => {
  handle = (url) => {
    if (url.includes("/calendar-links"))
      return json({
        google: "https://calendar.google.com/calendar/render",
        outlook: "https://outlook.live.com/calendar/0/deeplink/compose",
      });
    if (url.includes("/images")) return json({ items: [], total: 0 });
    if (url.includes("/ticket-types"))
      return json({
        items: [
          {
            id: "type-1",
            name: "General",
            price_amount: 1000,
            quantity_total: 10,
            quantity_sold: 0,
            quantity_reserved: 0,
          },
        ],
        total: 1,
      });
    if (url.includes("/by-slug/")) return json(event);
    throw new Error(`Unexpected ${url}`);
  };
  await render(PublicPages, {
    path: "/events/demo-event",
    route: "/events/demo-event",
  });
  assert.match(document.body.textContent, /Live event/);
  assert.match(document.body.textContent, /Live description/);
  assert.ok(
    document.querySelector(
      'a[href="/#/checkout/event-1?ticket=type-1&promo="]',
    ),
  );
});

test("an awaiting-payment order can retry after a failed payment", async () => {
  let failed = false;
  handle = (url, options) => {
    if (url === "/api/v1/orders/order-1")
      return json({
        id: "order-1",
        order_number: "BF-1",
        status: "awaiting_payment",
        total_amount: 1000,
        payments: [
          { id: "payment-1", status: failed ? "failed" : "initiated" },
        ],
        ticket_ids: [],
      });
    if (url === "/api/v1/payments/payment-1/simulate") {
      assert.equal(JSON.parse(options.body).outcome, "failure");
      failed = true;
      return json({ id: "payment-1", status: "failed" });
    }
    throw new Error(`Unexpected ${url}`);
  };
  await render(AttendeeApp, { path: "/account/orders/order-1" });
  const button = [...document.querySelectorAll("button")].find(
    (element) => element.textContent === "Simulate failure",
  );
  assert.ok(
    button,
    "Pending payment must remain available after a page reload.",
  );
  await act(async () => {
    button.click();
    await new Promise((resolve) => setTimeout(resolve, 30));
  });
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 15));
  });
  assert.equal(failed, true);
  assert.match(document.body.textContent, /Start payment/);
});

test("owner draft preview reads the private event and offers no checkout", async () => {
  handle = (url) => {
    if (url.includes("/images") || url.includes("/ticket-types"))
      return json({ items: [], total: 0 });
    if (url.includes("/calendar-links"))
      return json({
        google: "https://calendar.google.com/",
        outlook: "https://outlook.live.com/",
      });
    if (url === "/api/v1/events/event-1")
      return json({ ...event, status: "draft" });
    throw new Error(`Unexpected ${url}`);
  };
  await render(PublicPages, {
    path: "/preview/event-1",
    route: "/preview/event-1",
  });
  assert.match(document.body.textContent, /Live event/);
  assert.equal(document.querySelector('a[href*="checkout"]'), null);
  assert.ok(
    requests.some((request) => request.url === "/api/v1/events/event-1"),
  );
});

test("successful sign-in restores the real user and sign-out clears session consumers", async () => {
  handle = (url) => {
    if (url.endsWith("/auth/login"))
      return json({ access_token: "access", refresh_token: "refresh", user });
    if (url.endsWith("/me")) return json(user);
    if (url.endsWith("/auth/logout")) return json(null, 204);
    throw new Error(`Unexpected ${url}`);
  };
  function Probe() {
    const session = React.useContext(SessionContext);
    return React.createElement(
      "p",
      null,
      session.user?.full_name || "Signed out",
    );
  }
  await act(async () => {
    root.render(
      React.createElement(SessionProvider, null, React.createElement(Probe)),
    );
  });
  await act(async () => {
    await apiClient.login(user.email, "password");
    await new Promise((resolve) => setTimeout(resolve, 15));
  });
  assert.match(document.body.textContent, /Dana/);
  await act(async () => {
    await apiClient.logout();
    await new Promise((resolve) => setTimeout(resolve, 15));
  });
  assert.match(document.body.textContent, /Signed out/);
});

test("mobile workspace menu preserves account, organizer and admin navigation", async () => {
  handle = (url) => {
    if (
      url.includes("/events/my") ||
      url.includes("/venues") ||
      url.includes("/event-categories")
    )
      return json({ items: [], total: 0 });
    throw new Error(`Unexpected ${url}`);
  };
  await render(
    OrganizerApp,
    { path: "/organizer" },
    { ...user, platform_role: "platform_admin" },
  );
  const menu = document.querySelector("details.bf-mobile-nav");
  assert.ok(menu);
  assert.ok(
    menu.querySelector(
      'nav[aria-label="Workspace navigation"] a[href="/#/admin"]',
    ),
  );
  assert.ok(menu.querySelector('a[href="/#/account"]'));
  await act(async () => {
    menu.querySelector("summary").click();
  });
  assert.equal(menu.open, true);
});

test("editing an event preserves a saved venue when its options arrive later", async () => {
  let saved = false;
  handle = async (url, options) => {
    if (url === "/api/v1/events/event-1" && options.method === "PATCH") {
      assert.equal(JSON.parse(options.body).venue_id, "venue-1");
      saved = true;
      return json({ ...event, venue_id: "venue-1" });
    }
    if (url === "/api/v1/events/event-1")
      return json({
        ...event,
        venue_id: "venue-1",
        visibility: "public",
        capacity: 10,
      });
    if (url.startsWith("/api/v1/venues")) {
      await new Promise((resolve) => setTimeout(resolve, 30));
      return json({
        items: [{ id: "venue-1", name: "Demo hall", city: "Almaty" }],
        total: 1,
      });
    }
    if (
      url.startsWith("/api/v1/events/my") ||
      url.startsWith("/api/v1/event-categories")
    )
      return json({ items: [], total: 0 });
    throw new Error(`Unexpected ${url}`);
  };
  await render(OrganizerApp, { path: "/organizer/events/event-1/details" });
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 45));
  });
  const form = document.querySelector("form");
  assert.equal(form.elements.venue_id.value, "venue-1");
  await submit(form);
  assert.equal(saved, true);
});
