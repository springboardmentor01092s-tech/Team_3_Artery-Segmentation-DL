import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import api from "../api/client";
import { useAuth } from "../hooks/useAuth";
import CaseDetailPage from "./CaseDetailPage";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));
vi.mock("../hooks/useAuth", () => ({ useAuth: vi.fn() }));

const caseItem = {
  id: "case-1", case_identifier: "CASE-1", patient_identifier: "SYNTH-1",
  imaging_modality: "CTA", analysis_status: "uploaded", current_access: "owner",
  owner_full_name: "Owner", latest_image: {
    id: "image-1", original_filename: "angiogram.png", format: "PNG", width: 64, height: 64, file_size: 100,
  },
};
const analysis = {
  id: "analysis-1", created_at: "2026-01-01T00:00:00Z", model_name: "baseline.pth",
  model: { architecture: "legacy_unet", image_size: 256 }, candidate_count: 1,
  foreground_pixels: 12, threshold: 0.55,
  image_calibration: {
    status: "reported_valid_values", source: "DICOM PixelSpacing",
    row_spacing_mm_per_pixel: 0.3, column_spacing_mm_per_pixel: 0.25,
    calibration_type: "GEOMETRY", used_for_measurement: false,
    reason: "Reported only; not clinically validated for lumen measurement.",
    calibration_verified: false, transform_verified: false,
  },
  diameter_measurement: {
    measurement_status: "unavailable", reference_vessel_diameter_px: null,
    minimum_lumen_diameter_px: null, reference_vessel_diameter_mm: null,
    minimum_lumen_diameter_mm: null, stenosis_percentage: null,
    quality: "unavailable", reason: "No validated lumen mask or calibration is available.",
  },
  artifacts: {
    mask: "/api/analyses/analysis-1/artifacts/mask",
    overlay: "/api/analyses/analysis-1/artifacts/overlay",
    boxes: "/api/analyses/analysis-1/artifacts/boxes",
    heatmap: "/api/analyses/analysis-1/artifacts/heatmap",
  },
  candidates: [{ id: 1, x: 2, y: 3, width: 10, height: 12, pixel_area: 12, mean_predicted_probability: 0.8 }],
};

function renderPage(path = "/cases/case-1") {
  const utils = render(
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path="/cases/:caseId" element={<CaseDetailPage />} /></Routes>
    </MemoryRouter>
  );
  return utils;
}

test("opens and highlights the selected analysis from a history link", async () => {
  renderPage("/cases/case-1?analysis=analysis-1");
  const selected = await screen.findByText(/Candidate 1: box/);
  expect(selected.closest("article")).toHaveAttribute("id", "analysis-analysis-1");
  expect(selected.closest("article")).toHaveClass("ring-2");
});

beforeEach(() => {
  api.get.mockReset();
  api.post.mockReset();
  api.patch.mockReset();
  api.delete.mockReset();
  useAuth.mockReturnValue({ user: { role: "researcher" }, hasPermission: () => true });
  api.get.mockImplementation(async (path) => {
    if (path === "/api/cases/case-1") return { data: caseItem };
    if (path === "/api/cases/case-1/preprocessing-history") return { data: [] };
    if (path === "/api/cases/case-1/analyses") return { data: [analysis] };
    if (path === "/api/cases/case-1/image" || path.startsWith("/api/analyses/analysis-1/artifacts/")) {
      return { data: new Blob(["image"] ) };
    }
    if (path.startsWith("/api/cases/case-1/reports/")) return { data: new Blob(["report"]) };
    throw new Error(`Unexpected GET ${path}`);
  });
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:test-image") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
});

afterEach(() => vi.restoreAllMocks());

