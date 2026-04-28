<script setup lang="ts">
import { useRouter } from 'vue-router';
const router = useRouter();
function goHome() { router.push('/welcome'); }
function goLogin() { router.push('/login'); }
const lastUpdated = '28 april 2026';
</script>

<template>
  <div class="legal-root">
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
      <div class="legal-eyebrow">Verwerkersovereenkomst (DPA)</div>
      <h1>Data Processing Agreement</h1>
      <p class="lede">
        Voor onderwijsgegevens (PR's, broncode, feedback, scores) treedt
        jouw onderwijsinstelling op als verwerkingsverantwoordelijke en
        LEERA als verwerker. Deze pagina geeft de hoofdpunten van onze
        DPA in begrijpelijke taal. Het juridisch bindende document sluiten
        we per onderwijsinstelling separaat af.
      </p>
      <p class="meta">Laatst bijgewerkt: {{ lastUpdated }} · Status: pilot-versie, definitieve juridische review juni 2026</p>

      <!-- Status notice -->
      <div class="notice">
        <div class="notice-title">Pilot-versie</div>
        <p class="notice-body">
          De definitieve DPA wordt momenteel afgerond door een Nederlandse
          jurist en is gepland voor begin juni 2026. Voor de pilotperiode
          werken we op basis van de hoofdpunten hieronder en een korte
          schriftelijke pilot-DPA per instelling. Voor een kopie of voor
          het tekenen van een instellings-DPA, neem contact op:
          <a href="mailto:inno8techs@gmail.com">inno8techs@gmail.com</a>.
        </p>
      </div>

      <section>
        <h2>1. Partijen en rolverdeling</h2>
        <ul>
          <li><strong>Verwerkingsverantwoordelijke:</strong> de onderwijsinstelling (school, MBO, bootcamp) die LEERA gebruikt.</li>
          <li><strong>Verwerker:</strong> itec (LEERA-platform).</li>
        </ul>
        <p>
          De verwerkingsverantwoordelijke bepaalt het doel en de middelen
          van de verwerking. itec verwerkt persoonsgegevens uitsluitend
          op basis van schriftelijke instructies van de instelling, zoals
          vastgelegd in de overeenkomst en deze DPA.
        </p>
      </section>

      <section>
        <h2>2. Onderwerp en duur van de verwerking</h2>
        <p>
          <strong>Onderwerp:</strong> verwerking van persoonsgegevens van
          docenten, studenten en beheerders in het kader van het leveren
          van de Nakijken Copilot.
        </p>
        <p>
          <strong>Duur:</strong> voor de looptijd van de overeenkomst,
          plus 1 jaar archieftermijn (zie privacyverklaring).
        </p>
      </section>

      <section>
        <h2>3. Aard van de verwerking</h2>
        <ul>
          <li>Verzamelen van PR's en commits via GitHub-webhook</li>
          <li>Genereren van AI-feedback-concepten</li>
          <li>Vastleggen van docent-feedback en rubriekscores</li>
          <li>Berekenen en tonen van skill-metingen</li>
          <li>Versturen van transactionele e-mail (uitnodiging, instelmail)</li>
        </ul>
      </section>

      <section>
        <h2>4. Categorieën betrokkenen en gegevens</h2>
        <p><strong>Betrokkenen:</strong> studenten, docenten, schoolbeheerders.</p>
        <p><strong>Categorieën gegevens:</strong></p>
        <ul>
          <li>Identificerende gegevens (naam, e-mailadres, rol, GitHub-gebruikersnaam)</li>
          <li>Educatieve gegevens (klas, vak, lidmaatschap)</li>
          <li>Gebruikersgegenereerde inhoud (PR's, commits, broncode-snippets, feedback)</li>
          <li>Beoordelingsgegevens (rubriekscores, skill-metingen)</li>
          <li>Technische gegevens (sessietokens, foutlogs)</li>
        </ul>
        <p>
          We verwerken <strong>geen</strong> bijzondere persoonsgegevens
          (zoals gezondheid of BSN). Plaats dergelijke gegevens niet in
          PR-bodies of broncode.
        </p>
      </section>

      <section>
        <h2>5. Verplichtingen van itec als verwerker</h2>
        <ul>
          <li>Persoonsgegevens uitsluitend verwerken op schriftelijke instructie van de instelling</li>
          <li>Geheimhoudingsplicht opleggen aan medewerkers en onderaannemers</li>
          <li>Passende technische en organisatorische beveiligingsmaatregelen treffen (zie sectie 7)</li>
          <li>Hulp verlenen bij het beantwoorden van verzoeken van betrokkenen (inzage, rectificatie, verwijdering)</li>
          <li>Hulp verlenen bij DPIA's, audits en meldingen aan de Autoriteit Persoonsgegevens</li>
          <li>Datalekken binnen 48 uur melden aan de instelling</li>
          <li>Na afloop van de overeenkomst gegevens conform afspraak teruggeven of verwijderen</li>
        </ul>
      </section>

      <section>
        <h2>6. Sub-verwerkers (sub-processors)</h2>
        <p>
          De instelling geeft itec algemene toestemming om de volgende
          sub-verwerkers in te schakelen voor het leveren van de Dienst:
        </p>
        <table class="processors">
          <thead>
            <tr><th>Sub-verwerker</th><th>Doel</th><th>Locatie</th></tr>
          </thead>
          <tbody>
            <tr><td>Hostingleverancier (applicatie + database)</td><td>Draaien LEERA, opslag</td><td>EU</td></tr>
            <tr><td>Anthropic</td><td>LLM-feedback genereren</td><td>VS (SCC); EU-migratie gepland v1.1</td></tr>
            <tr><td>OpenAI (incidenteel als fallback)</td><td>LLM-feedback genereren</td><td>VS (SCC)</td></tr>
            <tr><td>Resend / SMTP-leverancier</td><td>Transactionele e-mail</td><td>EU</td></tr>
          </tbody>
        </table>
        <p>
          Wijzigingen in de lijst van sub-verwerkers melden we minimaal
          30 dagen vooraf aan de schoolbeheerder. De instelling kan binnen
          die termijn gemotiveerd bezwaar maken; in dat geval bekijken
          partijen samen een passende oplossing.
        </p>
      </section>

      <section>
        <h2>7. Beveiligingsmaatregelen</h2>
        <ul>
          <li>Versleuteling tijdens transport (TLS 1.2+)</li>
          <li>Versleuteling at-rest voor gevoelige velden en backups</li>
          <li>Wachtwoorden gehasht met moderne hash-functies (Argon2 / PBKDF2)</li>
          <li>Strikte toegangscontrole tot productiesystemen, met tweetraps-authenticatie</li>
          <li>Per-organisatie isolatie op database-niveau</li>
          <li>Logging en monitoring van toegangs- en wijzigingsactiviteit</li>
          <li>Periodieke beveiligingsreviews en patchcyclus</li>
          <li>Datalek-procedure met 48-uurs meldplicht aan de instelling</li>
        </ul>
      </section>

      <section>
        <h2>8. Internationale doorgifte</h2>
        <p>
          De LEERA-applicatie en database draaien in de EU. De huidige
          uitzondering is de aanroep naar het LLM (Anthropic / OpenAI),
          die in de VS plaatsvindt. Deze doorgifte wordt gedekt door de
          Standard Contractual Clauses (SCC's) van de Europese Commissie,
          aangevuld met aanvullende technische maatregelen (geen training
          op API-data, korte logbewaring bij Anthropic).
        </p>
        <p>
          itec werkt aan migratie naar een EU-residente LLM-route
          (AWS Bedrock, eu-central-1) in v1.1. Tot dat moment kan een
          instelling AI-feedback voor specifieke cohorten uitschakelen.
        </p>
      </section>

      <section>
        <h2>9. Audit en controle</h2>
        <p>
          De instelling heeft het recht om eens per 12 maanden, op eigen
          kosten en met inachtneming van een redelijke voorbereidingstijd,
          een audit te (laten) uitvoeren op de naleving van deze DPA. In
          plaats van een eigen audit kan itec audit-rapportages of
          beveiligingscertificeringen aanleveren wanneer beschikbaar.
        </p>
      </section>

      <section>
        <h2>10. Datalekken</h2>
        <p>
          itec meldt vermoedelijke datalekken die persoonsgegevens van
          de instelling raken zo snel mogelijk, en in elk geval binnen
          48 uur na detectie, schriftelijk aan de schoolbeheerder. De
          melding bevat de aard van de inbreuk, de getroffen categorieën
          gegevens en betrokkenen, de waarschijnlijke gevolgen en de
          getroffen of voorgenomen maatregelen.
        </p>
      </section>

      <section>
        <h2>11. Verzoeken van betrokkenen</h2>
        <p>
          Wanneer een betrokkene zich rechtstreeks tot itec wendt met een
          verzoek (inzage, rectificatie, verwijdering), stuurt itec het
          verzoek door aan de instelling en helpt waar nodig met de
          uitvoering. De instelling beslist op het verzoek.
        </p>
      </section>

      <section>
        <h2>12. Beëindiging en teruggave / verwijdering</h2>
        <p>
          Bij beëindiging van de overeenkomst geeft itec de
          persoonsgegevens, naar keuze van de instelling, terug of
          verwijdert deze, behoudens wettelijke bewaarplicht. De
          standaardroute is: 1 jaar gearchiveerd bewaren, daarna
          verwijderen. Op verzoek verwijderen we eerder.
        </p>
      </section>

      <section>
        <h2>13. Aansprakelijkheid en toepasselijk recht</h2>
        <p>
          Voor aansprakelijkheid en toepasselijk recht gelden de bepalingen
          uit de hoofdovereenkomst en de
          <router-link to="/voorwaarden">Algemene Voorwaarden</router-link>:
          Nederlands recht, bevoegde rechter Amsterdam, aansprakelijkheid
          beperkt tot één maandbedrag.
        </p>
      </section>

      <section>
        <h2>14. Contact</h2>
        <p>
          Voor vragen, audits of het tekenen van een instellingsspecifieke
          DPA: <a href="mailto:inno8techs@gmail.com">inno8techs@gmail.com</a>
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
.meta { font-size: 13px; color: var(--outline); margin-bottom: 32px; }

.notice {
  background: rgba(162, 201, 255, 0.06);
  border: 1px solid rgba(162, 201, 255, 0.20);
  border-radius: 12px; padding: 16px 20px;
  margin-bottom: 48px;
}
.notice-title {
  font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--primary); font-weight: 600; margin-bottom: 8px;
}
.notice-body { color: var(--on-surface-variant); font-size: 14px; line-height: 1.7; margin: 0; }

section { margin-bottom: 40px; }
h2 {
  font-size: 22px; line-height: 1.3; font-weight: 700;
  margin: 0 0 12px; letter-spacing: -0.01em;
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
