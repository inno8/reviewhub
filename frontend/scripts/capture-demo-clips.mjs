/**
 * capture-demo-clips.mjs — Playwright-driven screen recordings of
 * pre-scripted user flows. Drop the resulting webm clips into the
 * Leera pitch video as `<OffthreadVideo />` sources.
 *
 * Why screen recordings instead of static screenshots:
 *   Static + camera-dolly was a workaround. CodeRabbit-grade product
 *   videos use real recordings — UI state actually changes, cursors
 *   actually move, comments actually appear inline. We have a working
 *   product, we should show it working.
 *
 * What this does:
 *   - Spins up headed Chromium (recordings need a real graphics
 *     context; headless can deliver too but headed renders nicer
 *     antialiasing and accurate cursor compositing).
 *   - Injects a custom synthetic cursor into every page (Chromium's
 *     own cursor isn't captured into the WebM — we render our own).
 *   - Walks each scripted flow with smooth eased mouse moves + scrolls
 *     + hovers + occasional non-destructive clicks.
 *   - Saves one webm per flow to ../../leera-pitch-video/public/clips/.
 *
 * Usage:
 *   TEACHER_JWT=… STUDENT_JWT=… JAN_JWT=… \
 *     node scripts/capture-demo-clips.mjs [--only=NAME] [--headed]
 *
 * Re-runnable post-J2: pass --base=https://app.leera.app to record
 * against prod instead of localhost:5173.
 */
import {chromium} from 'playwright';
import {mkdir, rename, rm} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, resolve, join} from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = resolve(__dirname, '../../../leera-pitch-video/public/clips');
const VIEWPORT = {width: 1920, height: 1080};

const argv = process.argv.slice(2);
const flag = (name, fallback = null) => {
  const found = argv.find(a => a === `--${name}` || a.startsWith(`--${name}=`));
  if (!found) return fallback;
  if (!found.includes('=')) return true;
  return found.split('=', 2)[1];
};

const BASE = String(flag('base', 'http://localhost:5173')).replace(/\/$/, '');
const HEADED = !!flag('headed', true); // default true — recordings look nicer
const ONLY = flag('only');

const TEACHER_JWT = process.env.TEACHER_JWT;
const STUDENT_JWT = process.env.STUDENT_JWT;
const JAN_JWT = process.env.JAN_JWT;

if (!TEACHER_JWT || !STUDENT_JWT || !JAN_JWT) {
  console.error('Missing env vars: TEACHER_JWT, STUDENT_JWT, JAN_JWT');
  process.exit(2);
}

// ─────────────────────────────────────────────────────────────────────────────
// Cursor injection — runs on EVERY page load (SPA navigations don't fire
// addInitScript again, but the cursor element survives in <html> across
// vue-router pushes since the document doesn't reload).
//
// CSS transition on transform gives smooth follow without us needing to
// fine-grain Playwright's mouse.move() calls. Playwright can jump from
// A → B and the cursor visually eases between them.
// ─────────────────────────────────────────────────────────────────────────────
const CURSOR_INIT_SCRIPT = `
(function () {
  if (window.__leeraCursorInstalled) return;
  window.__leeraCursorInstalled = true;
  function install() {
    if (!document.documentElement) {
      requestAnimationFrame(install);
      return;
    }
    const c = document.createElement('div');
    c.id = '__leera-demo-cursor';
    Object.assign(c.style, {
      position: 'fixed',
      top: '0',
      left: '0',
      width: '28px',
      height: '28px',
      borderRadius: '50%',
      background: 'rgba(162, 201, 255, 0.95)',
      boxShadow:
        '0 0 0 2px rgba(255,255,255,0.85), ' +
        '0 0 18px 4px rgba(162,201,255,0.55), ' +
        '0 0 36px 8px rgba(162,201,255,0.25)',
      pointerEvents: 'none',
      zIndex: '2147483647',
      transform: 'translate(-50%, -50%) translate(-100px, -100px)',
      transition: 'transform 0.32s cubic-bezier(0.22, 1, 0.36, 1)',
      willChange: 'transform',
    });
    document.documentElement.appendChild(c);
    document.addEventListener('mousemove', (e) => {
      c.style.transform =
        'translate(-50%, -50%) translate(' + e.clientX + 'px, ' + e.clientY + 'px)';
    });
    // Click pulse: small ripple on every mousedown.
    document.addEventListener('mousedown', () => {
      c.animate(
        [
          {transform: c.style.transform + ' scale(1)', opacity: 1},
          {transform: c.style.transform + ' scale(1.6)', opacity: 0.7},
          {transform: c.style.transform + ' scale(1)', opacity: 1},
        ],
        {duration: 320, easing: 'cubic-bezier(.22,1,.36,1)'}
      );
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install);
  } else {
    install();
  }
})();
`;

