import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import CasesPage from "./CasesPage";

vi.mock("../api/client", () => ({
  default: {
    get: vi.fn(),
  },
}));

import api from "../api/client";

test("renders only cases returned by the API and an empty state", async () => {
  api.get.mockResolvedValue({ data: [] });
  render(
    <MemoryRouter>
      <CasesPage />
    </MemoryRouter>
  );
  await waitFor(() => {
    expect(screen.getByText(/No cases are visible for your account/i)).toBeInTheDocument();
  });
  expect(api.get).toHaveBeenCalledWith("/api/cases", { params: {} });
});

test("shows access and owner columns for authorized cases", async () => {
  api.get.mockResolvedValue({
    data: [
      {
        id: "case-1",
        case_identifier: "OWN-001",
        patient_identifier: "SYNTH-1",
        imaging_modality: "CTA",
        analysis_status: "created",
        current_access: "owner",
        owner_full_name: "Test User",
      },
    ],
  });
  render(
    <MemoryRouter>
      <CasesPage />
    </MemoryRouter>
  );
  await waitFor(() => {
    expect(screen.getByText("OWN-001")).toBeInTheDocument();
  });
  expect(screen.getByText("owner")).toBeInTheDocument();
  expect(screen.getByText("Test User")).toBeInTheDocument();
});

test("shows an API error and stops the loading state when case loading fails", async () => {
  api.get.mockRejectedValue({ response: { data: { detail: "Cases unavailable" } } });
  render(
    <MemoryRouter>
      <CasesPage />
    </MemoryRouter>
  );
  expect(screen.getByRole("status")).toHaveTextContent("Working...");
  await waitFor(() => expect(screen.getByText("Cases unavailable")).toBeInTheDocument());
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});
