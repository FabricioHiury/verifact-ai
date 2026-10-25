import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button } from "./ui/button";
import { requireData, timestamp, verdicts } from "./domain";
describe("UI contracts", () => {
  it("preserves times beyond one hour", () =>
    expect(timestamp(3661)).toBe("61:01"));
  it("never treats an API failure as analysis data", () =>
    expect(() =>
      requireData({ error: { error: { message: "Falha" } } }),
    ).toThrow());
  it("provides an explicit inconclusive label", () =>
    expect(verdicts.INCONCLUSIVE).toBe("Inconclusivo"));
  it("keeps disabled actions accessible", () => {
    render(<Button disabled>Retomar</Button>);
    expect(screen.getByRole("button", { name: "Retomar" })).toBeDisabled();
  });
});