// ─────────────────────────────────────────────────────────────────────────────
// Movement primitives
//
// Playwright's mouse.move() is INSTANT (one event). With our CSS
// transition the cursor smoothly catches up, but to record actual
// cursor *travel* we need the mouse to physically pass through
// intermediate points (browsers fire hover events, the recording
// captures intermediate frames). So we still step the mouse manually
// for non-trivial paths, then let the CSS transition smooth jitter.
// ─────────────────────────────────────────────────────────────────────────────

/** Ease-in-out cubic — smooth start + end. */
function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

/**
 * Smoothly move the mouse from its current position to (toX, toY) over
 * `durationMs`, in `steps` increments. Uses ease-in-out for natural feel.
 */
async function moveTo(page, toX, toY, durationMs = 900, steps = 24) {
  // Read current position via injected helper (Playwright doesn't expose it).
  const fromPos = await page.evaluate(() => {
    const c = document.getElementById('__leera-demo-cursor');
    if (!c) return [0, 0];
    const m = c.style.transform.match(/translate\((-?\d+\.?\d*)px,\s*(-?\d+\.?\d*)px\)/);
    return m ? [parseFloat(m[1]), parseFloat(m[2])] : [0, 0];
  });
  const fromX = fromPos[0];
  const fromY = fromPos[1];
  const stepMs = durationMs / steps;
  for (let i = 1; i <= steps; i++) {
    const t = easeInOutCubic(i / steps);
    const x = fromX + (toX - fromX) * t;
    const y = fromY + (toY - fromY) * t;
    await page.mouse.move(x, y);
    await page.waitForTimeout(stepMs);
  }
}

/** Move to an element's center (or a given offset within it). */
async function moveToSelector(page, selector, opts = {}) {
  const handle = await page.locator(selector).first();
  await handle.waitFor({state: 'visible', timeout: 5000}).catch(() => {});
  const box = await handle.boundingBox();
  if (!box) {
    console.warn(`  moveToSelector: ${selector} not found, skipping`);
    return;
  }
  const x = box.x + box.width / 2 + (opts.offsetX ?? 0);
  const y = box.y + box.height / 2 + (opts.offsetY ?? 0);
  await moveTo(page, x, y, opts.durationMs ?? 900);
}

/** Smooth scroll the page by `deltaY` over `durationMs`. */
async function smoothScroll(page, deltaY, durationMs = 1200, steps = 30) {
  const stepMs = durationMs / steps;
  for (let i = 1; i <= steps; i++) {
    const t = easeInOutCubic(i / steps);
    const prevT = easeInOutCubic((i - 1) / steps);
    const stepDelta = (t - prevT) * deltaY;
    await page.evaluate((dy) => window.scrollBy({top: dy, behavior: 'auto'}), stepDelta);
    await page.waitForTimeout(stepMs);
  }
}

/** Pause for `ms`, with an optional log message for clarity. */
async function pause(page, ms, label) {
  if (label) console.log(`    · ${label} (${ms}ms)`);
  await page.waitForTimeout(ms);
}

// ─────────────────────────────────────────────────────────────────────────────
// Flow scripts
//
// Each flow is a function (page) => Promise<void> that drives the page
// through a self-contained narrative. Total length should match the
// scene duration in LeeraPitch.tsx (within ~1s tolerance — we'll
// adjust playback rate per-scene to compensate).
// ─────────────────────────────────────────────────────────────────────────────

/** 12s — teacher reviews a drafted PR. Starts on session detail (the
 * inbox is a student-grid, not a PR list — clicking through it would
 * burn 4-5 seconds on navigation). The session-detail screen IS the
 * pitch's hero shot; start there. */
