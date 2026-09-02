import { describe, expect, it } from "vitest";
import { estimateErrorRatio, formatCount, formatMs, relationLabel, severityRank, sortFindingsBySeverity } from "./format";

describe("severityRank", () => {
  it("orders high > medium > low > info", () => {
    expect(severityRank("high")).toBeGreaterThan(severityRank("medium"));
    expect(severityRank("medium")).toBeGreaterThan(severityRank("low"));
    expect(severityRank("low")).toBeGreaterThan(severityRank("info"));
  });

  it("treats unknown severities as 0", () => {
    expect(severityRank("nonsense")).toBe(0);
  });
});

describe("sortFindingsBySeverity", () => {
  it("sorts by severity rank, then score, descending", () => {
    const findings = [
      { severity: "low", score: 999 },
      { severity: "high", score: 1 },
      { severity: "high", score: 50 },
      { severity: "medium", score: 10 },
    ];
    const sorted = sortFindingsBySeverity(findings);
    expect(sorted.map((f) => f.severity)).toEqual(["high", "high", "medium", "low"]);
    expect(sorted[0].score).toBe(50); // higher score wins within same severity
  });

  it("does not mutate the input array", () => {
    const findings = [{ severity: "low", score: 1 }, { severity: "high", score: 1 }];
    const copy = [...findings];
    sortFindingsBySeverity(findings);
    expect(findings).toEqual(copy);
  });
});

describe("formatMs", () => {
  it("formats sub-second values in ms", () => {
    expect(formatMs(12.345)).toBe("12.35 ms");
  });

  it("formats values over 1000ms in seconds", () => {
    expect(formatMs(2500)).toBe("2.50 s");
  });

  it("handles non-numeric input gracefully", () => {
    expect(formatMs(undefined)).toBe("-");
    expect(formatMs("not a number")).toBe("-");
    expect(formatMs(NaN)).toBe("-");
  });

  it("treats null as 0 (a common 'field absent' sentinel in EXPLAIN JSON)", () => {
    expect(formatMs(null)).toBe("0.00 ms");
  });
});

describe("formatCount", () => {
  it("adds thousands separators", () => {
    expect(formatCount(50000)).toBe((50000).toLocaleString());
  });
});

describe("relationLabel", () => {
  it("prefers relation + alias when they differ", () => {
    expect(relationLabel({ relation: "orders", alias: "o" })).toBe("orders o");
  });

  it("omits the alias when it matches the relation name", () => {
    expect(relationLabel({ relation: "orders", alias: "orders" })).toBe("orders");
  });

  it("falls back to index name, then a generic label", () => {
    expect(relationLabel({ index_name: "orders_pkey" })).toBe("index orders_pkey");
    expect(relationLabel({})).toBe("plan node");
  });
});

describe("estimateErrorRatio", () => {
  it("is 0 when there is no estimate to compare against", () => {
    expect(estimateErrorRatio({ plan_rows: 0, actual_rows: 100 })).toBe(0);
  });

  it("computes the worse-case ratio in either direction", () => {
    expect(estimateErrorRatio({ plan_rows: 10, actual_rows: 1000 })).toBe(100);
    expect(estimateErrorRatio({ plan_rows: 1000, actual_rows: 10 })).toBe(100);
  });
});
