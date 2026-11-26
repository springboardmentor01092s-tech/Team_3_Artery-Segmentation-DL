import { afterEach, expect, test, vi } from "vitest";
import api from "./client";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

test("attaches the persisted bearer token to requests", async () => {
  localStorage.setItem("artery_auth", JSON.stringify({ accessToken: "token-abc" }));
  let sentConfig;
  const response = await api.get("/probe", {
    adapter: async (config) => {
      sentConfig = config;
      return { data: { ok: true }, status: 200, statusText: "OK", headers: {}, config };
    },
  });
  expect(response.data).toEqual({ ok: true });
  expect(sentConfig.headers.Authorization).toBe("Bearer token-abc");
});

test("clears malformed persisted auth and continues the request without a token", async () => {
  localStorage.setItem("artery_auth", "not-json");
  let sentConfig;
  await api.get("/public-probe", {
    adapter: async (config) => {
      sentConfig = config;
      return { data: { ok: true }, status: 200, statusText: "OK", headers: {}, config };
    },
  });
  expect(sentConfig.headers.Authorization).toBeUndefined();
  expect(localStorage.getItem("artery_auth")).toBeNull();
});

test("clears a stale token after an unauthorized API response", async () => {
  localStorage.setItem("artery_auth", JSON.stringify({ accessToken: "expired-token" }));
  const adapter = async (config) => {
    const error = new Error("Unauthorized");
    error.config = config;
    error.response = { status: 401, data: { detail: "Invalid token" }, config };
    throw error;
  };
  await expect(api.get("/private-probe", { adapter })).rejects.toMatchObject({
    response: { status: 401 },
  });
  expect(localStorage.getItem("artery_auth")).toBeNull();
});
