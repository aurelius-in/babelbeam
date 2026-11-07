import { expect, test } from "@playwright/test";

const liveConfig = {
  app_name: "BabelBeam",
  provider_mode: "live",
  simulated: false,
  price_cents: 1499,
  trial_days: 14,
  currency: "usd",
  student_price_cents: 0,
  max_student_listeners: 10,
  included_class_seconds: 18000,
  plan_limits_approved: false,
  limits_are_proposed: true,
  minors_enabled: false,
  production_billing_enabled: false,
  billing_implemented: false,
};

test("home shows brand and Start Class only", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "BabelBeam" }).first()).toBeVisible();
  await expect(page.locator(".start-class-cta")).toBeVisible();
  await expect(page.getByRole("link", { name: /How to use|Cómo usar/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Pricing|Precio|Product|Install|Join|Sign in|Help/i })).toHaveCount(0);
  await expect(
    page.getByText(
      /Live translation for parishes|Teach the faith in English|Your words\. Their language|A product of Reliable AI Network|API online|Classroom preview|Checkout|\$14\.99|14 days free|Parish plan/i,
    ),
  ).toHaveCount(0);
  await expect(page.getByText(/In the room|Teach once\. Include everyone/i)).toHaveCount(0);
  await expect(page.locator(".sim-banner-live")).toHaveCount(0);
  await page.screenshot({ path: "test-results/home.png", fullPage: true });
});

test("how-to page keeps the classroom steps", async ({ page }) => {
  await page.goto("/how");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/Teach once|Enseña una vez/);
  await expect(page.getByText(/01/)).toBeVisible();
  await expect(page.getByRole("heading", { name: /Speak|Habla/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Class App|Class App para|Get Class App|Obtener Class App/i })).toBeVisible();
  await page.screenshot({ path: "test-results/how.png", fullPage: true });
});

test("install page offers the Class App download", async ({ page }) => {
  await page.goto("/install");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/Class App/i);
  await expect(page.getByRole("link", { name: /Download Class App \(Android\)|Descargar Class App \(Android\)/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Android Class App|Class App para Android/i })).toBeVisible();
});

test("a join link opens in Spanish with the code ready", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/join?code=482913");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/Class|Clase/i);
  await expect(page.getByLabel("Código de la clase")).toHaveValue("482913");
  await expect(page.getByText(/Código listo|Code ready/i)).toBeVisible();
  await page.screenshot({ path: "test-results/join-phone.png", fullPage: true });
});

test("student live captions use the full stage without an inner card", async ({ page }) => {
  await page.route("**/api/v1/health", (route) => route.fulfill({ json: { status: "ok" } }));
  await page.route("**/api/v1/public/config", (route) => route.fulfill({ json: liveConfig }));
  await page.route("**/api/v1/classes/join", (route) =>
    route.fulfill({
      json: { student_token: "student-demo", status: "live", voice: "valeria" },
    }),
  );
  await page.route("**/api/v1/classes/feed**", (route) =>
    route.fulfill({
      json: {
        status: "live",
        segments: [
          {
            id: "s1",
            spanish_text: "La paz esté con ustedes.",
            audio_state: "none",
            seq: 1,
          },
        ],
      },
    }),
  );

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/join?code=482913");
  await page.getByLabel("Tu nombre").fill("Maria");
  await page.getByRole("button", { name: "Entrar a la clase" }).click();
  await expect(page.locator(".student-live")).toBeVisible();
  await expect(page.locator(".reading-light")).toHaveCount(0);
  await expect(page.locator(".student-caption-live")).toContainText(/paz/i);
  await expect(page.getByRole("button", { name: "Hacer una pregunta" })).toBeVisible();
  await expect(page.getByText("Escuchando")).toBeVisible();
});

