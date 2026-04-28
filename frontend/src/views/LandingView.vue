<script setup lang="ts">
/**
 * LandingView — public marketing page at /welcome.
 *
 * Ported from the Claude Design hand-off bundle (leera-ui/project/Landing.html).
 * Visual fidelity is the priority — inline styles are preserved verbatim where
 * they carry the design intent. Tailwind utility classes are used only where
 * they map 1:1 to a CSS rule already in the design.
 *
 * What changed from the design HTML:
 *   - Vue lifecycle hooks instead of vanilla JS (scroll listener, intersection
 *     observers, typewriter loop)
 *   - Router pushes instead of `Leera.html` and `#pricing` href targets
 *   - Real LEERA logo from /logo/leera-wordmark-primary.svg (and mark for the
 *     compact footer slot) instead of the design's stylized inline SVG mark
 *   - Removed the duplicate "Bash" language card (design had two)
 *   - Cleaned up obvious Dutch typos in the design (likely AI hallucinations:
 *     "gestempeld" → "gekoppeld", "Greptodep" → "Goedkoop", etc.)
 */
import { onMounted, onUnmounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();

// ─────────────────────────────────────────────────────────────────────
// Mobile hamburger menu state
// Declared at the top because the watch() and onResize() handlers
// below reference it; declaring it later would put it in the temporal
// dead zone at script-setup eval time and throw a runtime
// ReferenceError in production builds.
// ─────────────────────────────────────────────────────────────────────
const mobileNavOpen = ref(false);
function toggleMobileNav() { mobileNavOpen.value = !mobileNavOpen.value; }

// ─────────────────────────────────────────────────────────────────────
// Sticky-nav scroll backdrop opacity
// ─────────────────────────────────────────────────────────────────────
const scrolled = ref(false);
function onScroll() {
  scrolled.value = window.scrollY > 50;
}

// ─────────────────────────────────────────────────────────────────────
// Hero mock — perspective tilt that follows the cursor
// ─────────────────────────────────────────────────────────────────────
const heroMockEl = ref<HTMLElement | null>(null);
function onMouseMove(e: MouseEvent) {
  const el = heroMockEl.value;
  if (!el) return;
  const rect = el.getBoundingClientRect();
  const x = e.clientX - rect.left - rect.width / 2;
  const y = e.clientY - rect.top - rect.height / 2;
  const rotateX = (y / rect.height) * -5;
  const rotateY = (x / rect.width) * 5;
  el.style.transform = `perspective(1200px) rotateX(${4 + rotateX}deg) rotateY(${rotateY}deg)`;
}

// ─────────────────────────────────────────────────────────────────────
// Reveal-on-scroll
// ─────────────────────────────────────────────────────────────────────
let revealObserver: IntersectionObserver | null = null;
let terminalObserver: IntersectionObserver | null = null;

// ─────────────────────────────────────────────────────────────────────
// Typewriter loop for the step-01 terminal
// ─────────────────────────────────────────────────────────────────────
let typingTimers: number[] = [];
function clearTimers() {
  typingTimers.forEach(t => window.clearTimeout(t));
  typingTimers = [];
}
function typeWriter(element: HTMLElement, delay = 0) {
  const text = element.dataset.text || '';
  const speed = parseInt(element.dataset.speed || '50', 10);
  element.textContent = '';
  element.style.opacity = '1';
  let i = 0;
  const startTimer = window.setTimeout(() => {
    const interval = window.setInterval(() => {
      if (i < text.length) {
        element.textContent += text[i];
        i++;
      } else {
        window.clearInterval(interval);
        const wrapper = element.closest('#terminal-step1');
        if (!wrapper) return;
        const all = Array.from(wrapper.querySelectorAll<HTMLElement>('.typewriter'));
        const idx = all.indexOf(element);
        if (idx < all.length - 1) {
          typeWriter(all[idx + 1], 100);
        } else {
          // Last line done — restart loop after 3s
          const restart = window.setTimeout(() => {
            const first = wrapper.querySelector<HTMLElement>('.typewriter');
            if (first) typeWriter(first, 300);
          }, 3000);
          typingTimers.push(restart);
        }
      }
    }, speed);
    typingTimers.push(interval as unknown as number);
  }, delay);
  typingTimers.push(startTimer);
}

// Close mobile menu when crossing back to desktop width
function onResize() {
  if (window.innerWidth > 768 && mobileNavOpen.value) {
    mobileNavOpen.value = false;
  }
}

// Body scroll lock when the mobile menu is open
watch(mobileNavOpen, (open) => {
  document.body.style.overflow = open ? 'hidden' : '';
});

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onResize);
  document.addEventListener('mousemove', onMouseMove);

  // Reveal observer
  revealObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) entry.target.classList.add('in');
    });
  }, { threshold: 0.1 });
  document.querySelectorAll('.reveal').forEach(el => revealObserver!.observe(el));

  // Terminal typewriter — kicks off when the step-01 terminal scrolls into view
  terminalObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      const el = entry.target as HTMLElement;
      if (entry.isIntersecting && !el.dataset.typed) {
        el.dataset.typed = 'true';
        const first = el.querySelector<HTMLElement>('.typewriter');
        if (first) typeWriter(first, 300);
      }
    });
  }, { threshold: 0.3 });
  const terminal = document.getElementById('terminal-step1');
  if (terminal) terminalObserver.observe(terminal);
});

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll);
  window.removeEventListener('resize', onResize);
  document.removeEventListener('mousemove', onMouseMove);
  revealObserver?.disconnect();
  terminalObserver?.disconnect();
  clearTimers();
  // Always restore body scroll on teardown
  document.body.style.overflow = '';
});