async function teacherReview(page) {
  await pause(page, 1000, 'session detail hydrating');

  // Cursor parks center, then drifts to a comment card.
  await moveTo(page, 1100, 400, 200);
  await pause(page, 400, 'idle');

  // Hover one of the inline comment cards (the AI's draft inline comments).
  // The session detail uses a generic class, no testid — fall back to a
  // structural selector under the comments section.
  await moveTo(page, 600, 500, 1100);
  await pause(page, 700, 'hover comment');

  // Sweep to the rubric panel on the right side of the page.
  // The rubric uses .glass-panel or similar styling on the right; we
  // approximate via coords (1700px is well within the right column).
  await moveTo(page, 1700, 350, 1100);
  await pause(page, 700, 'hover rubric');

  // Move down toward the Send button. Scroll first to get it in view.
  await smoothScroll(page, 400, 800);
  await pause(page, 300, 'scrolled to footer');

  // Hover Send (do NOT click — would post comments to the real PR).
  const sendBtn = page.locator('[data-testid="send-btn"]').first();
  if (await sendBtn.count()) {
    const box = await sendBtn.boundingBox().catch(() => null);
    if (box) {
      await moveTo(page, box.x + box.width / 2, box.y + box.height / 2, 1000);
      await pause(page, 1000, 'hover send');
    }
  } else {
    // Fallback path — sweep cursor across the bottom-right action area.
    await moveTo(page, 1700, 900, 1000);
    await pause(page, 1000);
  }

  await pause(page, 700, 'final hold');
}

/** 8s — student reads the latest feedback their teacher posted. */
async function studentReceive(page) {
  await pause(page, 800, 'dashboard hydrating');
  await moveTo(page, 1200, 200, 200);

  // Cursor lands on the "Latest feedback" hero.
  await moveToSelector(page, '[data-testid="latest-feedback-card"]', {durationMs: 1200});
  await pause(page, 700, 'hover hero');

  // Click → navigate to read-only session view.
  await page.locator('[data-testid="latest-feedback-card"]').first().click().catch(() => {});
  await page.waitForLoadState('networkidle', {timeout: 5000}).catch(() => {});
  await pause(page, 800, 'read-only session loaded');

  // Scroll through comments.
  await smoothScroll(page, 400, 1500);
  await pause(page, 400);

  // Cursor moves to "Bekijk op GitHub".
  await moveToSelector(page, '[data-testid="view-on-github-btn"]', {durationMs: 900}).catch(() => {});
  await pause(page, 800, 'hover github');
}

/** 8s — student walks the Code Review per-commit feed. */
async function codeReviewPage(page) {
  await pause(page, 800, 'code review hydrating');
  await moveTo(page, 1200, 200, 200);

  // Park briefly on the AI banner.
  await moveToSelector(page, '[data-testid="ai-vs-teacher-banner"]', {durationMs: 1100}).catch(() => {});
  await pause(page, 800, 'hover AI banner');

  // Scroll the commit list.
  await smoothScroll(page, 350, 1400);
  await pause(page, 400);

  // Hover one commit row's score.
  // CommitTimelineView doesn't have specific testids; fall back to first .commit row by class.
  const commitRow = page.locator('[data-testid^="commit-row"], article').first();
  if (await commitRow.count()) {
    const box = await commitRow.boundingBox();
    if (box) {
      await moveTo(page, box.x + box.width - 200, box.y + box.height / 2, 900);
      await pause(page, 1000, 'hover commit row score');
    }
  } else {
    // Generic fallback — just sweep cursor across the visible viewport.
    await moveTo(page, 1500, 600, 1000);
    await pause(page, 800);
  }

  await pause(page, 600, 'final hold');
}

/** 10s — teacher walks Jan's student profile. */
async function studentProfile(page) {
  await pause(page, 800, 'profile hydrating');
  await moveTo(page, 1200, 240, 200);

  // Eindniveau row.
  await moveTo(page, 960, 220, 1000);
  await pause(page, 800, 'hover eindniveau');

  // Scroll to per-criterium.
  await smoothScroll(page, 320, 1300);
  await pause(page, 400);
  await moveToSelector(page, '[data-testid="per-criterium-section"]', {durationMs: 1000, offsetY: -120}).catch(() => {});
  await pause(page, 1000, 'hover per-criterium');

  // Scroll further to trajectory.
  await smoothScroll(page, 400, 1400);
  await pause(page, 600, 'trajectory in view');

  // Sweep to recurring patterns.
  await moveTo(page, 1500, 700, 1000);
  await pause(page, 800, 'hover patterns');
}

