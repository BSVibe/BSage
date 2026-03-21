import { test, expect } from "./fixtures/index";
import { SettingsPage } from "./pages/SettingsPage";

test.describe("Settings", () => {
  let settingsPage: SettingsPage;

  test.beforeEach(async ({ page }) => {
    settingsPage = new SettingsPage(page);
    await settingsPage.goto();
  });

  test("現在の設定 レンダリング (llm_model, has_llm_api_key)", async ({}) => {
    await expect(settingsPage.heading).toBeVisible();
    await expect(settingsPage.llmModelInput).toBeVisible();

    const model = await settingsPage.getLLMModel();
    expect(model).toBeTruthy();
  });

  test("Safe Mode toggle → PATCH リクエスト 確認", async ({ page }) => {
    await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().includes("/api/config") && r.request().method() === "PATCH"
      ),
      settingsPage.toggleSafeMode(),
    ]);
  });

  test("LLM モデル 変更 + Save → PATCH body 確認", async ({ page }) => {
    const originalModel = await settingsPage.getLLMModel();
    const newModel = "claude-sonnet-4-6";

    if (originalModel !== newModel) {
      await settingsPage.setLLMModel(newModel);

      const [response] = await Promise.all([
        page.waitForResponse(
          (r) =>
            r.url().includes("/api/config") && r.request().method() === "PATCH"
        ),
        settingsPage.clickSave(),
      ]);

      const patchBody = await response.json();

      expect(patchBody).toBeTruthy();
      expect(patchBody.llm_model).toBe(newModel);
    }
  });

  test("Save ボタン 存在確認", async ({}) => {
    await expect(settingsPage.saveButton).toBeVisible();
  });
});
