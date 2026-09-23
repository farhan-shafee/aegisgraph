import { describe, expect, it } from "vitest";
import { runtimeCapabilities } from "./capabilities";

describe("versioned runtime capabilities", () => {
  it("hides absent, unknown and incompatible capabilities during staggered rollout", () => {
    for (const value of [
      null,
      {},
      { capabilities: null },
      { capabilities: [] },
    ])
      expect(runtimeCapabilities(value)).toEqual({});
    expect(
      runtimeCapabilities({
        capabilities: {
          replay: 1,
          hypotheses: 2,
          evidence_bundle: true,
          arbitrary: 1,
        },
      }),
    ).toEqual({ replay: 1 });
  });
});
