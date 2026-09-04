import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { analyzeBatchLog, analyzePlan, ApiError, comparePlans, fetchHistory } from "./api";

describe("analyzePlan", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("wraps a network failure in an ApiError with a helpful message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch")))
    );

    await expect(analyzePlan('{"Plan": {}}', "select 1")).rejects.toBeInstanceOf(ApiError);
    await expect(analyzePlan('{"Plan": {}}', "select 1")).rejects.toThrow(/Is the backend running/);
  });

  it("surfaces the server's error detail on a non-2xx response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 400,
          statusText: "Bad Request",
          json: () => Promise.resolve({ detail: "The plan is empty." }),
        })
      )
    );

    await expect(analyzePlan("", null)).rejects.toThrow("The plan is empty.");
  });

  it("sends the plan as parsed JSON when it is valid JSON text", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ id: "abc" }),
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await analyzePlan('{"Plan": {"Node Type": "Seq Scan"}}', "select 1");

    const [, options] = fetchMock.mock.calls[0];
    const sentBody = JSON.parse(options.body);
    expect(sentBody.plan).toEqual({ Plan: { "Node Type": "Seq Scan" } });
  });
});

describe("comparePlans", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts baseline and current plans to /compare", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ verdict: "unchanged" }),
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await comparePlans(
      { planText: '{"Plan": {"Node Type": "Seq Scan"}}', query: "select 1", label: null },
      { planText: '{"Plan": {"Node Type": "Index Scan"}}', query: "select 1", label: null }
    );

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/compare$/);
    const sentBody = JSON.parse(options.body);
    expect(sentBody.baseline.plan).toEqual({ Plan: { "Node Type": "Seq Scan" } });
    expect(sentBody.current.plan).toEqual({ Plan: { "Node Type": "Index Scan" } });
  });
});

describe("analyzeBatchLog", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts log text to /analyze/batch", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ entries_found: 0, results: [], parse_errors: [] }),
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await analyzeBatchLog("duration: 1.0 ms  plan:\n  {}");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/analyze\/batch$/);
    expect(JSON.parse(options.body)).toEqual({ log_text: "duration: 1.0 ms  plan:\n  {}", save: false });
  });
});

describe("fetchHistory", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("includes a fingerprint filter in the query string when provided", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [], total: 0 }),
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchHistory({ limit: 10, offset: 0, fingerprint: "abc123" });

    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("fingerprint=abc123");
  });

  it("omits the fingerprint param when not provided", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [], total: 0 }),
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchHistory({ limit: 10, offset: 0 });

    const [url] = fetchMock.mock.calls[0];
    expect(url).not.toContain("fingerprint");
  });
});
