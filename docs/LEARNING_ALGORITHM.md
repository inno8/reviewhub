# ReviewHub Learning Algorithm

## Technical Specification v1.0

---

## 1. Overview

The ReviewHub Learning Algorithm measures developer skill through **behavioral evidence** — what they actually write in code, commit after commit. It replaces the current system (which measures "absence of mistakes" starting from a perfect 100) with a Bayesian evidence-based model that starts from uncertainty and builds confidence through observation.

### Core Principles

1. **The code IS the resume.** Not self-reported answers, not certifications — what developers actually commit is the ground truth.
2. **Understanding is proven by behavior.** Fix & Learn creates a hypothesis ("developer understands X"). Future commits prove or disprove it.
3. **Expertise is not "no mistakes" — it's making the RIGHT decisions.** A junior can write bug-free simple code. An expert chooses the right abstraction, pattern, and approach for the situation.
4. **Confidence grows with evidence.** Two evaluations should not produce "Expert." The system needs data before it assigns labels.

---

## 2. Architecture: Three Measurement Layers

```
┌─────────────────────────────────────────────────────────┐
│  Layer 3: DECISION QUALITY                              │
│  "Did they choose the right approach?"                  │
│  Threading vs async? OOP vs functional?                 │
│  Right pattern for the right problem?                   │
│  ← Separates senior from junior                        │
├─────────────────────────────────────────────────────────┤
│  Layer 2: GROWTH TRAJECTORY                             │
│  "Are they getting better over time?"                   │
│  Issue repetition? Severity shifting down?              │
│  Complexity increasing? Recovery speed?                 │
│  ← Proves learning is happening                        │
├─────────────────────────────────────────────────────────┤
│  Layer 1: COMMIT QUALITY SNAPSHOT                       │
│  "How good is THIS commit?"                             │
│  Issue count, severity, density, complexity             │
│  ← Point-in-time measurement                           │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Layer 1: Commit Quality Snapshot

For every commit, we create a `SkillObservation` record per skill touched. This captures a point-in-time measurement of code quality **adjusted for complexity**.

### 3.1 Metrics Captured Per Commit

| Metric | Description | Source |
|--------|-------------|--------|
| `quality_score` | Raw LLM score for this skill (0-100) | LLM `skill_scores` |
| `complexity_factor` | How hard was the code? (0.0-1.0) | CommitClassifier |
| `issue_count` | Number of findings for this skill | Finding count |
| `severity_breakdown` | Count per severity level | FindingSkill records |
| `lines_changed` | Lines of code added/modified | Evaluation record |
| `weighted_score` | Final score = quality × complexity | Computed |

### 3.2 Complexity-Weighted Scoring

The critical insight: **simple code with no issues proves little**. A `print("hello")` with no issues is NOT evidence of expertise.

```
weighted_score = quality_score × complexity_weight

Where complexity_weight is derived from CommitClassifier:
  - simple commits  (score < 5):   complexity_weight = 0.4
  - medium commits  (score 5-15):  complexity_weight = 0.7
  - complex commits (score >= 15):  complexity_weight = 1.0
```

**Examples:**
| Developer | Code | Quality | Complexity | Weighted Score |
|-----------|------|---------|------------|----------------|
| Junior | Simple CRUD, clean | 92 | 0.4 | **36.8** |
| Junior | Complex async, messy | 45 | 1.0 | **45.0** |
| Senior | Complex distributed, clean | 88 | 1.0 | **88.0** |
| Senior | Simple utility, clean | 95 | 0.4 | **38.0** |

This means a junior writing simple clean code scores ~37, not 92. The system no longer rewards triviality.

### 3.3 Severity Impact Weights

Not all findings are equal. A critical security bug is a stronger negative signal than a style suggestion.

```python
SEVERITY_WEIGHTS = {
    'critical':   10.0,   # Fundamental gap — bugs, security holes
    'warning':     5.0,   # Code smell, potential issue
    'info':        2.0,   # Style, readability
    'suggestion':  1.0,   # Could be cleaner (barely affects score)
}
```

Issue density matters more than absolute count:

```
issue_density = total_weighted_issues / max(lines_changed, 10)