// ─────────────────────────────────────────────────────────────────────
// CTA targets
// ─────────────────────────────────────────────────────────────────────
function goLogin() {
  mobileNavOpen.value = false;
  router.push('/login');
}
function goSignup() {
  mobileNavOpen.value = false;
  router.push('/org-signup');
}
function scrollTo(id: string) {
  mobileNavOpen.value = false;
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

</script>

<template>
  <div class="landing-root">
    <!-- ════════════════════════ NAV ════════════════════════ -->
    <nav id="nav" :class="{ scrolled, 'menu-open': mobileNavOpen }">
      <div class="container" style="display:flex;align-items:center;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:40px">
          <a href="#top" style="display:flex;align-items:center;gap:10px;text-decoration:none">
            <img src="/logo/leera-wordmark-primary.svg" alt="LEERA" style="height:28px" />
          </a>
          <div style="display:flex;gap:28px" class="nav-links">
            <button @click="scrollTo('features')">Features</button>
            <button @click="scrollTo('how')">Hoe het werkt</button>
            <button @click="scrollTo('languages')">Talen</button>
          </div>
        </div>
        <div class="nav-desktop-actions" style="display:flex;gap:12px;align-items:center">
          <button @click="goLogin" class="login-link">Inloggen</button>
          <button @click="goSignup" class="primary-gradient cta-btn" style="color:var(--on-primary);padding:10px 20px;font-size:14px">
            Vraag een demo aan
          </button>
        </div>

        <!-- Mobile hamburger -->
        <button
          type="button"
          class="hamburger"
          :aria-expanded="mobileNavOpen"
          aria-controls="mobile-menu"
          aria-label="Menu"
          @click="toggleMobileNav"
        >
          <span class="hamburger-bar" :class="{ 'is-open': mobileNavOpen }"></span>
          <span class="hamburger-bar middle" :class="{ 'is-open': mobileNavOpen }"></span>
          <span class="hamburger-bar" :class="{ 'is-open': mobileNavOpen }"></span>
        </button>
      </div>
    </nav>

    <!-- Mobile menu sheet -->
    <Transition name="mobile-menu">
      <div
        v-if="mobileNavOpen"
        id="mobile-menu"
        class="mobile-menu"
        @click.self="mobileNavOpen = false"
      >
        <div class="mobile-menu-panel">
          <button @click="scrollTo('features')" class="mobile-menu-link">Features</button>
          <button @click="scrollTo('how')" class="mobile-menu-link">Hoe het werkt</button>
          <button @click="scrollTo('languages')" class="mobile-menu-link">Talen</button>
          <div class="mobile-menu-divider"></div>
          <button @click="goLogin" class="mobile-menu-link mobile-menu-secondary">Inloggen</button>
          <button @click="goSignup" class="mobile-menu-cta primary-gradient">
            Vraag een demo aan
          </button>
        </div>
      </div>
    </Transition>

    <!-- ════════════════════════ HERO ════════════════════════ -->
    <section id="top" class="hero">
      <div class="hero-grid dots drift"></div>
      <div class="container" style="position:relative;z-index:1;text-align:center">
        <h1 style="font-size:clamp(42px,7vw,72px);font-weight:800;letter-spacing:-2px;line-height:1.1;margin-bottom:20px">
          Elke commit een les.<br/>Elke <span style="background:linear-gradient(135deg,#a2c9ff,#58a6ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">PR een beoordeling</span><br/>die uit bewijs komt.
        </h1>
        <p style="font-size:20px;color:var(--on-surface-variant);max-width:720px;margin:0 auto 40px;line-height:1.6">
          LEERA reviewt de code van je studenten op elke commit, schrijft een rubric-concept in jouw stem, en houdt je het laatste woord. Een PR-review in 5 minuten — niet 20.
        </p>
        <div style="margin-bottom:80px">
          <div style="font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--outline);font-weight:700;margin-bottom:12px">Ontworpen voor de Nederlandse MBO-4 ICT</div>
          <div style="display:flex;gap:28px;justify-content:center;align-items:center;flex-wrap:wrap">
            <div style="display:flex;align-items:center;gap:8px;color:var(--on-surface-variant);font-size:14px">
              <span class="material-symbols-outlined" style="font-size:18px;color:var(--primary)">verified</span>
              AVG-compliant
            </div>
            <div style="display:flex;align-items:center;gap:8px;color:var(--on-surface-variant);font-size:14px">
              <span class="material-symbols-outlined" style="font-size:18px;color:var(--primary)">code</span>
              Werkt in GitHub
            </div>
            <div style="display:flex;align-items:center;gap:8px;color:var(--on-surface-variant);font-size:14px">
              <span class="material-symbols-outlined" style="font-size:18px;color:var(--primary)">edit_note</span>
              Rubric-gebaseerd
            </div>
          </div>
        </div>

        <!-- Animated hero mockup -->
        <div class="reveal" style="max-width:1000px;margin:0 auto;position:relative">
          <div ref="heroMockEl" id="hero-mock" class="glass glow" style="border-radius:16px;overflow:hidden;transform:perspective(1200px) rotateX(4deg);transition:transform .5s">
            <div style="background:var(--surface-container-lowest);padding:20px;border-bottom:1px solid rgba(139,145,157,.08)">
              <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px">
                <div style="width:40px;height:40px;border-radius:99px;background:linear-gradient(135deg,#a2c9ff,#58a6ff);display:grid;place-items:center;color:#00315c;font-weight:800;font-size:14px">VS</div>
                <div>
                  <div style="font-weight:700;font-size:15px">Vash De Stampede</div>
                  <div style="font-size:12px;color:var(--outline)">feat: JWT refresh-rotatie + expiry check</div>
                </div>
                <div style="margin-left:auto;display:inline-flex;align-items:center;gap:6px;background:rgba(162,201,255,.15);color:var(--primary);padding:4px 10px;border-radius:999px;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase">
                  <span style="width:6px;height:6px;border-radius:99px;background:var(--primary);animation:pulse 2s infinite"></span>Concept klaar
                </div>
              </div>
            </div>

            <div style="display:grid;grid-template-columns:1fr 320px;gap:0" class="hero-mock-grid">
              <!-- Diff -->
              <div style="padding:20px;background:var(--surface-container-low)">
                <div class="diff-mock">
                  <div class="diff-line" style="background:var(--surface-container);padding:8px 14px;border-bottom:1px solid rgba(139,145,157,.08)">
                    <span class="material-symbols-outlined" style="font-size:14px;color:var(--primary)">code</span>
                    <span class="mono" style="font-size:11px;color:var(--on-surface)">src/auth/auth.ts</span>
                  </div>
                  <div class="diff-line diff-rm" style="animation:fadeIn .6s .2s both">
                    <span class="ln">46</span>
                    <span style="color:#ff7b72">−</span>
                    <span style="color:var(--on-surface-variant)">const payload = jwt.verify(token, SECRET);</span>
                  </div>
                  <div class="diff-line diff-add" style="animation:fadeIn .6s .3s both">
                    <span class="ln">47</span>
                    <span style="color:#7ee1a7">+</span>
                    <span style="color:var(--on-surface-variant)">const payload = jwt.verify(token, SECRET, {</span>
                  </div>
                  <div class="diff-line diff-add" style="animation:fadeIn .6s .4s both">
                    <span class="ln">48</span>
                    <span style="color:#7ee1a7">+</span>
                    <span style="color:var(--on-surface-variant)">&nbsp;&nbsp;audience: "leera-api",</span>
                  </div>
                  <div class="diff-line diff-add" style="animation:fadeIn .6s .5s both">
                    <span class="ln">49</span>
                    <span style="color:#7ee1a7">+</span>
                    <span style="color:var(--on-surface-variant)">});</span>
                  </div>
                </div>

                <!-- AI comment -->
                <div style="margin-top:14px;background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-left:3px solid var(--error);border-radius:10px;padding:14px;animation:slideUp .6s .7s both">
                  <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
                    <span style="display:inline-flex;align-items:center;gap:6px;padding:3px 8px;border-radius:999px;font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;background:rgba(255,180,171,.15);color:var(--error)">Veiligheid</span>
                    <code class="mono" style="font-size:10px;color:var(--primary);background:var(--surface-container-high);padding:2px 6px;border-radius:4px">auth.ts:47</code>
                    <span style="font-weight:600;font-size:12px">Geen audience check</span>
                  </div>
                  <div style="font-size:12px;color:var(--on-surface-variant);line-height:1.5">Je verifieert de signature maar niet de <code class="mono" style="background:rgba(162,201,255,.12);color:var(--primary);padding:1px 4px;border-radius:3px">aud</code>-claim. Als je meerdere services hebt, accepteert deze token er één van een ander. Voeg <code class="mono" style="background:rgba(162,201,255,.12);color:var(--primary);padding:1px 4px;border-radius:3px">{ audience: "leera-api" }</code> toe.</div>
                </div>
              </div>

              <!-- Rubric -->
              <div style="padding:20px;background:var(--surface-container-low);border-left:1px solid rgba(139,145,157,.08)">
                <div style="font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--outline);font-weight:700;margin-bottom:10px">Eindbeoordeling</div>
                <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:14px">
                  <div style="font-size:36px;font-weight:800;letter-spacing:-1px;color:var(--primary);animation:scaleIn .6s .8s both">3.0</div>
                  <div style="font-size:13px;color:var(--outline)">/ 4.0</div>
                </div>
                <div style="display:flex;flex-direction:column;gap:10px">
                  <div style="background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-radius:10px;padding:12px;animation:slideUp .6s .9s both">
                    <div style="display:flex;align-items:center;gap:10px">
                      <div class="dial" style="width:36px;height:36px">
                        <svg width="36" height="36">
                          <circle cx="18" cy="18" r="14" stroke="var(--surface-container-high)" stroke-width="4" fill="none"/>
                          <circle cx="18" cy="18" r="14" stroke="var(--primary)" stroke-width="4" fill="none" stroke-dasharray="87.96" stroke-dashoffset="21.99" stroke-linecap="round" style="transform:rotate(-90deg);transform-origin:50% 50%"/>
                        </svg>
                      </div>
                      <div style="flex:1">
                        <div style="font-weight:600;font-size:12px">Veiligheid</div>
                        <div style="font-size:10px;color:var(--outline)">30%</div>
                      </div>
                    </div>
                  </div>
                  <div style="background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-radius:10px;padding:12px;animation:slideUp .6s 1s both">
                    <div style="display:flex;align-items:center;gap:10px">
                      <div class="dial" style="width:36px;height:36px">
                        <svg width="36" height="36">
                          <circle cx="18" cy="18" r="14" stroke="var(--surface-container-high)" stroke-width="4" fill="none"/>
                          <circle cx="18" cy="18" r="14" stroke="#7ee1a7" stroke-width="4" fill="none" stroke-dasharray="87.96" stroke-dashoffset="0" stroke-linecap="round" style="transform:rotate(-90deg);transform-origin:50% 50%"/>
                        </svg>
                      </div>
                      <div style="flex:1">
                        <div style="font-weight:600;font-size:12px">Leesbaarheid</div>
                        <div style="font-size:10px;color:var(--outline)">20%</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Floating elements -->
          <div class="float" style="position:absolute;top:-40px;right:-40px;background:rgba(126,225,167,.15);border:1px solid rgba(126,225,167,.3);padding:12px 16px;border-radius:10px;font-size:13px;color:#7ee1a7;font-weight:700;animation-delay:.3s;box-shadow:0 10px 30px -10px rgba(126,225,167,.3)">
            ✓ 7 comments gedraft in 2m 12s
          </div>
          <div class="float" style="position:absolute;bottom:-30px;left:-50px;background:rgba(162,201,255,.12);border:1px solid rgba(162,201,255,.25);padding:12px 16px;border-radius:10px;font-size:13px;color:var(--primary);font-weight:700;animation-delay:.6s;box-shadow:0 10px 30px -10px rgba(162,201,255,.3)">
            🎯 96% docent-acceptatie
          </div>
        </div>
      </div>
    </section>

    <!-- ════════════════════════ PROBLEM ════════════════════════ -->
    <section style="background:var(--surface-container-lowest);border-top:1px solid rgba(139,145,157,.08);border-bottom:1px solid rgba(139,145,157,.08);padding:80px 40px">
      <div class="container">
        <div class="reveal" style="text-align:center;margin-bottom:16px">
          <div style="font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--outline);font-weight:700;margin-bottom:16px">Het probleem</div>
          <h2 style="font-size:clamp(32px,5vw,52px);font-weight:800;letter-spacing:-1.5px;margin-bottom:16px">Het zit dieper dan <span style="color:var(--tertiary)">tijd</span>.</h2>
          <p style="font-size:18px;color:var(--on-surface-variant);max-width:680px;margin:0 auto 60px">Een docent verzuipt in PR's. Een student leert tussen commits in stilte. En aan het eind van het semester is groei een vermoeden, geen bewijs.</p>
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px">
          <div class="reveal" style="background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-radius:16px;padding:24px">
            <div style="width:48px;height:48px;border-radius:12px;background:rgba(255,186,66,.12);display:grid;place-items:center;margin-bottom:16px">
              <span class="material-symbols-outlined" style="font-size:24px;color:var(--tertiary)">schedule</span>
            </div>
            <h3 style="font-size:20px;font-weight:700;margin-bottom:12px">10 uur per week</h3>
            <div style="font-weight:600;color:var(--on-surface-variant);margin-bottom:8px;font-size:14px">Verzuipen in volume.</div>
            <p style="color:var(--on-surface-variant);line-height:1.6;font-size:14px">Per PR twintig minuten, maal dertig studenten, week na week. Tijd die niet naar lesgeven of één-op-één coaching gaat.</p>
          </div>

          <div class="reveal" style="background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-radius:16px;padding:24px;animation-delay:.1s">
            <div style="width:48px;height:48px;border-radius:12px;background:rgba(255,186,66,.12);display:grid;place-items:center;margin-bottom:16px">
              <span class="material-symbols-outlined" style="font-size:24px;color:var(--tertiary)">history_toggle_off</span>
            </div>
            <h3 style="font-size:20px;font-weight:700;margin-bottom:12px">+5 dagen vertraging</h3>
            <div style="font-weight:600;color:var(--on-surface-variant);margin-bottom:8px;font-size:14px">Feedback komt te laat.</div>
            <p style="color:var(--on-surface-variant);line-height:1.6;font-size:14px">Studenten leren wanneer ze schrijven, niet wanneer jij dagen later reviewt. De bug van maandag is op vrijdag al onderdeel van het volgende probleem.</p>
          </div>

          <div class="reveal" style="background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-radius:16px;padding:24px;animation-delay:.2s">
            <div style="width:48px;height:48px;border-radius:12px;background:rgba(255,186,66,.12);display:grid;place-items:center;margin-bottom:16px">
              <span class="material-symbols-outlined" style="font-size:24px;color:var(--tertiary)">help</span>
            </div>
            <h3 style="font-size:20px;font-weight:700;margin-bottom:12px">Onderbuik, geen bewijs</h3>
            <div style="font-weight:600;color:var(--on-surface-variant);margin-bottom:8px;font-size:14px">Groei is onzichtbaar.</div>
            <p style="color:var(--on-surface-variant);line-height:1.6;font-size:14px">Wie verbetert écht? Wie zit al weken vast op dezelfde fout? Zonder rubric-data per criterium beoordeel je op impressie. Coaching wordt gokwerk.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ════════════════════════ HOW IT WORKS ════════════════════════ -->
    <section id="how" style="background:var(--background);padding:80px 40px">
      <div class="container">
        <div class="reveal" style="text-align:center;margin-bottom:60px">
          <div style="font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--outline);font-weight:700;margin-bottom:16px">Zo werkt het</div>
          <h2 style="font-size:clamp(32px,5vw,52px);font-weight:800;letter-spacing:-1.5px;margin-bottom:16px">Van push naar feedback in seconden.</h2>
          <p style="font-size:18px;color:var(--on-surface-variant);max-width:680px;margin:0 auto">Drie stappen. Geen extra tools. Studenten blijven in GitHub, jij blijft de docent.</p>
        </div>

        <!-- Step 1: Student pusht -->
        <div class="reveal" style="margin-bottom:100px">
          <div class="how-row" style="display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:center">
            <div>
              <div style="display:inline-flex;align-items:center;gap:8px;background:rgba(162,201,255,.12);border:1px solid rgba(162,201,255,.2);padding:6px 12px;border-radius:8px;margin-bottom:16px">
                <span style="font-size:24px;font-weight:800;color:var(--primary)">01</span>
              </div>
              <h3 style="font-size:32px;font-weight:800;letter-spacing:-1px;margin-bottom:16px">Student pusht code</h3>
              <p style="font-size:16px;color:var(--on-surface-variant);line-height:1.7">Een commit landt op GitHub. LEERA reviewt elke commit op regel-niveau — de student ziet wat hij kan verbeteren voor hij een PR opent.</p>
            </div>
            <div style="position:relative">
              <div class="glass" style="background:var(--surface-container-lowest);border-radius:16px;padding:24px;box-shadow:0 20px 60px -20px rgba(162,201,255,.4)">
                <div id="terminal-step1" style="background:var(--surface-container-high);border-radius:10px;padding:16px;font-family:'Fira Code',monospace;font-size:13px;min-height:380px">
                  <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid rgba(139,145,157,.08)">
                    <div style="width:12px;height:12px;border-radius:99px;background:#ff5f57"></div>
                    <div style="width:12px;height:12px;border-radius:99px;background:#ffbd2e"></div>
                    <div style="width:12px;height:12px;border-radius:99px;background:#28ca41"></div>
                    <span style="margin-left:auto;font-size:10px;color:var(--outline)">bash</span>
                  </div>
                  <div style="display:flex;flex-direction:column;gap:8px">
                    <div style="display:flex;align-items:center;gap:8px">
                      <span style="color:var(--primary)">$</span>
                      <span class="typewriter" data-text="git add ." data-speed="50"></span>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px">
                      <span style="color:var(--primary)">$</span>
                      <span class="typewriter" data-text='git commit -m "Leera: elke commit een les"' data-speed="50"></span>
                    </div>
                    <div class="typewriter" data-text="[main a4f2c1b] Leera: elke commit een les" data-speed="30" style="color:var(--outline);font-size:11px;padding-left:16px"></div>
                    <div class="typewriter" data-text=" 2 files changed, 28 insertions(+), 4 deletions(-)" data-speed="30" style="color:var(--outline);font-size:11px;padding-left:16px"></div>
                    <div style="display:flex;align-items:center;gap:8px">
                      <span style="color:var(--primary)">$</span>
                      <span class="typewriter" data-text="git push" data-speed="50"></span>
                    </div>
                    <div class="typewriter" data-text="Enumerating objects: 5, done." data-speed="40" style="color:#7ee1a7;font-size:11px;padding-left:16px"></div>
                    <div class="typewriter" data-text="Writing objects: 100% (3/3), 892 bytes" data-speed="40" style="color:#7ee1a7;font-size:11px;padding-left:16px"></div>
                    <div class="typewriter" data-text="To github.com:inno8/codelens-test.git" data-speed="40" style="color:#7ee1a7;font-size:11px;padding-left:16px"></div>
                    <div class="typewriter" data-text="  f3a1b2c..a4f2c1b  main → main" data-speed="40" style="color:#7ee1a7;font-size:11px;padding-left:16px"></div>
                  </div>
                </div>
              </div>
              <div class="float" style="position:absolute;top:-20px;right:-30px;background:rgba(126,225,167,.15);border:1px solid rgba(126,225,167,.3);padding:10px 14px;border-radius:8px;font-size:12px;color:#7ee1a7;font-weight:700;box-shadow:0 10px 30px -10px rgba(126,225,167,.3);animation-delay:.4s">
                ✓ Pushed to GitHub
              </div>
            </div>
          </div>
        </div>

        <!-- Step 2: AI draftet -->
        <div class="reveal" style="margin-bottom:100px">
          <div class="how-row" style="display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:center">
            <div style="order:2">
              <div style="display:inline-flex;align-items:center;gap:8px;background:rgba(162,201,255,.12);border:1px solid rgba(162,201,255,.2);padding:6px 12px;border-radius:8px;margin-bottom:16px">
                <span style="font-size:24px;font-weight:800;color:var(--primary)">02</span>
              </div>
              <h3 style="font-size:32px;font-weight:800;letter-spacing:-1px;margin-bottom:16px">AI draftet concept</h3>
              <p style="font-size:16px;color:var(--on-surface-variant);line-height:1.7">De AI analyseert de diff, spot patronen, schrijft inline comments en vult rubric-scores in. Klaar voor jouw review.</p>
            </div>
            <div style="position:relative;order:1">
              <div class="glass" style="border-radius:16px;overflow:hidden;box-shadow:0 20px 60px -20px rgba(162,201,255,.4)">
                <div style="background:var(--surface-container-low);padding:20px;border-bottom:1px solid rgba(139,145,157,.08)">
                  <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
                    <div style="width:6px;height:6px;border-radius:99px;background:var(--primary);animation:pulse 2s infinite"></div>
                    <span style="font-size:11px;font-weight:700;color:var(--primary);letter-spacing:.08em;text-transform:uppercase">AI Draftet review…</span>
                    <span style="margin-left:auto;font-size:11px;color:var(--outline);font-family:'Fira Code',monospace">2m 18s</span>
                  </div>
                  <div style="display:flex;flex-direction:column;gap:10px">
                    <div style="display:flex;align-items:center;gap:10px;animation:slideUp .5s .2s both">
                      <span class="material-symbols-outlined" style="font-size:16px;color:#7ee1a7">check_circle</span>
                      <span style="font-size:12px;color:var(--on-surface-variant)">Diff geanalyseerd (47 regels)</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:10px;animation:slideUp .5s .4s both">
                      <span class="material-symbols-outlined" style="font-size:16px;color:#7ee1a7">check_circle</span>
                      <span style="font-size:12px;color:var(--on-surface-variant)">4 inline comments gedraft</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:10px;animation:slideUp .5s .6s both">
                      <div style="width:16px;height:16px;border:2px solid var(--primary);border-top-color:transparent;border-radius:99px;animation:spin 1s linear infinite"></div>
                      <span style="font-size:12px;color:var(--on-surface)">Rubric-scores berekenen…</span>
                    </div>
                  </div>
                </div>
                <div style="background:var(--surface-container-lowest);padding:16px">
                  <div style="font-size:10px;color:var(--outline);margin-bottom:8px;letter-spacing:.08em;text-transform:uppercase">Preview</div>
                  <div style="background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-left:3px solid var(--error);border-radius:8px;padding:10px;animation:slideUp .5s .8s both">
                    <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">
                      <span style="display:inline-flex;padding:2px 6px;border-radius:999px;font-size:9px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;background:rgba(255,180,171,.15);color:var(--error)">Security</span>
                      <code class="mono" style="font-size:9px;color:var(--primary)">auth.ts:47</code>
                    </div>
                    <div style="font-size:11px;color:var(--on-surface-variant);line-height:1.5">Generic error leaks info…</div>
                  </div>
                </div>
              </div>
              <div class="float" style="position:absolute;bottom:-20px;right:-30px;background:rgba(162,201,255,.15);border:1px solid rgba(162,201,255,.3);padding:10px 14px;border-radius:8px;font-size:12px;color:var(--primary);font-weight:700;box-shadow:0 10px 30px -10px rgba(162,201,255,.3);animation-delay:.5s">
                🤖 Concept klaar
              </div>
            </div>
          </div>
        </div>

        <!-- Step 3: Docent reviewt -->
        <div class="reveal">
          <div class="how-row" style="display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:center">
            <div>
              <div style="display:inline-flex;align-items:center;gap:8px;background:rgba(162,201,255,.12);border:1px solid rgba(162,201,255,.2);padding:6px 12px;border-radius:8px;margin-bottom:16px">
                <span style="font-size:24px;font-weight:800;color:var(--primary)">03</span>
              </div>
              <h3 style="font-size:32px;font-weight:800;letter-spacing:-1px;margin-bottom:16px">Jij reviewt & publiceert</h3>
              <p style="font-size:16px;color:var(--on-surface-variant);line-height:1.7">Lees, pas aan, verwijder waar nodig. Eén klik en de feedback gaat naar de student op de PR — waar ze werken.</p>
            </div>
            <div style="position:relative">
              <div class="glass" style="border-radius:16px;overflow:hidden;box-shadow:0 20px 60px -20px rgba(126,225,167,.4)">
                <div style="background:var(--surface-container-low);padding:20px">
                  <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
                    <div style="width:40px;height:40px;border-radius:99px;background:linear-gradient(135deg,#a2c9ff,#58a6ff);display:grid;place-items:center;color:#00315c;font-weight:800;font-size:14px">DM</div>
                    <div>
                      <div style="font-weight:700;font-size:13px">Dennis Meulenberg</div>
                      <div style="font-size:10px;color:var(--outline)">Reviewing Vash's PR</div>
                    </div>
                  </div>

                  <div style="background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-radius:10px;padding:14px;margin-bottom:12px">
                    <div style="font-size:11px;color:var(--outline);margin-bottom:10px;letter-spacing:.08em;text-transform:uppercase">AI Concept</div>
                    <div style="display:flex;flex-direction:column;gap:8px">
                      <div style="display:flex;align-items:center;gap:8px;font-size:12px">
                        <span class="material-symbols-outlined" style="font-size:16px;color:#7ee1a7">check_circle</span>
                        <span style="color:var(--on-surface-variant)">3 comments geaccepteerd</span>
                      </div>
                      <div style="display:flex;align-items:center;gap:8px;font-size:12px">
                        <span class="material-symbols-outlined" style="font-size:16px;color:var(--tertiary)">edit</span>
                        <span style="color:var(--on-surface-variant)">1 comment aangepast</span>
                      </div>
                      <div style="display:flex;align-items:center;gap:8px;font-size:12px">
                        <span class="material-symbols-outlined" style="font-size:16px;color:var(--primary)">fact_check</span>
                        <span style="color:var(--on-surface-variant)">Rubric: 3.2 / 4.0</span>
                      </div>
                    </div>
                  </div>

                  <button class="primary-gradient" style="width:100%;padding:12px;border:0;border-radius:8px;color:var(--on-primary);font-weight:700;font-size:14px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px">
                    <span class="material-symbols-outlined" style="font-size:18px">send</span>
                    Verstuur naar student
                  </button>
                </div>
              </div>
              <div class="float" style="position:absolute;top:-20px;left:-30px;background:rgba(126,225,167,.15);border:1px solid rgba(126,225,167,.3);padding:10px 14px;border-radius:8px;font-size:12px;color:#7ee1a7;font-weight:700;box-shadow:0 10px 30px -10px rgba(126,225,167,.3);animation-delay:.3s">
                ✓ Review in 4m
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ════════════════════════ FEATURES ════════════════════════ -->
    <section id="features">
      <div class="container">
        <div class="reveal" style="text-align:center;margin-bottom:60px">
          <h2 style="font-size:clamp(32px,5vw,52px);font-weight:800;letter-spacing:-1.5px;margin-bottom:16px">Bouwsteen voor klas-grootte feedback.</h2>
          <p style="font-size:18px;color:var(--on-surface-variant);max-width:680px;margin:0 auto">Niet één AI-tool, maar een werkflow. Van het eerste commit tot het eindniveau-overzicht.</p>
        </div>

        <!-- Onze aanpak section -->
        <div class="reveal" style="background:var(--surface-container-lowest);border-radius:20px;padding:60px 40px;margin-bottom:100px">
          <div style="text-align:center;margin-bottom:60px">
            <div style="font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--outline);font-weight:700;margin-bottom:12px">Onze aanpak</div>
            <h3 style="font-size:clamp(28px,4vw,42px);font-weight:800;letter-spacing:-1px;margin-bottom:12px">Niet één AI-call.</h3>
            <h3 style="font-size:clamp(28px,4vw,42px);font-weight:800;letter-spacing:-1px;margin-bottom:16px">Een pijplijn die jouw student kent.</h3>
            <p style="font-size:16px;color:var(--on-surface-variant);max-width:760px;margin:0 auto;line-height:1.7">Andere tools gooien elke PR in ChatGPT en hopen op het beste. Wij draaien eerst gevestigde tools, laden dan de student-historie in, en bouwen pas dán een unieke prompt — afgestemd op deze student, deze commit, jouw rubric.</p>
          </div>

          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px">
            <!-- Step 01 -->
            <div class="reveal" style="background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-radius:12px;padding:24px;position:relative">
              <div style="position:absolute;top:16px;right:16px;font-size:12px;color:var(--outline);font-weight:700">01</div>
              <div style="width:44px;height:44px;border-radius:10px;background:rgba(162,201,255,.12);display:grid;place-items:center;margin-bottom:16px">
                <span class="material-symbols-outlined" style="font-size:22px;color:var(--primary)">build</span>
              </div>
              <h4 style="font-size:16px;font-weight:700;margin-bottom:10px">Statische tools eerst</h4>
              <p style="font-size:13px;color:var(--on-surface-variant);line-height:1.6">Voor het LLM iets ziet, draaien we de gevestigde tools. Goedkoop, snel, betrouwbaar — en ze lossen al een groot deel van de comments op zonder één AI-token.</p>
            </div>

            <!-- Step 02 -->
            <div class="reveal" style="background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-radius:12px;padding:24px;position:relative;animation-delay:.1s">
              <div style="position:absolute;top:16px;right:16px;font-size:12px;color:var(--outline);font-weight:700">02</div>
              <div style="width:44px;height:44px;border-radius:10px;background:rgba(162,201,255,.12);display:grid;place-items:center;margin-bottom:16px">
                <span class="material-symbols-outlined" style="font-size:22px;color:var(--primary)">person_search</span>
              </div>
              <h4 style="font-size:16px;font-weight:700;margin-bottom:10px">Wij laden de student in</h4>
              <p style="font-size:13px;color:var(--on-surface-variant);line-height:1.6">Vorige rubric-scores, terugkerende fouten, skill-trajectorie, wat de student vorige week leerde. Geen leeg blad — de pijplijn weet wie hij voor zich heeft.</p>
            </div>

            <!-- Step 03 -->
            <div class="reveal" style="background:var(--surface-container);border:1px solid rgba(162,201,255,.3);border-radius:12px;padding:24px;position:relative;animation-delay:.2s;box-shadow:0 0 40px -16px rgba(162,201,255,.4)">
              <div style="position:absolute;top:16px;right:16px;font-size:12px;color:var(--primary);font-weight:700">03</div>
              <div style="width:44px;height:44px;border-radius:10px;background:rgba(162,201,255,.2);display:grid;place-items:center;margin-bottom:16px">
                <span class="material-symbols-outlined" style="font-size:22px;color:var(--primary)">tune</span>
              </div>
              <h4 style="font-size:16px;font-weight:700;margin-bottom:10px">Wij bouwen de unieke prompt</h4>
              <p style="font-size:13px;color:var(--on-surface-variant);line-height:1.6">Statische bevindingen + student-context + jouw rubric + jouw stem-kalibratie = één prompt op maat van deze student, deze commit, dit criterium. Niet één template voor iedereen.</p>
            </div>

            <!-- Step 04 -->
            <div class="reveal" style="background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-radius:12px;padding:24px;position:relative;animation-delay:.3s">
              <div style="position:absolute;top:16px;right:16px;font-size:12px;color:var(--outline);font-weight:700">04</div>
              <div style="width:44px;height:44px;border-radius:10px;background:rgba(255,186,66,.15);display:grid;place-items:center;margin-bottom:16px">
                <span class="material-symbols-outlined" style="font-size:22px;color:var(--tertiary)">how_to_reg</span>
              </div>
              <h4 style="font-size:16px;font-weight:700;margin-bottom:10px">Jij geeft het laatste woord</h4>
              <p style="font-size:13px;color:var(--on-surface-variant);line-height:1.6">Concept verschijnt in jouw inbox. Lezen, bijsturen, klikken. Geen comment gaat naar de student zonder jouw klik. Jouw bewerkingen leren de pijplijn hoe jij grade.</p>
            </div>
          </div>
        </div>

        <!-- Three feature cards in grid -->
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px;margin-bottom:100px">
          <div class="feature-card reveal">
            <div style="width:48px;height:48px;border-radius:12px;background:rgba(174,200,239,.12);display:grid;place-items:center;margin-bottom:20px">
              <span class="material-symbols-outlined" style="font-size:24px;color:var(--secondary)">how_to_reg</span>
            </div>
            <h3 style="font-size:20px;font-weight:700;margin-bottom:12px">Jij houdt het laatste woord</h3>
            <p style="color:var(--on-surface-variant);line-height:1.6;font-size:15px">Accepteren, bijsturen of schrappen. Geen comment gaat naar de student zonder dat jij Verstuur klikt.</p>
          </div>

          <div class="feature-card reveal" style="animation-delay:.1s">
            <div style="width:48px;height:48px;border-radius:12px;background:rgba(255,180,171,.12);display:grid;place-items:center;margin-bottom:20px">
              <span class="material-symbols-outlined" style="font-size:24px;color:var(--error)">repeat</span>
            </div>
            <h3 style="font-size:20px;font-weight:700;margin-bottom:12px">Terugkerende fouten in beeld</h3>
            <p style="color:var(--on-surface-variant);line-height:1.6;font-size:15px">Welke patronen blijft een student maken? LEERA herkent ze en maakt ze zichtbaar zodat coaching gericht wordt.</p>
          </div>

          <div class="feature-card reveal" style="animation-delay:.2s">
            <div style="width:48px;height:48px;border-radius:12px;background:rgba(210,168,255,.12);display:grid;place-items:center;margin-bottom:20px">
              <span class="material-symbols-outlined" style="font-size:24px;color:#d2a8ff">dashboard</span>
            </div>
            <h3 style="font-size:20px;font-weight:700;margin-bottom:12px">Klas-overzicht in één blik</h3>
            <p style="color:var(--on-surface-variant);line-height:1.6;font-size:15px">Per cohort: gemiddeld eindniveau, zwakste criteria, leerlingen die afglijden. Bewijs-gebaseerd. Niet onderbuik.</p>
          </div>
        </div>

        <!-- Feature 1: Feedback op elke commit -->
        <div class="reveal feat-row" style="display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:center;margin-bottom:120px">
          <div>
            <h3 style="font-size:36px;font-weight:800;letter-spacing:-1px;margin-bottom:16px">Feedback op elke commit</h3>
            <p style="font-size:16px;color:var(--on-surface-variant);line-height:1.7;margin-bottom:20px">Direct na de push krijgt de student AI-feedback op regel-niveau. Lossen ze het zelf op, dan komt de PR pas binnen als hij echt klaar is.</p>
          </div>
          <div style="position:relative">
            <div class="glass" style="border-radius:16px;overflow:hidden;box-shadow:0 20px 60px -20px rgba(162,201,255,.4)">
              <div style="background:var(--surface-container-low);padding:16px;border-bottom:1px solid rgba(139,145,157,.08)">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
                  <div style="width:6px;height:6px;border-radius:99px;background:var(--primary);animation:pulse 2s infinite"></div>
                  <span style="font-size:11px;font-weight:700;color:var(--primary);letter-spacing:.08em;text-transform:uppercase">AI Draftet…</span>
                </div>
                <div class="diff-mock" style="margin-bottom:12px">
                  <div class="diff-line" style="padding:6px 12px;background:var(--surface-container);border-bottom:1px solid rgba(139,145,157,.08)">
                    <span class="mono" style="font-size:10px;color:var(--outline)">src/auth/middleware.ts</span>
                  </div>
                  <div class="diff-line diff-add" style="animation:slideUp .5s .3s both">
                    <span class="ln" style="font-size:11px">12</span>
                    <span style="color:#7ee1a7;font-size:11px">+</span>
                    <span style="font-size:11px;color:var(--on-surface-variant)">if (!token) throw new AuthError();</span>
                  </div>
                </div>
                <div style="background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-left:3px solid var(--error);border-radius:8px;padding:10px;animation:slideUp .5s .6s both">
                  <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">
                    <span style="display:inline-flex;padding:2px 6px;border-radius:999px;font-size:9px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;background:rgba(255,180,171,.15);color:var(--error)">Security</span>
                    <code class="mono" style="font-size:9px;color:var(--primary)">:12</code>
                  </div>
                  <div style="font-size:11px;color:var(--on-surface-variant);line-height:1.5">Generic error leaks info. Use <code class="mono" style="background:rgba(162,201,255,.12);padding:1px 3px;border-radius:2px;font-size:10px">401</code> zonder details.</div>
                </div>
              </div>
              <div style="background:var(--surface-container-lowest);padding:12px;display:flex;align-items:center;gap:8px;font-size:11px;color:var(--on-surface-variant)">
                <span class="material-symbols-outlined" style="font-size:14px;color:var(--primary)">bolt</span>
                Gedraft in 2m 18s · 4 comments · rubric 3.2 / 4.0
              </div>
            </div>
            <div class="float" style="position:absolute;top:-20px;right:-20px;background:rgba(126,225,167,.15);border:1px solid rgba(126,225,167,.3);padding:10px 14px;border-radius:8px;font-size:12px;color:#7ee1a7;font-weight:700;box-shadow:0 10px 30px -10px rgba(126,225,167,.3);animation-delay:.2s">
              ✓ 87% sneller
            </div>
          </div>
        </div>

        <!-- Feature 2: Rubric in stem -->
        <div class="reveal feat-row" style="display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:center;margin-bottom:120px">
          <div style="order:2">
            <h3 style="font-size:36px;font-weight:800;letter-spacing:-1px;margin-bottom:16px">Rubric-concept in jouw stem</h3>
            <p style="font-size:16px;color:var(--on-surface-variant);line-height:1.7;margin-bottom:20px">Per criterium een score + bewijs + suggestie. De AI schrijft als jij — niet als ChatGPT.</p>
          </div>
          <div style="position:relative;order:1">
            <div class="glass" style="border-radius:16px;overflow:hidden;box-shadow:0 20px 60px -20px rgba(126,225,167,.4)">
              <div style="background:var(--surface-container-low);padding:20px">
                <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:16px">
                  <div style="font-size:44px;font-weight:800;letter-spacing:-1.5px;color:var(--primary);animation:scaleIn .6s both">3.2</div>
                  <div style="font-size:14px;color:var(--outline)">/ 4.0</div>
                  <div style="margin-left:auto;font-size:11px;color:#7ee1a7;font-weight:700;text-transform:uppercase;letter-spacing:.08em">Voldoende</div>
                </div>
                <div style="height:6px;background:var(--surface-container-high);border-radius:999px;overflow:hidden;margin-bottom:20px">
                  <div style="width:80%;height:100%;background:linear-gradient(90deg,var(--primary),var(--primary-container));border-radius:999px;animation:slideUp .6s .2s both"></div>
                </div>
                <div style="display:flex;flex-direction:column;gap:10px">
                  <div style="background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-radius:10px;padding:12px;animation:slideUp .5s .3s both">
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
                      <div class="dial" style="width:32px;height:32px">
                        <svg width="32" height="32">
                          <circle cx="16" cy="16" r="12" stroke="var(--surface-container-high)" stroke-width="3" fill="none"/>
                          <circle cx="16" cy="16" r="12" stroke="var(--primary)" stroke-width="3" fill="none" stroke-dasharray="75.4" stroke-dashoffset="18.85" stroke-linecap="round" style="transform:rotate(-90deg);transform-origin:50% 50%"/>
                        </svg>
                      </div>
                      <div style="flex:1">
                        <div style="font-weight:600;font-size:13px">Veiligheid</div>
                        <div style="font-size:10px;color:var(--outline)">30% · score 3</div>
                      </div>
                    </div>
                    <div style="font-size:10px;color:var(--on-surface-variant);line-height:1.5;font-style:italic;border-top:1px dashed rgba(139,145,157,.15);padding-top:8px">Expiry-check correct, maar localStorage opslag is geen secret store…</div>
                  </div>
                  <div style="background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-radius:10px;padding:12px;animation:slideUp .5s .4s both">
                    <div style="display:flex;align-items:center;gap:10px">
                      <div class="dial" style="width:32px;height:32px">
                        <svg width="32" height="32">
                          <circle cx="16" cy="16" r="12" stroke="var(--surface-container-high)" stroke-width="3" fill="none"/>
                          <circle cx="16" cy="16" r="12" stroke="#7ee1a7" stroke-width="3" fill="none" stroke-dasharray="75.4" stroke-dashoffset="0" stroke-linecap="round" style="transform:rotate(-90deg);transform-origin:50% 50%"/>
                        </svg>
                      </div>
                      <div style="flex:1">
                        <div style="font-weight:600;font-size:13px">Leesbaarheid</div>
                        <div style="font-size:10px;color:var(--outline)">20% · score 4</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="float" style="position:absolute;bottom:-20px;left:-20px;background:rgba(162,201,255,.15);border:1px solid rgba(162,201,255,.3);padding:10px 14px;border-radius:8px;font-size:12px;color:var(--primary);font-weight:700;box-shadow:0 10px 30px -10px rgba(162,201,255,.3);animation-delay:.4s">
              📊 6 criteria · auto-calc
            </div>
          </div>
        </div>

        <!-- Feature 3: Skill trajectorie -->
        <div class="reveal feat-row" style="display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:center;margin-bottom:80px">
          <div>
            <h3 style="font-size:36px;font-weight:800;letter-spacing:-1px;margin-bottom:16px">Skill-trajectorie per student</h3>
            <p style="font-size:16px;color:var(--on-surface-variant);line-height:1.7;margin-bottom:20px">Bayesiaanse scores per vaardigheid die zich aanpassen aan bewijs. Geen 100% bij default — pas confident als de student het verdiend heeft.</p>
          </div>
          <div style="position:relative">
            <div class="glass" style="border-radius:16px;overflow:hidden;box-shadow:0 20px 60px -20px rgba(255,186,66,.4)">
              <div style="background:var(--surface-container-low);padding:20px">
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
                  <div style="width:48px;height:48px;border-radius:99px;background:linear-gradient(135deg,#a2c9ff,#58a6ff);display:grid;place-items:center;color:#00315c;font-weight:800;font-size:18px">VS</div>
                  <div>
                    <div style="font-weight:700;font-size:14px">Vash De Stampede</div>
                    <div style="font-size:11px;color:var(--outline)">Klas 2A ICT — MBO-4</div>
                  </div>
                </div>
                <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:14px">
                  <div style="font-size:40px;font-weight:800;letter-spacing:-1.5px;animation:scaleIn .6s both">74<span style="font-size:18px;color:var(--outline)">%</span></div>
                  <div style="font-size:12px;color:#7ee1a7;font-weight:600">+6 deze week</div>
                </div>
                <div style="background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-radius:10px;padding:12px;margin-bottom:12px;animation:slideUp .5s .3s both">
                  <div style="font-size:10px;font-weight:700;color:var(--outline);letter-spacing:.08em;text-transform:uppercase;margin-bottom:8px">Mastery trend · 10w</div>
                  <svg width="100%" height="60" viewBox="0 0 200 60" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="tg" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stop-color="#a2c9ff" stop-opacity=".4"/>
                        <stop offset="100%" stop-color="#a2c9ff" stop-opacity="0"/>
                      </linearGradient>
                    </defs>
                    <path d="M0,50 L22,45 L44,38 L66,42 L88,32 L110,28 L132,30 L154,22 L176,28 L198,18 L200,58 L0,58 Z" fill="url(#tg)"/>
                    <path d="M0,50 L22,45 L44,38 L66,42 L88,32 L110,28 L132,30 L154,22 L176,28 L198,18" stroke="#a2c9ff" stroke-width="2" fill="none"/>
                  </svg>
                </div>
                <div style="display:flex;flex-direction:column;gap:8px">
                  <div style="animation:slideUp .5s .4s both">
                    <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px">
                      <span style="color:var(--on-surface)">Veiligheid</span>
                      <span style="color:var(--outline)">62% <span style="color:#7ee1a7;font-weight:600">+8</span></span>
                    </div>
                    <div style="height:4px;background:var(--surface-container-high);border-radius:999px;overflow:hidden">
                      <div style="width:62%;height:100%;background:var(--error);border-radius:999px"></div>
                    </div>
                  </div>
                  <div style="animation:slideUp .5s .5s both">
                    <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px">
                      <span style="color:var(--on-surface)">Testen</span>
                      <span style="color:var(--outline)">88% <span style="color:#7ee1a7;font-weight:600">+1</span></span>
                    </div>
                    <div style="height:4px;background:var(--surface-container-high);border-radius:999px;overflow:hidden">
                      <div style="width:88%;height:100%;background:#7ee1a7;border-radius:999px"></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="float" style="position:absolute;top:-20px;right:-20px;background:rgba(255,186,66,.15);border:1px solid rgba(255,186,66,.3);padding:10px 14px;border-radius:8px;font-size:12px;color:var(--tertiary);font-weight:700;box-shadow:0 10px 30px -10px rgba(255,186,66,.3);animation-delay:.2s">
              📈 Real-time tracking
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ════════════════════════ TALEN ════════════════════════ -->
    <section id="languages" style="background:var(--background);padding:80px 40px">
      <div class="container">
        <div class="reveal" style="text-align:center;margin-bottom:60px">
          <div style="font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--outline);font-weight:700;margin-bottom:12px">Talen</div>
          <h2 style="font-size:clamp(32px,5vw,52px);font-weight:800;letter-spacing:-1.5px;margin-bottom:16px">Werkt met je curriculum.</h2>
          <p style="font-size:16px;color:var(--on-surface-variant);max-width:680px;margin:0 auto;line-height:1.7">De talen die je studenten leren — Python tot SQL tot CSS — krijgen rubric-bewuste feedback. Niet één generieke prompt voor alles.</p>
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:16px;max-width:900px;margin:0 auto 40px">
          <!-- Python -->
          <div class="reveal lang-card">
            <svg width="20" height="20" viewBox="0 0 256 255" fill="none">
              <defs>
                <linearGradient id="py1" x1="12.959%" y1="12.039%" x2="79.639%" y2="78.201%"><stop offset="0%" stop-color="#387EB8"/><stop offset="100%" stop-color="#366994"/></linearGradient>
                <linearGradient id="py2" x1="19.128%" y1="20.579%" x2="90.742%" y2="88.429%"><stop offset="0%" stop-color="#FFE052"/><stop offset="100%" stop-color="#FFC331"/></linearGradient>
              </defs>
              <path d="M126.916.072c-64.832 0-60.784 28.115-60.784 28.115l.072 29.128h61.868v8.745H41.631S.145 61.355.145 126.77c0 65.417 36.21 63.097 36.21 63.097h21.61v-30.356s-1.165-36.21 35.632-36.21h61.362s34.475.557 34.475-33.319V33.97S194.67.072 126.916.072zM92.802 19.66a11.12 11.12 0 0 1 11.13 11.13 11.12 11.12 0 0 1-11.13 11.13 11.12 11.12 0 0 1-11.13-11.13 11.12 11.12 0 0 1 11.13-11.13z" fill="url(#py1)"/>
              <path d="M128.757 254.126c64.832 0 60.784-28.115 60.784-28.115l-.072-29.127H127.6v-8.745h86.441s41.486 4.705 41.486-60.712c0-65.416-36.21-63.096-36.21-63.096h-21.61v30.355s1.165 36.21-35.632 36.21h-61.362s-34.475-.557-34.475 33.32v56.013s-5.235 33.897 62.518 33.897zm34.114-19.586a11.12 11.12 0 0 1-11.13-11.13 11.12 11.12 0 0 1 11.13-11.131 11.12 11.12 0 0 1 11.13 11.13 11.12 11.12 0 0 1-11.13 11.13z" fill="url(#py2)"/>
            </svg>
            <span>Python</span>
          </div>

          <!-- JavaScript -->
          <div class="reveal lang-card" style="animation-delay:.05s">
            <svg width="20" height="20" viewBox="0 0 256 256" fill="none">
              <rect width="256" height="256" rx="28" fill="#F7DF1E"/>
              <path d="M67.312 213.932l19.59-11.856c3.78 6.701 7.218 12.371 15.465 12.371 7.905 0 12.889-3.092 12.889-15.12v-81.798h24.057v82.138c0 24.917-14.606 36.259-35.916 36.259-19.245 0-30.416-9.967-36.087-21.996m85.07-2.576l19.588-11.341c5.157 8.421 11.859 14.607 23.715 14.607 9.969 0 16.325-4.984 16.325-11.858 0-8.248-6.53-11.17-17.528-15.98l-6.013-2.58c-17.357-7.387-28.87-16.667-28.87-36.257 0-18.044 13.747-31.792 35.228-31.792 15.294 0 26.292 5.328 34.196 19.247l-18.732 12.03c-4.125-7.389-8.591-10.31-15.465-10.31-7.046 0-11.514 4.468-11.514 10.31 0 7.217 4.468 10.14 14.778 14.608l6.014 2.577c20.45 8.765 31.963 17.7 31.963 37.804 0 21.654-17.012 33.51-39.867 33.51-22.339 0-36.774-10.654-43.819-24.574" fill="#000"/>
            </svg>
            <span>JavaScript</span>
          </div>

          <!-- TypeScript -->
          <div class="reveal lang-card" style="animation-delay:.1s">
            <svg width="20" height="20" viewBox="0 0 256 256" fill="none">
              <rect width="256" height="256" fill="#3178C6"/>
              <path d="M56.611 128.85l-.081 10.483h33.32v94.68H113.42v-94.68h33.32v-10.28c0-5.69-.122-10.444-.284-10.566-.122-.162-20.399-.244-44.983-.203l-44.739.122-.122 10.443zM206.567 118.108c6.501 1.626 11.459 4.51 16.01 9.224 2.357 2.52 5.851 7.112 6.136 8.209.08.325-11.053 7.802-17.798 11.987-.244.162-1.22-.894-2.317-2.52-3.291-4.79-6.745-6.867-12.028-7.233-7.76-.529-12.759 3.535-12.718 10.321 0 1.992.284 3.17 1.097 4.796 1.707 3.535 4.876 5.648 14.832 9.955 18.326 7.883 26.168 13.084 31.045 20.48 5.445 8.25 6.664 21.415 2.966 31.208-4.063 10.646-14.14 17.879-28.323 20.276-4.388.772-14.79.65-19.504-.203-10.28-1.829-20.033-6.908-26.047-13.572-2.357-2.601-6.949-9.387-6.664-9.875.122-.162 1.178-.812 2.356-1.503 1.138-.65 5.446-3.13 9.509-5.486l7.355-4.267 1.544 2.276c2.154 3.29 6.867 7.802 9.712 9.305 8.167 4.308 19.383 3.698 24.909-1.26 2.357-2.153 3.332-4.388 3.332-7.68 0-2.966-.366-4.266-1.91-6.501-1.99-2.845-6.054-5.242-17.595-10.24-13.206-5.69-18.895-9.225-24.096-14.832-3.007-3.25-5.852-8.452-7.03-12.8-.975-3.616-1.22-12.678-.447-16.335 2.723-12.76 12.353-21.658 26.25-24.3 4.51-.853 14.994-.528 19.424.57z" fill="#FFF"/>
            </svg>
            <span>TypeScript</span>
          </div>

          <!-- Java -->
          <div class="reveal lang-card" style="animation-delay:.15s">
            <svg width="20" height="20" viewBox="0 0 256 346" fill="none">
              <path d="M82.554 267.473s-13.198 7.675 9.393 10.272c27.369 3.122 41.356 2.675 71.517-3.034 0 0 7.93 4.972 19.003 9.279-67.611 28.977-153.019-1.679-99.913-16.517M74.292 229.659s-14.803 10.958 7.805 13.296c29.236 3.016 52.324 3.263 92.276-4.43 0 0 5.526 5.602 14.215 8.666-81.747 23.904-172.798 1.885-114.296-17.532" fill="#5382A1"/>
              <path d="M143.942 165.515c16.66 19.18-4.377 36.44-4.377 36.44s42.301-21.837 22.874-49.183c-18.144-25.5-32.059-38.172 43.268-81.858 0 0-118.238 29.53-61.765 94.6" fill="#E76F00"/>
              <path d="M233.364 295.442s9.767 8.047-10.757 14.273c-39.026 11.823-162.432 15.393-196.714.471-12.323-5.36 10.787-12.8 18.056-14.362 7.581-1.644 11.914-1.337 11.914-1.337-13.705-9.655-88.583 18.957-38.034 27.15 137.853 22.356 251.292-10.066 215.535-26.195M88.9 190.48s-62.771 14.91-22.228 20.323c17.118 2.292 51.243 1.774 83.03-.89 25.978-2.19 52.063-6.85 52.063-6.85s-9.16 3.923-15.787 8.448c-63.744 16.765-186.886 8.966-151.435-8.183 29.981-14.492 54.358-12.848 54.358-12.848M201.506 253.422c64.8-33.672 34.839-66.03 13.927-61.67-5.126 1.066-7.387 1.99-7.387 1.99s1.896-2.963 5.529-4.231c41.295-14.512 73.064 42.845-13.355 65.647 0 0 .998-.895 1.286-1.736" fill="#5382A1"/>
              <path d="M162.439.371s35.887 35.9-34.037 91.101c-56.071 44.282-12.786 69.53-.023 98.377-32.73-29.53-56.75-55.526-40.635-79.72C111.395 74.612 176.918 57.393 162.44.37" fill="#E76F00"/>
              <path d="M95.268 344.665c62.199 3.982 157.712-2.209 159.974-31.64 0 0-4.348 11.158-51.404 20.018-53.088 9.99-118.564 8.824-157.399 2.421.001 0 7.95 6.58 48.83 9.201" fill="#5382A1"/>
            </svg>
            <span>Java</span>
          </div>

          <!-- C# -->
          <div class="reveal lang-card" style="animation-delay:.2s">
            <svg width="20" height="20" viewBox="0 0 256 256" fill="none">
              <rect width="256" height="256" rx="20" fill="#239120"/>
              <text x="128" y="170" font-family="Inter,sans-serif" font-size="160" font-weight="700" fill="#FFF" text-anchor="middle">C#</text>
            </svg>
            <span>C#</span>
          </div>

          <!-- PHP -->
          <div class="reveal lang-card" style="animation-delay:.25s">
            <svg width="20" height="20" viewBox="0 0 256 134" fill="none">
              <ellipse cx="128" cy="67" rx="128" ry="67" fill="#777BB3"/>
              <path d="M73 47h22c14 0 21 6 21 18s-9 19-23 19h-9l-3 14H66l11-51zm9 11l-4 18h7c8 0 12-3 12-10s-3-8-10-8h-5zm44-11h17l-2 12c5-8 12-12 21-12 11 0 16 7 14 18l-6 33h-15l5-29c1-5-1-7-5-7-7 0-11 5-13 14l-5 22h-15l11-51zm63 0h22c14 0 21 6 21 18s-9 19-23 19h-9l-3 14h-15l11-51zm9 11l-4 18h7c8 0 12-3 12-10s-3-8-10-8h-5z" fill="#FFF"/>
            </svg>
            <span>PHP</span>
          </div>

          <!-- HTML -->
          <div class="reveal lang-card" style="animation-delay:.3s">
            <svg width="20" height="20" viewBox="0 0 256 256" fill="none">
              <path d="M28 26l8 194 91 26 91-26 8-194H28zm149 60l-2 20-2 22-76-1 2 21h74l-5 58-1 14-46 13-46-13-3-32h21l1 16 25 7h1l25-7 3-28H73l-6-66h118l2-24H64l-2-21h119l-2 21z" fill="#E34C26"/>
            </svg>
            <span>HTML</span>
          </div>

          <!-- CSS -->
          <div class="reveal lang-card" style="animation-delay:.35s">
            <svg width="20" height="20" viewBox="0 0 256 256" fill="none">
              <path d="M28 26l8 194 91 26 91-26 8-194H28zm149 86l-1 14-3 29-1 8-46 13v1h-1l-46-13-3-34h22l2 17 25 7 25-7 3-25H64l-2-22-1-20h118l2-18H64l-2-21h121l-4 44z" fill="#1572B6"/>
            </svg>
            <span>CSS</span>
          </div>

          <!-- SQL -->
          <div class="reveal lang-card" style="animation-delay:.4s">
            <svg width="20" height="20" viewBox="0 0 256 256" fill="none">
              <ellipse cx="128" cy="48" rx="84" ry="28" fill="#CC2927"/>
              <path d="M44 48v60c0 16 38 28 84 28s84-12 84-28V48" stroke="#CC2927" stroke-width="14" fill="none"/>
              <path d="M44 116v60c0 16 38 28 84 28s84-12 84-28v-60" stroke="#CC2927" stroke-width="14" fill="none"/>
              <ellipse cx="128" cy="116" rx="84" ry="28" fill="none" stroke="#CC2927" stroke-width="6"/>
            </svg>
            <span>SQL</span>
          </div>

          <!-- Bash -->
          <div class="reveal lang-card" style="animation-delay:.45s">
            <svg width="20" height="20" viewBox="0 0 256 256" fill="none">
              <rect width="256" height="256" rx="24" fill="#293138"/>
              <path d="M64 88l32 24-32 24M104 144h64" stroke="#4EAA25" stroke-width="14" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
            <span>Bash</span>
          </div>
        </div>

        <!-- Frameworks subsection — same card grid pattern, brand-color logos. -->
        <div class="reveal" style="text-align:center;margin-top:48px;margin-bottom:32px">
          <div style="font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--outline);font-weight:700;margin-bottom:8px">Frameworks</div>
          <p style="font-size:14px;color:var(--on-surface-variant);max-width:520px;margin:0 auto">
            En de frameworks die je studenten gebruiken op MBO-4 niveau.
          </p>
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:16px;max-width:900px;margin:0 auto">
          <!-- Laravel — most common in MBO-4 -->
          <div class="reveal lang-card">
            <svg width="20" height="20" viewBox="0 0 50 52" fill="none">
              <path d="M49.626 11.564a.815.815 0 0 1 .028.209v10.972a.812.812 0 0 1-.405.703l-9.21 5.302v10.508c0 .288-.154.554-.403.7L20.42 51.115a.92.92 0 0 1-.144.058l-.054.016a.815.815 0 0 1-.413 0l-.061-.018a.794.794 0 0 1-.137-.056L.42 39.96a.812.812 0 0 1-.404-.703V6.342c0-.072.01-.142.028-.21a.756.756 0 0 1 .015-.05.793.793 0 0 1 .037-.087.798.798 0 0 1 .04-.069.8.8 0 0 1 .054-.072.736.736 0 0 1 .052-.06.83.83 0 0 1 .069-.058.752.752 0 0 1 .063-.05h.001L10.027.122a.811.811 0 0 1 .81 0l9.65 5.563h.002a.736.736 0 0 1 .063.05.789.789 0 0 1 .067.058.821.821 0 0 1 .054.06.78.78 0 0 1 .054.072.706.706 0 0 1 .04.069.806.806 0 0 1 .037.087.745.745 0 0 1 .015.05.81.81 0 0 1 .029.21v20.566l8.004-4.609v-10.51c0-.07.01-.141.028-.21a.694.694 0 0 1 .015-.05.847.847 0 0 1 .037-.086.825.825 0 0 1 .04-.069.781.781 0 0 1 .054-.073.694.694 0 0 1 .052-.06.852.852 0 0 1 .07-.057.722.722 0 0 1 .062-.05l9.65-5.564a.811.811 0 0 1 .811 0l9.65 5.563a.732.732 0 0 1 .064.05.835.835 0 0 1 .067.057.789.789 0 0 1 .054.061.741.741 0 0 1 .054.072.726.726 0 0 1 .04.069c.014.028.027.057.037.086a.732.732 0 0 1 .015.05Z" fill="#FF2D20"/>
            </svg>
            <span>Laravel</span>
          </div>

          <!-- Django -->
          <div class="reveal lang-card" style="animation-delay:.05s">
            <svg width="20" height="20" viewBox="0 0 256 256" fill="none">
              <rect width="256" height="256" rx="20" fill="#092E20"/>
              <path d="M48 56h32v144c-12 4-22 6-32 6-26 0-44-15-44-50 0-32 18-50 44-50zm0 76c-8 0-12 6-12 24 0 18 4 24 12 24 4 0 8-1 12-2v-44c-4-1-8-2-12-2zM112 96h32v104h-32V96zm0-40h32v24h-32V56zM168 96h32v8c8-6 16-10 24-10 24 0 36 14 36 40v66h-32v-60c0-12-6-18-16-18-4 0-8 2-12 4v74h-32V96z" fill="#FFF"/>
            </svg>
            <span>Django</span>
          </div>

          <!-- Vue -->
          <div class="reveal lang-card" style="animation-delay:.1s">
            <svg width="20" height="20" viewBox="0 0 256 220" fill="none">
              <path d="M204.8 0h-37.94L128 67.498 89.18 0H0L128 220 256 0h-51.2z" fill="#41B883"/>
              <path d="M167.1 0L128 67.498 89.18 0H51.2L128 132 204.8 0h-37.7z" fill="#34495E"/>
            </svg>
            <span>Vue</span>
          </div>

          <!-- React -->
          <div class="reveal lang-card" style="animation-delay:.15s">
            <svg width="20" height="20" viewBox="0 0 256 228" fill="none">
              <circle cx="128" cy="113.5" r="12" fill="#61DAFB"/>
              <ellipse cx="128" cy="113.5" rx="124" ry="48" stroke="#61DAFB" stroke-width="8" fill="none"/>
              <ellipse cx="128" cy="113.5" rx="124" ry="48" stroke="#61DAFB" stroke-width="8" fill="none" transform="rotate(60 128 113.5)"/>
              <ellipse cx="128" cy="113.5" rx="124" ry="48" stroke="#61DAFB" stroke-width="8" fill="none" transform="rotate(120 128 113.5)"/>
            </svg>
            <span>React</span>
          </div>

          <!-- Next.js -->
          <div class="reveal lang-card" style="animation-delay:.2s">
            <svg width="20" height="20" viewBox="0 0 256 256" fill="none">
              <circle cx="128" cy="128" r="128" fill="#000"/>
              <path d="M82 76v104h12V96l112 144 14-8L98 80c-2-3-6-4-10-4h-6zm74 0v60l12 16V76h-12z" fill="#FFF"/>
            </svg>
            <span>Next.js</span>
          </div>

          <!-- Spring Boot -->
          <div class="reveal lang-card" style="animation-delay:.25s">
            <svg width="20" height="20" viewBox="0 0 256 256" fill="none">
              <circle cx="128" cy="128" r="128" fill="#6DB33F"/>
              <path d="M180 60c-12 24-36 36-64 40-44 6-66 28-66 64 0 36 26 56 64 56 44 0 70-28 70-72 0-32-4-58-4-88zM84 192c-2-6-4-12-4-20 0-26 18-40 50-44 24-3 42-12 54-26-2 24-4 50-4 70 0 30-18 48-50 48-22 0-40-10-46-28zM196 44c-2-2-6-2-8 0L168 64l8 8 20-20c2-2 2-6 0-8z" fill="#FFF"/>
            </svg>
            <span>Spring Boot</span>
          </div>

          <!-- ASP.NET -->
          <div class="reveal lang-card" style="animation-delay:.3s">
            <svg width="20" height="20" viewBox="0 0 256 256" fill="none">
              <rect width="256" height="256" rx="20" fill="#512BD4"/>
              <text x="128" y="170" font-family="Inter,sans-serif" font-size="100" font-weight="700" fill="#FFF" text-anchor="middle">.NET</text>
            </svg>
            <span>ASP.NET</span>
          </div>

          <!-- Tailwind CSS -->
          <div class="reveal lang-card" style="animation-delay:.35s">
            <svg width="20" height="20" viewBox="0 0 256 154" fill="none">
              <path d="M128 0C93.867 0 72.533 17.067 64 51.2 76.8 34.133 91.733 27.733 108.8 32c9.737 2.434 16.697 9.499 24.401 17.318C145.751 62.057 160.275 76.8 192 76.8c34.133 0 55.467-17.067 64-51.2-12.8 17.067-27.733 23.467-44.8 19.2-9.737-2.434-16.697-9.499-24.401-17.318C174.249 14.743 159.725 0 128 0ZM64 76.8C29.867 76.8 8.533 93.867 0 128c12.8-17.067 27.733-23.467 44.8-19.2 9.737 2.434 16.697 9.499 24.401 17.318C81.751 138.857 96.275 153.6 128 153.6c34.133 0 55.467-17.067 64-51.2-12.8 17.067-27.733 23.467-44.8 19.2-9.737-2.434-16.697-9.499-24.401-17.318C110.249 91.543 95.725 76.8 64 76.8Z" fill="#06B6D4"/>
            </svg>
            <span>Tailwind</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ════════════════════════ VOOR WIE ════════════════════════ -->
    <section style="background:var(--surface-container-lowest);border-top:1px solid rgba(139,145,157,.08);border-bottom:1px solid rgba(139,145,157,.08);padding:120px 40px">
      <div class="container">
        <div class="reveal" style="max-width:800px">
          <div style="font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--outline);font-weight:700;margin-bottom:16px">Voor wie</div>
          <h2 style="font-size:clamp(32px,5vw,52px);font-weight:800;letter-spacing:-1.5px;margin-bottom:20px">Gebouwd voor de Nederlandse MBO-4 ICT-docent.</h2>
          <p style="font-size:18px;color:var(--on-surface-variant);line-height:1.7;margin-bottom:24px">Geen Amerikaans bootcamp. Geen havo-vwo cosmetica. LEERA is gemaakt voor de docenten die werkstukken nakijken op kerntaken, werkprocessen en gedragsindicatoren — in de taal van het examenproject.</p>

          <div style="background:var(--surface-container);border:1px solid rgba(139,145,157,.08);border-radius:16px;padding:24px;margin-top:32px">
            <ul style="list-style:none;display:flex;flex-direction:column;gap:14px">
              <li style="display:flex;align-items:start;gap:12px">
                <span class="material-symbols-outlined" style="font-size:20px;color:var(--primary);margin-top:2px">check_circle</span>
                <div>
                  <div style="font-weight:600;margin-bottom:4px">Rubric-templates op MBO-4 niveau, gekoppeld aan kerntaken</div>
                  <div style="font-size:14px;color:var(--on-surface-variant)">Configureer je template één keer — gebruik het voor alle studenten</div>
                </div>
              </li>
              <li style="display:flex;align-items:start;gap:12px">
                <span class="material-symbols-outlined" style="font-size:20px;color:var(--primary);margin-top:2px">check_circle</span>
                <div>
                  <div style="font-weight:600;margin-bottom:4px">Nederlandse feedback in jouw stem — geen vertaalde standaardzinnen</div>
                  <div style="font-size:14px;color:var(--on-surface-variant)">AI leert hoe jij schrijft en matcht je toon</div>
                </div>
              </li>
              <li style="display:flex;align-items:start;gap:12px">
                <span class="material-symbols-outlined" style="font-size:20px;color:var(--primary);margin-top:2px">check_circle</span>
                <div>
                  <div style="font-weight:600;margin-bottom:4px">GitHub-gebaseerd, omdat dat is waar je studenten straks werken</div>
                  <div style="font-size:14px;color:var(--on-surface-variant)">Studenten blijven in hun workflow — jij ook</div>
                </div>
              </li>
              <li style="display:flex;align-items:start;gap:12px">
                <span class="material-symbols-outlined" style="font-size:20px;color:var(--primary);margin-top:2px">check_circle</span>
                <div>
                  <div style="font-weight:600;margin-bottom:4px">AVG-compliant, data blijft in de EU</div>
                  <div style="font-size:14px;color:var(--on-surface-variant)">Geen Amerikaanse cloud zonder meer; voldoet aan GDPR</div>
                </div>
              </li>
            </ul>
          </div>
        </div>

      </div>
    </section>

    <!-- ════════════════════════ FOOTER ════════════════════════ -->
    <footer>
      <div class="container">
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:40px;margin-bottom:40px">
          <div>
            <img src="/logo/leera-wordmark-mono.svg" alt="LEERA" style="height:28px;margin-bottom:16px;opacity:.85" />
            <p style="color:var(--on-surface-variant);font-size:14px;line-height:1.6">Nakijken Copilot voor het MBO. Elke commit een les, elke PR een beoordeling die uit bewijs komt.</p>
          </div>

          <div>
            <div style="font-weight:700;margin-bottom:12px;font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--outline)">Product</div>
            <div style="display:flex;flex-direction:column;gap:8px">
              <button @click="scrollTo('features')" class="footer-link">Features</button>
              <button @click="scrollTo('how')" class="footer-link">Zo werkt het</button>
              <button @click="scrollTo('languages')" class="footer-link">Talen</button>
              <button @click="goLogin" class="footer-link">Inloggen</button>
            </div>
          </div>

          <div>
            <div style="font-weight:700;margin-bottom:12px;font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--outline)">Bedrijf</div>
            <div style="display:flex;flex-direction:column;gap:8px">
              <a href="mailto:inno8techs@gmail.com" class="footer-link">Contact</a>
              <router-link to="/privacy" class="footer-link">Privacy</router-link>
              <router-link to="/voorwaarden" class="footer-link">Voorwaarden</router-link>
              <router-link to="/dpa" class="footer-link">DPA</router-link>
            </div>
          </div>
        </div>

        <div style="border-top:1px solid rgba(139,145,157,.08);padding-top:24px;display:flex;justify-content:center;align-items:center;flex-wrap:wrap;gap:16px">
          <div style="color:var(--outline);font-size:13px">© 2026 LEERA</div>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.landing-root {
  /* Design tokens — mirror tailwind.config.js extends so this view matches the
     rest of the app even though the inline styles use the CSS-vars form. */
  --background: #10141a;
  --surface: #10141a;
  --surface-container-lowest: #0a0e14;
  --surface-container-low: #181c22;
  --surface-container: #1c2026;
  --surface-container-high: #262a31;
  --surface-container-highest: #31353c;
  --primary: #a2c9ff;
  --primary-container: #58a6ff;
  --on-primary: #00315c;
  --secondary: #aec8ef;
  --tertiary: #ffba42;
  --error: #ffb4ab;
  --on-surface: #dfe2eb;
  --on-surface-variant: #c0c7d4;
  --outline: #8b919d;
  --outline-variant: #414752;

  background: var(--background);
  color: var(--on-surface);
  font-family: 'Inter', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  font-feature-settings: "ss01", "cv11";
  overflow-x: hidden;
  min-height: 100vh;
}

.landing-root :deep(.mono),
.landing-root .mono {
  font-family: 'Fira Code', monospace;
  font-variant-ligatures: none;
}

.dots {
  background-image: radial-gradient(rgba(162, 201, 255, .06) 1px, transparent 1px);
  background-size: 22px 22px;
}

.primary-gradient {
  background: linear-gradient(135deg, #a2c9ff 0%, #58a6ff 100%);
}

.glow {
  box-shadow: 0 0 60px -20px rgba(162, 201, 255, .6), 0 20px 40px -20px rgba(0, 0, 0, .5);
}

.glass {
  background: rgba(28, 32, 38, .72);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid rgba(162, 201, 255, .08);
}

@keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-12px); } }
@keyframes drift { 0% { background-position: 0 0; } 100% { background-position: 22px 22px; } }
@keyframes pulse { 0%, 100% { opacity: .6; } 50% { opacity: 1; } }
@keyframes slideUp { from { opacity: 0; transform: translateY(40px); } to { opacity: 1; transform: translateY(0); } }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes scaleIn { from { opacity: 0; transform: scale(.92); } to { opacity: 1; transform: scale(1); } }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.drift { animation: drift 14s linear infinite; }
.float { animation: float 6s ease-in-out infinite; }

