import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import api from "../api/client";
import DashboardPage from "./DashboardPage";

vi.mock("../api/client", () => ({ default: { get: vi.fn() } }));

const stats = (role, user_count = null) => ({
  role, user_count, case_count: 2, image_count: 3, preprocessing_count: 4,
  failed_preprocessing_count: 1, processed_case_count: 1, pending_case_count: 1,
  segmentation_analysis_count: 2, disclaimer: "Research outputs only.",
});

function renderDashboard() {
  return render(<MemoryRouter><DashboardPage /></MemoryRouter>);
}

beforeEach(() => {
  api.get.mockReset();
  api.get.mockImplementation(async (path) => {
    if (path === "/api/dashboard/stats") return { data: stats("researcher") };
    if (path === "/api/models/info") return { data: { available: false, message: "No checkpoint" } };
    if (path === "/api/analyses?limit=5") return { data: [] };
    if (path === "/api/cases") return { data: [] };
    if (path === "/api/models/compare") return { data: { models: [] } };
    throw new Error(`Unexpected GET ${path}`);
  });
});

test("shows current-scope dashboard totals and omits administrator-only user totals", async () => {
  renderDashboard();
  expect(await screen.findByText("Operational overview from records visible to your account.")).toBeInTheDocument();
  expect(screen.getAllByText("2", { selector: ".text-3xl" })).toHaveLength(2);
  expect(screen.getByText("Model unavailable. No checkpoint")).toBeInTheDocument();
  expect(screen.queryByText("Users")).not.toBeInTheDocument();
  expect(api.get).toHaveBeenCalledWith("/api/dashboard/stats");
});

test("includes the administrator user count when the backend provides it", async () => {
  api.get.mockImplementation(async (path) => {
    if (path === "/api/dashboard/stats") return { data: stats("administrator", 5) };
    if (path === "/api/models/info") return { data: { available: false } };
    if (path === "/api/analyses?limit=5") return { data: [] };
    if (path === "/api/cases") return { data: [] };
    if (path === "/api/models/compare") return { data: { models: [] } };
    throw new Error(`Unexpected GET ${path}`);
  });
  renderDashboard();
  expect(await screen.findByText("Users")).toBeInTheDocument();
  expect(screen.getByText("5", { selector: ".text-3xl" })).toBeInTheDocument();
});

test("shows recent cases returned by the authorized case API", async () => {
  api.get.mockImplementation(async (path) => {
    if (path === "/api/dashboard/stats") return { data: stats("researcher") };
    if (path === "/api/models/info") return { data: { available: false } };
    if (path === "/api/analyses?limit=5") return { data: [] };
    if (path === "/api/cases") return { data: [{ id: "case-1", case_identifier: "DEMO-1", imaging_modality: "CTA", current_access: "owner", analysis_status: "pending" }] };
    if (path === "/api/models/compare") return { data: { models: [] } };
    throw new Error(`Unexpected GET ${path}`);
  });
  renderDashboard();
  expect(await screen.findByRole("link", { name: "DEMO-1" })).toHaveAttribute("href", "/cases/case-1");
});

test("renders a dashboard statistics API error instead of a permanent spinner", async () => {
  api.get.mockImplementation(async (path) => {
    if (path === "/api/dashboard/stats") throw { response: { data: { detail: "Dashboard unavailable" } } };
    if (path === "/api/models/info") return { data: { available: false } };
    if (path === "/api/analyses?limit=5") return { data: [] };
    if (path === "/api/cases") return { data: [] };
    if (path === "/api/models/compare") return { data: { models: [] } };
    throw new Error(`Unexpected GET ${path}`);
  });
  renderDashboard();
  expect(await screen.findByText("Dashboard unavailable")).toBeInTheDocument();
  expect(screen.queryByText("Loading dashboard...")).not.toBeInTheDocument();
});

test("clears the previous protected validation preview while another image loads", async () => {
  let resolveFirst;
  let resolveSecond;
  api.get.mockImplementation((path) => {
    if (path === "/api/dashboard/stats") return Promise.resolve({ data: stats("researcher") });
    if (path === "/api/models/info") return Promise.resolve({ data: { available: true } });
    if (path === "/api/analyses?limit=5") return Promise.resolve({ data: [] });
    if (path === "/api/cases") return Promise.resolve({ data: [] });
    if (path === "/api/models/compare") return Promise.resolve({ data: { models: [] } });
    if (path === "/api/models/validation/examples") return Promise.resolve({ data: [
      { file_name: "one.png", label: "small_target", image_url: "/protected/one", metrics: { dice: 0.4, gt_pixels: 20, pred_pixels: 22 } },
      { file_name: "two.png", label: "large_target", image_url: "/protected/two", metrics: { dice: 0.5, gt_pixels: 40, pred_pixels: 42 } },
    ] });
    if (path === "/protected/one") return new Promise((resolve) => { resolveFirst = resolve; });
    if (path === "/protected/two") return new Promise((resolve) => { resolveSecond = resolve; });
    throw new Error(`Unexpected GET ${path}`);
  });
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:validation") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
  renderDashboard();
  const firstButton = await screen.findByRole("button", { name: /one\.png/ });
  await act(async () => resolveFirst({ data: new Blob(["one"]) }));
  expect(await screen.findByAltText(/one\.png/)).toBeInTheDocument();
  fireEvent.click(await screen.findByRole("button", { name: /two\.png/ }));
  expect(screen.queryByAltText(/one\.png/)).not.toBeInTheDocument();
  expect(screen.getByText("Loading protected validation comparison...")).toBeInTheDocument();
  await act(async () => resolveSecond({ data: new Blob(["two"]) }));
  expect(await screen.findByAltText(/two\.png/)).toBeInTheDocument();
  expect(firstButton).toBeInTheDocument();
  await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:validation"));
});
