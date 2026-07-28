import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SearchForm } from "./SearchForm";

const { stations } = vi.hoisted(() => ({
  stations: [{ station_id: "TRA_1000", name_zh: "台北", name_en: "Taipei", transport_mode: "tra" }],
}));

vi.mock("../services/api", () => ({
  getAllStations: vi.fn().mockResolvedValue(stations),
  searchRoutes: vi.fn().mockResolvedValue({ routes: [], alerts: [], cached: true, data_possibly_outdated: false }),
}));

async function selectStation(label: string, mode: string, stationId: string) {
  const modeSelect = await screen.findByRole("combobox", { name: `${label}運具` });
  fireEvent.change(modeSelect, { target: { value: mode } });
  const stationSelect = screen.getByRole("combobox", { name: `${label}站名` });
  fireEvent.change(stationSelect, { target: { value: stationId } });
}

describe("SearchForm", () => {
  it("shows required-field errors when submitting with empty origin/destination", async () => {
    const onResults = vi.fn();
    render(<SearchForm onResults={onResults} />);
    await screen.findByRole("combobox", { name: "起點運具" });

    fireEvent.click(screen.getByRole("button", { name: "查詢路線" }));

    expect(screen.getAllByText("此欄位為必填")).toHaveLength(2);
    expect(onResults).not.toHaveBeenCalled();
  });

  it("shows an error when origin and destination are the same station", async () => {
    const onResults = vi.fn();
    render(<SearchForm onResults={onResults} />);

    await selectStation("起點", "tra", "TRA_1000");
    await selectStation("終點", "tra", "TRA_1000");

    fireEvent.click(screen.getByRole("button", { name: "查詢路線" }));

    expect(screen.getAllByText("起點與終點不得相同")).toHaveLength(2);
    expect(onResults).not.toHaveBeenCalled();
  });
});
