import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import api from "../api/client";
import CreateCasePage from "./CreateCasePage";

vi.mock("../api/client", () => ({ default: { post: vi.fn() } }));

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/cases/new"]}>
      <Routes>
        <Route path="/cases/new" element={<CreateCasePage />} />
        <Route path="/cases/:caseId" element={<p>Case detail route</p>} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => api.post.mockReset());

test("creates a case with normalized optional fields and opens its detail route", async () => {
  api.post.mockResolvedValue({ data: { id: "case-123" } });
  renderPage();
  fireEvent.change(screen.getByLabelText("Case ID"), { target: { value: "CASE-123" } });
  fireEvent.change(screen.getByLabelText("Pseudonymous patient ID"), { target: { value: "SYNTH-123" } });
  fireEvent.change(screen.getByLabelText("Age"), { target: { value: "54" } });
  fireEvent.click(screen.getByRole("button", { name: "Save case" }));
  expect(await screen.findByText("Case detail route")).toBeInTheDocument();
  const [, payload] = api.post.mock.calls[0];
  expect(payload).toMatchObject({
    case_identifier: "CASE-123", patient_identifier: "SYNTH-123", age: 54,
    scan_date: null, imaging_modality: "CTA",
  });
});