/* Scroll-reveal */
.reveal {
  opacity: 0;
  transform: translateY(40px);
  transition: opacity .8s cubic-bezier(.16, 1, .3, 1), transform .8s cubic-bezier(.16, 1, .3, 1);
}
.reveal.in {
  opacity: 1;
  transform: translateY(0);
}

/* Nav */
.landing-root nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  padding: 18px 40px;
  background: rgba(16, 20, 26, .85);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(139, 145, 157, .08);
  transition: background .3s;
}
.landing-root nav.scrolled { background: rgba(16, 20, 26, .95); }
.landing-root .nav-links button {
  background: none;
  border: 0;
  color: var(--on-surface-variant);
  cursor: pointer;
  font: inherit;
  font-weight: 500;
  font-size: 14px;
  transition: color .2s;
}
.landing-root .nav-links button:hover { color: var(--on-surface); }
.landing-root .login-link {
  background: none;
  border: 0;
  color: var(--on-surface-variant);
  cursor: pointer;
  font: inherit;
  font-size: 14px;
  padding: 8px 12px;
  transition: color .2s;
}
.landing-root .login-link:hover { color: var(--on-surface); }

/* Hamburger button — hidden on desktop, shown on mobile */
.landing-root .hamburger {
  display: none;
  background: none;
  border: 0;
  padding: 8px;
  cursor: pointer;
  flex-direction: column;
  gap: 5px;
  width: 40px;
  height: 40px;
  align-items: center;
  justify-content: center;
}
.landing-root .hamburger-bar {
  display: block;
  width: 22px;
  height: 2px;
  background: var(--on-surface);
  border-radius: 2px;
  transition: transform .3s cubic-bezier(.16, 1, .3, 1), opacity .2s;
  transform-origin: center;
}
.landing-root .hamburger-bar.is-open:nth-child(1) { transform: translateY(7px) rotate(45deg); }
.landing-root .hamburger-bar.middle.is-open { opacity: 0; }
.landing-root .hamburger-bar.is-open:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }

