import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import api from "../api/client";
import AdminAuditPage from "./AdminAuditPage";

vi.mock("../api/client", () => ({ default: { get: vi.fn() } }));

beforeEach(() => api.get.mockReset());

test("shows loading feedback and renders audit events returned by the admin API", async () => {
  let finish;
  api.get.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
  render(<AdminAuditPage />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading audit logs...");
  finish({ data: [{ id: 1, created_at: "2026-11-24T12:00:00Z", action: "user.updated", resource_type: "user", resource_id: "7", actor_id: "2" }] });
  expect(await screen.findByText("user.updated")).toBeInTheDocument();
  expect(screen.getByText("user 7")).toBeInTheDocument();
  expect(screen.queryByText("Loading audit logs...")).not.toBeInTheDocument();
});

test("shows an API error and an explicit empty state", async () => {
  api.get.mockRejectedValueOnce({ response: { data: { detail: "Administrator access required" } } });
  const { unmount } = render(<AdminAuditPage />);
  expect(await screen.findByText("Administrator access required")).toBeInTheDocument();
  unmount();

  api.get.mockResolvedValueOnce({ data: [] });
  render(<AdminAuditPage />);
  expect(await screen.findByText("No audit events found.")).toBeInTheDocument();
});

test("refreshes audit records on request", async () => {
  api.get.mockResolvedValueOnce({ data: [] }).mockResolvedValueOnce({ data: [
    { id: 2, created_at: "2026-11-25T10:00:00Z", action: "case.shared", resource_type: "case", resource_id: "case-2", actor_id: "user-1" },
  ] });
  render(<AdminAuditPage />);
  expect(await screen.findByText("No audit events found.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Refresh audit logs" }));

  expect(await screen.findByText("case.shared")).toBeInTheDocument();
  expect(api.get).toHaveBeenCalledTimes(2);
});
