import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import api from "../api/client";
import ReportsPage from "./ReportsPage";

vi.mock("../api/client", () => ({ default: { get: vi.fn() } }));

beforeEach(() => {
  api.get.mockReset();
  api.get.mockImplementation(async (path) => {
    if (path === "/api/cases") return { data: [{ id: "case-1", case_identifier: "CARD-1", imaging_modality: "XCA", analysis_status: "segmentation_completed", latest_image: { width: 512, height: 512, format: "PNG" } }] };
    if (path.endsWith("/reports/csv")) return { data: new Blob(["case_identifier\nCARD-1"]) };
    throw new Error(`Unexpected ${path}`);
  });
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:report") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
});

test("downloads the selected case report from the real API endpoint", async () => {
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const schedule = vi.spyOn(window, "setTimeout");
  render(<MemoryRouter><ReportsPage /></MemoryRouter>);
  expect(await screen.findByText(/CARD-1 · 512 × 512 PNG/)).toBeInTheDocument();
  fireEvent.click(screen.getAllByRole("button", { name: "Download" })[1]);
  await waitFor(() => expect(api.get).toHaveBeenCalledWith("/api/cases/case-1/reports/csv", { responseType: "blob" }));
  expect(await screen.findByText("CSV report download started.")).toBeInTheDocument();
  expect(click).toHaveBeenCalledOnce();
  expect(schedule).toHaveBeenCalledWith(expect.any(Function), 1000);
});

test("reports case loading errors instead of fabricating exports", async () => {
  api.get.mockRejectedValueOnce(new Error("offline"));
  render(<MemoryRouter><ReportsPage /></MemoryRouter>);
  expect(await screen.findByText(/Accessible cases could not be loaded/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Download" })).not.toBeInTheDocument();
});
