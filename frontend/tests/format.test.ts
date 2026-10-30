import { describe, expect, it } from "vitest";
import { kickoffTime, marketLabel, shiftDay, statusLabel } from "../lib/format";

describe("timezone handling", () => {
  it("converts UTC kickoffs to Oslo across the DST change (last Sunday of October)", () => {
    expect(kickoffTime("2026-10-24T18:00:00Z", "Europe/Oslo")).toBe("20:00"); // CEST, UTC+2
    expect(kickoffTime("2026-10-31T18:00:00Z", "Europe/Oslo")).toBe("19:00"); // CET, UTC+1
  });
  it("shows MLS evening kickoffs on the correct local day", () => {
    expect(kickoffTime("2026-11-01T00:30:00Z", "America/New_York")).toBe("20:30");
  });
  it("shifts calendar days without DST drift", () => {
    expect(shiftDay("2026-10-25", 1)).toBe("2026-10-26");
    expect(shiftDay("2026-03-01", -1)).toBe("2026-02-28");
  });
});

describe("labels", () => {
  it("marks postponed and live correctly", () => {
    expect(statusLabel("PST", null)).toEqual({ text: "Postponed", tone: "void" });
    expect(statusLabel("2H", 67).tone).toBe("live");
    expect(statusLabel("FT", 90).tone).toBe("final");
  });
  it("never uses guarantee language", () => {
    const l = [marketLabel("1X2", "1", "A", "B"), marketLabel("OU2.5", "Over"), marketLabel("BTTS", "Yes")].join(" ").toLowerCase();
    expect(l).not.toMatch(/guarantee|sure|safe/);
  });
});