Where total_weighted_issues = sum(count × weight for each severity)
```

A commit with 2 critical issues in 20 lines is worse than 5 suggestions in 200 lines.

---

## 4. Layer 2: Growth Trajectory

Layer 2 analyzes patterns **across commits over time**. This is where we detect whether learning is actually happening.

### 4.1 Issue Repetition Detection

The most powerful signal: **does the same type of issue keep appearing?**

The existing `Pattern` model tracks this, but the new algorithm adds a lifecycle:

```
FIRST_SEEN → RECURRING → DECLINING → RESOLVED → REINFORCED

Timeline:
Commit #1:  bare_except found        → Pattern created (FIRST_SEEN)
Commit #4:  bare_except again        → frequency++ (RECURRING)
Commit #8:  bare_except again        → frequency++ (RECURRING, flagged)
Commit #12: proper exception used    → no occurrence (DECLINING)
Commit #16: proper exception used    → no occurrence (DECLINING)
Commit #20: 5 commits clean          → auto-resolve (RESOLVED)
Commit #30: proper exception in      → REINFORCED (pattern internalized)
            complex error handler
```

**Scoring impact:**
- RECURRING pattern: `-3 per occurrence` (you're not learning)
- DECLINING: `+0` (neutral — waiting for proof)
- RESOLVED: `+5 bonus` (behavioral change confirmed)
- REINFORCED: `+3 bonus` (pattern truly internalized)
- RELAPSED (resolved then reappears): `-8` (regression)

### 4.2 Severity Graduation

Track how the **distribution** of issue severities shifts over time:

```
Month 1:  critical=40%  warning=30%  info=20%  suggestion=10%
Month 2:  critical=25%  warning=35%  info=25%  suggestion=15%
Month 3:  critical=10%  warning=25%  info=35%  suggestion=30%
          ↑ Developer is GROWING — same volume, lighter severity
```

This is tracked in `GrowthSnapshot` records (weekly aggregations).

### 4.3 Complexity Progression

Track whether developers are **attempting harder work** over time:

```
Weeks 1-4:   avg_complexity = 0.35 (simple functions, templates)
Weeks 5-8:   avg_complexity = 0.55 (error handling, API design)
Weeks 9-12:  avg_complexity = 0.80 (async, patterns, architecture)
             ↑ Developer is STRETCHING — tackling harder problems
```

Complexity progression is a positive signal even if quality scores temporarily dip — struggling with harder code is better than coasting on easy code.

### 4.4 Recovery Speed

How quickly does a developer fix raised issues?

```
recovery_speed = median_time(finding.created_at → finding.fixed_at)
```

Fast recovery = engaged learner. Slow/never = disengaged or struggling.

---

## 5. Layer 3: Decision Quality

This is the highest-order measurement. It evaluates not just "is the code correct?" but "did the developer make the RIGHT architectural and design decisions?"

### 5.1 What Decision Quality Measures

| Decision Area | Junior Choice | Senior Choice |
|---------------|---------------|---------------|
| Error handling | `except: pass` | Specific exceptions, proper propagation |
| Concurrency | Sequential awaits for independent ops | `Promise.all()` / `asyncio.gather()` |
| Data structures | Array scan for lookup | Hash map for O(1) access |
| Paradigm | Force OOP everywhere | Functional for transforms, OOP for domain |
| Validation | Validate everywhere or nowhere | Validate at boundaries, trust internals |
| Abstraction | Premature abstraction or none | Right-sized, extracted when pattern appears 3+ times |

### 5.2 LLM Prompt Enhancement

The evaluation prompt includes a new section for decision quality:

```
DECISION QUALITY ASSESSMENT:
Beyond correctness, evaluate the developer's architectural choices:
1. Did they choose the right approach for this problem?
2. Would a senior engineer have made the same design decision?
3. Is there a fundamentally better approach (not just style preference)?

For each decision quality observation, include:
- "decision_quality": "appropriate" | "suboptimal" | "poor"
- "better_approach": "<what a senior would do and WHY>"
- "decision_category": "error_handling" | "concurrency" | "data_structures" |
                       "paradigm" | "validation" | "abstraction" | "performance" |
                       "security_design" | "api_design" | "testing_strategy"
