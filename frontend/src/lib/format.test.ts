import { describe, expect, it } from "vitest";
import { AI_LABEL, PROVENANCE_LABEL, chunkHex, fmtBytes, fmtScore, pct, shareRef } from "./format";

describe("format helpers", () => {
  it("chunks a SHA-256 into 8 groups of 8", () => {
    const h = "a".repeat(64);
    expect(chunkHex(h)).toHaveLength(8);
    expect(chunkHex(h)[0]).toBe("aaaaaaaa");
  });
  it("builds share references from case ids", () => {
    expect(shareRef("0123456789abcdef0123456789abcdef")).toBe("VF-01234567-89AB");
  });
  it("formats sizes and percentages", () => {
    expect(fmtBytes(512)).toBe("512 B");
    expect(fmtBytes(2048)).toBe("2.0 KB");
    expect(pct(0.9531)).toBe("95.3%");
    expect(pct(null)).toBe("—");
  });
  it("never shows a model score as exactly 0 or 1", () => {
    expect(fmtScore(1)).toBe(">0.999");
    expect(fmtScore(0.0001)).toBe("<0.001");
    expect(fmtScore(0.6409)).toBe("0.641");
  });
  it("never labels missing provenance as fake", () => {
    expect(PROVENANCE_LABEL.NO_PROVENANCE_FOUND.text.toLowerCase()).not.toContain("fake");
    expect(PROVENANCE_LABEL.NO_PROVENANCE_FOUND.tone).toBe("neutral");
  });
  it("uses hedged AI wording", () => {
    for (const v of Object.values(AI_LABEL)) {
      expect(v.text.toLowerCase()).not.toMatch(/definitely|100%|real\b|fake/);
    }
  });
});
