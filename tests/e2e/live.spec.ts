import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("live local services: transcript, source citation and downloadable PDF", async ({
  page,
}) => {
  test.skip(
    !process.env.LIVE_ANALYSIS_ID,
    "Opt-in: requires a completed real local analysis, never fixture interception",
  );
  await page.goto(`/analyses/${process.env.LIVE_ANALYSIS_ID}`);
  await expect(page.getByRole("heading", { name: "claim.mp3" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Transcrição", exact: true }),
  ).toBeVisible();
  await expect(
    page
      .locator("section")
      .filter({
        has: page.getByRole("heading", { name: "Transcrição", exact: true }),
      })
      .getByText("O Brasil tem 26 estados e um distrito federal.", {
        exact: true,
      }),
  ).toBeVisible();
  await page.getByText(/Evidências e fontes/).click();
  await expect(
    page
      .getByRole("link")
      .filter({ hasText: /Unidades|IBGE|Brasil/i })
      .first(),
  ).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Baixar PDF" }).click();
  const download = await downloadPromise;
  const path = await download.path();
  expect(path).not.toBeNull();
  if (!path) throw new Error("PDF download path missing");
  const bytes = await readFile(path);
  expect(bytes.subarray(0, 5).toString()).toBe("%PDF-");
});