```

### 5.3 Decision Quality Score

Decision quality observations feed into the skill score:

```python
DECISION_WEIGHTS = {
    'appropriate':  +5,   # Good instinct — right tool for the job
    'suboptimal':   -2,   # Works but not ideal
    'poor':         -8,   # Wrong approach — fundamental misunderstanding
}
```

This is the signal that separates a developer who writes "correct code" from one who writes "the right code."

---

## 6. The Behavioral Proof System

This is the algorithm's core innovation. It connects Fix & Learn to future commits to verify whether understanding is real.

### 6.1 The Proof Lifecycle

```
┌──────────┐     ┌──────────────┐     ┌─────────────┐
│  TEACH   │────▶│  WATCH       │────▶│  PROVE      │
│          │     │              │     │             │
│ Fix&Learn│     │ Monitor next │     │ Same issue  │
│ explains │     │ commits for  │     │ type found, │
│ concept  │     │ similar code │     │ handled     │
│          │     │ patterns     │     │ correctly   │
│ Status:  │     │ Status:      │     │ Status:     │
│ TAUGHT   │     │ PENDING      │     │ PROVEN      │
└──────────┘     └──────────────┘     └─────────────┘
                        │                    │
                        ▼ (same mistake)     ▼ (3+ correct)
                 ┌──────────────┐     ┌─────────────┐
                 │  RELAPSE     │     │ REINFORCED  │
                 │              │     │             │
                 │ Score drops  │     │ Pattern     │
                 │ Concept re-  │     │ fully       │
                 │ queued for   │     │ internalized│
                 │ deeper teach │     │             │
                 └──────────────┘     └─────────────┘
```

### 6.2 How Proofs Are Detected

When a new evaluation comes in, the system checks all `PENDING` LearningProofs for that user:

```python
# Pseudocode for proof detection
for proof in user.pending_learning_proofs():
    skill = proof.skill
    issue_type = proof.issue_type  # e.g., "bare_except", "sql_injection"

    # Check if this commit touches the same skill area
    if skill in current_evaluation.skills_touched:
        # Check if the same issue type appears
        if issue_type in current_evaluation.issue_types:
            proof.status = 'RELAPSED'
            proof.relapse_commit = commit_sha
            # Score penalty: understanding was superficial
        else:
            # Similar code context, no issue = potential proof
            proof.proof_evidence_count += 1
            if proof.proof_evidence_count >= 2:
                proof.status = 'PROVEN'
                proof.proven_at = now()
                proof.proof_commit = commit_sha
                # Score bonus: behavioral change confirmed
```

### 6.3 Scoring Impact

| Event | Score Impact | Rationale |
|-------|-------------|-----------|
| Fix & Learn "got_it" | +2 | Claimed understanding (unverified) |
| Fix & Learn "partial" | +1 | Partial understanding |
| PROVEN (behavioral proof) | +8 | Real evidence of learning |
| REINFORCED (3+ proofs) | +3 bonus | Pattern fully internalized |
| RELAPSED | -5 | Understanding was superficial |
| RELAPSED after PROVEN | -10 | Regression from confirmed skill |

**The key insight:** Fix & Learn's self-reported answer is worth 20% of the signal. The behavioral proof from future commits is worth 80%.

---

## 7. Bayesian Skill Rating Model

### 7.1 Why Bayesian?

The current system starts at 100 (optimistic) and deducts. This means everyone starts as an "Expert" and degrades. The Bayesian approach starts at **50 (uncertain)** and moves toward the developer's true skill level based on evidence.

### 7.2 The Update Formula

```python
def update_skill_score(current_score, confidence, observation):
    """
    Bayesian-inspired skill score update.

    Args:
        current_score: Current skill score (0-100)
        confidence: How confident we are in the score (0.0-1.0)
        observation: New SkillObservation data
    """
    # Calculate observation signal strength
    weighted_score = observation.quality_score * observation.complexity_weight
    severity_penalty = observation.issue_density * severity_factor
    signal = weighted_score - severity_penalty

    # Learning rate decreases as confidence grows
    # High confidence = score is stable, hard to move
    # Low confidence = score is volatile, easy to move
    learning_rate = max(0.05, 0.35 * (1 - confidence))

    # Update score
    new_score = current_score * (1 - learning_rate) + signal * learning_rate
    new_score = clamp(new_score, 0, 100)

    # Update confidence (grows with each observation)
    # Complexity-weighted: complex code gives more confidence
    confidence_gain = 0.02 * observation.complexity_weight
    new_confidence = min(1.0, confidence + confidence_gain)

    return new_score, new_confidence
