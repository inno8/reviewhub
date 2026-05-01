<script setup lang="ts">
/**
 * RubricPublicView — public, no-auth /rubric page.
 *
 * Sells LEERA's grading rubric to school admins, docenten, and curious
 * students/parents. The MBO-4 readiness signal: schools that visit the
 * booth on May 7 will scan this before signing.
 *
 * Design source: docs/prompts/rubric-public-page.md + Claude Design
 * handoff at .claude/design-rubric/leera-ui/project/Rubric.html.
 *
 * The design ships with 8 English skill ids (security, code_quality,
 * architecture, testing, performance, documentation, validation,
 * best_practices) and per-skill weights (1.5×, 1.2×, etc.). The current
 * backend rubric was migrated to 6 Crebo Dutch ids (code_ontwerp,
 * code_kwaliteit, veiligheid, testen, verbetering, samenwerking) per
 * Option A. We're rendering the design as-designed for the May 7
 * launch — the public page can drift slightly from the per-cohort
 * rubric without confusing teachers, since the cohort rubric is what
 * actually grades the code. v1.1 todo: align this page to the 6 Crebo
 * criteria so the public-facing copy and the backend speak the same
 * vocabulary.
 *
 * Nav + footer copied verbatim from LandingView so navigation between
 * /landing and /rubric feels seamless.
 */
import { onMounted, onBeforeUnmount, ref } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();

// Mobile nav state — same pattern as LandingView.
const mobileNavOpen = ref(false);
const scrolled = ref(false);

function toggleMobileNav() {
  mobileNavOpen.value = !mobileNavOpen.value;
}

function closeMobileNav() {
  mobileNavOpen.value = false;
}

function goLogin() {
  router.push({ name: 'login' });
}

