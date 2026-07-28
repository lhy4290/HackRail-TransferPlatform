import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RouteResults } from "./RouteResults";

describe("RouteResults", () => {
  it("shows '無可用路線' when there are no routes", () => {
    render(<RouteResults routes={[]} alerts={[]} selectedRouteId={null} onSelectRoute={vi.fn()} />);
    expect(screen.getByText("無可用路線")).toBeInTheDocument();
  });

  it("shows the backend-provided message instead of the default when given", () => {
    render(
      <RouteResults
        routes={[]}
        alerts={[]}
        selectedRouteId={null}
        onSelectRoute={vi.fn()}
        message="此運具路網資料尚未開放，暫無法查詢路線"
      />,
    );
    expect(screen.getByText("此運具路網資料尚未開放，暫無法查詢路線")).toBeInTheDocument();
  });
});
