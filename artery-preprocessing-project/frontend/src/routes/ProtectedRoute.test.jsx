import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import ProtectedRoute from "./ProtectedRoute";

vi.mock("../hooks/useAuth", () => ({ useAuth: vi.fn() }));
import { useAuth } from "../hooks/useAuth";

function renderRoutes(path = "/private") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<p>Login route</p>} />
        <Route path="/dashboard" element={<p>Dashboard route</p>} />
        <Route element={<ProtectedRoute roles={["administrator"]} />}>
          <Route path="/private" element={<p>Administrator content</p>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => vi.clearAllMocks());

test("shows a loading state while session verification is pending", () => {
  useAuth.mockReturnValue({ loading: true, isAuthenticated: false, user: null });
  renderRoutes();
  expect(screen.getByText("Checking session...")).toBeInTheDocument();
  expect(screen.queryByText("Administrator content")).not.toBeInTheDocument();
});

test("redirects unauthenticated users to login", () => {
  useAuth.mockReturnValue({ loading: false, isAuthenticated: false, user: null });
  renderRoutes();
  expect(screen.getByText("Login route")).toBeInTheDocument();
});

test("redirects authenticated users without the required role", () => {
  useAuth.mockReturnValue({
    loading: false, isAuthenticated: true, user: { role: "researcher" },
  });
  renderRoutes();
  expect(screen.getByText("Dashboard route")).toBeInTheDocument();
});

test("renders protected content for an authorized role", () => {
  useAuth.mockReturnValue({
    loading: false, isAuthenticated: true, user: { role: "administrator" },
  });
  renderRoutes();
  expect(screen.getByText("Administrator content")).toBeInTheDocument();
});