test("shows analysis visualizations and candidate metadata, then downloads all report formats", async () => {
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  renderPage();
  expect(await screen.findByRole("heading", { name: "CASE-1" })).toBeInTheDocument();
  const diameterPanel = screen.getByRole("region", { name: "Diameter-based stenosis measurement" });
  expect(diameterPanel).toHaveTextContent("Reference vessel diameter: Unable to calculate");
  expect(diameterPanel).toHaveTextContent("Minimum lumen diameter: Unable to calculate");
  expect(diameterPanel).toHaveTextContent("Reference diameter (pixel estimate): Unable to calculate");
  expect(diameterPanel).toHaveTextContent("Minimum lumen diameter (pixel estimate): Unable to calculate");
  expect(diameterPanel).toHaveTextContent("Narrowing percentage: Unable to calculate");
  expect(diameterPanel).toHaveTextContent("Measurement location: Unable to calculate");
  const calibrationPanel = screen.getByRole("region", { name: "Image calibration metadata" });
  expect(calibrationPanel).toHaveTextContent("DICOM reports row/column PixelSpacing: 0.3 / 0.25 mm per pixel");
  expect(calibrationPanel).toHaveTextContent("not clinically validated for lumen measurement");
  expect(calibrationPanel).toHaveTextContent("Calibration verified: no");
  expect(calibrationPanel).toHaveTextContent("image transform verified: no");
  for (const alt of [
    "Binary mask from model output", "Overlay from model output",
    "Candidate boxes from model output", "Probability heatmap from model output",
  ]) expect(await screen.findByAltText(alt)).toBeInTheDocument();
  expect(screen.getByText(/Candidate 1: box 2, 3, 10×12/)).toBeInTheDocument();

  for (const format of ["pdf", "csv", "json"]) {
    fireEvent.click(screen.getByRole("button", { name: format.toUpperCase() }));
    await waitFor(() => expect(api.get).toHaveBeenCalledWith(
      `/api/cases/case-1/reports/${format}`, { responseType: "blob" }
    ));
  }
  expect(click).toHaveBeenCalledTimes(3);
});