// Smooth scroll for anchor links inside the page (#skills, #niveaus, #contact).
function scrollTo(id: string) {
  closeMobileNav();
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Skill cards expand/collapse — one open at a time keeps the page from
// growing into a wall of text on mobile.
const expandedSkill = ref<string | null>(null);

function toggleSkill(skill: string) {
  expandedSkill.value = expandedSkill.value === skill ? null : skill;
}

// Scroll-reveal: add `.in` class when an element scrolls into view.
function revealOnScroll() {
  const reveals = document.querySelectorAll('.reveal');
  reveals.forEach(el => {
    const rect = el.getBoundingClientRect();
    if (rect.top < window.innerHeight * 0.85) el.classList.add('in');
  });
  scrolled.value = window.scrollY > 50;
}

onMounted(() => {
  window.addEventListener('scroll', revealOnScroll, { passive: true });
  // Fire once on mount so above-the-fold cards aren't blank.
  revealOnScroll();
});
onBeforeUnmount(() => {
  window.removeEventListener('scroll', revealOnScroll);
});

// Static rubric data. Lives here rather than in a Django endpoint
// because the page is public + the copy needs designer review (Dutch
// tone, typography). Once the rubric content stabilizes, v1.1 can
// expose a /api/rubric/public/ endpoint and this view renders from
// fetched data so per-school overrides are possible.
interface SkillLevel {
  niveau: 1 | 2 | 3 | 4;
  label: string;
  description: string;
}
interface Skill {
  id: string;
  name: string;
  weight: string;
  description: string;
  icon: string;
  color: string;
  colorRgb: string;
  levels: SkillLevel[];
  example?: { lines: { kind: 'comment' | 'bad' | 'good'; text: string }[] };
}

const skills: Skill[] = [
  {
    id: 'security',
    name: 'Beveiliging',
    weight: '1.5×',
    description: 'Of de code geen ruimte laat voor SQL injection, XSS, IDOR, hardcoded secrets, of authenticatie-fouten.',
    icon: 'shield',
    color: '#ff6b6b',
    colorRgb: '255,107,107',
    levels: [
      { niveau: 1, label: 'Onvoldoende', description: 'Kritieke kwetsbaarheden: SQL injection, hardcoded wachtwoorden, gebruikers kunnen elkaars data wijzigen. Niet inleverbaar.' },
      { niveau: 2, label: 'Zwak', description: 'Sommige beveiligingszorgen. Ontbrekende input-validatie of auth-checks. Werkt maar niet veilig genoeg om te live te gaan.' },
      { niveau: 3, label: 'Voldoende', description: 'Basis-beveiliging toegepast. Kleine zorgen blijven. Voldoende voor schoolwerk.' },
      { niveau: 4, label: 'Goed — Stage-rijp', description: 'Defense in depth. Threat modeling zichtbaar. Geen evidente kwetsbaarheden. Stage-rijp.' },
    ],
    example: {
      lines: [
        { kind: 'comment', text: '// Niveau 1 — SQL injection mogelijk' },
        { kind: 'bad', text: "DB::select(\"SELECT * FROM books WHERE title = '$search'\")" },
        { kind: 'comment', text: '' },
        { kind: 'comment', text: '// Niveau 3 — Query builder beschermt tegen injection' },
        { kind: 'good', text: "Book::where('title', $search)->get()" },
        { kind: 'comment', text: '' },
        { kind: 'comment', text: '// Crebo: B1-K1-W3 "Werkt volgens veiligheidsrichtlijnen"' },
      ],
    },
  },
  {
    id: 'code-quality',
    name: 'Code Kwaliteit',
    weight: '1.0×',
    description: 'Leesbaarheid, naamgeving, consistentie, herhaling.',
    icon: 'auto_awesome',
    color: '#4ecdc4',
    colorRgb: '78,205,196',
    levels: [
      { niveau: 1, label: 'Onvoldoende', description: 'Moeilijk te lezen. Magic numbers. Copy-paste duplicatie.' },
      { niveau: 2, label: 'Zwak', description: 'Inconsistente stijl. Onduidelijke namen.' },
      { niveau: 3, label: 'Voldoende', description: 'Leesbaar. Consistente stijl. Redelijke namen.' },
      { niveau: 4, label: 'Goed — Stage-rijp', description: 'Heldere intent overal. Goed gefactored. Makkelijk te onderhouden.' },
    ],
    example: {
      lines: [
        { kind: 'comment', text: '# Niveau 1 — magic number, onduidelijke naam' },
        { kind: 'bad', text: 'def calc(x): return x * 0.21' },
        { kind: 'comment', text: '' },
        { kind: 'comment', text: '# Niveau 3 — heldere intentie' },
        { kind: 'good', text: 'BTW_TARIEF = 0.21' },
        { kind: 'good', text: 'def bereken_btw(bedrag_excl):' },
        { kind: 'good', text: '    return bedrag_excl * BTW_TARIEF' },
      ],
    },
  },
  {
    id: 'architecture',
    name: 'Architectuur',
    weight: '1.0×',
    description: 'Scheiding van verantwoordelijkheden, lagen, abstracties.',
    icon: 'account_tree',
    color: '#a2c9ff',
    colorRgb: '162,201,255',
    levels: [
      { niveau: 1, label: 'Onvoldoende', description: 'Strak gekoppeld. Geen scheiding. Controllers doen database én rendering.' },
      { niveau: 2, label: 'Zwak', description: 'Wat structuur, maar laag-overschrijdingen.' },
      { niveau: 3, label: 'Voldoende', description: 'Heldere lagen. Dunne controllers. Sensibele grenzen.' },
      { niveau: 4, label: 'Goed — Stage-rijp', description: 'Idiomatisch voor het framework. Uitbreidbaar. SOLID toegepast.' },
    ],
  },
  {
    id: 'testing',
    name: 'Testen',
    weight: '1.2×',
    description: 'Of er tests zijn, of ze de juiste dingen testen, of edge cases gedekt zijn.',
    icon: 'science',
    color: '#95e1d3',
    colorRgb: '149,225,211',
    levels: [
      { niveau: 1, label: 'Onvoldoende', description: 'Geen tests.' },
      { niveau: 2, label: 'Zwak', description: 'Een paar happy-path tests.' },
      { niveau: 3, label: 'Voldoende', description: 'Edge cases gedekt voor hoofdfeatures. Tests zijn onafhankelijk.' },
      { niveau: 4, label: 'Goed — Stage-rijp', description: 'Brede dekking inclusief faalmodes. Integration én unit tests.' },
    ],
  },
  {
    id: 'performance',
    name: 'Performance',
    weight: '0.8×',
    description: 'Query-efficiency, caching waar nodig, geen voor-de-hand-liggende bottlenecks.',
    icon: 'speed',
    color: '#ffba42',
    colorRgb: '255,186,66',
    levels: [
      { niveau: 1, label: 'Onvoldoende', description: 'N+1 queries. Geen eager loading. Evidente bottlenecks.' },
      { niveau: 2, label: 'Zwak', description: 'Wat inefficiëntie. Geen caching waar het ertoe doet.' },
      { niveau: 3, label: 'Voldoende', description: 'Eager loading waar nodig. Queries zijn redelijk.' },
      { niveau: 4, label: 'Goed — Stage-rijp', description: 'Geprofileerd, geoptimaliseerd, geïndexeerd.' },
    ],
    example: {
      lines: [
        { kind: 'comment', text: '# Niveau 1 — N+1 probleem' },
        { kind: 'bad', text: 'for order in Order.all():' },
        { kind: 'bad', text: '    print(order.customer.name)  # Query per order!' },
        { kind: 'comment', text: '' },
        { kind: 'comment', text: '# Niveau 3 — Eager loading' },
        { kind: 'good', text: "for order in Order.select_related('customer').all():" },
        { kind: 'good', text: '    print(order.customer.name)  # Één query' },
      ],
    },
  },
  {
    id: 'documentation',
    name: 'Documentatie',
    weight: '0.6×',
    description: 'README, inline documentatie van niet-triviale code.',
    icon: 'article',
    color: '#b19cd9',
    colorRgb: '177,156,217',
    levels: [
      { niveau: 1, label: 'Onvoldoende', description: 'Geen README. Geen comments waar ze nodig zijn.' },
      { niveau: 2, label: 'Zwak', description: 'Minimale README. Weinig inline uitleg.' },
      { niveau: 3, label: 'Voldoende', description: 'README met setup-instructies. Comments bij complexe delen.' },
      { niveau: 4, label: 'Goed — Stage-rijp', description: "Volledige README + docstrings op publieke API's. Architectuur-beslissingen gedocumenteerd." },
    ],
  },
  {
    id: 'validation',
    name: 'Validatie',
    weight: '1.0×',
    description: 'Of input gevalideerd wordt voordat het de business-logic raakt.',
    icon: 'check_circle',
    color: '#ff8b94',
    colorRgb: '255,139,148',
    levels: [
      { niveau: 1, label: 'Onvoldoende', description: 'Geen validatie. User-input komt rechtstreeks in de database.' },
      { niveau: 2, label: 'Zwak', description: 'Wat validatie, maar inconsistent toegepast.' },
      { niveau: 3, label: 'Voldoende', description: 'Alle user-input wordt gevalideerd. Heldere foutmeldingen.' },
      { niveau: 4, label: 'Goed — Stage-rijp', description: 'Centraal validatie-systeem. Business rules in dedicated validators.' },
    ],
  },
  {
    id: 'best-practices',
    name: 'Best Practices',
    weight: '0.8×',
    description: 'Of de code de framework-conventies volgt en niet het wiel opnieuw uitvindt.',
    icon: 'workspace_premium',
    color: '#7ee1a7',
    colorRgb: '126,225,167',
    levels: [
      { niveau: 1, label: 'Onvoldoende', description: 'Negeert framework-conventies. Vindt het wiel opnieuw uit.' },
      { niveau: 2, label: 'Zwak', description: 'Gebruikt wat conventies, maar inconsistent.' },
      { niveau: 3, label: 'Voldoende', description: 'Volgt de framework-standaarden. Gebruikt ingebouwde features.' },
      { niveau: 4, label: 'Goed — Stage-rijp', description: 'Idiomatisch. Gebruikt community best-practices. Volgt de happy path.' },
    ],
  },
];

// Niveau-mapping section: visual columns showing what each niveau looks
// like across multiple skills. Hand-curated short labels per skill.
const niveauColumns = [
  {
    niveau: 1, color: '#ff6b6b', label: 'Onvoldoende',
    chips: [
      { color: '#ff6b6b', text: 'Kritieke bugs' },
      { color: '#4ecdc4', text: 'Onleesbaar' },
      { color: '#a2c9ff', text: 'Geen structuur' },
      { color: '#95e1d3', text: 'Geen tests' },
    ],
  },
  {
    niveau: 2, color: '#ffba42', label: 'Zwak',
    chips: [
      { color: '#ff6b6b', text: 'Wat zorgen' },
      { color: '#4ecdc4', text: 'Inconsistent' },
      { color: '#a2c9ff', text: 'Wat lagen' },
      { color: '#95e1d3', text: 'Happy path' },
    ],
  },
  {
    niveau: 3, color: '#a2c9ff', label: 'Voldoende',
    chips: [
      { color: '#ff6b6b', text: 'Basis veilig' },
      { color: '#4ecdc4', text: 'Leesbaar' },
      { color: '#a2c9ff', text: 'Heldere lagen' },
      { color: '#95e1d3', text: 'Edge cases' },
    ],
  },
  {
    niveau: 4, color: '#7ee1a7', label: 'Goed — Stage-rijp',
    chips: [
      { color: '#ff6b6b', text: 'Defense in depth' },
      { color: '#4ecdc4', text: 'Onderhoudbaar' },
      { color: '#a2c9ff', text: 'SOLID' },
      { color: '#95e1d3', text: 'Brede dekking' },
    ],
  },
];

const dontGrade = [
  {
    icon: 'palette',
    title: 'Geen aesthetics',
    description: 'LEERA graadt niet op "mooie code" of cleverness om de cleverness. Als het werkt en voldoet aan de rubric, is het goed.',
  },
  {
    icon: 'code_blocks',
    title: 'Geen framework-dogma',
    description: 'Als je Laravel gebruikt, graadt LEERA op Laravel-conventies. Als je vanilla PHP schrijft, graadt het daarop. Geen rigide "je moet X gebruiken".',
  },
  {
    icon: 'block',
    title: 'Niets buiten de rubric',
    description: 'Als een skill niet in jouw rubric zit, graadt LEERA er niet op. Jij bepaalt wat belangrijk is voor jouw klas.',
  },
];
</script>

<template>
  <div class="rubric-root">
    <!-- ════════════════════════ NAV ════════════════════════ -->
    <!-- Mirrors LandingView.nav structure so /landing → /rubric feels
         seamless. Same logo, same gradient login button on the right;
         middle links scoped to this page's anchors. -->
    <nav id="nav" :class="{ scrolled, 'menu-open': mobileNavOpen }">
      <div class="container" style="display:flex;align-items:center;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:40px">
          <router-link to="/landing" style="display:flex;align-items:center;gap:10px;text-decoration:none">
            <img src="/logo/leera-wordmark-primary.svg" alt="LEERA" style="height:28px" />
          </router-link>
          <div style="display:flex;gap:28px" class="nav-links">
            <button @click="scrollTo('skills')">Skills</button>
            <button @click="scrollTo('niveaus')">Niveaus</button>
            <router-link to="/landing" custom v-slot="{ navigate }">
              <button @click="navigate">Home</button>
            </router-link>
          </div>
        </div>
        <div class="nav-desktop-actions" style="display:flex;gap:12px;align-items:center">
          <button @click="goLogin" class="login-link">Inloggen</button>
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

    <Transition name="mobile-menu">
      <div
        v-if="mobileNavOpen"
        id="mobile-menu"
        class="mobile-menu"
        @click.self="closeMobileNav"
      >
        <div class="mobile-menu-inner">
          <button @click="scrollTo('skills')">Skills</button>
          <button @click="scrollTo('niveaus')">Niveaus</button>
          <router-link to="/landing" @click="closeMobileNav">Home</router-link>
          <button @click="goLogin">Inloggen</button>
        </div>
      </div>
    </Transition>

    <!-- ════════════════════════ HERO ════════════════════════ -->
    <section class="hero">
      <div class="hero-grid dots drift" aria-hidden="true"></div>
      <div class="container" style="position:relative;z-index:1;text-align:center">
        <h1 class="hero-title">Hoe LEERA jouw code beoordeelt</h1>
        <p class="hero-sub">Acht skills. Vier niveaus. Eén docent met de eindstem.</p>
        <div style="display:flex;gap:16px;justify-content:center;flex-wrap:wrap">
          <button @click="scrollTo('skills')" class="primary-gradient cta-btn cta-btn--primary">
            <span class="material-symbols-outlined" style="font-size:18px">arrow_downward</span>
            Bekijk de skills
          </button>
          <button @click="scrollTo('contact')" class="cta-btn cta-btn--secondary">
            Plan een gesprek
          </button>
        </div>
      </div>
    </section>

    <!-- ════════════════════════ PHILOSOPHY ════════════════════════ -->
    <section class="section--alt" style="padding:80px 40px">
      <div class="container">
        <div style="text-align:center;margin-bottom:60px">
          <div class="kicker">Filosofie</div>
          <h2 class="section-title">Hoe het werkt</h2>
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px">
          <div class="philosophy-card reveal">
            <div class="philosophy-icon" style="background:rgba(162,201,255,.12)">
              <span class="material-symbols-outlined" style="font-size:24px;color:var(--primary)">fact_check</span>
            </div>
            <h3 class="philosophy-title">Rubric-aligned</h3>
            <p class="philosophy-tag">Geen vibe-cijfers</p>
            <p class="philosophy-body">Docent stelt de gewichten in. LEERA graadt tegen die rubric, niet tegen een generieke AI-mening.</p>
          </div>

          <div class="philosophy-card reveal">
            <div class="philosophy-icon" style="background:rgba(126,225,167,.12)">
              <span class="material-symbols-outlined" style="font-size:24px;color:var(--success, #7ee1a7)">trending_up</span>
            </div>
            <h3 class="philosophy-title">Behavioral proof</h3>
            <p class="philosophy-tag">Niet één PR, maar het patroon</p>
            <p class="philosophy-body">Skills bewegen op observatie, niet op één toets. LEERA kijkt of een student een geflaagde issue fixt én niet opnieuw introduceert.</p>
          </div>

          <div class="philosophy-card reveal">
            <div class="philosophy-icon" style="background:rgba(255,186,66,.12)">
              <span class="material-symbols-outlined" style="font-size:24px;color:var(--tertiary, #ffba42)">school</span>
            </div>
            <h3 class="philosophy-title">Docent met eindstem</h3>
            <p class="philosophy-tag">AI doet het concept. De docent stuurt</p>
            <p class="philosophy-body">Geen LEERA-comment gaat naar GitHub zonder dat jij op Send klikt. Jij reviewt, past aan, verwijdert waar nodig.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ════════════════════════ SKILLS GRID ════════════════════════ -->
    <section id="skills">
      <div class="container">
        <div style="text-align:center;margin-bottom:60px">
          <div class="kicker">De acht skills</div>
          <h2 class="section-title">Wat LEERA beoordeelt</h2>
          <p class="section-sub">Elke skill heeft vier niveaus — van onvoldoende tot stage-rijp. Klik op een skill voor de volledige definities en een code-voorbeeld.</p>
        </div>

        <div class="skills-grid">
          <div
            v-for="skill in skills"
            :key="skill.id"
            class="skill-card reveal"
            :class="{ expanded: expandedSkill === skill.id }"
            :data-skill="skill.id"
            @click="toggleSkill(skill.id)"
          >
            <div class="skill-accent" :style="{ background: skill.color }"></div>
            <div class="skill-header">
              <div style="flex:1">
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-wrap:wrap">
                  <span class="material-symbols-outlined" :style="{ fontSize: '20px', color: skill.color }">{{ skill.icon }}</span>
                  <h3 class="skill-name">{{ skill.name }}</h3>
                  <span
                    class="skill-weight-pill"
                    :style="{
                      background: `rgba(${skill.colorRgb},.15)`,
                      color: skill.color,
                    }"
                  >{{ skill.weight }} weight</span>
                </div>
                <p class="skill-desc">{{ skill.description }}</p>
                <div class="niveau-dots" :style="{ color: skill.color }">
                  <div
                    v-for="n in 4"
                    :key="n"
                    class="niveau-dot active"
                  ></div>
                </div>
              </div>
              <span
                class="material-symbols-outlined skill-chevron"
                :style="{ transform: expandedSkill === skill.id ? 'rotate(180deg)' : 'rotate(0deg)' }"
              >expand_more</span>
            </div>
            <div class="skill-body" v-show="expandedSkill === skill.id">
              <div class="level-table">
                <div
                  v-for="level in skill.levels"
                  :key="level.niveau"
                  class="level-row"
                >
                  <span :class="['level-badge', `level-${level.niveau}`]">Niveau {{ level.niveau }}</span>
                  <div>
                    <div class="level-row-title">{{ level.label }}</div>
                    <p class="level-row-desc">{{ level.description }}</p>
                  </div>
                </div>
              </div>
              <pre v-if="skill.example" class="code-example"><span
                v-for="(line, i) in skill.example.lines"
                :key="i"
                :class="`code-${line.kind}`"
              >{{ line.text }}{{ '\n' }}</span></pre>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ════════════════════════ NIVEAU MAPPING ════════════════════════ -->
    <section id="niveaus" class="section--alt">
      <div class="container">
        <div style="text-align:center;margin-bottom:60px">
          <div class="kicker">Niveau-mapping</div>
          <h2 class="section-title">Van onvoldoende tot stage-rijp</h2>
          <p class="section-sub">Elk niveau is gekalibreerd aan wat een docent verwacht aan het eind van jaar 4. Niveau 1 = niet inleverbaar, Niveau 4 = klaar voor het werkveld.</p>
        </div>

        <div class="niveau-grid">
          <div
            v-for="col in niveauColumns"
            :key="col.niveau"
            class="niveau-column"
            :style="{ borderColor: col.color }"
          >
            <div class="niveau-title" :style="{ color: col.color }">Niveau {{ col.niveau }}</div>
            <div class="niveau-desc">{{ col.label }}</div>
            <div style="display:flex;flex-direction:column;gap:6px">
              <div v-for="(chip, i) in col.chips" :key="i" class="skill-chip">
                <span class="skill-chip-dot" :style="{ background: chip.color }"></span>
                {{ chip.text }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ════════════════════════ WAT WE NIET GRADEREN ════════════════════════ -->
    <section>
      <div class="container">
        <div style="max-width:800px;margin:0 auto">
          <div style="text-align:center;margin-bottom:40px">
            <div class="kicker">Wat we NIET graderen</div>
            <h2 class="section-title">Geen FAANG-meningen</h2>
            <p class="section-sub">LEERA graadt volgens jouw rubric, niet volgens wat Silicon Valley "clean code" noemt.</p>
          </div>

          <div style="display:flex;flex-direction:column;gap:16px">
            <div v-for="item in dontGrade" :key="item.title" class="dontgrade-card">
              <span class="material-symbols-outlined" style="font-size:20px;color:var(--outline)">{{ item.icon }}</span>
              <div>
                <div class="dontgrade-title">{{ item.title }}</div>
                <p class="dontgrade-body">{{ item.description }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ════════════════════════ CTA ════════════════════════ -->
    <section id="contact" class="section--alt">
      <div class="container" style="text-align:center">
        <h2 class="section-title">Klaar om je vak in te richten?</h2>
        <p class="section-sub" style="max-width:560px;margin:0 auto 40px">Probeer LEERA gratis tot 1 september of plan een gesprek om te zien hoe het in jouw klas past.</p>
        <div style="display:flex;gap:16px;justify-content:center;flex-wrap:wrap">
          <router-link to="/org-signup" class="primary-gradient cta-btn cta-btn--primary">
            <span class="material-symbols-outlined" style="font-size:18px">play_arrow</span>
            Probeer gratis tot 1 sept
          </router-link>
          <a href="mailto:inno8techs@gmail.com" class="cta-btn cta-btn--secondary">
            <span class="material-symbols-outlined" style="font-size:18px">chat</span>
            Plan een gesprek
          </a>
        </div>
      </div>
    </section>

    <!-- ════════════════════════ FOOTER ════════════════════════ -->
    <!-- Same structure as LandingView.footer. Adds an active "Rubric"
         link on the Product column so visitors landing here from a
         deep link can navigate the rest of the marketing site. -->
    <footer>
      <div class="container">
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:40px;margin-bottom:40px">
          <div>
            <img src="/logo/leera-wordmark-mono.svg" alt="LEERA" style="height:28px;margin-bottom:16px;opacity:.85" />
            <p style="color:var(--on-surface-variant);font-size:14px;line-height:1.6">Nakijken Copilot voor het MBO. Elke commit een les, elke PR een beoordeling die uit bewijs komt.</p>
          </div>

          <div>
            <div class="footer-heading">Product</div>
            <div style="display:flex;flex-direction:column;gap:8px">
              <router-link to="/landing" class="footer-link">Home</router-link>
              <router-link to="/rubric" class="footer-link">Rubric</router-link>
              <button @click="goLogin" class="footer-link">Inloggen</button>
            </div>
          </div>

          <div>
            <div class="footer-heading">Bedrijf</div>
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
.rubric-root {
  /* Local design tokens — same palette LandingView uses. Public pages
     have their own root so they don't inherit AppShell's layout chrome. */
  --background: #10141a;
  --surface-container-lowest: #0a0e14;
  --surface-container-low: #181c22;
  --surface-container: #1c2026;
  --surface-container-high: #262a31;
  --primary: #a2c9ff;
  --primary-container: #58a6ff;
  --on-primary: #00315c;
  --tertiary: #ffba42;
  --success: #7ee1a7;
  --on-surface: #dfe2eb;
  --on-surface-variant: #c0c7d4;
  --outline: #8b919d;

  background: var(--background);
  color: var(--on-surface);
  font-family: 'Inter', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  font-feature-settings: "ss01", "cv11";
  min-height: 100vh;
  overflow-x: hidden;
}

.rubric-root *,
.rubric-root *::before,
.rubric-root *::after {
  box-sizing: border-box;
}

/* Drift dots backdrop on the hero — same primitive LandingView uses */
.dots {
  background-image: radial-gradient(rgba(162, 201, 255, .06) 1px, transparent 1px);
  background-size: 22px 22px;
}
.primary-gradient {
  background: linear-gradient(135deg, #a2c9ff 0%, #58a6ff 100%);
}
@keyframes drift {
  0% { background-position: 0 0; }
  100% { background-position: 22px 22px; }
}
.drift {
  animation: drift 14s linear infinite;
}

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

/* Nav (mirrors LandingView) */
nav {
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
nav.scrolled {
  background: rgba(16, 20, 26, .95);
}
nav button,
nav .nav-links button,
nav .nav-links a button {
  background: none;
  border: 0;
  color: var(--on-surface-variant);
  font: inherit;
  font-weight: 500;
  font-size: 14px;
  cursor: pointer;
  padding: 0;
  transition: color .2s;
}
nav .nav-links button:hover,
nav .login-link:hover {
  color: var(--on-surface);
}
.login-link {
  color: var(--on-surface-variant);
  font-size: 14px;
  cursor: pointer;
  background: none;
  border: 0;
  font-family: inherit;
}

/* Hamburger */
.hamburger {
  display: none;
  flex-direction: column;
  gap: 5px;
  width: 28px;
  background: none;
  border: 0;
  padding: 4px;
  cursor: pointer;
}
.hamburger-bar {
  width: 100%;
  height: 2px;
  background: var(--on-surface);
  border-radius: 2px;
  transition: transform .3s, opacity .3s;
}
.hamburger-bar.is-open:nth-child(1) {
  transform: translateY(7px) rotate(45deg);
}
.hamburger-bar.is-open.middle {
  opacity: 0;
}
.hamburger-bar.is-open:nth-child(3) {
  transform: translateY(-7px) rotate(-45deg);
}

.mobile-menu {
  position: fixed;
  inset: 0;
  z-index: 99;
  background: rgba(10, 14, 20, .96);
  backdrop-filter: blur(20px);
  padding: 100px 24px 40px;
}
.mobile-menu-inner {
  display: flex;
  flex-direction: column;
  gap: 24px;
  text-align: center;
}
.mobile-menu-inner button,
.mobile-menu-inner a {
  background: none;
  border: 0;
  color: var(--on-surface);
  font-family: inherit;
  font-size: 22px;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
}
.mobile-menu-enter-from,
.mobile-menu-leave-to {
  opacity: 0;
}
.mobile-menu-enter-active,
.mobile-menu-leave-active {
  transition: opacity .2s;
}

/* Sections */
section {
  padding: 100px 40px;
  position: relative;
}
.container {
  max-width: 1200px;
  margin: 0 auto;
}
.section--alt {
  background: var(--surface-container-lowest);
  border-top: 1px solid rgba(139, 145, 157, .08);
  border-bottom: 1px solid rgba(139, 145, 157, .08);
}

.kicker {
  font-size: 10px;
  letter-spacing: .2em;
  text-transform: uppercase;
  color: var(--outline);
  font-weight: 700;
  margin-bottom: 16px;
}
.section-title {
  font-size: clamp(28px, 4vw, 42px);
  font-weight: 800;
  letter-spacing: -1px;
  margin-bottom: 16px;
}
.section-sub {
  font-size: 16px;
  color: var(--on-surface-variant);
  max-width: 680px;
  margin: 0 auto;
}

/* Hero */
.hero {
  min-height: 60vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  padding-top: 80px;
}
.hero-grid {
  position: absolute;
  inset: 0;
  opacity: .4;
  pointer-events: none;
}
.hero-title {
  font-size: clamp(36px, 6vw, 64px);
  font-weight: 800;
  letter-spacing: -2px;
  line-height: 1.1;
  margin-bottom: 20px;
}
.hero-sub {
  font-size: 18px;
  color: var(--on-surface-variant);
  max-width: 620px;
  margin: 0 auto 40px;
  line-height: 1.6;
}

/* CTA buttons */
.cta-btn {
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
  text-decoration: none;
  font-family: inherit;
}
.cta-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 40px -16px rgba(162, 201, 255, .5);
}
.cta-btn:active {
  transform: translateY(0);
}
.cta-btn--primary {
  color: var(--on-primary);
}
.cta-btn--secondary {
  background: var(--surface-container);
  color: var(--on-surface);
}

/* Philosophy */
.philosophy-card {
  background: var(--surface-container);
  border: 1px solid rgba(139, 145, 157, .08);
  border-radius: 12px;
  padding: 24px;
  text-align: center;
}
.philosophy-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  margin: 0 auto 16px;
}
.philosophy-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 8px;
}
.philosophy-tag {
  font-size: 13px;
  color: var(--outline);
  margin-bottom: 12px;
}
.philosophy-body {
  font-size: 14px;
  color: var(--on-surface-variant);
  line-height: 1.6;
}

/* Skills grid */
.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: 20px;
}
.skill-card {
  position: relative;
  background: var(--surface-container-low);
  border: 1px solid rgba(139, 145, 157, .08);
  border-radius: 16px;
  overflow: hidden;
  transition: transform .3s, box-shadow .3s, border-color .3s;
  cursor: pointer;
}
.skill-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 40px -12px rgba(162, 201, 255, .2);
}
.skill-card.expanded {
  border-color: rgba(162, 201, 255, .3);
}
.skill-accent {
  width: 4px;
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
}
.skill-header {
  padding: 24px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
}
.skill-name {
  font-size: 18px;
  font-weight: 700;
}
.skill-weight-pill {
  display: inline-flex;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
}
.skill-desc {
  font-size: 14px;
  color: var(--on-surface-variant);
  line-height: 1.5;
}
.skill-chevron {
  font-size: 20px;
  color: var(--outline);
  transition: transform .3s;
}
.skill-body {
  padding: 0 24px 24px 24px;
}

