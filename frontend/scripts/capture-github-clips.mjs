/**
 * capture-github-clips.mjs — Playwright capture of the two GitHub
 * scenes the Leera pitch needs: student opens a PR, student reads
 * posted feedback. Replaces <GithubPlaceholder /> in LeeraPitch.tsx.
 *
 * Why this script (and not Supademo): Supademo's capture lives in the
 * user's logged-in Chrome via the extension. We can't drive that from
 * here. The other 4 demo clips (teacher review, student profile, etc.)
 * were captured with this same Playwright + synthetic-cursor toolchain,
 * so doing GitHub the same way also keeps the cursor language consistent
 * across the whole pitch.
 *
 * GitHub's web UI requires a real session cookie (PATs only auth API
 * calls). We solve that with a one-time headed login that saves the
 * storage state to a JSON file; subsequent runs reuse it.
 *
 *   # First time: log in once. Browser opens, you click through GitHub
 *   # login (handles 2FA naturally). Script auto-detects and saves state.
 *   node scripts/capture-github-clips.mjs --login
 *
 *   # Capture both flows (uses saved state):
 *   node scripts/capture-github-clips.mjs
 *
 *   # Single flow:
 *   node scripts/capture-github-clips.mjs --only=create-pr
 *   node scripts/capture-github-clips.mjs --only=view-feedback
 *
 * The script also preps + cleans up a fresh demo branch via the gh CLI
 * so the create-pr flow has something real to attach to. The hover stops
 * before the green "Create pull request" click — we don't actually want
 * to spam the repo with demo PRs.
 *
 * Output:
 *   ../../leera-pitch-video/public/clips/github-create-pr.webm
 *   ../../leera-pitch-video/public/clips/github-view-feedback.webm
 */
import {chromium} from 'playwright';
import {mkdir, rename, rm, access} from 'node:fs/promises';
import {existsSync, writeFileSync, mkdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, resolve} from 'node:path';
import {execSync, spawnSync} from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = resolve(__dirname, '../../../leera-pitch-video/public/clips');
const AUTH_DIR = resolve(__dirname, '../../playwright-auth');
const STATE_PATH = resolve(AUTH_DIR, 'github-state.json');
const VIEWPORT = {width: 1920, height: 1080};

const REPO = 'inno8/codelens-test';
const FEEDBACK_PR = 4;          // Has a single clean Nakijken Copilot rubric comment.
const LOCAL_CLONE = 'C:/Users/yanic/dev/codelens-test';

const argv = process.argv.slice(2);
const flag = (name, fallback = null) => {
  const found = argv.find(a => a === `--${name}` || a.startsWith(`--${name}=`));
  if (!found) return fallback;
  if (!found.includes('=')) return true;
  return found.split('=', 2)[1];
};

const LOGIN_MODE = !!flag('login', false);
const ONLY = flag('only');

// ─────────────────────────────────────────────────────────────────────────────
// Synthetic cursor — same CSS, same colors, same easing as the other 4
// product clips (capture-demo-clips.mjs). Visual continuity matters.
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
// Movement primitives — copied from capture-demo-clips.mjs so cursor
// motion matches the other clips frame-for-frame.
// ─────────────────────────────────────────────────────────────────────────────
function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

