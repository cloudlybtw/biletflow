import test from "node:test";
import assert from "node:assert/strict";
import { createClient, ApiError } from "../src/lib/client.js";
function response(body, status = 200) {
  return new Response(body == null ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
function storage() {
  const data = new Map();
  return {
    getItem: (key) => data.get(key),
    setItem: (key, value) => data.set(key, value),
    removeItem: (key) => data.delete(key),
  };
}
const pair = {
  access_token: "old",
  refresh_token: "refresh1",
  user: { id: "u1" },
};

test("login, two concurrent unauthorized requests share one refresh and rotate both tokens", async () => {
  let exchanges = 0;
  const client = createClient({
    storage: storage(),
    fetcher: async (url, options) => {
      if (url.endsWith("/auth/login")) return response(pair);
      if (url.endsWith("/auth/refresh")) {
        exchanges++;
        await new Promise((resolve) => setTimeout(resolve, 5));
        assert.equal(JSON.parse(options.body).refresh_token, "refresh1");
        return response({
          ...pair,
          access_token: "new",
          refresh_token: "refresh2",
        });
      }
      return options.headers.Authorization === "Bearer new"
        ? response({ id: "u1" })
        : response({ error: { message: "Expired" } }, 401);
    },
  });
  await client.login("user@example.com", "password");
  const results = await Promise.all([
    client.request("/me"),
    client.request("/orders"),
  ]);
  assert.equal(exchanges, 1);
  assert.deepEqual(results, [{ id: "u1" }, { id: "u1" }]);
});
test("refresh does not resurrect a session after logout", async () => {
  let finish;
  let started;
  const ready = new Promise((resolve) => {
    started = resolve;
  });
  const client = createClient({
    storage: storage(),
    fetcher: async (url) => {
      if (url.endsWith("/auth/login")) return response(pair);
      if (url.endsWith("/auth/refresh")) {
        started();
        return new Promise((resolve) => {
          finish = () => resolve(response({ ...pair, access_token: "new" }));
        });
      }
      if (url.endsWith("/auth/logout")) return response(null, 204);
      return response({ error: { message: "Expired" } }, 401);
    },
  });
  await client.login("a", "b");
  const request = client.request("/me");
  await ready;
  await client.logout();
  finish();
  await assert.rejects(request);
  assert.equal(client.hasSession(), false);
});
test("refresh failure clears invalid session and retries only once", async () => {
  let refreshes = 0;
  const client = createClient({
    storage: storage(),
    fetcher: async (url) => {
      if (url.endsWith("/auth/login")) return response(pair);
      if (url.endsWith("/auth/refresh")) refreshes++;
      return response(
        { error: { code: "REFRESH_TOKEN_INVALID", message: "Sign in again." } },
        401,
      );
    },
  });
  await client.login("a", "b");
  await assert.rejects(client.request("/me"), ApiError);
  assert.equal(refreshes, 1);
  assert.equal(client.hasSession(), false);
});
test("logout clears local tokens even when server is unavailable", async () => {
  const client = createClient({
    storage: storage(),
    fetcher: async (url) =>
      url.endsWith("/auth/login") ? response(pair) : response({}, 500),
  });
  await client.login("a", "b");
  await assert.rejects(client.logout());
  assert.equal(client.hasSession(), false);
});
test("lists include all pages and malformed pages fail", async () => {
  const offsets = [];
  const client = createClient({
    fetcher: async (url) => {
      const offset = Number(
        new URL(url, "http://test").searchParams.get("offset"),
      );
      offsets.push(offset);
      return response({
        items: Array(offset ? 1 : 100).fill({ id: "x" }),
        total: 101,
      });
    },
  });
  assert.equal((await client.all("/events?q=demo")).length, 101);
  assert.deepEqual(offsets, [0, 100]);
  const invalid = createClient({
    fetcher: async () => response({ items: [], total: 10 }),
  });
  await assert.rejects(invalid.all("/events"), /incomplete/);
});
test("mutation errors retain server message, code and validation details", async () => {
  const client = createClient({
    fetcher: async () =>
      response(
        {
          error: {
            message: "Sold out.",
            code: "SOLD_OUT",
            details: { remaining: 0 },
          },
        },
        409,
      ),
  });
  await assert.rejects(
    client.request("/events/e/orders", { method: "POST", body: {} }),
    (error) =>
      error.message === "Sold out." &&
      error.code === "SOLD_OUT" &&
      error.details.remaining === 0,
  );
});
test("FormData uploads keep their multipart boundary and authenticated downloads use bearer token", async () => {
  let checked = false;
  const client = createClient({
    fetcher: async (url, options) => {
      if (url.endsWith("/auth/login")) return response(pair);
      assert.equal(options.headers.Authorization, "Bearer old");
      assert.equal(options.headers["Content-Type"], undefined);
      checked = true;
      return response({ id: "image" });
    },
  });
  await client.login("a", "b");
  const body = new FormData();
  body.append("file", new Blob(["image"]), "image.png");
  await client.request("/events/e/images", { method: "POST", body });
  assert.equal(checked, true);
});

test("suspension clears the session without a refresh attempt", async () => {
  const client = createClient({
    storage: storage(),
    fetcher: async (url) =>
      url.endsWith("/auth/login")
        ? response(pair)
        : response(
            {
              error: {
                code: "ACCOUNT_SUSPENDED",
                message: "Account suspended.",
              },
            },
            403,
          ),
  });
  await client.login("a", "b");
  await assert.rejects(
    client.request("/me"),
    (error) => error.code === "ACCOUNT_SUSPENDED",
  );
  assert.equal(client.hasSession(), false);
});