test("Start Class opens the live QR class page", async ({ page }) => {
  await page.route("**/api/v1/health", (route) => route.fulfill({ json: { status: "ok" } }));
  await page.route("**/api/v1/public/config", (route) => route.fulfill({ json: liveConfig }));
  await page.route("**/api/v1/classes/cues**", (route) =>
    route.fulfill({ json: { status: "live", cues: [], listener_count: 2, unread_count: 0 } }),
  );
  await page.route("**/api/v1/classes", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        json: {
          join_code: "482913",
          teacher_token: "teacher-demo",
          lesson_id: "lesson-demo",
          lesson_token: "lesson-token-demo",
          status: "live",
        },
      });
      return;
    }
    await route.fallback();
  });
  await page.route("**/api/v1/classes/end", (route) =>
    route.fulfill({
      json: { status: "ended", lesson_id: "lesson-demo", lesson_token: "lesson-token-demo" },
    }),
  );
  await page.route("**/api/v1/lessons/lesson-demo**", (route) =>
    route.fulfill({
      json: {
        id: "lesson-demo",
        status: "ended",
        segments: [],
        outline: { status: "queued", english: "", spanish: "", ai_additions: [] },
        publication: { status: "private", share_path: "" },
        retention_days: 90,
      },
    }),
  );

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.locator(".start-class-cta").click();
  await expect(page).toHaveURL(/\/app/);
  await expect(page.getByRole("button", { name: "Start Class" })).toHaveCount(0);
  await expect(page.getByText("482 913")).toBeVisible();
  await expect(page.getByRole("img", { name: "QR code for students to join this class" })).toBeVisible();
  await expect(page.locator(".listener-pill")).toContainText(/2 students/i);
  await expect(page.getByRole("button", { name: "Student questions" })).toBeVisible();
  await expect(page.getByText("Keep screen awake during class")).toBeVisible();
  await expect(page.getByText("Play a soft sound for new questions")).toBeVisible();
  await expect(page.getByText("Say next")).toHaveCount(0);
  await expect(page.getByText(/Students join free|Sign-in and billing|Classroom preview/i)).toHaveCount(0);
  await expect(page.locator(".legal-disclaimer")).toContainText(/AI-generated voice/i);
  await page.getByRole("button", { name: "End Class" }).click();
  await expect(page.getByRole("button", { name: "End class now" })).toBeVisible();
  await page.getByRole("button", { name: "Keep class open" }).click();
  await expect(page.getByText("482 913")).toBeVisible();
  await page.getByRole("button", { name: "End Class" }).click();
  await page.getByRole("button", { name: "End class now" }).click();
  await expect(page).toHaveURL(/\/lessons\/lesson-demo/);
  await expect(page.getByRole("heading", { name: /Lesson review|Revisión/i })).toBeVisible();
});

test("a student reply plays on the teacher English clip", async ({ page }) => {
  const spanishAudio = Buffer.from("spanish-class-mpeg").toString("base64");
  const englishAudio = Buffer.from("english-reply-mpeg").toString("base64");
  let releaseCue = false;
  const questionCue = {
    id: "cue-1",
    english_text: "Thank you",
    audio_base64: englishAudio,
    audio_content_type: "audio/mpeg",
    kind: "student_reply",
    student_name: "Alex",
    listened: false,
  };
  await page.route("**/api/v1/health", (route) => route.fulfill({ json: { status: "ok" } }));
  await page.route("**/api/v1/public/config", (route) => route.fulfill({ json: liveConfig }));
  await page.route("**/api/v1/classes/cues**", (route) => {
    if (!releaseCue) {
      return route.fulfill({ json: { status: "live", cues: [], listener_count: 1, unread_count: 0 } });
    }
    return route.fulfill({
      json: {
        status: "live",
        listener_count: 1,
        unread_count: 1,
        cues: [questionCue],
      },
    });
  });
  await page.route("**/api/v1/classes/questions/**", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: { cue: questionCue } });
      return;
    }
    if (route.request().method() === "POST") {
      await route.fulfill({ json: { unread_count: 0 } });
      return;
    }
    await route.fallback();
  });
  await page.route("**/api/v1/classes/line", (route) =>
    route.fulfill({
      json: {
        spanish_text: "La paz sea contigo.",
        audio_base64: spanishAudio,
        audio_content_type: "audio/mpeg",
      },
    }),
  );
  await page.route("**/api/v1/classes", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        json: { join_code: "482913", teacher_token: "teacher-demo", status: "live" },
      });
      return;
    }
    await route.fallback();
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/app");
  await expect(page.getByText("482 913")).toBeVisible();
  await expect(page.locator(".listener-pill")).toContainText(/1 student/i);
  await page.getByRole("button", { name: /Type a line|Escribir/i }).click();
  await page.getByLabel(/Type a line|Escribir/i).fill("Peace be with you.");
  await page.getByRole("button", { name: /Send|Enviar/i }).click();
  const classAudio = page.getByLabel(/Spanish|Español/i);
  await expect.poll(async () => classAudio.getAttribute("src")).toContain(spanishAudio);
  releaseCue = true;
  await expect(page.locator(".question-badge-count")).toHaveText("1", { timeout: 6_000 });
  await page.getByRole("button", { name: "Student questions" }).click();
  await page.getByRole("button", { name: /Alex/ }).click();
  const replyAudio = page.getByLabel("Tap to hear the English reply");
  await expect.poll(async () => replyAudio.getAttribute("src"), { timeout: 6_000 }).toMatch(/^blob:/);
  await expect(page.getByRole("status").filter({ hasText: "Thank you" })).toBeVisible();
  await page.getByRole("button", { name: "Tap to hear the English reply" }).click();
  await expect(replyAudio).toHaveAttribute("src", /^blob:/);
});
