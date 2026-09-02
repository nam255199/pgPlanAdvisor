import { beforeEach, describe, expect, it } from "vitest";
import { getApiKey, getSaveByDefault, setApiKey, setSaveByDefault } from "./settings";

beforeEach(() => {
  window.localStorage.clear();
});

describe("settings", () => {
  it("defaults to an empty API key", () => {
    expect(getApiKey()).toBe("");
  });

  it("round-trips an API key through localStorage", () => {
    setApiKey("sekret");
    expect(getApiKey()).toBe("sekret");
  });

  it("defaults save-by-default to false", () => {
    expect(getSaveByDefault()).toBe(false);
  });

  it("round-trips the save-by-default flag", () => {
    setSaveByDefault(true);
    expect(getSaveByDefault()).toBe(true);
    setSaveByDefault(false);
    expect(getSaveByDefault()).toBe(false);
  });
});