test("requests optional Integrated Gradients attribution for a lesion analysis", async () => {
  api.post.mockResolvedValue({ data: {} });
  renderPage();
  await screen.findByRole("heading", { name: "CASE-1" });
  fireEvent.click(await screen.findByRole("button", { name: "Generate Integrated Gradients attribution" }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/api/analyses/analysis-1/explain"));
  expect(await screen.findByText(/attribution generated.*not clinical evidence/i)).toBeInTheDocument();
});

test("requests and displays a persisted ARCADE ground-truth comparison", async () => {
  const comparison = {
    dataset_split: "stenosis/train", image_id: 1, annotation_ids: [98], category_ids: [26],
    width: 512, height: 512, alignment_verified: true,
    metrics_semantics: "pixel overlap with lesion labels; not clinical stenosis metrics",
    checkpoint_matches_current: true, checkpoint_identity_verified: true,
    metrics: { dice: 0.65, iou: 0.48, precision: 0.49, recall: 0.96, tp: 2378, fp: 2413, fn: 92 },
    predicted_components: [{ candidate_id: 5, overlaps_ground_truth: true, ground_truth_overlap_pixels: 2378, predicted_pixels: 3100 },
      { candidate_id: 3, overlaps_ground_truth: false, ground_truth_overlap_pixels: 0, predicted_pixels: 597 }],
  };
  let saved = false;
  api.post.mockImplementation(async (path) => {
    if (path.endsWith("/ground-truth")) saved = true;
    return { data: {} };
  });
  const originalGet = api.get.getMockImplementation();
  api.get.mockImplementation(async (path, options) => {
    if (path === "/api/cases/case-1/analyses" && saved) {
      return { data: [{ ...analysis, ground_truth_comparison: comparison,
        artifacts: { ...analysis.artifacts, ground_truth_comparison: "/api/analyses/analysis-1/artifacts/ground_truth_comparison" } }] };
    }
    return originalGet(path, options);
  });
  renderPage();
  await screen.findByRole("heading", { name: "CASE-1" });
  fireEvent.click(await screen.findByRole("button", { name: "Compare with ARCADE train ground truth" }));
  expect(api.post).toHaveBeenCalledWith("/api/analyses/analysis-1/ground-truth");
  const region = await screen.findByRole("region", { name: "ARCADE ground-truth comparison" });
  expect(region).toHaveTextContent("image ID 1");
  expect(region).toHaveTextContent("annotation IDs 98");
  expect(region).toHaveTextContent("Dice 0.6500");
  expect(region).toHaveTextContent("Candidate 5: overlaps");
  expect(region).toHaveTextContent("Candidate 3: does not overlap");
  expect(await screen.findByAltText("Ground-truth / prediction comparison from model output")).toBeInTheDocument();
});

test("uploads an image and starts segmentation with visible progress/completion feedback", async () => {
  api.post.mockImplementation(async (path) => ({ data: path.endsWith("/analyze") ? {} : { ok: true } }));
  const { container } = renderPage();
  expect(await screen.findByRole("heading", { name: "CASE-1" })).toBeInTheDocument();
  const image = new File(["png"], "new-image.png", { type: "image/png" });
  fireEvent.change(container.querySelector('input[type="file"]'), { target: { files: [image] } });
  fireEvent.click(screen.getByRole("button", { name: "Upload" }));
  expect(await screen.findByText(/Image uploaded/)).toBeInTheDocument();
  expect(api.post).toHaveBeenCalledWith("/api/cases/case-1/upload", expect.any(FormData));

  fireEvent.click(screen.getByRole("button", { name: "Run lesion analysis" }));
  expect(await screen.findByText(/Lesion-region analysis completed/)).toBeInTheDocument();
  expect(api.post).toHaveBeenCalledWith("/api/cases/case-1/analyze");
});

test("runs the optional SYNTAX mode and shows pixel-width limitations and cross-sections", async () => {
  const experimental = {
    ...analysis,
    analysis_mode: "vessel_region_experimental",
    target_semantics: "union of annotated SYNTAX coronary artery segments; not a validated lumen boundary",
    region_component_count: 1,
    minimum_estimated_vessel_region_width_px: 8.5,
    width_unit: "pixel",
    width_measurements: [{ x: 12, y: 30, width_px: 8.5, vessel_axis_angle_degrees: 0 }],
    width_quality_notes: ["Pixel-only local widths."],
    artifacts: {
      mask: "/api/analyses/analysis-1/artifacts/mask",
      overlay: "/api/analyses/analysis-1/artifacts/overlay",
      heatmap: "/api/analyses/analysis-1/artifacts/heatmap",
      centerline: "/api/analyses/analysis-1/artifacts/centerline",
      cross_sections: "/api/analyses/analysis-1/artifacts/cross_sections",
    },
    candidates: [],
  };
  api.get.mockImplementation(async (path) => {
    if (path === "/api/cases/case-1") return { data: caseItem };
    if (path === "/api/cases/case-1/preprocessing-history") return { data: [] };
    if (path === "/api/cases/case-1/analyses") return { data: [experimental] };
    if (path === "/api/cases/case-1/image" || path.startsWith("/api/analyses/analysis-1/artifacts/")) return { data: new Blob(["image"]) };
    throw new Error(`Unexpected GET ${path}`);
  });
  api.post.mockResolvedValue({ data: {} });
  renderPage();
  await screen.findByRole("heading", { name: "CASE-1" });
  fireEvent.change(screen.getByRole("combobox", { name: "Analysis mode" }), {
    target: { value: "vessel_region_experimental" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Run experimental vessel-region analysis" }));
  expect(await screen.findByText(/Experimental SYNTAX vessel-region analysis completed/)).toBeInTheDocument();
  expect(api.post).toHaveBeenCalledWith("/api/cases/case-1/analyze?mode=vessel_region_experimental");
  expect(await screen.findByRole("region", { name: "Experimental vessel-region widths" })).toHaveTextContent("8.5 px");
  expect(screen.getByText(/not lumen diameters/)).toBeInTheDocument();
  expect(await screen.findByAltText("Perpendicular width sections from model output")).toBeInTheDocument();
});