/* Mobile menu sheet */
.landing-root .mobile-menu {
  position: fixed;
  inset: 64px 0 0 0;
  z-index: 90;
  background: rgba(10, 14, 20, .92);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  display: flex;
  flex-direction: column;
}
.landing-root .mobile-menu-panel {
  display: flex;
  flex-direction: column;
  padding: 24px 20px 32px;
  gap: 4px;
  border-bottom: 1px solid rgba(139, 145, 157, .08);
  background: var(--surface-container-lowest);
}
.landing-root .mobile-menu-link {
  background: none;
  border: 0;
  color: var(--on-surface);
  font: inherit;
  font-size: 18px;
  font-weight: 600;
  text-align: left;
  padding: 14px 8px;
  cursor: pointer;
  border-radius: 8px;
  transition: background .15s;
}
.landing-root .mobile-menu-link:hover,
.landing-root .mobile-menu-link:focus-visible {
  background: rgba(162, 201, 255, .08);
  outline: none;
}
.landing-root .mobile-menu-secondary {
  color: var(--on-surface-variant);
  font-size: 16px;
}
.landing-root .mobile-menu-divider {
  height: 1px;
  background: rgba(139, 145, 157, .1);
  margin: 8px 0;
}
.landing-root .mobile-menu-cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px 20px;
  border-radius: 12px;
  border: 0;
  color: var(--on-primary);
  font: inherit;
  font-weight: 700;
  font-size: 15px;
  margin-top: 8px;
  cursor: pointer;
  transition: transform .2s, box-shadow .3s;
}
.landing-root .mobile-menu-cta:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 36px -16px rgba(162, 201, 255, .5);
}