const FLOWS = [
  {
    name: 'teacher-review',
    jwt: TEACHER_JWT,
    // Direct to a known drafted session in Webdev cohort — sess 56
    // (Lucas's "Validate email format on signup"). The inbox itself is
    // a student-grid not a PR-list, so we skip it for tighter pacing.
    path: '/grading/sessions/56',
    flow: teacherReview,
    note: 'Teacher reviews a drafted PR end-to-end',
  },
  {
    name: 'student-receive',
    jwt: STUDENT_JWT,
    path: '/',
    flow: studentReceive,
    note: 'Student dashboard → click Latest feedback hero → read PR',
  },
  {
    name: 'code-review',
    jwt: STUDENT_JWT,
    path: '/timeline',
    flow: codeReviewPage,
    note: 'Per-commit AI auto-review feed',
  },
  {
    name: 'student-profile',
    jwt: TEACHER_JWT,
    path: '/grading/students/12',
    flow: studentProfile,
    note: 'Teacher views Jan profile (radar + per-criterium + trajectory)',
  },
];

async function captureFlow(browser, spec) {
  console.log(`\n[${spec.name}] ${spec.note}`);
  // recordVideo writes to a temp dir; we rename to our final filename
  // after the context closes (Playwright doesn't let us name it directly).
  const tmpVideoDir = resolve(OUT_DIR, '_tmp');
  await mkdir(tmpVideoDir, {recursive: true});

  const context = await browser.newContext({
    viewport: VIEWPORT,
    recordVideo: {
      dir: tmpVideoDir,
      size: VIEWPORT,
    },
    deviceScaleFactor: 1,
  });
  await context.addInitScript(spec.jwt ? `window.localStorage.setItem('reviewhub_token', '${spec.jwt}');` : '');
  await context.addInitScript({content: CURSOR_INIT_SCRIPT});

  const page = await context.newPage();
  page.on('pageerror', err => console.warn(`  [pageerror] ${err.message.slice(0, 200)}`));

  const start = Date.now();
  try {
    await page.goto(`${BASE}${spec.path}`, {waitUntil: 'domcontentloaded'});
    // Tiny pause so the cursor element is in the DOM before the recording
    // starts capturing meaningful frames.
    await page.waitForTimeout(500);
    await spec.flow(page);
  } finally {
    const recording = await page.video();
    await context.close();  // finalizes the .webm
    if (recording) {
      const tmpPath = await recording.path();
      const finalPath = resolve(OUT_DIR, `${spec.name}.webm`);
      // Remove any existing file.
      if (existsSync(finalPath)) await rm(finalPath);
      await rename(tmpPath, finalPath);
      const ms = Date.now() - start;
      console.log(`  ✓ ${spec.name}.webm  (${ms}ms wall, recording saved)`);
    } else {
      console.warn(`  [warn] ${spec.name}: no recording emitted`);
    }
  }
}

async function main() {
  await mkdir(OUT_DIR, {recursive: true});
  console.log(`Demo clip capture`);
  console.log(`  base: ${BASE}`);
  console.log(`  out:  ${OUT_DIR}`);

  const browser = await chromium.launch({headless: !HEADED, slowMo: 0});
  let captured = 0;
  let failed = 0;
  try {
    const targets = ONLY ? FLOWS.filter(f => f.name === ONLY) : FLOWS;
    if (ONLY && targets.length === 0) {
      console.error(`No flow named "${ONLY}". Valid: ${FLOWS.map(f => f.name).join(', ')}`);
      process.exit(2);
    }
    for (const spec of targets) {
      try {
        await captureFlow(browser, spec);
        captured++;
      } catch (e) {
        failed++;
        console.error(`  ✗ ${spec.name}: ${e.message}`);
      }
    }
  } finally {
    await browser.close();
  }
  // Best-effort cleanup of the temp dir.
  await rm(resolve(OUT_DIR, '_tmp'), {recursive: true, force: true}).catch(() => {});

  console.log('');
  console.log(`Done — ${captured} captured, ${failed} failed`);
  if (failed) process.exit(1);
}

main().catch(e => {
  console.error('Fatal:', e);
  process.exit(1);
});
