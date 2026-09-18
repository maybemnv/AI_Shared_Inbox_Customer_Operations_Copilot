import { expect, test } from "@playwright/test";

import { isLocalApiUrl } from "../lib/api";

test("fixture runtime boundary recognizes loopback URL forms", () => {
  expect(isLocalApiUrl("http://[::1]:8103")).toBe(true);
  expect(isLocalApiUrl("https://api.example.com")).toBe(false);
});