/* Slide-down enter/leave */
.mobile-menu-enter-active .mobile-menu-panel,
.mobile-menu-leave-active .mobile-menu-panel {
  transition: transform .25s cubic-bezier(.16, 1, .3, 1), opacity .2s;
}
.mobile-menu-enter-from .mobile-menu-panel,
.mobile-menu-leave-to .mobile-menu-panel {
  transform: translateY(-12px);
  opacity: 0;
}
.mobile-menu-enter-active,
.mobile-menu-leave-active { transition: opacity .2s; }
.mobile-menu-enter-from,
.mobile-menu-leave-to { opacity: 0; }

/* Sections */
.landing-root section { padding: 120px 40px; position: relative; }
.landing-root .container { max-width: 1200px; margin: 0 auto; }

/* Hero */
.landing-root .hero {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}
.landing-root .hero-grid {
  position: absolute;
  inset: 0;
  opacity: .4;
  pointer-events: none;
}

/* Feature cards */
.landing-root .feature-card {
  background: var(--surface-container-low);
  border: 1px solid rgba(139, 145, 157, .08);
  border-radius: 20px;
  padding: 32px;
  transition: transform .3s, box-shadow .3s, border-color .3s;
}
.landing-root .feature-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 20px 60px -20px rgba(162, 201, 255, .3);
  border-color: rgba(162, 201, 255, .2);
}

