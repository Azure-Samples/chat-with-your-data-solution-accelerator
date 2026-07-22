import { describe, expect, it } from "vitest";
import { formatCitationLabel } from "@/pages/chat/components/CitationPanel/CitationPanel";

describe("formatCitationLabel", () => {
  it("returns a short label unchanged", () => {
    expect(formatCitationLabel("Benefit_Options.pdf")).toBe(
      "Benefit_Options.pdf",
    );
  });

  it("returns an empty label unchanged", () => {
    expect(formatCitationLabel("")).toBe("");
  });

  it("passes a label exactly at the 50-char threshold through verbatim", () => {
    const exact = "a".repeat(50);
    expect(exact).toHaveLength(50);
    expect(formatCitationLabel(exact)).toBe(exact);
  });

  it("middle-truncates a label longer than the threshold", () => {
    const long =
      "Woodgrove-Insurance_2024_Long_Benefits_Concepts_For_Employees.pdf - Part 1";
    const result = formatCitationLabel(long);
    expect(result).toBe(
      `${long.slice(0, 20)}...${long.slice(-20)}`,
    );
    expect(result.length).toBeLessThan(long.length);
  });

  it("keeps the meaningful tail of a long label visible", () => {
    const long =
      "Woodgrove-Insurance_2024_Long_Benefits_Concepts_For_Employees.pdf - Part 1";
    // The tail carries the part suffix the user needs to disambiguate chunks.
    expect(formatCitationLabel(long).endsWith("- Part 1")).toBe(true);
  });

  it("inserts the ellipsis between the head and tail segments", () => {
    const long = `${"H".repeat(30)}${"T".repeat(30)}`;
    expect(formatCitationLabel(long)).toBe(
      `${"H".repeat(20)}...${"T".repeat(20)}`,
    );
  });
});
