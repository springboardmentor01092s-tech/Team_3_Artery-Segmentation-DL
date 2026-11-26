import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import api from "../api/client";
import ProfilePage from "./ProfilePage";

const { refresh } = vi.hoisted(() => ({ refresh: vi.fn() }));

vi.mock("../api/client", () => ({ default: { patch: vi.fn() } }));
vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({ user: { email: "researcher@example.test", role: "researcher", full_name: "Research User" }, refresh }),
}));

beforeEach(() => {
  api.patch.mockReset();
  refresh.mockReset();
  refresh.mockResolvedValue(undefined);
});

test("updates profile, refreshes the session, and clears the optional password", async () => {
  api.patch.mockResolvedValue({ data: {} });
  render(<ProfilePage />);

  fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Updated User" } });
  fireEvent.change(screen.getByLabelText("New password (optional)"), { target: { value: "long-password" } });
  fireEvent.click(screen.getByRole("button", { name: "Save profile" }));

  await waitFor(() => expect(api.patch).toHaveBeenCalledWith("/api/auth/me", { full_name: "Updated User", password: "long-password" }));
  expect(await screen.findByText("Profile updated.")).toBeInTheDocument();
  expect(refresh).toHaveBeenCalledOnce();
  expect(screen.getByLabelText("New password (optional)")).toHaveValue("");
});

test("shows the profile API error and re-enables the form", async () => {
  api.patch.mockRejectedValue({ response: { data: { detail: "Profile update denied" } } });
  render(<ProfilePage />);
  fireEvent.click(screen.getByRole("button", { name: "Save profile" }));
  expect(await screen.findByText("Profile update denied")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save profile" })).toBeEnabled();
  expect(refresh).not.toHaveBeenCalled();
});