/* Diff mock */
.landing-root .diff-mock {
  background: var(--surface-container-lowest);
  border: 1px solid rgba(139, 145, 157, .08);
  border-radius: 12px;
  overflow: hidden;
  font-size: 13px;
}
.landing-root .diff-line {
  display: flex;
  gap: 12px;
  padding: 6px 14px;
  font-family: 'Fira Code', monospace;
  line-height: 1.6;
}
.landing-root .diff-add {
  background: linear-gradient(90deg, rgba(126, 225, 167, .10), rgba(126, 225, 167, 0));
  border-left: 2px solid #7ee1a7;
}
.landing-root .diff-rm {
  background: linear-gradient(90deg, rgba(255, 180, 171, .10), rgba(255, 180, 171, 0));
  border-left: 2px solid var(--error);
}
.landing-root .ln {
  color: rgba(139, 145, 157, .5);
  user-select: none;
  min-width: 32px;
  text-align: right;
}

/* Rubric dial */
.landing-root .dial { position: relative; width: 80px; height: 80px; }

/* CTA buttons */
.landing-root .cta-btn {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 14px 28px;
  border-radius: 12px;
  font-weight: 700;
  font-size: 15px;
  border: 0;
  cursor: pointer;
  transition: transform .2s, box-shadow .3s;
  font-family: inherit;
}
.landing-root .cta-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 40px -16px rgba(162, 201, 255, .5);
}
.landing-root .cta-btn:active { transform: translateY(0); }

