import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";

function rgb(value) {
  const match = value.match(/^rgb\((\d+),\s*(\d+),\s*(\d+)\)$/);
  assert.ok(match, `Expected resolved opaque RGB color, got ${value}`);
  return match.slice(1).map(Number);
}
function luminance(color) {
  return color
    .map((c) => {
      c /= 255;
      return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    })
    .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);
}
function contrast(a, b) {
  const x = luminance(rgb(a)),
    y = luminance(rgb(b));
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

test("rendered seat states retain AA text and control boundary contrast", () => {
  const css = readFileSync(
    new URL("../src/pages/ProductApp.css", import.meta.url),
    "utf8",
  );
  const dom = new JSDOM(
    `<style>${css}</style><div class="bf-spatial-seats">${["available", "selected", "held", "sold", "unavailable"].map((s) => `<label data-state="${s}">${s}</label>`).join("")}</div>`,
  );
  try {
    for (const label of dom.window.document.querySelectorAll("label")) {
      const style = dom.window.getComputedStyle(label);
      assert.ok(
        contrast(style.color, style.backgroundColor) >= 4.5,
        `${label.dataset.state} text contrast`,
      );
      assert.ok(
        contrast(style.borderTopColor, style.backgroundColor) >= 3,
        `${label.dataset.state} boundary contrast`,
      );
    }
  } finally {
    dom.window.close();
  }
});
