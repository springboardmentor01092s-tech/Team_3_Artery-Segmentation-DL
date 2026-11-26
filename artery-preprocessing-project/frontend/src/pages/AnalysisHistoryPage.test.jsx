import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";
import api from "../api/client";
import AnalysisHistoryPage from "./AnalysisHistoryPage";

vi.mock("../api/client", () => ({ default: { get: vi.fn() } }));

test("loads access-scoped analysis history and filters by case text and mode", async () => {
  const records = [
    { id: "a1", case_id: "case-1", case_identifier: "CARD-01", created_at: "2026-01-01T00:00:00Z", model_name: "unet.pth", status: "completed", candidate_count: 2, analysis_mode: "lesion" },
    { id: "a2", case_id: "case-2", case_identifier: "CARD-02", created_at: "2026-01-02T00:00:00Z", model_name: "syntax.pth", status: "completed", candidate_count: 1, analysis_mode: "vessel_region_experimental" },
  ];
  api.get.mockImplementation(async (_path, { params }) => {
    const filtered = records.filter((record) =>
      (!params.search || record.case_identifier.includes(params.search))
      && (!params.mode || record.analysis_mode === params.mode));
    return { data: filtered.slice(params.offset, params.offset + params.limit), headers: { "x-total-count": String(filtered.length) } };
  });
  render(<MemoryRouter><AnalysisHistoryPage /></MemoryRouter>);
  expect(await screen.findByText("CARD-01")).toBeInTheDocument();
  expect(screen.getByText("CARD-02")).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: "Open analysis" })[0]).toHaveAttribute("href", "/cases/case-1?analysis=a1");
  fireEvent.change(screen.getByRole("textbox", { name: "Search history" }), { target: { value: "CARD-02" } });
  expect(await screen.findByText("CARD-02")).toBeInTheDocument();
  expect(screen.queryByText("CARD-01")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Analysis mode"), { target: { value: "lesion" } });
  expect(await screen.findByText(/No analyses match these filters/)).toBeInTheDocument();
  expect(api.get).toHaveBeenLastCalledWith("/api/analyses", { params: { limit: 25, offset: 0, search: "CARD-02", mode: "lesion" } });
});

test("shows an honest empty state and backend error", async () => {
  api.get.mockResolvedValueOnce({ data: [] });
  const { unmount } = render(<MemoryRouter><AnalysisHistoryPage /></MemoryRouter>);
  expect(await screen.findByText("No analyses yet")).toBeInTheDocument();
  unmount();
  api.get.mockRejectedValueOnce(new Error("unavailable"));
  render(<MemoryRouter><AnalysisHistoryPage /></MemoryRouter>);
  expect(await screen.findByText(/Analysis history could not be loaded/)).toBeInTheDocument();
});

test("paginates server results and requests the next offset", async () => {
  const pageOne = Array.from({ length: 25 }, (_, index) => ({ id: `a${index}`, case_id: "case-1", case_identifier: `CASE-${index}`, created_at: "2026-01-01T00:00:00Z", model_name: "unet.pth", status: "completed", candidate_count: 1, analysis_mode: "lesion" }));
  const pageTwo = [{ id: "a25", case_id: "case-1", case_identifier: "CASE-25", created_at: "2026-01-01T00:00:00Z", model_name: "unet.pth", status: "completed", candidate_count: 1, analysis_mode: "lesion" }];
  api.get.mockImplementation(async (_path, { params }) => ({
    data: params.offset === 0 ? pageOne : pageTwo,
    headers: { "x-total-count": "26" },
  }));
  render(<MemoryRouter><AnalysisHistoryPage /></MemoryRouter>);
  expect(await screen.findByText("CASE-0")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(await screen.findByText("CASE-25")).toBeInTheDocument();
  expect(api.get).toHaveBeenLastCalledWith("/api/analyses", { params: { limit: 25, offset: 25, search: undefined, mode: undefined } });
});
