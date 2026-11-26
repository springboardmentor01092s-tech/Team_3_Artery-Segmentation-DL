import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import App from "./App";
import { useAuth } from "./hooks/useAuth";

vi.mock("./hooks/useAuth", () => ({ useAuth: vi.fn() }));
vi.mock("./pages/AdminAuditPage", () => ({ default: () => <p>Audit route content</p> }));
vi.mock("./pages/AdminUsersPage", () => ({ default: () => <p>Users route content</p> }));
vi.mock("./pages/AnalysisHistoryPage", () => ({ default: () => <p>History route content</p> }));
vi.mock("./pages/CaseDetailPage", () => ({ default: () => <p>Case detail route content</p> }));
vi.mock("./pages/CasesPage", () => ({ default: () => <p>Cases route content</p> }));
vi.mock("./pages/CreateCasePage", () => ({ default: () => <p>Create case route content</p> }));
vi.mock("./pages/DashboardPage", () => ({ default: () => <p>Dashboard route content</p> }));
vi.mock("./pages/DatasetPage", () => ({ default: () => <p>Dataset route content</p> }));
vi.mock("./pages/LoginPage", () => ({ default: () => <p>Login route content</p> }));
vi.mock("./pages/ImageUploadPage", () => ({ default: () => <p>Upload route content</p> }));
vi.mock("./pages/ModelComparisonPage", () => ({ default: () => <p>Models route content</p> }));
vi.mock("./pages/PreprocessPage", () => ({ default: () => <p>Preprocess route content</p> }));
vi.mock("./pages/ProfilePage", () => ({ default: () => <p>Profile route content</p> }));
vi.mock("./pages/ReportsPage", () => ({ default: () => <p>Reports route content</p> }));
vi.mock("./pages/RegisterPage", () => ({ default: () => <p>Register route content</p> }));

let session;

beforeEach(() => {
  session = {
    loading: false,
    isAuthenticated: true,
    user: { role: "researcher", full_name: "Test User", permissions: ["image:upload", "image:preprocess"] },
    logout: vi.fn(),
  };
  useAuth.mockImplementation(() => session);
});

function renderApp(path) {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

test("mounts admin nested routes and shows admin navigation only for administrators", () => {
  session.user.role = "administrator";
  renderApp("/admin/audit");
  expect(screen.getByText("Audit route content")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "User management" })).toHaveAttribute("href", "/admin/users");
  expect(screen.getByRole("link", { name: "Audit logs" })).toHaveAttribute("href", "/admin/audit");
  expect(screen.getByRole("link", { name: "Dataset inspection" })).toHaveAttribute("href", "/dataset");
});

test("blocks admin and dataset routes for roles without those permissions", () => {
  const { unmount } = renderApp("/admin/users");
  expect(screen.getByText("Dashboard route content")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "User management" })).not.toBeInTheDocument();
  unmount();

  renderApp("/dataset");
  expect(screen.getByText("Dashboard route content")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Dataset inspection" })).not.toBeInTheDocument();
});

test("allows data scientists to access the dataset route but not admin routes", () => {
  session.user.role = "data_scientist";
  const { unmount } = renderApp("/dataset");
  expect(screen.getByText("Dataset route content")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Dataset inspection" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "User management" })).not.toBeInTheDocument();
  unmount();

  renderApp("/admin/audit");
  expect(screen.getByText("Dashboard route content")).toBeInTheDocument();
});

test("redirects unauthenticated and unknown routes through the configured defaults", () => {
  session.isAuthenticated = false;
  renderApp("/cases");
  expect(screen.getByText("Login route content")).toBeInTheDocument();
});

test("keeps the static new-case route distinct from a case-id route and redirects unknown paths", () => {
  const { unmount } = renderApp("/cases/new");
  expect(screen.getByText("Create case route content")).toBeInTheDocument();
  unmount();

  renderApp("/not-a-route");
  expect(screen.getByText("Dashboard route content")).toBeInTheDocument();
});

test("mounts the new upload, history, reports, and model comparison routes in the app shell", () => {
  const routes = [
    ["/upload", "Upload route content", "Image upload"],
    ["/history", "History route content", "Analysis history"],
    ["/reports", "Reports route content", "Reports"],
    ["/models", "Models route content", "Model comparison"],
  ];
  for (const [path, content, label] of routes) {
    const { unmount } = renderApp(path);
    expect(screen.getByText(content)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: label })).toHaveAttribute("href", path);
    unmount();
  }
});
