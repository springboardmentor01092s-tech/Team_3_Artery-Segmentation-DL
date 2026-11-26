import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import api from "../api/client";
import PreprocessPage from "./PreprocessPage";
import { useAuth } from "../hooks/useAuth";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock("../hooks/useAuth", () => ({ useAuth: vi.fn() }));

const caseDetail = {
  id: "case-1", case_identifier: "PRE-1", latest_image: {
    id: "image-1", format: "PNG", width: 64, height: 64, file_size: 100,
  },
};

beforeEach(() => {
  api.get.mockReset();
  api.post.mockReset();
  useAuth.mockReturnValue({ hasPermission: () => true });
  let history = [];
  api.get.mockImplementation(async (path) => {
    if (path === "/api/cases") return { data: [{ id: "case-1", case_identifier: "PRE-1" }] };
    if (path === "/api/cases/case-1") return { data: caseDetail };
    if (path === "/api/cases/case-1/preprocessing-history") return { data: history };
    if (path === "/api/cases/case-1/image" || path.startsWith("/api/cases/case-1/processed-image/")) {
      return { data: new Blob(["image"]) };
    }
    throw new Error(`Unexpected GET ${path}`);
  });
  api.post.mockImplementation(async (path, payload) => {
    expect(path).toBe("/api/cases/case-1/preprocess");
    history = [{ id: "run-1", status: "completed", processed_width: 64, processed_height: 64, duration_ms: 12 }];
    return { data: history[0], config: payload };
  });
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:preprocess") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("preprocesses the selected case, reloads history, and shows both image previews", async () => {
  render(
    <MemoryRouter initialEntries={["/preprocess?caseId=case-1"]}>
      <Routes><Route path="/preprocess" element={<PreprocessPage />} /></Routes>
    </MemoryRouter>
  );
  expect(await screen.findByText("Original Image")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Start preprocessing" }));
  expect(await screen.findByText(/Preprocessing completed/)).toBeInTheDocument();
  expect(await screen.findByAltText("Original")).toBeInTheDocument();
  expect(await screen.findByAltText("Preprocessed")).toBeInTheDocument();
  expect(api.post).toHaveBeenCalledWith("/api/cases/case-1/preprocess", expect.objectContaining({
    normalize: true, target_width: 512, target_height: 512, denoise_ksize: 3,
  }));
  expect(api.get).toHaveBeenCalledWith("/api/cases/case-1/image", { responseType: "blob" });
  expect(api.get).toHaveBeenCalledWith("/api/cases/case-1/processed-image/run-1", { responseType: "blob" });
});

test("shows explicit loading states while the case list and selected case are pending", () => {
  api.get.mockImplementation(() => new Promise(() => {}));
  render(
    <MemoryRouter initialEntries={["/preprocess?caseId=case-1"]}>
      <Routes><Route path="/preprocess" element={<PreprocessPage />} /></Routes>
    </MemoryRouter>
  );
  expect(screen.getByText("Loading cases...")).toBeInTheDocument();
  expect(screen.getByText("Loading case and preprocessing history...")).toBeInTheDocument();
});

test("shows server errors from the preprocessing API and restores the action button", async () => {
  api.post.mockRejectedValue({ response: { data: { detail: "Invalid preprocessing options" } } });
  render(
    <MemoryRouter initialEntries={["/preprocess?caseId=case-1"]}>
      <Routes><Route path="/preprocess" element={<PreprocessPage />} /></Routes>
    </MemoryRouter>
  );
  expect(await screen.findByText("Original Image")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Start preprocessing" }));
  expect(await screen.findByText("Invalid preprocessing options")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Start preprocessing" })).toBeEnabled();
});

test("disables preprocessing when the account lacks the backend operation permission", async () => {
  useAuth.mockReturnValue({ hasPermission: () => false });
  render(
    <MemoryRouter initialEntries={["/preprocess?caseId=case-1"]}>
      <Routes><Route path="/preprocess" element={<PreprocessPage />} /></Routes>
    </MemoryRouter>
  );
  expect(await screen.findByText("Original Image")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Start preprocessing" })).toBeDisabled();
  expect(api.post).not.toHaveBeenCalled();
});