async function moveTo(page, toX, toY, durationMs = 900, steps = 24) {
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

async function moveToSelector(page, selector, opts = {}) {
  const handle = page.locator(selector).first();
  await handle.waitFor({state: 'visible', timeout: 5000}).catch(() => {});
  const box = await handle.boundingBox();
  if (!box) {
    console.warn(`  moveToSelector: ${selector} not visible, skipping`);
    return false;
  }
  const x = box.x + box.width / 2 + (opts.offsetX ?? 0);
  const y = box.y + box.height / 2 + (opts.offsetY ?? 0);
  await moveTo(page, x, y, opts.durationMs ?? 900);
  return true;
}

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

async function pause(page, ms, label) {
  if (label) console.log(`    · ${label} (${ms}ms)`);
  await page.waitForTimeout(ms);
}

/**
 * Type into a real input field, character by character with realistic
 * jitter. Avoids page.fill() because the recording wants to *show* the
 * typing, not jump to the final string.
 */
async function typeInto(page, selector, text, perCharMs = 38) {
  const el = page.locator(selector).first();
  await el.click();
  await pause(page, 200);
  for (const ch of text) {
    await page.keyboard.type(ch);
    await page.waitForTimeout(perCharMs + Math.random() * 22);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Login phase — opens headed Chrome, lets the human log in, saves state.
// ─────────────────────────────────────────────────────────────────────────────
async function loginAndSaveState() {
  await mkdir(AUTH_DIR, {recursive: true});
  console.log('Login mode — a Chrome window will open.');
  console.log('1. Sign in to GitHub (handle 2FA if prompted)');
  console.log('2. Once you see your dashboard (github.com/), wait — script will save and close.');
  console.log('3. Window will stay open for up to 5 minutes regardless.');
  console.log('');

  const browser = await chromium.launch({headless: false});
  const context = await browser.newContext({viewport: VIEWPORT});
  const page = await context.newPage();

  let pageClosed = false;
  page.on('close', () => {
    console.log('  [event] page closed by user');
    pageClosed = true;
  });
  page.on('framenavigated', frame => {
    if (frame === page.mainFrame()) {
      console.log(`  [nav] ${frame.url()}`);
    }
  });

  await page.goto('https://github.com/login', {waitUntil: 'domcontentloaded'}).catch(e => {
    console.log(`  [goto error] ${e.message.slice(0, 100)}`);
  });

  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const start = Date.now();
  let loggedIn = false;
  let lastCookieSig = '';

  while (Date.now() - start < 5 * 60_000) {
    if (pageClosed) {
      console.log('  [info] page closed — checking cookies one final time');
      break;
    }
    try {
      const cookies = await context.cookies('https://github.com');
      // Log cookie set changes (helps debug what's actually being set).
      const sig = cookies.map(c => c.name).sort().join(',');
      if (sig !== lastCookieSig) {
        console.log(`  [cookies] ${cookies.length} cookies: ${sig.slice(0, 200)}`);
        lastCookieSig = sig;
      }
      // Multiple signals — any indicates a real session.
      const hasDotcomUser = cookies.some(c => c.name === 'dotcom_user' && c.value);
      const hasUserSession = cookies.some(c => c.name === 'user_session' && c.value);
      const hasLoggedIn = cookies.some(c => c.name === 'logged_in' && c.value === 'yes');
      if (hasDotcomUser || (hasUserSession && hasLoggedIn)) {
        console.log('  [signal] login detected via cookies');
        loggedIn = true;
        break;
      }
    } catch (e) {
      const msg = String(e.message);
      if (msg.includes('has been closed') || msg.includes('Target page')) {
        console.log(`  [context error] ${msg.slice(0, 100)} — exiting poll`);
        break;
      }
    }
    await sleep(1500);
  }

  // Final cookie check (in case page closed but cookies are good).
  if (!loggedIn) {
    try {
      const cookies = await context.cookies('https://github.com');
      const hasDotcomUser = cookies.some(c => c.name === 'dotcom_user' && c.value);
      const hasUserSession = cookies.some(c => c.name === 'user_session' && c.value);
      const hasLoggedIn = cookies.some(c => c.name === 'logged_in' && c.value === 'yes');
      if (hasDotcomUser || (hasUserSession && hasLoggedIn)) {
        console.log('  [signal] login detected on final check');
        loggedIn = true;
      }
    } catch {}
  }

  if (!loggedIn) {
    console.error('No login signal detected. Either you didn\'t finish logging in,');
    console.error('or the cookies aren\'t what we expected.');
    try {
      const cookies = await context.cookies('https://github.com');
      console.error(`Cookies seen: ${cookies.map(c => c.name).join(', ') || '(none)'}`);
    } catch {}
    await browser.close().catch(() => {});
    process.exit(1);
  }

  await context.storageState({path: STATE_PATH});
  console.log(`✓ Logged in. State saved to ${STATE_PATH}`);
  await browser.close().catch(() => {});
  console.log('  Re-run without --login to capture clips.');
}

// ─────────────────────────────────────────────────────────────────────────────
// Branch prep — uses gh CLI (already authed as inno8). Creates a fresh
// branch with a tiny commit, pushes, returns the branch name. The
// create-pr capture navigates to the compare page for this branch.
// ─────────────────────────────────────────────────────────────────────────────
function sh(cmd, opts = {}) {
  return execSync(cmd, {stdio: ['ignore', 'pipe', 'inherit'], ...opts}).toString().trim();
}

function prepDemoBranch() {
  const ts = Date.now().toString(36);
  const branch = `demo/email-validation-${ts}`;
  console.log(`  prep branch: ${branch}`);

  const opts = {cwd: LOCAL_CLONE};
  // Make sure we're starting from clean main.
  sh('git fetch origin main', opts);
  sh('git checkout main', opts);
  sh('git reset --hard origin/main', opts);
  sh(`git checkout -b ${branch}`, opts);

  // Add a tiny realistic-looking change. Don't touch existing files
  // (avoid merge conflicts on cleanup); add a new file in a stable
  // subdir.
  const file = 'src/email_validator.py';
  mkdirSync(`${LOCAL_CLONE}/src`, {recursive: true});

  const content = `"""Validate email format on signup."""
import re

EMAIL_RE = re.compile(r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")


def is_valid_email(value: str) -> bool:
    """Return True if value is a syntactically plausible email."""
    if not value or len(value) > 254:
        return False
    return bool(EMAIL_RE.match(value))
`;
  writeFileSync(`${LOCAL_CLONE}/${file}`, content, 'utf-8');

  sh(`git add ${file}`, opts);
  sh(`git commit -m "feat: validate email format on signup"`, opts);
  sh(`git push -u origin ${branch}`, opts);
  return branch;
}

function cleanupDemoBranch(branch) {
  if (!branch) return;
  console.log(`  cleanup branch: ${branch}`);
  try {
    execSync(`gh api -X DELETE /repos/${REPO}/git/refs/heads/${branch}`, {stdio: 'inherit'});
  } catch (e) {
    console.warn(`    (failed to delete remote branch — clean up manually if needed)`);
  }
  // Local cleanup
  try {
    execSync('git checkout main', {cwd: LOCAL_CLONE, stdio: 'ignore'});
    execSync(`git branch -D ${branch}`, {cwd: LOCAL_CLONE, stdio: 'ignore'});
  } catch {}
}

// ─────────────────────────────────────────────────────────────────────────────
// Flow scripts
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 10s — student fills out the PR creation form.
 *
 * The narrative beat is "klaar voor docent-review. Een eenvoudige PR-titel,
 * een paar regels uitleg, klikken — en het werk staat in de lijst van de
 * docent." We hover the green button at the end, but DO NOT click. No real
 * demo PR gets created (we'd just have to clean it up).
 */
async function flowCreatePr(page, branch) {
  await page.goto(`https://github.com/${REPO}/compare/main...${branch}?expand=1`, {
    waitUntil: 'domcontentloaded',
  });
  await pause(page, 1500, 'compare page hydrating');

  // Cursor parks center-ish, then drifts to the title input.
  await moveTo(page, 1200, 300, 200);
  await pause(page, 400);

  // Hover/click title. GitHub's "Title" input has id="pull_request_title".
  await moveToSelector(page, '#pull_request_title', {durationMs: 900});
  await pause(page, 300);

  // The branch's commit message auto-fills the title. Clear it and
  // type the canonical title to make the recording feel deliberate.
  await page.locator('#pull_request_title').click();
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Delete');
  await pause(page, 200);
  for (const ch of 'feat: validate email format on signup') {
    await page.keyboard.type(ch);
    await page.waitForTimeout(34 + Math.random() * 22);
  }
  await pause(page, 400, 'title typed');

  // Click into the description. GitHub uses a textarea with id="pull_request_body".
  await moveToSelector(page, '#pull_request_body', {durationMs: 800, offsetY: -40});
  await pause(page, 200);
  await page.locator('#pull_request_body').click().catch(() => {});
  await pause(page, 200);
  for (const ch of 'Adds basic email validation. Edge cases en tests volgen.') {
    await page.keyboard.type(ch);
    await page.waitForTimeout(28 + Math.random() * 18);
  }
  await pause(page, 500, 'body typed');

  // Sweep down to the green "Create pull request" button. Hover, no click.
  await smoothScroll(page, 200, 700);
  await pause(page, 200);

  // The submit button is a <button name="commit"> with text "Create pull request".
  // GitHub also has a split button ("Create draft"); aim for the primary one.
  const created = await moveToSelector(page, 'button[type="submit"][name="commit"]', {
    durationMs: 1100,
  }).catch(() => false);
  if (!created) {
    // Fallback: any "Create pull request" labeled button.
    await moveToSelector(page, 'button:has-text("Create pull request")', {durationMs: 1100})
      .catch(() => {});
  }
  await pause(page, 1100, 'hover Create button');
  await pause(page, 400, 'final hold');
}

/**
 * 9s — student opens the reviewed PR and reads the inline rubric.
 *
 * PR #4 has exactly the right state: one OPEN PR with a single
 * Nakijken Copilot rubric comment containing the criterion table.
 * Scroll, dwell on the table, hold final frame.
 */
async function flowViewFeedback(page) {
  await page.goto(`https://github.com/${REPO}/pull/${FEEDBACK_PR}`, {
    waitUntil: 'domcontentloaded',
  });
  await pause(page, 1500, 'PR page hydrating');

  // Cursor parks top-right, then drifts down to the comment header.
  await moveTo(page, 1300, 280, 200);
  await pause(page, 400);

  // Scroll the conversation tab into view (PR opens on Conversation
  // by default, so the timeline is right below the header).
  await smoothScroll(page, 380, 1200);
  await pause(page, 400);

  // The Nakijken Copilot comment is a normal issue comment. Selector
  // targeting: there's typically a `.timeline-comment` for each post.
  // We aim for the first non-system comment (the rubric).
  const moved = await moveToSelector(page, '.timeline-comment .comment-body table', {
    durationMs: 1200,
    offsetY: -60,
  });
  if (!moved) {
    // Fallback selectors — GitHub's class names shift over time.
    await moveToSelector(page, '.timeline-comment .comment-body', {durationMs: 1100})
      .catch(() => {});
  }
  await pause(page, 800, 'hover rubric table');

  // Sweep cursor along a few rows of the rubric to draw the eye.
  await moveTo(page, 700, 600, 900);
  await pause(page, 600);
  await moveTo(page, 1200, 700, 900);
  await pause(page, 600);

  // Scroll a touch more to bring the rubric tail into view.
  await smoothScroll(page, 200, 800);
  await pause(page, 800, 'final hold on rubric');
}

const FLOWS = [
  {
    name: 'github-create-pr',
    flow: flowCreatePr,
    note: 'Student opens the compare page, fills title + body, hovers Create',
    needsBranch: true,
  },
  {
    name: 'github-view-feedback',
    flow: flowViewFeedback,
    note: `Student reads the Nakijken rubric on PR #${FEEDBACK_PR}`,
    needsBranch: false,
  },
];

async function captureFlow(browser, spec, branch) {
  console.log(`\n[${spec.name}] ${spec.note}`);
  const tmpVideoDir = resolve(OUT_DIR, '_tmp');
  await mkdir(tmpVideoDir, {recursive: true});

  const context = await browser.newContext({
    viewport: VIEWPORT,
    storageState: STATE_PATH,
    recordVideo: {dir: tmpVideoDir, size: VIEWPORT},
    deviceScaleFactor: 1,
  });
  await context.addInitScript({content: CURSOR_INIT_SCRIPT});

  const page = await context.newPage();
  page.on('pageerror', err => console.warn(`  [pageerror] ${err.message.slice(0, 200)}`));

  const start = Date.now();
  try {
    await spec.flow(page, branch);
  } finally {
    const recording = await page.video();
    await context.close();
    if (recording) {
      const tmpPath = await recording.path();
      const finalPath = resolve(OUT_DIR, `${spec.name}.webm`);
      if (existsSync(finalPath)) await rm(finalPath);
      await rename(tmpPath, finalPath);
      const ms = Date.now() - start;
      console.log(`  ✓ ${spec.name}.webm  (${ms}ms wall)`);
    } else {
      console.warn(`  [warn] ${spec.name}: no recording emitted`);
    }
  }
}

async function main() {
  if (LOGIN_MODE) {
    return loginAndSaveState();
  }

  // Verify state file exists.
  try {
    await access(STATE_PATH);
  } catch {
    console.error(`No GitHub session state at ${STATE_PATH}.`);
    console.error('Run with --login first:');
    console.error('  node scripts/capture-github-clips.mjs --login');
    process.exit(2);
  }

  await mkdir(OUT_DIR, {recursive: true});
  console.log(`GitHub demo capture`);
  console.log(`  out:   ${OUT_DIR}`);
  console.log(`  state: ${STATE_PATH}`);

  const targets = ONLY ? FLOWS.filter(f => f.name === ONLY) : FLOWS;
  if (ONLY && targets.length === 0) {
    console.error(`No flow named "${ONLY}". Valid: ${FLOWS.map(f => f.name).join(', ')}`);
    process.exit(2);
  }

  let demoBranch = null;
  if (targets.some(t => t.needsBranch)) {
    console.log(`\n[prep] Creating demo branch on ${REPO}…`);
    demoBranch = prepDemoBranch();
  }

  // Recordings need a real graphics context; headed renders nicer.
  const browser = await chromium.launch({headless: false, slowMo: 0});
  let captured = 0;
  let failed = 0;
  try {
    for (const spec of targets) {
      try {
        await captureFlow(browser, spec, demoBranch);
        captured++;
      } catch (e) {
        failed++;
        console.error(`  ✗ ${spec.name}: ${e.message}`);
      }
    }
  } finally {
    await browser.close();
  }
  await rm(resolve(OUT_DIR, '_tmp'), {recursive: true, force: true}).catch(() => {});

  if (demoBranch) {
    console.log('');
    cleanupDemoBranch(demoBranch);
  }

  console.log('');
  console.log(`Done — ${captured} captured, ${failed} failed`);
  if (failed) process.exit(1);
}

main().catch(e => {
  console.error('Fatal:', e);
  process.exit(1);
});
