import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { getAllStations } from "../services/api";
import { StationModeSelect } from "./StationModeSelect";

const { stations } = vi.hoisted(() => ({
  stations: [
    { station_id: "KRTC_R16", name_zh: "左營", name_en: "Zuoying", transport_mode: "metro_kaohsiung" },
    { station_id: "TRA_4340", name_zh: "新左營", name_en: "Xinzuoying", transport_mode: "tra" },
    { station_id: "TRA_1000", name_zh: "台北", name_en: "Taipei", transport_mode: "tra" },
    { station_id: "THSR_1070", name_zh: "左營", name_en: "Zuoying", transport_mode: "thsr" },
  ],
}));

vi.mock("../services/api", () => ({
  getAllStations: vi.fn().mockResolvedValue(stations),
}));

describe("StationModeSelect", () => {
  it("only lists station options for the selected transport mode", async () => {
    const onChange = vi.fn();
    render(<StationModeSelect label="起點" onChange={onChange} />);

    const modeSelect = await screen.findByRole("combobox", { name: "起點運具" });
    fireEvent.change(modeSelect, { target: { value: "tra" } });

    const stationSelect = screen.getByRole("combobox", { name: "起點站名" });
    const options = Array.from(stationSelect.querySelectorAll("option")).map((o) => o.textContent);

    expect(options).toContain("台北 (Taipei)");
    expect(options).toContain("新左營 (Xinzuoying)");
    expect(options).not.toContain("左營 (Zuoying)");
  });

  it("disables the station select until a mode is chosen", async () => {
    render(<StationModeSelect label="終點" onChange={vi.fn()} />);
    await screen.findByRole("combobox", { name: "終點運具" });

    const stationSelect = screen.getByRole("combobox", { name: "終點站名" });
    expect(stationSelect).toBeDisabled();
  });

  it("calls onChange with the selected station id, and resets it when the mode changes", async () => {
    const onChange = vi.fn();
    render(<StationModeSelect label="起點" onChange={onChange} />);

    const modeSelect = await screen.findByRole("combobox", { name: "起點運具" });
    fireEvent.change(modeSelect, { target: { value: "tra" } });
    const stationSelect = screen.getByRole("combobox", { name: "起點站名" });
    fireEvent.change(stationSelect, { target: { value: "TRA_1000" } });

    expect(onChange).toHaveBeenLastCalledWith("TRA_1000");

    fireEvent.change(modeSelect, { target: { value: "thsr" } });
    expect(onChange).toHaveBeenLastCalledWith(null);
  });

  it("shows an error message and keeps the mode select disabled when the station fetch fails", async () => {
    vi.mocked(getAllStations).mockRejectedValueOnce(new Error("network error"));

    render(<StationModeSelect label="起點" onChange={vi.fn()} />);

    expect(await screen.findByText("站點資料載入失敗，請確認後端服務是否已啟動")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "起點運具" })).toBeDisabled();
  });
});
