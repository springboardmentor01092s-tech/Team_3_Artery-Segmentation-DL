import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import api from "../api/client";
import ModelComparisonPage from "./ModelComparisonPage";

vi.mock("../api/client", () => ({ default: { get: vi.fn() } }));

test("shows only available validation metrics and labels missing evaluations", async () => {
  api.get.mockImplementation(async (path) => path === "/api/models/info"
    ? { data: { available: true, active_checkpoint: "best.pth", architecture: "UNet", image_size: 256, threshold: 0.55 } }
    : { data: { comparison_note: "same split", models: [
      { name: "best.pth", resolved_architecture: "UNet", epoch: 4, validation_evaluation: { split: "stenosis/val", samples: 200, threshold: 0.55, metrics: { per_image_macro: { dice: 0.4, iou: 0.3, precision: 0.5, recall: 0.6 } } } },
      { name: "candidate.pth", resolved_architecture: "ResUNet", epoch: 2 },
    ] } });
  render(<ModelComparisonPage />);
  expect(await screen.findByRole("row", { name: /best\.pth/ })).toBeInTheDocument();
  expect(screen.getByText("0.4000")).toBeInTheDocument();
  expect(screen.getByText("No saved evaluation")).toBeInTheDocument();
  expect(screen.getAllByText("Not evaluated").length).toBeGreaterThan(0);
});

test("shows model API errors", async () => {
  api.get.mockRejectedValue(new Error("offline"));
  render(<ModelComparisonPage />);
  expect(await screen.findByText(/Model comparison data could not be loaded/)).toBeInTheDocument();
});
