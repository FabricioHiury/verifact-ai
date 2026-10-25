import { test, expect } from "@playwright/test";

test("isolated synthetic fixture: transcript, uncertainty and manual naming", async ({
  page,
}) => {
  const id = "synthetic-fixture";
  const analysis = {
    id,
    title: "Fixture sintética — não é uma análise real",
    status: "PARTIALLY_COMPLETED",
    stage: "GENERATING_REPORT",
    error: null,
    error_code: null,
    limitations: ["Evidências sintéticas somente para teste"],
    revision: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path.endsWith("/events"))
      return route.fulfill({
        contentType: "text/event-stream",
        body: ": fixture\n\n",
      });
    if (path.endsWith("/media"))
      return route.fulfill({
        status: 404,
        body: "No media in synthetic fixture",
      });
    if (path.includes("/speakers"))
      return route.fulfill({
        json:
          route.request().method() === "PATCH"
            ? { id: "voice-1", cluster: "UNKNOWN", manual_name: "Nome manual" }
            : [{ id: "voice-1", cluster: "UNKNOWN", manual_name: null }],
      });
    if (path.endsWith("/transcript"))
      return route.fulfill({
        json: [
          {
            id: "segment-1",
            start_time: 12,
            end_time: 15,
            text: "Afirmação sintética para teste.",
            speaker_id: null,
            manual_speaker_id: null,
          },
        ],
      });
    if (path.endsWith("/claims"))
      return route.fulfill({
        json: [
          {
            id: "claim-1",
            statement: "Afirmação sintética para teste.",
            context: "Fixture isolada",
            topic: "Teste",
            start_time: 12,
            end_time: 15,
            speaker_id: null,
            verdict: {
              classification: "INCONCLUSIVE",
              reasoning: "Fixture sem evidência real",
              limitations: ["Somente teste"],
              model: "fixture",
              prompt_version: "fixture",
            },
            evidence: [],
          },
        ],
      });
    return route.fulfill({ json: analysis });
  });
  await page.goto(`/analyses/${id}`);
  await expect(
    page.getByRole("heading", { name: analysis.title }),
  ).toBeVisible();
  await expect(
    page.getByRole("article").getByText("Inconclusivo", { exact: true }),
  ).toBeVisible();
  await page.getByText("Evidências e fontes (0)").click();
  await expect(page.getByText(/Isso não demonstra falsidade/)).toBeVisible();
  await page.getByPlaceholder("Nome atribuído manualmente").fill("Nome manual");
  const saved = page.waitForRequest(
    (request) =>
      request.method() === "PATCH" && request.url().includes("speakers"),
  );
  await page.getByRole("button", { name: "Salvar nome" }).click();
  const request = await saved;
  expect(request.postDataJSON()).toEqual({ name: "Nome manual" });
  await expect(page.getByRole("link", { name: "Baixar PDF" })).toHaveAttribute(
    "href",
    /report\.pdf$/,
  );
});
