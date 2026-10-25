import { test, expect } from "@playwright/test";
test("dashboard and permission-aware upload without fabricated results", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Mais contexto/ }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Nova análise" }).first().click();
  await expect(
    page.getByLabel("Arraste MP3/MP4 ou selecione um arquivo"),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Enviar e analisar" }),
  ).toBeDisabled();
  await expect(page.getByText(/adaptador experimental Docker/)).toBeVisible();
  await page.getByRole("button", { name: "Enviar URL" }).click();
  await expect(page.getByText("Confirme a permissão de uso")).toBeVisible();
});
