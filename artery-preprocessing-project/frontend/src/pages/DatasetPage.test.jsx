import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import api from "../api/client";
import DatasetPage from "./DatasetPage";

vi.mock("../api/client", () => ({ default: { get: vi.fn() } }));

const summary = {
  directory: "sample-images", exists: true, supported_count: 0, unreadable_count: 0,
  formats: {}, note: "Sample image note.", sample_supported_count: 0, uploaded_supported_count: 0,
  sample: { directory: "sample-images", exists: true, supported_count: 0, unreadable_count: 0, formats: {}, note: "Empty." },
  uploaded: { directory: "uploads", exists: true, supported_count: 0, unreadable_count: 0, formats: {}, note: "No accessible uploads." },
  arcade: {
    root: "ARCADE", exists: true,
    tasks: {
      stenosis: {
        train: { image_count: 1000, annotation_status: "available", annotation_image_count: 1000, annotation_count: 2300, category_ids: [26], selection_eligible: true, note: "Training and validation annotations are reported separately." },
        val: { image_count: 200, annotation_status: "available", annotation_image_count: 200, annotation_count: 400, category_ids: [26], selection_eligible: true, note: "Validation only." },
        test: { image_count: 300, annotation_status: "not_inspected", annotation_image_count: null, annotation_count: null, category_ids: [], selection_eligible: false, note: "Test split is a holdout; its annotation file is not opened or used by this summary." },
      },
    },
  },
};

beforeEach(() => {
  api.get.mockReset();
  api.get.mockResolvedValue({ data: summary });
});

test("shows ARCADE task splits and clearly identifies test as an unopened holdout", async () => {
  render(<MemoryRouter><DatasetPage /></MemoryRouter>);
  expect(await screen.findByRole("heading", { name: "ARCADE dataset" })).toBeInTheDocument();
  expect(screen.getByRole("article", { name: "stenosis train split" })).toHaveTextContent("COCO annotations: 2300");
  expect(screen.getByRole("article", { name: "stenosis val split" })).toHaveTextContent("Image files: 200");
  const holdout = screen.getByRole("article", { name: "stenosis test split" });
  expect(holdout).toHaveTextContent("test (holdout)");
  expect(holdout).toHaveTextContent("Annotations: not inspected; excluded from model selection.");
});

test("shows dataset summary API errors", async () => {
  api.get.mockRejectedValueOnce({ response: { data: { detail: "Dataset summary unavailable." } } });
  render(<MemoryRouter><DatasetPage /></MemoryRouter>);
  expect(await screen.findByText("Dataset summary unavailable.")).toBeInTheDocument();
});
