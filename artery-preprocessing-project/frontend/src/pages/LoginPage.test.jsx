import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";
import { AuthProvider } from "../hooks/useAuth";
import LoginPage from "./LoginPage";
import api from "../api/client";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

beforeEach(() => {
  localStorage.clear();
  api.get.mockReset();
  api.post.mockReset();
});

test("login form renders required fields", () => {
  render(
    <MemoryRouter>
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    </MemoryRouter>
  );
  expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  expect(screen.getByLabelText("Email")).toBeInTheDocument();
  expect(screen.getByLabelText("Password")).toBeInTheDocument();
});

test("successful login fetches the profile and navigates to the dashboard", async () => {
  api.post.mockResolvedValue({ data: { access_token: "token-123" } });
  api.get.mockResolvedValue({ data: { id: "u1", role: "researcher", full_name: "Research User" } });
  render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<h1>Dashboard home</h1>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.org" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "Password123" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("heading", { name: "Dashboard home" })).toBeInTheDocument();
  expect(api.post).toHaveBeenCalledWith("/api/auth/login", { email: "user@example.org", password: "Password123" });
  expect(api.get).toHaveBeenCalledWith("/api/auth/me");
  expect(JSON.parse(localStorage.getItem("artery_auth")).user.full_name).toBe("Research User");
});

test("login surfaces server errors and re-enables the submit button", async () => {
  api.post.mockRejectedValue({ response: { data: { detail: "Invalid credentials" } } });
  render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthProvider><LoginPage /></AuthProvider>
    </MemoryRouter>
  );
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.org" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "bad" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByText("Invalid credentials")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled());
});