/* Language pill */
.landing-root .lang-card {
  background: var(--surface-container);
  border: 1px solid rgba(139, 145, 157, .08);
  border-radius: 10px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  transition: border-color .25s, transform .25s;
}
.landing-root .lang-card:hover {
  border-color: rgba(162, 201, 255, .3);
  transform: translateY(-2px);
}
.landing-root .lang-card span {
  font-weight: 600;
  font-size: 14px;
}

/* Footer */
.landing-root footer {
  background: var(--surface-container-lowest);
  border-top: 1px solid rgba(139, 145, 157, .08);
  padding: 60px 40px 40px;
}
.landing-root .footer-link {
  background: none;
  border: 0;
  color: var(--on-surface-variant);
  cursor: pointer;
  font: inherit;
  font-size: 14px;
  text-align: left;
  text-decoration: none;
  padding: 0;
  transition: color .2s;
}
.landing-root .footer-link:hover { color: var(--on-surface); }

/* ─────────────────────────────────────────────────────────────────
   Mobile / tablet
   The Claude Design hand-off uses inline styles for layout. Inline
   styles always beat CSS unless we either (a) use !important or (b)
   target attribute selectors. The rules below use both so that the
   landing page collapses cleanly on phones without re-writing every
   inline style.
   ───────────────────────────────────────────────────────────────── */

