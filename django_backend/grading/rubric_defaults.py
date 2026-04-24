"""
Default rubric definition(s) used across seed commands and data migrations.

Single source of truth for the Crebo 25604 (MBO-4 Software Developer) aligned
rubric that Leera ships with. Every criterion is mapped to an official
werkproces so teachers immediately recognise the vocational education
framework.

Every level carries both a short `label` (standard MBO beheersingsniveau
naming — identical across all criteria, so the UI dropdown can render
"{score} — {label}" without truncation) and the long Dutch `description`
(rendered once below the dropdown).

Importers:
  - grading.management.commands.seed_e2e_grading
  - grading.management.commands.seed_dogfood_cohort
  - grading.management.commands.migrate_rubrics_to_crebo
  - grading.management.commands.add_level_labels_to_rubrics
"""
from __future__ import annotations


# Standard MBO-4 beheersingsniveau labels — same 4 labels across every
# criterion. Kept here as a module-level constant so the
# add_level_labels_to_rubrics migration can reuse it on stored rubrics.
LEVEL_LABELS: dict[int, str] = {
    1: "Nog niet beheerst",
    2: "Gedeeltelijk beheerst",
    3: "Op opleidingsniveau",
    4: "Boven niveau",
}


CREBO_RUBRIC_CRITERIA = [
    {
        "id": "code_ontwerp",
        "name": "Code-ontwerp",
        "kerntaak": "B1-K1-W2",
        "kerntaak_label": "Ontwerpt software",
        "weight": 15,
        "levels": [
            {"score": 1, "label": "Nog niet beheerst", "description": "Geen duidelijke structuur; alles in één functie of bestand."},
            {"score": 2, "label": "Gedeeltelijk beheerst", "description": "Basis-structuur, maar abstractie ontbreekt; veel herhaling."},
            {"score": 3, "label": "Op opleidingsniveau", "description": "Logische opbouw, duidelijke scheiding van verantwoordelijkheden."},
            {"score": 4, "label": "Boven niveau", "description": "Doordacht ontwerp; herbruikbaar, uitbreidbaar, minimale coupling."},
        ],
    },
    {
        "id": "code_kwaliteit",
        "name": "Code-kwaliteit",
        "kerntaak": "B1-K1-W3",
        "kerntaak_label": "Realiseert (onderdelen van) software",
        "weight": 20,
        "levels": [
            {"score": 1, "label": "Nog niet beheerst", "description": "Moeilijk leesbaar; onduidelijke namen; geen foutafhandeling."},
            {"score": 2, "label": "Gedeeltelijk beheerst", "description": "Werkt, maar inconsistent; cryptische namen; fouten worden geslikt."},
            {"score": 3, "label": "Op opleidingsniveau", "description": "Leesbaar, idiomatic, fouten worden met context afgehandeld."},
            {"score": 4, "label": "Boven niveau", "description": "Professioneel niveau; zelf-documenterend, robuust, edge cases afgedekt."},
        ],
    },
    {
        "id": "veiligheid",
        "name": "Veiligheid",
        "kerntaak": "B1-K1-W3",
        "kerntaak_sub": "veiligheid",
        "kerntaak_label": "Realiseert software (sub: veiligheid)",
        "weight": 20,
        "levels": [
            {"score": 1, "label": "Nog niet beheerst", "description": "Duidelijke kwetsbaarheden: hardcoded secrets, SQL-injectie, geen input-validatie."},
            {"score": 2, "label": "Gedeeltelijk beheerst", "description": "Bewust van veiligheid, maar met gaten; inconsistente input-checks."},
            {"score": 3, "label": "Op opleidingsniveau", "description": "Standaard praktijken: parameterized queries, input-validatie, geen secrets in code."},
            {"score": 4, "label": "Boven niveau", "description": "Threat-modeled, least-privilege, defense in depth; edge cases doordacht."},
        ],
    },
    {
        "id": "testen",
        "name": "Testen",
        "kerntaak": "B1-K1-W4",
        "kerntaak_label": "Test software",
        "weight": 20,
        "levels": [
            {"score": 1, "label": "Nog niet beheerst", "description": "Geen tests aanwezig."},
            {"score": 2, "label": "Gedeeltelijk beheerst", "description": "Alleen happy-path tests; edge cases en errors ongetest."},
            {"score": 3, "label": "Op opleidingsniveau", "description": "Happy- en error-paden getest; redelijke dekking."},
            {"score": 4, "label": "Boven niveau", "description": "Grondige dekking incl. edge cases en regressies; tests zijn zelf leesbaar."},
        ],
    },
    {
        "id": "verbetering",
        "name": "Verbetering",
        "kerntaak": "B1-K1-W5",
        "kerntaak_label": "Doet verbetervoorstellen voor de software",
        "weight": 10,
        "levels": [
            {"score": 1, "label": "Nog niet beheerst", "description": "Geen reactie op eerdere feedback; TODOs blijven openstaan."},
            {"score": 2, "label": "Gedeeltelijk beheerst", "description": "Past feedback deels toe, zonder onderliggende patronen te herkennen."},
            {"score": 3, "label": "Op opleidingsniveau", "description": "Verwerkt feedback consistent; doet kleine verbeteringen uit eigen initiatief."},
            {"score": 4, "label": "Boven niveau", "description": "Refactored proactief; stelt verbeteringen voor die verder gaan dan de opdracht."},
        ],
    },
    {
        "id": "samenwerking",
        "name": "Samenwerking",
        "kerntaak": "B1-K2-W1+W3",
        "kerntaak_label": "Voert overleg & reflecteert op het werk",
        "weight": 15,
        "levels": [
            {"score": 1, "label": "Nog niet beheerst", "description": "Commit-messages onduidelijk; PR-beschrijving ontbreekt; geen reactie op review."},
            {"score": 2, "label": "Gedeeltelijk beheerst", "description": "Basis-beschrijving; reageert op reviews maar kort of defensief."},
            {"score": 3, "label": "Op opleidingsniveau", "description": "Duidelijke commit-messages, PR-beschrijving toont context, constructieve reactie."},
            {"score": 4, "label": "Boven niveau", "description": "PR-beschrijving documenteert keuzes en trade-offs; reflecteert zelfstandig."},
        ],
    },
]


# A canonical criterion ID is considered "old-shape" (pre-Crebo) if it matches
# one of these slugs. Used by migrate_rubrics_to_crebo to detect rubrics that
# still carry the English 4-criterion structure.
LEGACY_CRITERION_IDS = frozenset({"readability", "error_handling", "security", "testing"})