```

### 7.3 Learning Rate Behavior

| Confidence | Learning Rate | Behavior |
|------------|---------------|----------|
| 0.0 (new) | 0.35 | Scores move rapidly — calibrating |
| 0.2 | 0.28 | Still adjusting quickly |
| 0.5 | 0.175 | Settling into true level |
| 0.8 | 0.07 | Stable — requires consistent evidence to change |
| 1.0 | 0.05 | Very stable — only sustained patterns move the score |

### 7.4 Bonus/Penalty Events

Beyond commit observations, these events modify the score:

```python
# Behavioral proof bonuses
PROOF_PROVEN:      +8 × learning_rate
PROOF_REINFORCED:  +3 × learning_rate
PROOF_RELAPSED:    -5 × learning_rate

# Pattern resolution bonuses
PATTERN_RESOLVED:  +5 × learning_rate
PATTERN_RELAPSED:  -8 × learning_rate

# Fix & Learn (small — claims, not proof)
FIX_LEARN_GOT_IT:  +2 × learning_rate
FIX_LEARN_PARTIAL: +1 × learning_rate
```

---

## 8. Confidence System

### 8.1 Confidence Levels

Confidence determines what labels we show to the user. We do NOT show "Expert" when we have 2 data points.

| Confidence | Observations | Display Label | UI Treatment |
|------------|-------------|---------------|-------------|
| 0.0-0.15 | 1-3 | "Preliminary" | Greyed out, dotted border |
| 0.15-0.40 | 4-10 | "Developing" | Partial opacity |
| 0.40-0.70 | 11-25 | "Established" | Normal display |
| 0.70-1.0 | 25+ | "Verified" | Full confidence, badge |

### 8.2 Per-Skill Confidence

Confidence is tracked per skill, not globally. A developer might have:
- `error_handling`: confidence 0.85 (50 relevant commits) → "Verified"
- `security`: confidence 0.12 (2 relevant commits) → "Preliminary"
- `testing`: confidence 0.0 (never touched) → Not shown

### 8.3 Display Rules

- **Confidence < 0.15**: Show score but NO level label. Show "Not enough data" instead of "Expert."
- **Confidence 0.15-0.40**: Show score with level label + "(developing)" qualifier.
- **Confidence > 0.40**: Show score with level label, no qualifier.
- **Never touched**: Don't show the skill at all (current behavior, already correct).

---

## 9. Level Mapping

### 9.1 Individual Skill Levels

Based on the Bayesian score (which is complexity-weighted), skill levels map to:

| Level | Score Range | What It Means (proven by behavior) |
|-------|-------------|-------------------------------------|
| **Novice** | 0-15 | Frequent critical issues, doesn't handle basic patterns |
| **Beginner** | 15-30 | Handles simple cases, repeats mistakes, needs guidance |
| **Competent** | 30-50 | Standard scenarios handled, starting to see patterns |
| **Proficient** | 50-70 | Anticipates problems, good patterns, growing complexity |
| **Expert** | 70-85 | Right tool for every job, teaches through code quality |
| **Master** | 85-100 | Exceptional across complex code — requires massive evidence |

Note: With complexity-weighted scoring, these ranges are meaningful. A score of 70 means consistently high-quality code on complex problems, not just "no issues on simple code."

### 9.2 Overall Developer Level

The composite developer level uses a weighted formula across all skills:

```python
def calculate_overall_level(user):
    """
    Composite level from all skill observations.
    Only skills with sufficient confidence contribute.
    """
    weights = {
        'code_quality':    0.25,  # Core skill — always relevant
        'improvement':     0.20,  # Growth trajectory
        'decision_quality': 0.15, # Architectural choices
        'fix_rate':        0.10,  # Engagement with feedback
        'behavioral_proof': 0.15, # Proven understanding (not just claims)
        'complexity_growth': 0.10,# Tackling harder problems
        'breadth':         0.05,  # Range of skills demonstrated
    }
