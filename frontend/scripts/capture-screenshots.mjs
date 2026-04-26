/**
 * capture-screenshots.mjs — automated demo-screenshot capture for the
 * Leera pitch video (Remotion).
 *
 * Drives a headless Chromium against the running Vite dev server,
 * injects auth via localStorage, walks the canonical demo routes, and
 * writes PNGs to ../../leera-pitch-video/public/screenshots/.
 *
 * Usage:
 *
 *   # Three JWTs come in via env vars (mint via:
 *   #   ./venv/Scripts/python manage.py shell -c "...RefreshToken.for_user...")
 *   TEACHER_JWT=eyJ... STUDENT_JWT=eyJ... JAN_JWT=eyJ... \
 *     node scripts/capture-screenshots.mjs
 *
 *   # Optional flags:
 *   --headed       run with a visible browser (debug captures)
 *   --base=URL     override frontend base URL (default http://localhost:5173)
 *   --only=NAME    capture a single shot by name (good for iterating)
 *   --slow=MS      slow each step by N ms for debugging
 *
 * Designed to be re-runnable: same script captures the localhost preview
 * today and the production URL post-J2 deploy.
 */
import {chromium} from 'playwright';
import {mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {dirname, join, resolve} from 'node:path';

const argv = process.argv.slice(2);
const flag = (name, fallback = null) => {
  const found = argv.find(a => a === `--${name}` || a.startsWith(`--${name}=`));
  if (!found) return fallback;
  if (!found.includes('=')) return true;
  return found.split('=', 2)[1];
};

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = resolve(__dirname, '../../../leera-pitch-video/public/screenshots');
const BASE = String(flag('base', 'http://localhost:5173')).replace(/\/$/, '');
const HEADED = !!flag('headed', false);
const ONLY = flag('only');
const SLOW = Number(flag('slow', 0));

const TEACHER_JWT = process.env.TEACHER_JWT;
const STUDENT_JWT = process.env.STUDENT_JWT;  // tester (id=5)
const JAN_JWT = process.env.JAN_JWT;          // jan.deboer (id=12)

if (!TEACHER_JWT || !STUDENT_JWT || !JAN_JWT) {
  console.error('Missing env vars: TEACHER_JWT, STUDENT_JWT, JAN_JWT');
  process.exit(2);
}

const VIEWPORT = {width: 1920, height: 1080};

/**
 * Walk all the routes the pitch video composes against. Each entry:
 *   name    — output filename (without extension)
 *   jwt     — which user to mount the page as
 *   path    — frontend path to navigate to
 *   wait    — selector that confirms the page is ready
 *   pre     — optional async fn(page) run BEFORE screenshot (e.g. click,
 *             scroll, focus an editor for the mid-edit shot)
 *   note    — short human description (logged on capture)
 */
const SHOTS = [
  // ── TEACHER ────────────────────────────────────────────────────────
  {
    name: '01-teacher-dashboard',
    jwt: TEACHER_JWT,
    path: '/',
    wait: '[data-testid="inbox-kpi-row"]',
    note: 'Teacher dashboard — Vandaag op je bord, KPIs, Next up, Reviewtijd',
  },
  {
    name: '02-teacher-inbox-drafted',
    jwt: TEACHER_JWT,
    path: '/grading?state=drafted',
    wait: '[data-testid="grading-inbox-row"], h1, .grading-inbox',
    waitTimeoutMs: 8000,
    note: 'Teacher inbox filtered to drafted PRs',
  },
  {
    name: '03-teacher-session-detail-drafted',
    jwt: TEACHER_JWT,
    path: '/grading/sessions/56',  // Webdev student drafted session
    wait: '[data-testid="anchored-comment-list"], h1, h2',
    waitTimeoutMs: 12000,
    note: 'Session detail with AI draft — rubric panel + inline comments',
  },
  {
    name: '06-teacher-student-profile-jan',
    jwt: TEACHER_JWT,
    path: '/grading/students/12',
    wait: '[data-testid="per-criterium-section"]',
    waitTimeoutMs: 10000,
    note: 'Teacher view of Jan de Boer — radar + per-criterium + trajectory',
  },

  // ── STUDENT (tester) ───────────────────────────────────────────────
  {
    name: '07-student-dashboard-tester',
    jwt: STUDENT_JWT,
    path: '/',
    wait: '[data-testid="student-front-door"], h1, h2',
    waitTimeoutMs: 8000,
    note: 'Student dashboard — Latest feedback hero + Eindniveau + Focus',
  },
  {
    name: '08-student-my-feedback',
    jwt: STUDENT_JWT,
    path: '/my/prs',
    wait: '[data-testid="pr-list"], [data-testid="empty-state"], h1',
    waitTimeoutMs: 8000,
    note: 'My Feedback — student PR list with iteration chain',
  },
  {
    name: '09-student-session-readonly',
    jwt: STUDENT_JWT,
    path: '/grading/sessions/71',
    wait: '[data-testid="student-readonly-footer"]',
    waitTimeoutMs: 10000,
    note: 'Student read-only session view — feedback + Bekijk op GitHub',
  },
  {
    name: '10-student-code-review',
    jwt: STUDENT_JWT,
    path: '/timeline',
    wait: '[data-testid="ai-vs-teacher-banner"], h1',
    waitTimeoutMs: 8000,
    note: 'Code Review — per-commit AI auto-review feed',
  },

  // ── STUDENT (jan — confident scores, post-boost) ──────────────────
  {
    name: '07b-student-dashboard-jan',
    jwt: JAN_JWT,
    path: '/',
    wait: '[data-testid="student-front-door"], h1',
    waitTimeoutMs: 8000,
    note: 'Jan dashboard — confident eindniveau (boosted observations)',
  },

  // ── B-roll ─────────────────────────────────────────────────────────
  {
    name: '13-teacher-cohort-overview',
    jwt: TEACHER_JWT,
    path: '/grading/cohorts/5/overview',
    wait: 'h1, h2',
    waitTimeoutMs: 8000,
    note: 'Klas-overzicht — recurring patterns across the cohort',
  },
  {
    name: '14-student-skills-dashboard',
    jwt: JAN_JWT,
    path: '/skills',
    wait: 'h1, h2',
    waitTimeoutMs: 10000,
    note: 'Skills page — per-skill drill-down',
  },
];

async function setAuthAndNavigate(page, jwt, path, base) {
  // The frontend's auth store reads `reviewhub_token` from localStorage at
  // mount time and bootstraps the user from /api/users/me/. Setting the
  // token before the SPA loads dodges the login redirect.
  await page.context().addInitScript((token) => {
    try {
      window.localStorage.setItem('reviewhub_token', token);
    } catch (e) { /* localStorage unavailable — falls through to login */ }
  }, jwt);
  await page.goto(`${base}${path}`, {waitUntil: 'domcontentloaded'});
}

async function captureOne(browser, shot, base) {
  const ctx = await browser.newContext({viewport: VIEWPORT});
  const page = await ctx.newPage();
  // Suppress Vue warnings from cluttering output but surface page errors.
  page.on('pageerror', err => console.warn(`  [pageerror] ${shot.name}: ${err.message.slice(0, 200)}`));
  const start = Date.now();
  try {
    await setAuthAndNavigate(page, shot.jwt, shot.path, base);

    // Wait for the marker selector that says "this page is hydrated."
    // Fall back to a fixed sleep if waitForSelector times out — better
    // to capture a half-rendered shot than to skip entirely. Investors
    // would rather see "almost loaded" than nothing.
    if (shot.wait) {
      const timeout = shot.waitTimeoutMs ?? 6000;
      try {
        await page.waitForSelector(shot.wait, {timeout});
      } catch (e) {
        console.warn(`  [warn] ${shot.name}: wait selector "${shot.wait}" timed out (${timeout}ms); capturing anyway`);
      }
    }
    // Network-idle settle for any in-flight API fetches (KPI calls, etc.).
    try {
      await page.waitForLoadState('networkidle', {timeout: 4000});
    } catch { /* keep going */ }

    if (shot.pre) await shot.pre(page);
    if (SLOW) await page.waitForTimeout(SLOW);

    const filePath = join(OUT_DIR, `${shot.name}.png`);
    await page.screenshot({path: filePath, fullPage: false, type: 'png'});
    const ms = Date.now() - start;
    console.log(`  ✓ ${shot.name}.png  (${ms}ms)  ${shot.note}`);
  } finally {
    await ctx.close();
  }
}

async function main() {
  await mkdir(OUT_DIR, {recursive: true});
  console.log(`Capturing ${SHOTS.length} screenshots`);
  console.log(`  base: ${BASE}`);
  console.log(`  out:  ${OUT_DIR}`);
  console.log('');

  const browser = await chromium.launch({headless: !HEADED, slowMo: HEADED ? 200 : 0});
  let captured = 0;
  let failed = 0;
  try {
    const targets = ONLY ? SHOTS.filter(s => s.name === ONLY) : SHOTS;
    if (ONLY && targets.length === 0) {
      console.error(`No shot named "${ONLY}". Valid: ${SHOTS.map(s => s.name).join(', ')}`);
      process.exit(2);
    }
    for (const shot of targets) {
      try {
        await captureOne(browser, shot, BASE);
        captured++;
      } catch (e) {
        failed++;
        console.error(`  ✗ ${shot.name}: ${e.message}`);
      }
    }
  } finally {
    await browser.close();
  }
  console.log('');
  console.log(`Done — ${captured} captured, ${failed} failed`);
  if (failed) process.exit(1);
}

main().catch(e => {
  console.error('Fatal:', e);
  process.exit(1);
});
