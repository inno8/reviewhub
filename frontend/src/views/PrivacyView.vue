<script setup lang="ts">
import { useRouter } from 'vue-router';
const router = useRouter();
function goHome() { router.push('/welcome'); }
function goLogin() { router.push('/login'); }
const lastUpdated = '28 april 2026';
</script>

<template>
  <div class="legal-root">
    <!-- Top nav -->
    <header class="legal-nav">
      <div class="container nav-row">
        <button @click="goHome" class="brand-btn" aria-label="Naar home">
          <img src="/logo/leera-wordmark-primary.svg" alt="LEERA" class="brand-logo" />
        </button>
        <div class="nav-actions">
          <button @click="goHome" class="nav-link">Home</button>
          <button @click="goLogin" class="nav-cta">Inloggen</button>
        </div>
      </div>
    </header>

    <main class="container legal-body">
      <div class="legal-eyebrow">Privacyverklaring</div>
      <h1>Hoe LEERA met jouw gegevens omgaat</h1>
      <p class="lede">
        LEERA is een Nakijken Copilot voor het Nederlandse MBO. We verwerken
        gegevens van docenten, studenten en schoolbeheerders om PR-feedback
        te kunnen genereren en de leerlijn van studenten zichtbaar te maken.
        Deze verklaring legt uit wat we verzamelen, waarom, hoe lang we het
        bewaren en welke rechten je hebt onder de AVG.
      </p>
      <p class="meta">Laatst bijgewerkt: {{ lastUpdated }}</p>

      <!-- 1. Wie zijn wij -->
      <section>
        <h2>1. Wie zijn wij</h2>
        <p>
          LEERA wordt geleverd door <strong>itec</strong>, een Nederlandse
          onderneming gevestigd in Nederland. We zijn de
          verwerkingsverantwoordelijke voor het LEERA-platform, behalve waar
          we expliciet als verwerker optreden voor een onderwijsinstelling
          (zie sectie 9). Vragen over privacy gaan naar
          <a href="mailto:inno8techs@gmail.com">inno8techs@gmail.com</a>.
        </p>
      </section>

      <!-- 2. Wat we verzamelen -->
      <section>
        <h2>2. Welke gegevens we verzamelen</h2>

        <h3>Accountgegevens</h3>
        <ul>
          <li>Naam en e-mailadres (om in te loggen en je toe te wijzen aan een klas)</li>
          <li>Rol (student, docent, schoolbeheerder)</li>
          <li>Wachtwoord (versleuteld opgeslagen, nooit in platte tekst)</li>
        </ul>

        <h3>Onderwijsgegevens</h3>
        <ul>
          <li>Klas (cohort), vak (course) en lidmaatschap</li>
          <li>GitHub-koppeling: GitHub-gebruikersnaam en repositories die je expliciet koppelt</li>
          <li>Pull requests, commits, en de daarin opgenomen broncode</li>
          <li>Door de docent geschreven (en door AI voorgestelde) feedback</li>
          <li>Beoordelingen, rubriekscores en skill-metingen</li>
        </ul>

        <h3>Gebruiksgegevens</h3>
        <ul>
          <li>Aanmeldmomenten en sessietokens (kort levensduur)</li>
          <li>Welke pagina's je opent in de app</li>
          <li>Foutlogs (technische diagnostiek, geen broncode)</li>
        </ul>

        <p>
          We verzamelen <strong>geen</strong> bijzondere persoonsgegevens
          (gezondheid, religie, politieke voorkeur, BSN, etc.). Plaats geen
          dergelijke gegevens in PR-bodies, commits of broncode.
        </p>
      </section>

      <!-- 3. Waarvoor we het gebruiken -->
      <section>
        <h2>3. Waarvoor we deze gegevens gebruiken</h2>
        <ul>
          <li><strong>Service leveren:</strong> AI-feedback genereren op PR's, rubriekscores berekenen, klas- en studentoverzichten tonen.</li>
          <li><strong>Leerlijn zichtbaar maken:</strong> skill-metingen bijhouden, terugkerende fouten herkennen, voortgang aan student en docent laten zien.</li>
          <li><strong>Account & toegang:</strong> inloggen, organisatie-isolatie, beheer van rollen.</li>
          <li><strong>Beveiliging:</strong> misbruik detecteren, rate-limiting, foutdiagnostiek.</li>
          <li><strong>Communicatie:</strong> uitnodigingen, wachtwoord-instelmails, productupdates die direct met je gebruik te maken hebben.</li>
        </ul>
        <p>
          We gebruiken je gegevens <strong>niet</strong> voor advertenties,
          niet voor profilering buiten de onderwijscontext, en we verkopen
          ze nooit aan derden.
        </p>
      </section>

      <!-- 4. Rechtsgrondslag -->
      <section>
        <h2>4. Rechtsgrondslag (AVG art. 6)</h2>
        <ul>
          <li><strong>Uitvoering van de overeenkomst</strong> (art. 6 lid 1 b) — voor het leveren van de dienst aan je school of bootcamp.</li>
          <li><strong>Gerechtvaardigd belang</strong> (art. 6 lid 1 f) — voor beveiliging, fraudepreventie en productverbetering. We wegen jouw belangen mee.</li>
          <li><strong>Wettelijke verplichting</strong> (art. 6 lid 1 c) — voor zover we gegevens moeten bewaren of overleggen aan toezichthouders.</li>
        </ul>
      </section>

      <!-- 5. AI-verwerking -->
      <section>
        <h2>5. AI-verwerking van je code</h2>
        <p>
          Om feedback op een PR te kunnen schrijven, sturen we de diff (de
          gewijzigde regels code), de PR-titel en -beschrijving, en de
          rubriekdefinitie van de docent naar een large language model
          (LLM). Het LLM stelt een feedback-concept voor; de docent leest,
          past aan, en klikt pas dan op Versturen.
        </p>
        <p>
          We gebruiken vandaag <strong>Anthropic Claude</strong> (en
          incidenteel OpenAI-modellen) als LLM-leverancier. Anthropic
          verwerkt API-aanvragen standaard in de Verenigde Staten en
          gebruikt API-data <strong>niet</strong> om hun modellen te trainen
          (per Anthropic's commercial terms). De gegevens worden binnen
          maximaal 30 dagen verwijderd uit Anthropic's logs.
        </p>
        <p>
          Onze huidige Claude-API-aanroepen gaan via Anthropic's
          standaardendpoint, dat in de VS staat. Dit betekent dat
          studentcode kortstondig de EU verlaat. We dekken deze doorgifte
          met de <strong>Standard Contractual Clauses</strong> van de
          Europese Commissie (Schrems II-conform). We werken aan migratie
          naar een EU-residente LLM-route (AWS Bedrock,
          eu-central-1 / Frankfurt) en willen dit afgerond hebben in v1.1
          (zomer 2026). Tot die tijd kun je in je instellingen aangeven dat
          AI-feedback voor jouw klas uit moet staan; dan blijft alle
          studentcode binnen LEERA's eigen EU-infrastructuur.
        </p>
      </section>

      <!-- 6. Verwerkers -->
      <section>
        <h2>6. Verwerkers (sub-processors)</h2>
        <p>We schakelen de volgende verwerkers in om de dienst te leveren:</p>
        <table class="processors">
          <thead>
            <tr><th>Verwerker</th><th>Doel</th><th>Locatie</th></tr>
          </thead>
          <tbody>
            <tr><td>Hosting (applicatie + database)</td><td>Draaien van LEERA, opslaan van data</td><td>EU (Nederland / Frankfurt)</td></tr>
            <tr><td>PostgreSQL</td><td>Hoofddatabase</td><td>EU</td></tr>
            <tr><td>Anthropic</td><td>LLM-feedback genereren</td><td>VS (SCC); EU-migratie gepland</td></tr>
            <tr><td>OpenAI (incidenteel)</td><td>LLM-fallback</td><td>VS (SCC)</td></tr>
            <tr><td>Resend / SMTP-leverancier</td><td>Transactionele e-mail (uitnodigingen, instelmails)</td><td>EU</td></tr>
            <tr><td>GitHub (van klant)</td><td>PR's en commits ophalen</td><td>VS — gegevens komen al van GitHub</td></tr>
          </tbody>
        </table>
        <p>
          Wijzigingen in de lijst van verwerkers melden we minimaal 30 dagen
          van tevoren via e-mail aan de schoolbeheerder.
        </p>
      </section>

      <!-- 7. Hosting -->
      <section>
        <h2>7. Hosting en grensoverschrijdende doorgifte</h2>
        <p>
          De LEERA-applicatie en database draaien <strong>in de EU</strong>.
          Alle gebruikersgegevens, broncode-snippets, feedback en
          rubriekscores die in LEERA worden opgeslagen, blijven in de EU.
          De enige doorgifte naar buiten de EU vindt plaats wanneer een PR
          ter beoordeling naar het LLM wordt gestuurd (zie sectie 5). Voor
          die doorgifte gelden de SCC's van de Europese Commissie.
        </p>
      </section>

      <!-- 8. Bewaartermijnen -->
      <section>
        <h2>8. Bewaartermijnen</h2>
        <ul>
          <li><strong>Actieve cohorten:</strong> we bewaren PR's, feedback en skill-metingen zolang de cohort loopt.</li>
          <li><strong>Na afloop van een cohort:</strong> gegevens worden 1 jaar in een gearchiveerde staat bewaard, zodat een student op haar leerlijn kan terugkijken.</li>
          <li><strong>Verwijderverzoek:</strong> op verzoek van de school of de individuele student verwijderen we eerder. Stuur een e-mail aan <a href="mailto:inno8techs@gmail.com">inno8techs@gmail.com</a>; we reageren binnen 30 dagen.</li>
          <li><strong>Logs:</strong> applicatielogs en foutlogs maximaal 90 dagen.</li>
          <li><strong>Backups:</strong> roterende backups maximaal 35 dagen.</li>
        </ul>
      </section>

      <!-- 9. Rol school -->
      <section>
        <h2>9. Rol van de school</h2>
        <p>
          Voor onderwijsgegevens (PR's, feedback, scores van studenten) treedt
          jouw school of opleiding op als
          <strong>verwerkingsverantwoordelijke</strong> en LEERA als
          <strong>verwerker</strong>. We sluiten met elke onderwijsinstelling
          een verwerkersovereenkomst (DPA) op grond van AVG art. 28. Vraag
          een kopie op via je schoolbeheerder of stuur een e-mail aan
          <a href="mailto:inno8techs@gmail.com">inno8techs@gmail.com</a>.
        </p>
      </section>

      <!-- 10. Beveiliging -->
      <section>
        <h2>10. Beveiliging</h2>
        <ul>
          <li>Versleutelde verbindingen (TLS 1.2+) voor alle verkeer</li>
          <li>Wachtwoorden gehasht met moderne hash-functies (Argon2 / PBKDF2)</li>
          <li>Toegang tot productie alleen via tweetraps-authenticatie</li>
          <li>Per-organisatie isolatie op database-niveau (org-scoped queries)</li>
          <li>Foutlogs gescand op persoonsgegevens vóór ze in storage komen</li>
          <li>Periodieke beveiligingsreviews</li>
        </ul>
      </section>

      <!-- 11. Jouw rechten -->
      <section>
        <h2>11. Jouw rechten onder de AVG</h2>
        <ul>
          <li><strong>Inzage</strong> — vraag een kopie op van wat we over je hebben</li>
          <li><strong>Rectificatie</strong> — onjuiste gegevens laten corrigeren</li>
          <li><strong>Wissing</strong> — vergeet-mij verzoek (zie sectie 8)</li>
          <li><strong>Beperking</strong> — verwerking tijdelijk pauzeren</li>
          <li><strong>Bezwaar</strong> — bezwaar maken tegen verwerking op basis van gerechtvaardigd belang</li>
          <li><strong>Overdraagbaarheid</strong> — je gegevens in machine-leesbaar formaat ontvangen</li>
          <li><strong>Klacht indienen</strong> — bij de Autoriteit Persoonsgegevens (autoriteitpersoonsgegevens.nl)</li>
        </ul>
        <p>
          Stuur verzoeken aan
          <a href="mailto:inno8techs@gmail.com">inno8techs@gmail.com</a>.
          We reageren binnen 30 dagen.
        </p>
      </section>

      <!-- 12. Cookies -->
      <section>
        <h2>12. Cookies</h2>
        <p>
          We gebruiken alleen functionele cookies (sessietoken, voorkeur
          lichte/donkere modus). We gebruiken <strong>geen</strong>
          tracking-cookies, geen advertentiepixels en geen analytics-cookies
          van derden. Daarom hebben we geen cookie-banner nodig.
        </p>
      </section>

      <!-- 13. Minderjarigen -->
      <section>
        <h2>13. Minderjarigen</h2>
        <p>
          MBO-studenten zijn vaak 16 jaar of ouder. LEERA is bedoeld voor
          gebruik binnen een onderwijsinstelling; de school is
          verantwoordelijk voor de juiste juridische grondslag (instemming
          van ouders waar dat nodig is, of een onderwijsovereenkomst). We
          hebben op dit moment geen aparte ouder-toestemmingsflow; als jouw
          school die nodig heeft, neem contact op zodat we daarover kunnen
          afstemmen.
        </p>
      </section>

      <!-- 14. Wijzigingen -->
      <section>
        <h2>14. Wijzigingen in dit beleid</h2>
        <p>
          We kunnen deze verklaring aanpassen wanneer we onze dienst
          uitbreiden of een verwerker wisselen. Materiële wijzigingen melden
          we minimaal 30 dagen van tevoren per e-mail aan de schoolbeheerder.
          De huidige versie is altijd te vinden op deze pagina.
        </p>
      </section>

      <!-- 15. Contact -->
      <section>
        <h2>15. Contact</h2>
        <p>
          <strong>itec — LEERA</strong><br />
          Privacy contact: <a href="mailto:inno8techs@gmail.com">inno8techs@gmail.com</a>
        </p>
      </section>

      <div class="legal-foot">
        <button @click="goHome" class="back-link">← Terug naar home</button>
      </div>
    </main>

    <footer class="legal-footer">
      <div class="container">
        <div class="legal-footer-row">
          <div class="legal-footer-copy">© 2026 LEERA</div>
          <div class="legal-footer-links">
            <router-link to="/privacy" class="footer-link">Privacy</router-link>
            <router-link to="/voorwaarden" class="footer-link">Voorwaarden</router-link>
            <router-link to="/dpa" class="footer-link">DPA</router-link>
            <a href="mailto:inno8techs@gmail.com" class="footer-link">Contact</a>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.legal-root {
  --background: #10141a;
  --surface: #161b22;
  --surface-container: #1c222b;
  --on-surface: #dfe2eb;
  --on-surface-variant: #a8b0bd;
  --outline: #8b919d;
  --primary: #a2c9ff;
  --outline-variant: rgba(139, 145, 157, 0.18);
  background: var(--background);
  color: var(--on-surface);
  min-height: 100vh;
  font-family: 'Inter', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}
.container { max-width: 880px; margin: 0 auto; padding: 0 24px; }

.legal-nav {
  position: sticky; top: 0; z-index: 10;
  background: rgba(16, 20, 26, 0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--outline-variant);
}
.nav-row { display: flex; align-items: center; justify-content: space-between; height: 64px; }
.brand-btn { background: none; border: none; cursor: pointer; padding: 0; }
.brand-logo { height: 26px; display: block; }
.nav-actions { display: flex; gap: 8px; align-items: center; }
.nav-link {
  background: none; border: none; color: var(--on-surface-variant);
  font-size: 14px; cursor: pointer; padding: 8px 12px;
}
.nav-link:hover { color: var(--on-surface); }
.nav-cta {
  background: var(--primary); color: #0b1220; border: none;
  padding: 8px 16px; border-radius: 8px; font-weight: 600;
  font-size: 14px; cursor: pointer;
}
.nav-cta:hover { opacity: 0.9; }

.legal-body { padding: 64px 24px 96px; }
.legal-eyebrow {
  display: inline-block; font-size: 12px; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--primary); font-weight: 600;
  margin-bottom: 12px;
}
h1 {
  font-size: clamp(32px, 4vw, 44px); line-height: 1.15;
  font-weight: 700; margin: 0 0 16px;
  letter-spacing: -0.02em;
}
.lede { font-size: 18px; line-height: 1.6; color: var(--on-surface-variant); margin: 0 0 12px; }
.meta { font-size: 13px; color: var(--outline); margin-bottom: 56px; }

section { margin-bottom: 40px; }
h2 {
  font-size: 22px; line-height: 1.3; font-weight: 700;
  margin: 0 0 12px; letter-spacing: -0.01em;
}
h3 {
  font-size: 16px; font-weight: 600; margin: 20px 0 8px;
  color: var(--on-surface);
}
p { line-height: 1.7; color: var(--on-surface-variant); margin: 0 0 12px; font-size: 15px; }
ul { padding-left: 22px; margin: 0 0 12px; }
li { line-height: 1.7; color: var(--on-surface-variant); margin-bottom: 6px; font-size: 15px; }
strong { color: var(--on-surface); font-weight: 600; }
a { color: var(--primary); text-decoration: none; }
a:hover { text-decoration: underline; }

table.processors {
  width: 100%; border-collapse: collapse; margin: 12px 0 8px;
  font-size: 14px;
}
table.processors th, table.processors td {
  text-align: left; padding: 10px 12px;
  border-bottom: 1px solid var(--outline-variant);
}
table.processors th {
  font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--outline); font-weight: 600;
}
table.processors td { color: var(--on-surface-variant); }

.legal-foot { margin-top: 48px; padding-top: 24px; border-top: 1px solid var(--outline-variant); }
.back-link {
  background: none; border: none; color: var(--primary);
  font-size: 14px; cursor: pointer; padding: 0;
}
.back-link:hover { text-decoration: underline; }

.legal-footer { border-top: 1px solid var(--outline-variant); padding: 24px 0; }
.legal-footer-row {
  display: flex; flex-wrap: wrap; gap: 16px;
  justify-content: space-between; align-items: center;
}
.legal-footer-copy { color: var(--outline); font-size: 13px; }
.legal-footer-links { display: flex; gap: 20px; flex-wrap: wrap; }
.footer-link {
  background: none; border: none; color: var(--on-surface-variant);
  font-size: 13px; cursor: pointer; padding: 0; text-decoration: none;
}
.footer-link:hover { color: var(--on-surface); }
</style>