/* Tablet: relax the two-column grids before we hit phone widths */
@media (max-width: 1024px) {
  .landing-root .how-row,
  .landing-root .feat-row { gap: 40px !important; }
}

/* Phone */
@media (max-width: 768px) {
  /* Sections — kill the 40px horizontal inline padding and trim vertical */
  .landing-root section { padding: 64px 20px !important; }
  .landing-root section[style*="padding:80px 40px"],
  .landing-root section[style*="padding: 80px 40px"] { padding: 64px 20px !important; }
  .landing-root section[style*="padding:120px 40px"],
  .landing-root section[style*="padding: 120px 40px"] { padding: 72px 20px !important; }

  /* Inner card padding (Onze aanpak block) */
  .landing-root [style*="padding:60px 40px"],
  .landing-root [style*="padding: 60px 40px"] { padding: 36px 20px !important; }

  /* Big margin-bottom blocks become reasonable on phones */
  .landing-root [style*="margin-bottom:100px"],
  .landing-root [style*="margin-bottom: 100px"] { margin-bottom: 56px !important; }
  .landing-root [style*="margin-bottom:120px"],
  .landing-root [style*="margin-bottom: 120px"] { margin-bottom: 56px !important; }
  .landing-root [style*="margin-bottom:80px"],
  .landing-root [style*="margin-bottom: 80px"] { margin-bottom: 48px !important; }
  .landing-root [style*="margin-bottom:60px"],
  .landing-root [style*="margin-bottom: 60px"] { margin-bottom: 40px !important; }

  /* Nav: hide desktop link row + actions, show the hamburger */
  .landing-root nav { padding: 12px 16px !important; }
  .landing-root .nav-links { display: none; }
  .landing-root .nav-desktop-actions { display: none !important; }
  .landing-root .hamburger { display: flex; }

  /* Hero */
  .landing-root .hero { min-height: auto !important; padding: 96px 20px 56px !important; }
  .landing-root .hero h1 { letter-spacing: -1px !important; }
  .landing-root .hero p { font-size: 16px !important; }
  /* Flatten the perspective tilt so the mock sits flat on phones */
  .landing-root #hero-mock { transform: none !important; }

  /* Hero mock — when the diff/rubric grid stacks, swap left-border for top-border */
  .landing-root .hero-mock-grid { grid-template-columns: 1fr !important; }
  .landing-root .hero-mock-grid > div:nth-child(2) {
    border-left: 0 !important;
    border-top: 1px solid rgba(139, 145, 157, .08) !important;
  }

  /* "Hoe het werkt" + Features rows: stack and reset order overrides */
  .landing-root .how-row,
  .landing-root .feat-row { grid-template-columns: 1fr !important; gap: 32px !important; }
  .landing-root .how-row > div[style*="order:2"],
  .landing-root .feat-row > div[style*="order:2"] { order: initial !important; }

  /* Floating decorative badges overflow viewport with negative offsets — hide */
  .landing-root .float { display: none !important; }

  /* Inline section heading sizes inside features (h3 36px, h3 32px) */
  .landing-root .how-row h3[style*="font-size:32px"],
  .landing-root .feat-row h3[style*="font-size:36px"] { font-size: 26px !important; }

  /* Large numerals inside mockups — keep readable but not gigantic */
  .landing-root [style*="font-size:44px"] { font-size: 36px !important; }
  .landing-root [style*="font-size:40px"] { font-size: 32px !important; }
  .landing-root [style*="font-size:36px"] { font-size: 28px !important; }

  /* Feature cards: tighter padding */
  .landing-root .feature-card { padding: 24px !important; }

  /* Footer: tighter padding, single-column friendly */
  .landing-root footer { padding: 40px 20px 24px !important; }
  .landing-root footer [style*="grid-template-columns:repeat(auto-fit,minmax(200px,1fr))"] { gap: 24px !important; }

  /* The terminal in step-01 — keep min-height but allow shrink on tiny screens */
  #terminal-step1 { min-height: 320px !important; font-size: 11px !important; }

  /* Hero trust badges — already wrap, just tighten gap */
  .landing-root .hero [style*="gap:28px"] { gap: 16px !important; }
}

/* Tiny phones (<= 380px) */
@media (max-width: 380px) {
  .landing-root section { padding: 56px 16px !important; }
  .landing-root nav { padding: 10px 12px !important; }
  .landing-root .feature-card { padding: 20px !important; }
  /* Hero h1 line-breaks get awkward sub-360px — let it wrap naturally */
  .landing-root .hero h1 br { display: none; }
}
</style>