```

### 9.3 Composite Level Thresholds

| Level | Composite Score | Requirements |
|-------|----------------|--------------|
| **Novice** | 0-15 | Any |
| **Beginner** | 15-30 | >= 5 evaluations |
| **Competent** | 30-50 | >= 10 evaluations, >= 3 skills with data |
| **Proficient** | 50-70 | >= 20 evaluations, >= 5 skills, some proven concepts |
| **Expert** | 70-85 | >= 30 evaluations, proven concepts > relapsed, complexity growth |
| **Master** | 85-100 | >= 50 evaluations, broad skill coverage, sustained excellence |

A developer cannot be labeled "Expert" without sufficient evidence, regardless of how high their scores are.

---

## 10. Data Models

### 10.1 New Models

#### SkillObservation
One record per commit per skill touched. The raw evidence.

```python
class SkillObservation(models.Model):
    """Per-commit, per-skill quality snapshot — the raw evidence."""
    user = ForeignKey(User)
    project = ForeignKey(Project)
    evaluation = ForeignKey(Evaluation)
    skill = ForeignKey(Skill)
    commit_sha = CharField(max_length=40)

    # Quality measurement
    quality_score = FloatField()          # Raw LLM score (0-100)
    complexity_weight = FloatField()      # From CommitClassifier (0.4-1.0)
    weighted_score = FloatField()         # quality × complexity
    lines_changed = PositiveIntegerField()

    # Issue breakdown
    issue_count = PositiveIntegerField(default=0)
    critical_count = PositiveIntegerField(default=0)
    warning_count = PositiveIntegerField(default=0)
    info_count = PositiveIntegerField(default=0)
    suggestion_count = PositiveIntegerField(default=0)
    issue_density = FloatField(default=0) # weighted_issues / lines

    # Decision quality (Layer 3)
    decision_appropriate = PositiveIntegerField(default=0)
    decision_suboptimal = PositiveIntegerField(default=0)
    decision_poor = PositiveIntegerField(default=0)

    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'skill_observations'
        indexes = [
            Index(fields=['user', 'skill', 'created_at']),
            Index(fields=['user', 'project', 'created_at']),
            Index(fields=['evaluation']),
        ]
```

#### LearningProof
Connects Fix & Learn concepts to future behavioral evidence.

```python
class LearningProof(models.Model):
    """Tracks whether Fix & Learn understanding is proven by future behavior."""

    class Status(models.TextChoices):
        TAUGHT = 'taught', 'Taught'
        PENDING = 'pending', 'Pending Proof'
        PROVEN = 'proven', 'Proven'
        REINFORCED = 'reinforced', 'Reinforced'
        RELAPSED = 'relapsed', 'Relapsed'

    user = ForeignKey(User)
    skill = ForeignKey(Skill)
    finding = ForeignKey(Finding)        # Original finding that was taught
    issue_type = CharField(max_length=200) # e.g., "bare_except", "sql_injection"

    # Teaching context
    taught_at = DateTimeField()
    understanding_level = CharField()    # got_it / partial / not_yet
    concept_summary = TextField()        # What was explained

    # Proof tracking
    status = CharField(choices=Status.choices, default='taught')
    proof_evidence_count = PositiveIntegerField(default=0) # Commits where concept applied correctly
    proof_commit = CharField(max_length=40, blank=True)    # Commit that proved understanding
    proven_at = DateTimeField(null=True)
    relapse_commit = CharField(max_length=40, blank=True)  # Commit where mistake repeated
    relapsed_at = DateTimeField(null=True)
    score_impact_applied = FloatField(default=0)           # Total score impact from this proof

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        db_table = 'learning_proofs'
        indexes = [
            Index(fields=['user', 'status']),
            Index(fields=['user', 'skill', 'issue_type']),
        ]
