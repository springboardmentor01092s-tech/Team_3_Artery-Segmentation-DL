import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import api from "../api/client";
import AdminUsersPage from "./AdminUsersPage";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), patch: vi.fn() } }));

let account;
beforeEach(() => {
  api.get.mockReset();
  api.patch.mockReset();
  account = { id: "user-1", full_name: "Research User", email: "research@example.org", role: "researcher", is_active: true };
  api.get.mockImplementation(async () => ({ data: [{ ...account }] }));
  api.patch.mockImplementation(async (_path, patch) => {
    account = { ...account, ...patch };
    return { data: { ...account } };
  });
});

test("loads users, updates a role and activation state, and refreshes the table", async () => {
  render(<AdminUsersPage />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading users...");
  const role = await screen.findByRole("combobox");
  await act(async () => fireEvent.change(role, { target: { value: "radiologist" } }));
  await waitFor(() => expect(role).toHaveValue("radiologist"));
  expect(api.patch).toHaveBeenCalledWith("/api/admin/users/user-1", { role: "radiologist" });

  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Deactivate" })));
  expect(await screen.findByRole("button", { name: "Activate" })).toBeInTheDocument();
  expect(api.patch).toHaveBeenLastCalledWith("/api/admin/users/user-1", { is_active: false });
  expect(api.get).toHaveBeenCalledTimes(3);
});

test("shows admin API errors and recovers after a successful reload", async () => {
  api.get.mockRejectedValueOnce({ response: { data: { detail: "Admin access required" } } });
  render(<AdminUsersPage />);
  expect(await screen.findByText("Admin access required")).toBeInTheDocument();
  api.get.mockResolvedValue({ data: [{ ...account }] });
  fireEvent.click(screen.getByRole("button", { name: "Reload users" }));
  expect(await screen.findByText("research@example.org")).toBeInTheDocument();
  expect(screen.queryByText("Admin access required")).not.toBeInTheDocument();
});
