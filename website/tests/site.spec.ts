import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/** Collects console errors, page errors and any request that leaves localhost. */
function watch(page: Page) {
  const errors: string[] = [];
  const external: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("request", (r) => {
    if (new URL(r.url()).hostname !== "localhost") external.push(r.url());
  });
  return { errors, external };
}

const coreState = (page: Page) => page.getByTestId("core-layer").getAttribute("data-core-state");

test("loads with no console errors and no third-party requests", async ({ page }) => {
  const w = watch(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Your laptop.");
  await expect(page.getByTestId("core-layer")).toBeAttached();
  await page.waitForTimeout(1500);
  expect(w.errors).toEqual([]);
  expect(w.external).toEqual([]);
});

test("every section is present and the page never scrolls sideways", async ({ page }) => {
  await page.goto("/");
  for (const id of ["thesis", "problem", "demo", "how", "say", "capabilities", "trust", "roadmap", "states", "contact"]) {
    await expect(page.locator(`#${id}`)).toBeAttached();
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("contact goes to Likki by email", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("contact-cta")).toHaveAttribute("href", /^mailto:likithreddysaribala@gmail\.com/);
});

test.describe("demo confirm gate", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/#demo");
    await page.getByTestId("demo-panel").scrollIntoViewIfNeeded();
  });

  test("yes: the action completes and the core shows success", async ({ page }) => {
    await page.getByTestId("demo-email").click();
    await expect(page.getByTestId("confirm-card")).toBeVisible({ timeout: 15_000 });
    expect(await coreState(page)).toBe("confirming");
    await page.getByTestId("confirm-yes").click();
    await expect(page.getByTestId("demo-reply")).toHaveText(/Sent\./, { timeout: 10_000 });
    expect(await coreState(page)).toBe("success");
  });

  test("no: nothing happens", async ({ page }) => {
    await page.getByTestId("demo-email").click();
    await expect(page.getByTestId("confirm-card")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("confirm-no").click();
    await expect(page.getByTestId("demo-reply")).toHaveText(/Cancelled\. Nothing was sent\./);
    await expect(page.locator('[data-status]', { hasText: "Send the email" })).toHaveCount(0);
  });

  test("Enter means yes, Esc means no", async ({ page }) => {
    await page.getByTestId("demo-share").click();
    await expect(page.getByTestId("confirm-card")).toBeVisible({ timeout: 15_000 });
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("demo-reply")).toHaveText(/Nothing was shared/);
    // Let the first card finish leaving before asking again.
    await expect(page.getByTestId("confirm-card")).toHaveCount(0);

    await page.getByTestId("demo-share").click();
    await expect(page.getByTestId("confirm-card")).toBeVisible({ timeout: 15_000 });
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("demo-reply")).toHaveText(/Shared with legal/, { timeout: 10_000 });
  });

  test("a low-risk question answers without asking", async ({ page }) => {
    await page.getByTestId("demo-calendar").click();
    await expect(page.getByTestId("demo-reply")).toHaveText(/stand-up at 9:30/, { timeout: 15_000 });
    await expect(page.getByTestId("confirm-card")).toHaveCount(0);
  });
});

test("confirm card times out to No after 60 s and never auto-confirms", async ({ page }) => {
  await page.clock.install();
  await page.goto("/#demo");
  await page.getByTestId("demo-panel").scrollIntoViewIfNeeded();
  await page.getByTestId("demo-email").click();
  await expect(page.getByTestId("confirm-card")).toBeVisible({ timeout: 15_000 });
  await page.clock.fastForward(59_000);
  await expect(page.getByTestId("confirm-card")).toBeVisible();
  await page.clock.fastForward(2_000);
  await expect(page.getByTestId("demo-reply")).toHaveText(/Cancelled\. Nothing was sent\./, { timeout: 10_000 });
  await expect(page.getByTestId("core-layer")).toHaveAttribute("data-core-state", "standby");
  await expect(page.locator("[data-status]", { hasText: "Send the email" })).toHaveCount(0);
});

test("Pause motion pauses the core", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("pause-motion").click();
  await expect(page.getByTestId("core-layer")).toHaveAttribute("data-core-state", "paused");
  await page.getByTestId("pause-motion").click();
  await expect(page.getByTestId("core-layer")).not.toHaveAttribute("data-core-state", "paused");
});

test.describe("reduced motion", () => {
  test.use({ reducedMotion: "reduce" });
  test("content is visible and the core holds still", async ({ page }) => {
    await page.goto("/");
    await page.locator("#problem").scrollIntoViewIfNeeded();
    // Reveal targets must not stay hidden when animation is off.
    await expect(page.locator("#problem [data-reveal]").first()).toHaveCSS("opacity", "1");
    await page.locator("canvas").waitFor();
    await page.waitForTimeout(800);
    const a = await page.locator("canvas").screenshot();
    await page.waitForTimeout(700);
    const b = await page.locator("canvas").screenshot();
    expect(a.equals(b)).toBe(true);
  });
});

test("no serious or critical accessibility violations", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);
  // Reveal and scroll-scrubbed animations would read as low contrast mid-fade: scan the settled page.
  await page.addStyleTag({ content: "[data-reveal],.hero-in,.thesis-word{opacity:1!important;transform:none!important}" });
  const results = await new AxeBuilder({ page }).exclude("canvas").analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.nodes.length} × ${v.nodes[0]?.target}`)).toEqual([]);
});
