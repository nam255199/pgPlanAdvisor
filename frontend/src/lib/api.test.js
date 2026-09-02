import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { analyzePlan, ApiError } from "./api";

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
