<script setup lang="ts">
/**
 * LandingView — public marketing page for leera.app
 *
 * Audience: Dutch MBO-4 ICT teachers + school administrators evaluating
 * the product. Visual reference: https://www.coderabbit.ai/ — same
 * music-no-voiceover language, dark surface with primary-blue accents,
 * real product UI as proof, restrained kinetic motion.
 *
 * Sections (top → bottom):
 *   1. Sticky header with wordmark + nav + CTA
 *   2. Hero — tagline, sub, dual CTA, faux-rubric visual
 *   3. Problem strip — "20 min × 30 students × every week..."
 *   4. How it works — 3-step diagram
 *   5. Features grid — 6 cards
 *   6. Built for Dutch MBO docent — short rationale + quotes
 *   7. Pricing teaser — €200/cohort/maand
 *   8. Final CTA
 *   9. Footer
 *
 * No backend calls. Static-but-real-product copy. Updates here are
 * just edits to the strings — no other moving parts.
 */
import { ref, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();

// Sticky-header backdrop opacity transitions on scroll. Subtle, not flashy.
const scrolled = ref(false);
function onScroll() {
  scrolled.value = window.scrollY > 24;
}
onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }));
onUnmounted(() => window.removeEventListener('scroll', onScroll));

function goLogin() { router.push('/login'); }
function goSignup() { router.push('/org-signup'); }
function scrollTo(id: string) {
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
</script>

<template>
  <div class="min-h-screen bg-background text-on-surface antialiased">
    <!-- ────────────────────────── HEADER ────────────────────────── -->
    <header
      :class="[
        'fixed top-0 left-0 right-0 z-50 transition-all duration-300 backdrop-blur-md',
        scrolled
          ? 'bg-background/85 border-b border-outline-variant/20'
          : 'bg-transparent border-b border-transparent',
      ]"
    >
      <div class="max-w-7xl mx-auto px-6 lg:px-10 h-16 flex items-center justify-between">
        <a href="#top" class="flex items-center gap-3">
          <img src="/logo/leera-wordmark-primary.svg" alt="LEERA" class="h-7" />
        </a>
        <nav class="hidden md:flex items-center gap-8 text-sm text-on-surface-variant">
          <button @click="scrollTo('how')" class="hover:text-on-surface transition-colors">Zo werkt het</button>
          <button @click="scrollTo('features')" class="hover:text-on-surface transition-colors">Functies</button>
          <button @click="scrollTo('built-for')" class="hover:text-on-surface transition-colors">Voor wie</button>
          <button @click="scrollTo('pricing')" class="hover:text-on-surface transition-colors">Prijzen</button>
        </nav>
        <div class="flex items-center gap-3">
          <button
            @click="goLogin"
            class="hidden sm:inline-flex text-sm font-medium text-on-surface-variant hover:text-on-surface transition-colors px-3 py-2"
          >
            Inloggen
          </button>
          <button
            @click="goSignup"
            class="inline-flex items-center gap-1.5 bg-primary text-on-primary text-sm font-bold px-4 py-2 rounded-lg hover:opacity-90 active:scale-[0.98] transition-all shadow-lg shadow-primary/20"
          >
            Vraag een demo aan
            <span class="material-symbols-outlined text-base">arrow_forward</span>
          </button>
        </div>
      </div>
    </header>

    <!-- ────────────────────────── BACKGROUND ATMOSPHERE ────────────────────────── -->
    <!-- Soft gradient orbs behind the hero. Same visual language as the
         pitch video's BackgroundOrbs but static, since this is a web
         page not a 30fps composition. -->
    <div class="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
      <div class="absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full bg-primary/10 blur-3xl"></div>
      <div class="absolute top-1/3 -right-40 w-[500px] h-[500px] rounded-full bg-tertiary/10 blur-3xl"></div>
      <div class="absolute bottom-0 left-1/3 w-[400px] h-[400px] rounded-full bg-primary-container/10 blur-3xl"></div>
    </div>

    <!-- ────────────────────────── HERO ────────────────────────── -->
    <section id="top" class="relative pt-40 pb-24 px-6 lg:px-10">
      <div class="max-w-7xl mx-auto grid lg:grid-cols-2 gap-12 items-center">
        <div>
          <!-- Eyebrow -->
          <div class="inline-flex items-center gap-2 px-3 py-1.5 mb-6 rounded-full bg-surface-container-low border border-outline-variant/20 text-xs font-semibold text-on-surface-variant tracking-wide">
            <span class="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>
            Nakijken Copilot — gebouwd voor het MBO
          </div>

          <h1 class="text-4xl md:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.05] text-on-surface mb-6">
            Elke commit een les.
            <span class="block bg-gradient-to-r from-primary to-primary-container bg-clip-text text-transparent">
              Elke PR een beoordeling
            </span>
            die uit bewijs komt.
          </h1>

          <p class="text-lg md:text-xl text-on-surface-variant mb-10 max-w-xl leading-relaxed">
            LEERA reviewt de code van je studenten op elke commit, schrijft een rubric-concept in jouw stem,
            en houdt je het laatste woord. Een PR-review in 5 minuten — niet 20.
          </p>

          <div class="flex flex-wrap gap-3">
            <button
              @click="goSignup"
              class="inline-flex items-center gap-2 bg-primary text-on-primary text-base font-bold px-6 py-3.5 rounded-xl hover:opacity-90 active:scale-[0.98] transition-all shadow-xl shadow-primary/20"
            >
              Vraag een demo aan
              <span class="material-symbols-outlined">arrow_forward</span>
            </button>
            <button
              @click="scrollTo('how')"
              class="inline-flex items-center gap-2 bg-surface-container-low border border-outline-variant/20 text-base font-semibold px-6 py-3.5 rounded-xl hover:bg-surface-container active:scale-[0.98] transition-all"
            >
              <span class="material-symbols-outlined">play_arrow</span>
              Zie hoe het werkt
            </button>
          </div>

          <!-- Mini social-proof strip -->
          <div class="mt-12 pt-8 border-t border-outline-variant/10">
            <p class="text-xs uppercase tracking-widest text-outline mb-4 font-bold">
              Ontworpen voor de Nederlandse MBO-4 ICT
            </p>
            <div class="flex flex-wrap items-center gap-8 text-sm text-on-surface-variant">
              <span class="flex items-center gap-2">
                <span class="material-symbols-outlined text-base text-primary">verified</span>
                AVG-compliant
              </span>
              <span class="flex items-center gap-2">
                <span class="material-symbols-outlined text-base text-primary">code</span>
                Werkt in GitHub
              </span>
              <span class="flex items-center gap-2">
                <span class="material-symbols-outlined text-base text-primary">school</span>
                Rubric-gebaseerd
              </span>
            </div>
          </div>
        </div>

        <!-- Hero visual — faux rubric review panel.
             Built in HTML/CSS so it stays crisp + can be edited like
             any other component. Communicates "AI drafts, teacher
             decides" without a single screenshot. -->
        <div class="relative">
          <div class="relative bg-surface-container-low rounded-2xl border border-outline-variant/20 shadow-2xl shadow-black/40 p-6 backdrop-blur-sm">
            <!-- Faux header -->
            <div class="flex items-center justify-between pb-4 border-b border-outline-variant/10">
              <div class="flex items-center gap-3">
                <div class="w-9 h-9 rounded-full bg-primary/15 flex items-center justify-center">
                  <span class="material-symbols-outlined text-primary text-lg">rate_review</span>
                </div>
                <div>
                  <p class="text-xs text-outline">Nakijken Copilot</p>
                  <p class="text-sm font-bold text-on-surface">PR #42 — Lucas / email-validator</p>
                </div>
              </div>
              <div class="text-[10px] font-bold uppercase tracking-widest text-tertiary bg-tertiary/15 px-2 py-1 rounded-md">
                AI-concept
              </div>
            </div>

            <!-- Rubric rows -->
            <div class="mt-4 space-y-2">
              <div v-for="row in [
                { name: 'Code-ontwerp', score: 3, max: 4 },
                { name: 'Code-kwaliteit', score: 3, max: 4 },
                { name: 'Veiligheid', score: 2, max: 4 },
                { name: 'Testen', score: 2, max: 4 },
                { name: 'Verbetering', score: 3, max: 4 },
                { name: 'Samenwerking', score: 3, max: 4 },
              ]" :key="row.name" class="flex items-center justify-between gap-3 py-2 px-3 rounded-lg bg-surface-container-lowest border border-outline-variant/10">
                <span class="text-sm text-on-surface">{{ row.name }}</span>
                <div class="flex items-center gap-2">
                  <div class="flex gap-1">
                    <span
                      v-for="n in row.max"
                      :key="n"
                      :class="['w-1.5 h-3.5 rounded-sm transition-colors', n <= row.score ? 'bg-primary' : 'bg-outline-variant/30']"
                    ></span>
                  </div>
                  <span class="text-xs font-mono text-on-surface-variant tabular-nums">{{ row.score }}/{{ row.max }}</span>
                </div>
              </div>
            </div>

            <!-- AI comment teaser -->
            <div class="mt-4 p-3 rounded-lg bg-primary-container/5 border border-primary/15">
              <p class="text-xs font-bold text-primary uppercase tracking-widest mb-1">AI-concept · regel 47</p>
              <p class="text-sm text-on-surface-variant leading-relaxed">
                Deze <code class="font-mono text-xs text-tertiary bg-surface-container-lowest px-1 py-0.5 rounded">except:</code> vangt elke fout zonder onderscheid.
                Vang de specifieke uitzondering op zodat onverwachte bugs niet onzichtbaar worden.
              </p>
            </div>

            <!-- Action footer -->
            <div class="mt-4 flex items-center justify-between gap-3">
              <p class="text-xs text-outline">
                <span class="text-on-surface-variant font-semibold">Jij</span> beslist: accepteren, bijsturen of schrappen.
              </p>
              <button class="inline-flex items-center gap-1.5 bg-primary text-on-primary text-xs font-bold px-3 py-2 rounded-lg shadow-lg shadow-primary/20">
                Verstuur naar student
                <span class="material-symbols-outlined text-sm">send</span>
              </button>
            </div>
          </div>

          <!-- Floating accent — "5 min" badge -->
          <div class="absolute -bottom-4 -left-4 bg-tertiary text-on-tertiary px-4 py-2.5 rounded-xl font-bold text-sm shadow-2xl shadow-black/40 rotate-[-3deg]">
            <p class="text-xs uppercase tracking-widest opacity-80">Review-tijd</p>
            <p class="text-2xl leading-none">≤ 5 min</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ────────────────────────── PROBLEM ────────────────────────── -->
    <section class="relative px-6 lg:px-10 py-20 border-y border-outline-variant/10 bg-surface-container-lowest/50">
      <div class="max-w-5xl mx-auto text-center">
        <p class="text-xs uppercase tracking-widest text-outline mb-4 font-bold">Het probleem</p>
        <h2 class="text-3xl md:text-4xl font-bold leading-tight text-on-surface mb-6">
          Code nakijken duurt langer dan
          <span class="text-tertiary">code lesgeven.</span>
        </h2>
        <div class="grid md:grid-cols-3 gap-6 mt-10 text-left">
          <div class="p-6 bg-surface-container-low rounded-xl border border-outline-variant/10">
            <p class="text-3xl font-bold text-tertiary mb-2">20<span class="text-base text-outline ml-1">min</span></p>
            <p class="text-sm text-on-surface-variant">Per PR. Diff lezen, rubric scoren, comment in jouw stem schrijven.</p>
          </div>
          <div class="p-6 bg-surface-container-low rounded-xl border border-outline-variant/10">
            <p class="text-3xl font-bold text-tertiary mb-2">×30<span class="text-base text-outline ml-1">studenten</span></p>
            <p class="text-sm text-on-surface-variant">Elke klas. Elke week opnieuw. Zondagavonden nakijken werd standaard.</p>
          </div>
          <div class="p-6 bg-surface-container-low rounded-xl border border-outline-variant/10">
            <p class="text-3xl font-bold text-tertiary mb-2">10<span class="text-base text-outline ml-1">u/wk</span></p>
            <p class="text-sm text-on-surface-variant">Tijd die niet naar lesgeven, één-op-één coaching of curriculum gaat.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ────────────────────────── HOW IT WORKS ────────────────────────── -->
    <section id="how" class="relative px-6 lg:px-10 py-24">
      <div class="max-w-7xl mx-auto">
        <div class="text-center mb-16">
          <p class="text-xs uppercase tracking-widest text-outline mb-4 font-bold">Zo werkt het</p>
          <h2 class="text-3xl md:text-4xl font-bold leading-tight text-on-surface mb-4">
            Van push naar feedback in seconden.
          </h2>
          <p class="text-lg text-on-surface-variant max-w-2xl mx-auto">
            Drie stappen. Geen extra tools. Studenten blijven in GitHub, jij blijft de docent.
          </p>
        </div>

        <div class="grid md:grid-cols-3 gap-6 lg:gap-8 relative">
          <!-- Connector line behind cards (desktop only) -->
          <div class="hidden md:block absolute top-12 left-[16%] right-[16%] h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent"></div>

          <div v-for="(step, i) in [
            { num: '01', title: 'Student pusht code', body: 'Een commit landt op GitHub. LEERA reviewt elke commit op regelniveau — de student ziet wat hij kan verbeteren voor hij een PR opent.', icon: 'rocket_launch' },
            { num: '02', title: 'AI schrijft het concept', body: 'Bij een PR genereert LEERA een rubric-score per criterium plus inline comments in jouw stem. Geen lege textarea meer.', icon: 'auto_awesome' },
            { num: '03', title: 'Jij houdt het laatste woord', body: 'Lees het concept. Pas aan, schrap, voeg toe. Klik Verstuur. Comments verschijnen op de PR — daar waar de student al werkt.', icon: 'how_to_reg' },
          ]" :key="step.num" class="relative bg-surface-container-low rounded-2xl border border-outline-variant/10 p-6 hover:border-primary/30 transition-colors">
            <div class="absolute top-6 right-6 text-5xl font-bold text-outline-variant/20 leading-none">{{ step.num }}</div>
            <div class="w-12 h-12 rounded-xl bg-primary/15 flex items-center justify-center mb-5">
              <span class="material-symbols-outlined text-primary text-2xl">{{ step.icon }}</span>
            </div>
            <h3 class="text-xl font-bold text-on-surface mb-3">{{ step.title }}</h3>
            <p class="text-sm text-on-surface-variant leading-relaxed">{{ step.body }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ────────────────────────── FEATURES ────────────────────────── -->
    <section id="features" class="relative px-6 lg:px-10 py-24 bg-surface-container-lowest/50 border-y border-outline-variant/10">
      <div class="max-w-7xl mx-auto">
        <div class="text-center mb-16">
          <p class="text-xs uppercase tracking-widest text-outline mb-4 font-bold">Functies</p>
          <h2 class="text-3xl md:text-4xl font-bold leading-tight text-on-surface mb-4">
            Bouwsteen voor klas-grootte feedback.
          </h2>
          <p class="text-lg text-on-surface-variant max-w-2xl mx-auto">
            Niet één AI-tool, maar een werkflow. Van het eerste commit tot het eindniveau-overzicht.
          </p>
        </div>

        <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          <article v-for="f in [
            { title: 'Feedback op elke commit', body: 'Direct na de push krijgt de student AI-feedback op regel-niveau. Lossen ze het zelf op, dan komt de PR pas binnen als hij echt klaar is.', icon: 'bolt' },
            { title: 'Rubric-concept in jouw stem', body: 'Per criterium een score + bewijs + suggestie. De AI schrijft als jij — niet als ChatGPT.', icon: 'edit_note' },
            { title: 'Jij houdt het laatste woord', body: 'Accepteren, bijsturen of schrappen. Geen enkele comment gaat naar de student zonder dat jij Verstuur klikt.', icon: 'how_to_reg' },
            { title: 'Skill-trajectorie per student', body: 'Bayesiaanse scores per vaardigheid die zich aanpassen aan bewijs. Geen 100% bij default — pas confident als de student het verdiend heeft.', icon: 'trending_up' },
            { title: 'Terugkerende fouten in beeld', body: 'Welke patronen blijft een student maken? LEERA herkent ze en maakt ze zichtbaar zodat coaching gericht wordt.', icon: 'pattern' },
            { title: 'Klas-overzicht in één blik', body: 'Per cohort: gemiddeld eindniveau, zwakste criteria, leerlingen die afglijden. Bewijs-gebaseerd. Niet onderbuik.', icon: 'insights' },
          ]" :key="f.title" class="group bg-surface-container-low rounded-2xl border border-outline-variant/10 p-6 hover:border-primary/30 hover:bg-surface-container transition-all">
            <div class="w-11 h-11 rounded-xl bg-primary/15 flex items-center justify-center mb-4 group-hover:bg-primary/25 transition-colors">
              <span class="material-symbols-outlined text-primary text-xl">{{ f.icon }}</span>
            </div>
            <h3 class="text-lg font-bold text-on-surface mb-2">{{ f.title }}</h3>
            <p class="text-sm text-on-surface-variant leading-relaxed">{{ f.body }}</p>
          </article>
        </div>
      </div>
    </section>

    <!-- ────────────────────────── BUILT FOR ────────────────────────── -->
    <section id="built-for" class="relative px-6 lg:px-10 py-24">
      <div class="max-w-5xl mx-auto">
        <div class="grid md:grid-cols-2 gap-12 items-center">
          <div>
            <p class="text-xs uppercase tracking-widest text-outline mb-4 font-bold">Voor wie</p>
            <h2 class="text-3xl md:text-4xl font-bold leading-tight text-on-surface mb-6">
              Gebouwd voor de Nederlandse MBO-4 ICT-docent.
            </h2>
            <p class="text-lg text-on-surface-variant leading-relaxed mb-6">
              Geen Amerikaans bootcamp. Geen havo-vwo cosmetica. LEERA is gemaakt
              voor de docenten die werkstukken nakijken op kerntaken,
              werkprocessen en gedragskenmerken — in de taal van het Examenproject.
            </p>
            <ul class="space-y-3">
              <li v-for="point in [
                'Rubric-templates op MBO-4 niveau, gekoppeld aan kerntaken',
                'Nederlandse feedback in jouw stem — geen vertaalde standaardzinnen',
                'GitHub-gebaseerd, omdat dat is waar je studenten straks werken',
                'AVG-compliant; data blijft in EU-regio',
              ]" :key="point" class="flex items-start gap-3 text-sm text-on-surface-variant">
                <span class="material-symbols-outlined text-primary text-lg mt-0.5 shrink-0">check_circle</span>
                <span>{{ point }}</span>
              </li>
            </ul>
          </div>

          <!-- Quote card -->
          <figure class="relative bg-surface-container-low rounded-2xl border border-outline-variant/10 p-8 shadow-xl shadow-black/30">
            <span class="material-symbols-outlined text-primary text-4xl opacity-30 absolute top-4 left-4">format_quote</span>
            <blockquote class="text-lg md:text-xl font-medium text-on-surface leading-relaxed mt-6 mb-6">
              Mijn zondagavonden waren nakijktijd. Met LEERA review ik op vrijdag,
              klaar voor het weekend.
            </blockquote>
            <figcaption class="flex items-center gap-3 pt-4 border-t border-outline-variant/10">
              <div class="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
                <span class="material-symbols-outlined text-primary text-base">person</span>
              </div>
              <div>
                <p class="text-sm font-bold text-on-surface">Jan, ICT-docent</p>
                <p class="text-xs text-outline">Media College — pilot 2026</p>
              </div>
            </figcaption>
          </figure>
        </div>
      </div>
    </section>

    <!-- ────────────────────────── PRICING ────────────────────────── -->
    <section id="pricing" class="relative px-6 lg:px-10 py-24 bg-surface-container-lowest/50 border-y border-outline-variant/10">
      <div class="max-w-3xl mx-auto text-center">
        <p class="text-xs uppercase tracking-widest text-outline mb-4 font-bold">Prijzen</p>
        <h2 class="text-3xl md:text-4xl font-bold leading-tight text-on-surface mb-4">
          Eén tarief. Per cohort. Geen verrassingen.
        </h2>
        <p class="text-lg text-on-surface-variant mb-12">
          Onbeperkt PR-reviews, onbeperkt commits, onbeperkt studenten in het cohort.
          Betaal alleen voor de klassen die je actief nakijkt.
        </p>

        <div class="bg-surface-container-low rounded-2xl border border-primary/30 p-8 md:p-10 shadow-2xl shadow-primary/10 max-w-md mx-auto">
          <p class="text-sm font-bold uppercase tracking-widest text-primary mb-2">Cohort-licentie</p>
          <div class="flex items-baseline justify-center gap-2 mb-6">
            <span class="text-5xl font-bold text-on-surface">€200</span>
            <span class="text-lg text-on-surface-variant">/ cohort / maand</span>
          </div>
          <ul class="space-y-3 text-left text-sm text-on-surface-variant mb-8">
            <li v-for="point in [
              'Onbeperkt PR-reviews + commit-feedback',
              'Tot 30 studenten per cohort',
              'Rubric-templates + jouw stem-kalibratie',
              'Skill-trajectorie + groei-rapportage',
              'AVG-compliant, EU-hosting',
              'E-mail support binnen 24 uur',
            ]" :key="point" class="flex items-start gap-3">
              <span class="material-symbols-outlined text-primary text-lg mt-0.5 shrink-0">check</span>
              <span>{{ point }}</span>
            </li>
          </ul>
          <button
            @click="goSignup"
            class="w-full bg-primary text-on-primary text-base font-bold py-3.5 rounded-xl hover:opacity-90 active:scale-[0.98] transition-all shadow-lg shadow-primary/20"
          >
            Vraag een demo aan
          </button>
          <p class="text-xs text-outline mt-4">Pilot-tarieven beschikbaar voor MBO-instellingen</p>
        </div>
      </div>
    </section>

    <!-- ────────────────────────── FINAL CTA ────────────────────────── -->
    <section class="relative px-6 lg:px-10 py-24">
      <div class="max-w-4xl mx-auto text-center">
        <h2 class="text-3xl md:text-5xl font-bold leading-tight text-on-surface mb-6">
          Klaar om je weekenden terug te krijgen?
        </h2>
        <p class="text-lg text-on-surface-variant mb-10 max-w-2xl mx-auto">
          We zoeken nog 3 MBO-instellingen voor de pilot van schooljaar 2026/27.
          Plan een demo van 30 minuten — we laten zien wat het scheelt.
        </p>
        <div class="flex flex-wrap items-center justify-center gap-3">
          <button
            @click="goSignup"
            class="inline-flex items-center gap-2 bg-primary text-on-primary text-base font-bold px-6 py-3.5 rounded-xl hover:opacity-90 active:scale-[0.98] transition-all shadow-xl shadow-primary/20"
          >
            Vraag een demo aan
            <span class="material-symbols-outlined">arrow_forward</span>
          </button>
          <a
            href="mailto:hallo@leera.app"
            class="inline-flex items-center gap-2 bg-surface-container-low border border-outline-variant/20 text-base font-semibold px-6 py-3.5 rounded-xl hover:bg-surface-container active:scale-[0.98] transition-all"
          >
            <span class="material-symbols-outlined">mail</span>
            hallo@leera.app
          </a>
        </div>
      </div>
    </section>

    <!-- ────────────────────────── FOOTER ────────────────────────── -->
    <footer class="px-6 lg:px-10 py-12 border-t border-outline-variant/10">
      <div class="max-w-7xl mx-auto">
        <div class="grid md:grid-cols-4 gap-8 mb-10">
          <div class="md:col-span-2">
            <img src="/logo/leera-wordmark-mono.svg" alt="LEERA" class="h-7 mb-4 opacity-80" />
            <p class="text-sm text-on-surface-variant max-w-md">
              Nakijken Copilot voor het MBO. Elke commit een les, elke PR een
              beoordeling die uit bewijs komt.
            </p>
          </div>
          <div>
            <p class="text-xs font-bold uppercase tracking-widest text-outline mb-4">Product</p>
            <ul class="space-y-2 text-sm">
              <li><button @click="scrollTo('how')" class="text-on-surface-variant hover:text-on-surface transition-colors">Zo werkt het</button></li>
              <li><button @click="scrollTo('features')" class="text-on-surface-variant hover:text-on-surface transition-colors">Functies</button></li>
              <li><button @click="scrollTo('pricing')" class="text-on-surface-variant hover:text-on-surface transition-colors">Prijzen</button></li>
              <li><button @click="goLogin" class="text-on-surface-variant hover:text-on-surface transition-colors">Inloggen</button></li>
            </ul>
          </div>
          <div>
            <p class="text-xs font-bold uppercase tracking-widest text-outline mb-4">Bedrijf</p>
            <ul class="space-y-2 text-sm">
              <li><a href="mailto:hallo@leera.app" class="text-on-surface-variant hover:text-on-surface transition-colors">Contact</a></li>
              <li><a href="#" class="text-on-surface-variant hover:text-on-surface transition-colors">Privacy</a></li>
              <li><a href="#" class="text-on-surface-variant hover:text-on-surface transition-colors">Voorwaarden</a></li>
              <li><a href="#" class="text-on-surface-variant hover:text-on-surface transition-colors">DPA</a></li>
            </ul>
          </div>
        </div>
        <div class="pt-8 border-t border-outline-variant/10 flex flex-wrap items-center justify-between gap-4">
          <p class="text-xs text-outline">
            © 2026 LEERA · Gemaakt voor docenten in Nederland
          </p>
          <p class="text-xs text-outline">
            <span class="text-on-surface-variant font-mono">v1.0</span> · Pilot 2026
          </p>
        </div>
      </div>
    </footer>
  </div>
</template>
