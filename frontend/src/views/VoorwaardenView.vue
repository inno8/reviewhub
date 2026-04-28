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
      <div class="legal-eyebrow">Algemene Voorwaarden</div>
      <h1>Voorwaarden voor het gebruik van LEERA</h1>
      <p class="lede">
        Deze voorwaarden gelden tussen <strong>Inno8</strong> (LEERA) en de
        onderwijsinstelling, opleidingsorganisatie of individuele gebruiker
        ("Klant", "jij") die zich op het LEERA-platform registreert. Door
        LEERA te gebruiken ga je akkoord met deze voorwaarden.
      </p>
      <p class="meta">Laatst bijgewerkt: {{ lastUpdated }}</p>

      <section>
        <h2>1. Definities</h2>
        <ul>
          <li><strong>Dienst:</strong> het LEERA-platform, inclusief de Nakijken Copilot, web-applicatie, API en bijbehorende documentatie.</li>
          <li><strong>Klant:</strong> de organisatie (school, MBO, bootcamp) of natuurlijke persoon die een account heeft.</li>
          <li><strong>Eindgebruiker:</strong> docent, student of beheerder die namens een Klant inlogt.</li>
          <li><strong>Cohort:</strong> een klas die als licentie-eenheid wordt beheerd.</li>
          <li><strong>Inno8:</strong> de aanbieder van LEERA.</li>
        </ul>
      </section>

      <section>
        <h2>2. Toegang en gebruik</h2>
        <p>
          Inno8 verleent de Klant een niet-exclusief, niet-overdraagbaar
          recht om de Dienst te gebruiken voor de duur van de overeenkomst,
          binnen de afgenomen cohorten.
        </p>
        <p>De Klant en Eindgebruikers verbinden zich ertoe:</p>
        <ul>
          <li>Geen toegang te delen met derden buiten de eigen instelling</li>
          <li>De Dienst niet te gebruiken voor onrechtmatige doeleinden</li>
          <li>Geen pogingen te doen de beveiliging te omzeilen of de infrastructuur te belasten</li>
          <li>Geen scraping, reverse engineering of het bouwen van een concurrerend product op basis van LEERA</li>
        </ul>
      </section>

      <section>
        <h2>3. Licentie en prijzen</h2>
        <p>
          De standaardprijs is <strong>€200 per cohort per maand</strong>,
          tenzij in een aanvullende offerte anders is afgesproken. Een
          cohort omvat één klas (typisch 20-30 studenten) en de bijbehorende
          docenten en beheerder.
        </p>
        <p>
          Pilotperiodes en proefcohorten kunnen kosteloos of tegen een
          aangepast tarief worden aangeboden; afspraken daarover staan in
          de pilot-overeenkomst tussen Inno8 en de Klant.
        </p>
        <p>
          Facturatie is per maand, vooraf, op basis van het aantal actieve
          cohorten. Betalingstermijn 30 dagen.
        </p>
      </section>

      <section>
        <h2>4. Eigendom van content</h2>
        <p>
          De broncode, PR's, commits en feedback die Eindgebruikers in
          LEERA plaatsen blijven <strong>eigendom van de Klant
          en/of de student</strong>. Inno8 heeft alleen het recht om deze
          content te verwerken voor zover nodig om de Dienst te leveren.
        </p>
        <p>
          AI-gegenereerde feedback-concepten zijn werkproducten van de
          Dienst; de docent die de feedback definitief vrijgeeft is de
          inhoudelijk verantwoordelijke. Inno8 doet geen claim op de
          uiteindelijk verzonden feedback.
        </p>
        <p>
          De LEERA-software, het ontwerp, de rubriek-engine, het
          skill-model en alle achterliggende technologie blijven eigendom
          van Inno8.
        </p>
      </section>

      <section>
        <h2>5. Beschikbaarheid (SLA)</h2>
        <p>
          Inno8 spant zich naar beste vermogen in om de Dienst beschikbaar
          te houden tijdens reguliere kantooruren in Nederland. Voor de
          pilotfase en v1.0 geldt <strong>geen formele SLA</strong>; we
          streven naar een typische beschikbaarheid van 99% per maand,
          gemeten over de webapplicatie.
        </p>
        <p>
          Geplande onderhoudsvensters worden minimaal 48 uur van tevoren
          aangekondigd. Niet-geplande storingen worden zo snel mogelijk
          hersteld; status-updates verschijnen via e-mail aan de
          schoolbeheerder.
        </p>
        <p>
          Een formele SLA met responstijden en kredietregeling kan in een
          afzonderlijke overeenkomst worden afgesproken voor klanten die
          dit nodig hebben.
        </p>
      </section>

      <section>
        <h2>6. Aansprakelijkheid</h2>
        <p>
          Inno8 is alleen aansprakelijk voor directe schade die rechtstreeks
          en aantoonbaar door Inno8 is veroorzaakt. De totale
          aansprakelijkheid van Inno8 onder deze overeenkomst is in alle
          gevallen <strong>beperkt tot het bedrag dat de Klant in de maand
          voorafgaand aan de schadeveroorzakende gebeurtenis aan Inno8
          heeft betaald</strong>.
        </p>
        <p>
          Inno8 is niet aansprakelijk voor:
        </p>
        <ul>
          <li>Indirecte schade, gevolgschade, gederfde winst of verlies van data</li>
          <li>Schade door foutieve invoer, foutief gebruik of onbevoegd gebruik door Eindgebruikers</li>
          <li>Schade door storingen bij verwerkers (LLM-leveranciers, hostingpartij, GitHub, e-mailprovider) buiten redelijke controle van Inno8</li>
          <li>Inhoudelijke beoordelingsfouten in feedback die de docent zonder eigen review heeft doorgestuurd; LEERA is een Copilot, geen vervanger van de docent</li>
        </ul>
        <p>
          Bovenstaande uitsluitingen gelden niet bij opzet of bewuste
          roekeloosheid van Inno8.
        </p>
      </section>

      <section>
        <h2>7. Beëindiging</h2>
        <p>
          Beide partijen kunnen de overeenkomst op elk moment opzeggen met
          inachtneming van een <strong>opzegtermijn van 30 dagen</strong>.
          Opzegging gaat per e-mail aan
          <a href="mailto:inno8techs@gmail.com">inno8techs@gmail.com</a>
          (of, voor opzegging door Inno8, per e-mail aan de schoolbeheerder).
        </p>
        <p>
          Bij beëindiging blijven gegevens nog 1 jaar gearchiveerd
          beschikbaar (zie privacyverklaring sectie 8). Direct verwijderen
          op verzoek is mogelijk.
        </p>
        <p>
          Inno8 kan de overeenkomst per direct beëindigen bij ernstige
          schending van deze voorwaarden door de Klant, zoals
          niet-betaling na ingebrekestelling, misbruik van de Dienst, of
          inbreuk op de beveiliging.
        </p>
      </section>

      <section>
        <h2>8. Wijzigingen</h2>
        <p>
          Inno8 kan deze voorwaarden van tijd tot tijd aanpassen. Materiële
          wijzigingen worden minimaal 30 dagen van tevoren per e-mail
          gemeld aan de schoolbeheerder. De Klant kan in dat geval binnen
          30 dagen de overeenkomst kosteloos opzeggen als de wijzigingen
          niet aanvaardbaar zijn.
        </p>
      </section>

      <section>
        <h2>9. Toepasselijk recht</h2>
        <p>
          Op deze overeenkomst is <strong>Nederlands recht</strong> van
          toepassing. Geschillen worden voorgelegd aan de bevoegde rechter
          in <strong>Amsterdam</strong>, tenzij dwingend recht een andere
          rechter aanwijst.
        </p>
      </section>

      <section>
        <h2>10. Overige bepalingen</h2>
        <ul>
          <li>Inno8 mag rechten en verplichtingen overdragen aan een opvolger; de Klant kan dat niet zonder schriftelijke toestemming.</li>
          <li>Als een bepaling van deze voorwaarden niet rechtsgeldig blijkt, blijven de overige bepalingen onverkort van kracht.</li>
          <li>Afwijkende afspraken zijn alleen geldig als ze schriftelijk zijn vastgelegd en door beide partijen zijn ondertekend.</li>
        </ul>
      </section>

      <section>
        <h2>11. Contact</h2>
        <p>
          <strong>Inno8 — LEERA</strong><br />
          Contact: <a href="mailto:inno8techs@gmail.com">inno8techs@gmail.com</a>
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
p { line-height: 1.7; color: var(--on-surface-variant); margin: 0 0 12px; font-size: 15px; }
ul { padding-left: 22px; margin: 0 0 12px; }
li { line-height: 1.7; color: var(--on-surface-variant); margin-bottom: 6px; font-size: 15px; }
strong { color: var(--on-surface); font-weight: 600; }
a { color: var(--primary); text-decoration: none; }
a:hover { text-decoration: underline; }

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