```

#### GrowthSnapshot
Weekly aggregations for timeline and trend analysis.

```python
class GrowthSnapshot(models.Model):
    """Weekly growth snapshot for timeline visualization."""
    user = ForeignKey(User)
    project = ForeignKey(Project, null=True)  # null = cross-project
    week_start = DateField()                  # Monday of the week

    # Score summary
    avg_weighted_score = FloatField()
    avg_complexity = FloatField()
    evaluation_count = PositiveIntegerField()

    # Severity distribution (as percentages)
    pct_critical = FloatField(default=0)
    pct_warning = FloatField(default=0)
    pct_info = FloatField(default=0)
    pct_suggestion = FloatField(default=0)

    # Growth signals
    patterns_resolved = PositiveIntegerField(default=0)
    patterns_relapsed = PositiveIntegerField(default=0)
    concepts_proven = PositiveIntegerField(default=0)
    concepts_relapsed = PositiveIntegerField(default=0)
    new_skills_touched = PositiveIntegerField(default=0)

    # Computed
    growth_velocity = FloatField(default=0)  # Score change rate

    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'growth_snapshots'
        unique_together = ['user', 'project', 'week_start']
        indexes = [
            Index(fields=['user', 'week_start']),
        ]
```

### 10.2 Modified Models

#### SkillMetric (enhanced)

Add to existing fields:

```python
# New fields
confidence = FloatField(default=0.0)          # 0.0-1.0, Bayesian confidence
observation_count = PositiveIntegerField(default=0)  # Total observations for this skill
bayesian_score = FloatField(default=50.0)     # New Bayesian score (replaces score starting at 100)
proven_concepts = PositiveIntegerField(default=0)
relapsed_concepts = PositiveIntegerField(default=0)
```

#### Evaluation (enhanced)

The `commit_complexity` and `complexity_score` fields already exist. No changes needed.

---

## 11. Integration Points

### 11.1 Evaluation Ingestion (InternalEvaluationCreateView)

After creating findings and finding_skills:

```
1. Create SkillObservation records (one per skill touched)
   - Compute weighted_score = quality × complexity_weight
   - Compute issue_density
   - Record decision quality counts

2. Update SkillMetric with Bayesian formula
   - Use weighted_score as signal (not raw quality_score)
   - Update confidence based on complexity

3. Check LearningProofs for this user
   - For each PENDING proof matching a skill in this commit:
     - If same issue_type appears: mark RELAPSED
     - If skill touched, no issue: increment proof_evidence_count
     - If proof_evidence_count >= 2: mark PROVEN

4. Update Patterns (existing logic, enhanced)
   - Check for RESOLVED patterns relapsing

5. Update GrowthSnapshot (weekly aggregation)
   - Upsert current week's snapshot

6. Recalculate DeveloperProfile with new algorithm
```

### 11.2 Fix & Learn (CheckUnderstandingView)

After LLM evaluates understanding:

```
1. Create LearningProof record
   - status = 'pending' (if got_it or partial)
   - issue_type = pattern_key from finding
   - concept_summary = LLM explanation

2. Apply small immediate score bonus (+2 or +1)
   - The real impact comes later from behavioral proof
```

### 11.3 LLM Evaluation Prompt

Add to EVALUATION_PROMPT:

```
DECISION QUALITY (required for each finding):
In addition to correctness issues, evaluate the developer's design decisions:

For each finding, add:
  "decision_quality": "appropriate" | "suboptimal" | "poor"

Also add a separate "decision_observations" array for approach-level feedback:
[
    {
        "observation": "<what decision was made>",
        "quality": "appropriate" | "suboptimal" | "poor",
        "better_approach": "<what a senior would do differently>",
        "category": "<decision category>",
        "skills_affected": ["<skill_slug>"]
    }
]

Decision categories: error_handling, concurrency, data_structures,
paradigm, validation, abstraction, performance, security_design,
api_design, testing_strategy

Judge decisions relative to the context — a simple script doesn't need
enterprise patterns. Penalize over-engineering as "suboptimal" too.
```

---

## 12. The Developer Journey

What this algorithm enables — a complete view of a developer's growth:

```
Timeline: ─────────────────────────────────────────────────▶
           First commit                              Today

Score:     ╭─╮   ╭──╮        ╭────────────╮   ╭─────────
           │ │   │  │  ╭──╮  │            │   │
        ───╯ ╰───╯  ╰──╯  ╰──╯            ╰───╯

Level:     Novice → Beginner ──→ Competent ────→ Proficient
                                                  ▲
Milestones: ● First PR   ● First fix   ● Pattern     ● Complexity
                                        internalized   jump

Confidence:  ░░░░░░░░  ▒▒▒▒▒▒▒▒  ▓▓▓▓▓▓▓▓  ████████
             Preliminary Developing Established Verified

