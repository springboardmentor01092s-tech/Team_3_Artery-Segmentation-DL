import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import api from "../api/client";
import { useAuth } from "../hooks/useAuth";
import ImageUploadPage from "./ImageUploadPage";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock("../hooks/useAuth", () => ({ useAuth: vi.fn() }));

beforeEach(() => {
  api.get.mockReset(); api.post.mockReset();
  useAuth.mockReturnValue({ hasPermission: () => true });
  api.get.mockResolvedValue({ data: [{ id: "case-1", case_identifier: "CARD-1", imaging_modality: "XCA" }] });
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:preview") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
});

test("validates, previews, and uploads a supported image to the selected case", async () => {
  api.post.mockResolvedValue({ data: { original_filename: "angiogram.png", width: 512, height: 512, format: "PNG" } });
  const { container } = render(<MemoryRouter><ImageUploadPage /></MemoryRouter>);
  expect(await screen.findByLabelText("Destination case")).toBeInTheDocument();
  const file = new File(["png"], "angiogram.png", { type: "image/png" });
  fireEvent.change(container.querySelector('input[type="file"]'), { target: { files: [file] } });
  expect(await screen.findByAltText("Local image preview before upload")).toHaveAttribute("src", "blob:preview");
  fireEvent.click(screen.getByRole("button", { name: "Upload to case" }));
  expect(await screen.findByText(/Uploaded angiogram.png/)).toBeInTheDocument();
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/api/cases/case-1/upload", expect.any(FormData)));
});

test("rejects unsupported files and disables upload without permission", async () => {
  useAuth.mockReturnValue({ hasPermission: () => false });
  const { container } = render(<MemoryRouter><ImageUploadPage /></MemoryRouter>);
  await screen.findByLabelText("Destination case");
  const file = new File(["text"], "bad.txt", { type: "text/plain" });
  fireEvent.change(container.querySelector('input[type="file"]'), { target: { files: [file] } });
  expect(await screen.findByText(/Choose a PNG, JPEG, or single-frame DICOM/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Upload to case" })).toBeDisabled();
  expect(api.post).not.toHaveBeenCalled();
});
