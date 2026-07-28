import { describe, expect, it } from "vitest";
import { formatSegmentMinutes, formatTotalDuration } from "./formatDuration";

describe("formatTotalDuration", () => {
  it("shows only minutes when under an hour", () => {
    expect(formatTotalDuration(45)).toBe("45分鐘");
  });

  it("shows hours and minutes when over an hour", () => {
    expect(formatTotalDuration(185)).toBe("3小時5分鐘");
  });

  it("omits minutes when exactly on the hour", () => {
    expect(formatTotalDuration(120)).toBe("2小時");
  });
});

describe("formatSegmentMinutes", () => {
  it("zero-pads single-digit minutes", () => {
    expect(formatSegmentMinutes(5)).toBe("05分");
  });

  it("keeps two-digit minutes as-is", () => {
    expect(formatSegmentMinutes(23)).toBe("23分");
  });
});