Proven concepts: 12/18 taught (67% behavioral proof rate)
Active patterns:  3 still recurring
Strongest: Backend (72), Security (68)
Weakest:   Testing (31), Frontend (28)
Recommendation: "Clean Code" ch.7-9, Testing exercises B
```

---

## 13. Migration Strategy

### Phase 1: Data Models + Scoring Engine
1. Add new models (SkillObservation, LearningProof, GrowthSnapshot)
2. Add new fields to SkillMetric (confidence, bayesian_score, observation_count)
3. Implement new scoring functions
4. Update InternalEvaluationCreateView

### Phase 2: Behavioral Proof System
1. Create LearningProof on Fix & Learn completion
2. Check proofs during evaluation ingestion
3. Apply proof bonuses/penalties

### Phase 3: Growth Tracking
1. Generate GrowthSnapshot on each evaluation
2. API endpoints for timeline data
3. Frontend timeline visualization

### Phase 4: Decision Quality
1. Update EVALUATION_PROMPT with decision quality section
2. Parse decision observations from LLM response
3. Store in SkillObservation
4. Factor into skill scoring

### Backward Compatibility
- Keep existing `score` field on SkillMetric (for backward compat)
- New `bayesian_score` field is the source of truth
- Frontend reads `bayesian_score` when available, falls back to `score`
- Existing evaluations can be replayed to generate SkillObservation records (optional)

---

## 14. API Changes

### New Endpoints

```
GET /api/skills/timeline/<user_id>/
  → GrowthSnapshot[] for timeline chart

GET /api/skills/proofs/<user_id>/
  → LearningProof[] with status breakdown

GET /api/skills/observations/<user_id>/?skill=<slug>
  → SkillObservation[] for detailed per-commit view
```

### Modified Endpoints

```
GET /api/skills/performance/<user_id>/
  → Add: confidence per skill, proven/relapsed counts,
         behavioral_proof_rate, complexity_progression

GET /api/skills/dashboard/skills/
  → Use bayesian_score, show confidence level,
    hide skills below confidence threshold

GET /api/skills/user/<user_id>/
  → Include confidence, observation_count per skill
```

---

## 15. Constants & Configuration

```python
# Complexity weights (from CommitClassifier level)
COMPLEXITY_WEIGHTS = {
    'simple': 0.4,
    'medium': 0.7,
    'complex': 1.0,
}

# Severity impact on score
SEVERITY_WEIGHTS = {
    'critical': 10.0,
    'warning': 5.0,
    'info': 2.0,
    'suggestion': 1.0,
}

# Bayesian scoring
INITIAL_SCORE = 50.0
INITIAL_CONFIDENCE = 0.0
MAX_LEARNING_RATE = 0.35
MIN_LEARNING_RATE = 0.05
CONFIDENCE_GAIN_PER_OBSERVATION = 0.02

# Behavioral proof
PROOF_REQUIRED_EVIDENCE = 2      # Commits needed to mark PROVEN
PROOF_SCORE_BONUS = 8.0
REINFORCED_BONUS = 3.0
RELAPSE_PENALTY = -5.0
RELAPSE_AFTER_PROVEN_PENALTY = -10.0
FIX_LEARN_GOT_IT_BONUS = 2.0
FIX_LEARN_PARTIAL_BONUS = 1.0

# Pattern scoring
PATTERN_RESOLVED_BONUS = 5.0
PATTERN_RELAPSED_PENALTY = -8.0
PATTERN_RECURRING_PENALTY = -3.0

# Confidence thresholds
CONFIDENCE_PRELIMINARY = 0.15
CONFIDENCE_DEVELOPING = 0.40
CONFIDENCE_ESTABLISHED = 0.70
CONFIDENCE_VERIFIED = 0.85

# Level thresholds
LEVEL_THRESHOLDS = {
    'master': 85,
    'expert': 70,
    'proficient': 50,
    'competent': 30,
    'beginner': 15,
    'novice': 0,
}

# Minimum evaluations for level labels
MIN_EVALS_FOR_LEVEL = {
    'master': 50,
    'expert': 30,
    'proficient': 20,
    'competent': 10,
    'beginner': 5,
    'novice': 0,
}
```