.niveau-dots {
  display: flex;
  gap: 6px;
  margin-top: 12px;
}
.niveau-dot {
  width: 8px;
  height: 8px;
  border-radius: 99px;
  background: var(--surface-container-high);
  transition: background .2s;
}
.niveau-dot.active {
  background: currentColor;
}

/* Level table inside expanded card */
.level-table {
  background: var(--surface-container);
  border: 1px solid rgba(139, 145, 157, .08);
  border-radius: 10px;
  overflow: hidden;
  margin-top: 16px;
}
.level-row {
  padding: 16px;
  border-bottom: 1px solid rgba(139, 145, 157, .08);
  display: grid;
  grid-template-columns: 90px 1fr;
  gap: 16px;
  align-items: start;
}
.level-row:last-child {
  border-bottom: 0;
}
.level-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 6px;
  font-weight: 700;
  font-size: 12px;
  white-space: nowrap;
}
.level-1 { background: rgba(255, 107, 107, .12); color: #ff6b6b; }
.level-2 { background: rgba(255, 186, 66, .12); color: #ffba42; }
.level-3 { background: rgba(162, 201, 255, .12); color: #a2c9ff; }
.level-4 { background: rgba(126, 225, 167, .12); color: #7ee1a7; }
.level-row-title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 4px;
}
.level-row-desc {
  font-size: 13px;
  color: var(--on-surface-variant);
  line-height: 1.5;
}

/* Code example */
.code-example {
  background: var(--surface-container-lowest);
  border: 1px solid rgba(139, 145, 157, .08);
  border-radius: 10px;
  padding: 16px;
  margin-top: 16px;
  font-family: 'Fira Code', ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre;
  margin-bottom: 0;
}
.code-comment { color: var(--outline); font-style: italic; }
.code-bad { color: #ff6b6b; }
.code-good { color: #7ee1a7; }

/* Niveau-mapping grid */
.niveau-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-top: 40px;
}
.niveau-column {
  background: var(--surface-container);
  border: 1px solid rgba(139, 145, 157, .08);
  border-radius: 12px;
  padding: 20px;
}
.niveau-title {
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 4px;
}
.niveau-desc {
  font-size: 11px;
  color: var(--outline);
  margin-bottom: 16px;
  text-transform: uppercase;
  letter-spacing: .08em;
}
.skill-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  background: var(--surface-container-high);
}
.skill-chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 99px;
}

/* Wat we niet graderen */
.dontgrade-card {
  background: var(--surface-container);
  border: 1px solid rgba(139, 145, 157, .08);
  border-left: 3px solid var(--outline);
  border-radius: 10px;
  padding: 20px;
  display: flex;
  gap: 16px;
}
.dontgrade-title {
  font-weight: 700;
  font-size: 15px;
  margin-bottom: 6px;
}
.dontgrade-body {
  font-size: 14px;
  color: var(--on-surface-variant);
  line-height: 1.6;
}

/* Footer */
footer {
  background: var(--surface-container-lowest);
  border-top: 1px solid rgba(139, 145, 157, .08);
  padding: 60px 40px 40px;
}
.footer-heading {
  font-weight: 700;
  margin-bottom: 12px;
  font-size: 13px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--outline);
}
.footer-link {
  color: var(--outline);
  font-size: 13px;
  text-decoration: none;
  background: none;
  border: 0;
  cursor: pointer;
  font-family: inherit;
  text-align: left;
  padding: 0;
}
.footer-link:hover {
  color: var(--on-surface);
}

/* Mobile */
@media (max-width: 768px) {
  section {
    padding: 80px 24px;
  }
  nav {
    padding: 14px 24px;
  }
  .hero {
    min-height: 50vh;
    padding-top: 60px;
  }
  .niveau-grid {
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  .level-row {
    grid-template-columns: 80px 1fr;
    gap: 12px;
    padding: 12px;
  }
  .nav-links,
  .nav-desktop-actions {
    display: none !important;
  }
  .hamburger {
    display: flex;
  }
  footer {
    padding: 40px 24px 32px;
  }
}
</style>
