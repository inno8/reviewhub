<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import SkillRadarChart from '@/components/charts/SkillRadarChart.vue';
import ProgressChart from '@/components/charts/ProgressChart.vue';
import RecentFindings from '@/components/dashboard/RecentFindings.vue';
import CategoryRadarChart from '@/components/charts/CategoryRadarChart.vue';
import RecommendationsWidget from '@/components/skills/RecommendationsWidget.vue';
import SkillBreakdownDialog from '@/components/skills/SkillBreakdownDialog.vue';
import { api } from '@/composables/useApi';
import { useProjectsStore } from '@/stores/projects';
import { useAuthStore } from '@/stores/auth';

// Skill breakdown dialog state
const breakdownOpen = ref(false);
const breakdownSkillId = ref<number | null>(null);
function openSkillBreakdown(id: number) {
  breakdownSkillId.value = id;
  breakdownOpen.value = true;
}

interface UserStat {
  id: number; username: string; email: string; display_name: string;
  total_evaluations: number; total_findings: number; avg_score: number;
  categories: { id: number; name: string }[];
}

const route = useRoute();
const projectsStore = useProjectsStore();
const authStore = useAuthStore();

// Admin user selection
const adminUsers = ref<UserStat[]>([]);
const adminLoading = ref(false);
const adminSearch = ref('');
const adminCategories = ref<{ id: number; name: string }[]>([]);
const adminCategoryFilter = ref<number | null>(null);
const adminProjectFilter = ref<number | null>(null);
const selectedUserId = ref<number | null>(null);

// Dashboard data
const loading = ref(false);
const overview = ref<any>(null);
const categoryScores = ref<any[]>([]);
const progressData = ref<any[]>([]);
const recentFindings = ref<any[]>([]);
const skillCategories = ref<any[]>([]);

// Pattern tracker
const patterns = ref<any[]>([]);
const patternsLoading = ref(false);
const showResolved = ref(false);
const resolvingId = ref<number | null>(null);

const showUserList = computed(() => authStore.isAdmin && !selectedUserId.value);

onMounted(async () => {
  await projectsStore.fetchProjects();
  
  // Check for ?user= query param
  const queryUser = route.query.user;
  if (queryUser) {
    selectedUserId.value = Number(queryUser);
  }

  // For developers: auto-select own ID. For admin: show user list first
  if (!selectedUserId.value && !authStore.isAdmin) {
    selectedUserId.value = authStore.user?.id ?? null;
  }

  if (authStore.isAdmin) {
    await loadAdminUsers();
  }

  if (selectedUserId.value) await loadDashboardData();
});

watch(() => projectsStore.selectedProjectId, async () => {
  if (selectedUserId.value) await loadDashboardData();
});

watch([adminSearch, adminCategoryFilter, adminProjectFilter], () => loadAdminUsers());

async function loadAdminUsers() {
  adminLoading.value = true;
  try {
    const [usersRes, catsRes] = await Promise.all([
      api.users.adminStats({
        search: adminSearch.value || undefined,
        category: adminCategoryFilter.value || undefined,
        project: adminProjectFilter.value || undefined,
      } as any),
      api.categories.list(),
    ]);
    adminUsers.value = usersRes.data;
    adminCategories.value = (catsRes.data.results || catsRes.data || []);
  } catch { /* ignore */ } finally { adminLoading.value = false; }
}

function selectUser(userId: number) {
  selectedUserId.value = userId;
  loadDashboardData();
}

function backToList() {
  selectedUserId.value = null;
  overview.value = null;
  skillCategories.value = [];
}

async function loadDashboardData() {
  if (!selectedUserId.value) return;
  loading.value = true;
  try {
    const projectId = projectsStore.selectedProjectId ?? undefined;
    const userId = authStore.isAdmin ? selectedUserId.value : undefined;
    const [overviewRes, skillsRes, progressRes, recentRes] = await Promise.all([
      api.dashboard.overview(projectId, userId),
      api.dashboard.skills(projectId, userId),
      api.dashboard.progress(projectId, 8, userId),
      api.dashboard.recent(projectId, 10, userId),
    ]);
    overview.value = overviewRes.data;
    categoryScores.value = skillsRes.data;
    progressData.value = progressRes.data;
    recentFindings.value = recentRes.data;

    const catRes = await api.skills.user(
      selectedUserId.value,
      projectId != null ? projectId : undefined,
    );
    skillCategories.value = catRes.data.categories || [];
  } catch (e) { console.error(e); } finally { loading.value = false; }

  // Load patterns in parallel (non-blocking)
  loadPatterns();
}

async function loadPatterns() {
  patternsLoading.value = true;
  try {
    const projectId = projectsStore.selectedProjectId ?? undefined;
    const { data } = await api.evaluations.patterns({ projectId });
    patterns.value = Array.isArray(data) ? data : (data.results || []);
  } catch { /* ignore */ } finally { patternsLoading.value = false; }
}

// Pattern info dialog
const patternInfoOpen = ref(false);
const patternInfoData = ref<{ name: string; description: string } | null>(null);

const PATTERN_DESCRIPTIONS: Record<string, string> = {
  'clean_code': 'Clean Code refers to writing code that is easy to read, understand, and maintain. It includes consistent naming conventions, proper formatting, avoiding unnecessary complexity, and following language-specific style guides (e.g. PEP 8 for Python). Clean code reduces bugs because other developers (and future you) can understand what the code does at a glance.',
  'code_structure': 'Code Structure is about organizing your code into logical, modular pieces. Good structure means separating concerns, using functions for reusable logic, keeping files focused on a single responsibility, and avoiding deeply nested code. Well-structured code is easier to test, debug, and extend.',
  'dry_principle': 'DRY (Don\'t Repeat Yourself) means avoiding code duplication. When you see the same logic repeated in multiple places, extract it into a shared function or module. Duplicated code means every bug fix or change must be applied in multiple places, increasing the risk of inconsistency and bugs.',
  'input_validation': 'Input Validation means checking and sanitizing all data that comes from external sources (user input, API requests, file uploads) before using it. Without validation, your application is vulnerable to injection attacks (SQL injection, XSS), crashes from unexpected data types, and security breaches.',
  'error_handling': 'Error Handling means anticipating what can go wrong and writing code to handle those situations gracefully. This includes using try/except blocks, validating return values, handling edge cases (empty lists, null values), and providing meaningful error messages instead of crashing silently.',
  'edge_cases': 'Edge Cases are unusual or extreme inputs that your code might not handle correctly — empty strings, zero values, very large numbers, null/undefined values, or unexpected data types. Testing for edge cases prevents bugs that only appear in production with real-world data.',
  'html_semantics': 'HTML Semantics means using the right HTML elements for their intended purpose — header, nav, main, article, button instead of generic div tags with click handlers. Semantic HTML improves accessibility (screen readers), SEO, and makes code more readable and maintainable.',
  'accessibility': 'Accessibility (a11y) means making your web application usable by everyone, including people with disabilities. This includes adding alt text to images, using proper heading hierarchy, ensuring keyboard navigation works, providing ARIA labels for interactive elements, and maintaining sufficient color contrast.',
  'css_organization': 'CSS Organization means keeping your stylesheets clean, avoiding inline styles, using consistent naming conventions (BEM, utility classes), and eliminating duplicate rules. Well-organized CSS uses variables for colors/spacing, groups related styles, and avoids specificity wars.',
  'responsive_design': 'Responsive Design means building layouts that adapt to different screen sizes — mobile, tablet, and desktop. This involves using relative units (rem, %), media queries, flexbox/grid layouts, and testing on multiple devices. A responsive site provides a good experience regardless of screen size.',
  'xss_csrf_prevention': 'XSS (Cross-Site Scripting) prevention means never inserting user-provided data into HTML without sanitizing it. Using innerHTML with user data allows attackers to inject malicious scripts. Use textContent, template literals with proper escaping, or sanitization libraries instead.',
  'database_queries': 'Secure Database Queries means using parameterized queries (prepared statements) instead of string concatenation to build SQL. String concatenation allows SQL injection attacks where an attacker can modify your query to access, modify, or delete data they shouldn\'t have access to.',
  'secrets_management': 'Secrets Management means never hardcoding passwords, API keys, tokens, or other sensitive values directly in your source code. Instead, use environment variables, secret managers (like AWS Secrets Manager), or .env files (excluded from git). Hardcoded secrets in git history can be found and exploited by anyone.',
  'comments_docs': 'Comments & Documentation means writing clear inline comments for complex logic, docstrings for functions explaining parameters and return values, and maintaining README files. Good documentation helps others (and future you) understand the codebase without reading every line of code.',
  'solid_principles': 'SOLID Principles are five design principles for writing maintainable object-oriented code: Single Responsibility (one class = one job), Open/Closed (open for extension, closed for modification), Liskov Substitution, Interface Segregation, and Dependency Inversion. Following SOLID reduces coupling and makes code easier to change.',
  'api_design': 'API Design means creating consistent, intuitive REST endpoints with proper HTTP methods (GET for reading, POST for creating, etc.), meaningful status codes, clear error responses, versioning, and proper authentication. A well-designed API is easy for other developers to use without reading extensive documentation.',
};

interface CodeExample { bad: string; good: string; language: string; }

const PATTERN_EXAMPLES: Record<string, CodeExample> = {
  'clean_code': {
    language: 'python',
    bad: `# Bad: unclear names, no spacing
def p(d,t):
    r=d*t/100
    return d+r

x=p(1000,5)
print(x)`,
    good: `# Good: descriptive names, clear logic
def calculate_total_with_tax(price, tax_rate):
    tax_amount = price * tax_rate / 100
    return price + tax_amount

total = calculate_total_with_tax(1000, 5)
print(f"Total: {total}")`,
  },
  'input_validation': {
    language: 'python',
    bad: `# Bad: SQL injection vulnerability
def get_user(name):
    query = "SELECT * FROM users WHERE name = '" + name + "'"
    cursor.execute(query)
    return cursor.fetchone()`,
    good: `# Good: parameterized query
def get_user(name):
    if not name or not isinstance(name, str):
        raise ValueError("Invalid name")
    cursor.execute(
        "SELECT * FROM users WHERE name = ?",
        (name,)
    )
    return cursor.fetchone()`,
  },
  'dry_principle': {
    language: 'javascript',
    bad: `// Bad: duplicated logic
function addTax5(price) {
  return price + price * 0.05;
}
function addTax10(price) {
  return price + price * 0.10;
}
function addTax21(price) {
  return price + price * 0.21;
}`,
    good: `// Good: single reusable function
function addTax(price, rate) {
  return price + price * (rate / 100);
}

addTax(100, 5);   // 105
addTax(100, 10);  // 110
addTax(100, 21);  // 121`,
  },
  'error_handling': {
    language: 'python',
    bad: `# Bad: no error handling, crashes on bad input
def divide(a, b):
    return a / b

def read_config():
    f = open("config.json")
    return json.loads(f.read())`,
    good: `# Good: handles errors gracefully
def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def read_config():
    try:
        with open("config.json") as f:
            return json.loads(f.read())
    except FileNotFoundError:
        return {}  # sensible default
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid config: {e}")`,
  },
  'secrets_management': {
    language: 'python',
    bad: `# Bad: secrets hardcoded in source
API_KEY = "sk-abc123secret456"
DB_PASSWORD = "admin123"
SECRET = "mysupersecretkey"

conn = connect(password=DB_PASSWORD)`,
    good: `# Good: secrets from environment
import os

API_KEY = os.environ["API_KEY"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
SECRET = os.environ["SECRET_KEY"]

conn = connect(password=DB_PASSWORD)
# Store secrets in .env (gitignored)`,
  },
  'html_semantics': {
    language: 'html',
    bad: '\x3c!-- Bad: div soup, no semantics -->\n\x3cdiv class="header">My Site\x3c/div>\n\x3cdiv class="nav">\n  \x3cdiv onclick="goto(\'/\')">Home\x3c/div>\n  \x3cdiv onclick="goto(\'/about\')">About\x3c/div>\n\x3c/div>\n\x3cdiv class="content">Welcome!\x3c/div>\n\x3cdiv class="footer">\u00a9 2024\x3c/div>',
    good: '\x3c!-- Good: semantic HTML -->\n\x3cheader>\x3ch1>My Site\x3c/h1>\x3c/header>\n\x3cnav>\n  \x3ca href="/">Home\x3c/a>\n  \x3ca href="/about">About\x3c/a>\n\x3c/nav>\n\x3cmain>\n  \x3carticle>Welcome!\x3c/article>\n\x3c/main>\n\x3cfooter>\u00a9 2024\x3c/footer>',
  },
  'css_organization': {
    language: 'css',
    bad: `/* Bad: duplicated styles, inline-like */
.btn-blue { background: blue; color: white;
  padding: 10px 20px; border: none; cursor: pointer; }
.btn-red { background: red; color: white;
  padding: 10px 20px; border: none; cursor: pointer; }
.btn-green { background: green; color: white;
  padding: 10px 20px; border: none; cursor: pointer; }`,
    good: `/* Good: shared base, color variants */
.btn {
  color: white;
  padding: 10px 20px;
  border: none;
  cursor: pointer;
}
.btn--primary { background: var(--blue); }
.btn--danger  { background: var(--red); }
.btn--success { background: var(--green); }`,
  },
  'xss_csrf_prevention': {
    language: 'javascript',
    bad: '// Bad: XSS vulnerability via innerHTML\nconst name = getUserInput();\ndocument.getElementById("greeting").innerHTML =\n  "\x3ch1>Hello " + name + "\x3c/h1>";\n// If name contains a script tag → XSS!',
    good: '// Good: safe text insertion\nconst name = getUserInput();\nconst el = document.getElementById("greeting");\nel.textContent = "Hello " + name;\n// Tags are rendered as plain text, not executed',
  },
  'database_queries': {
    language: 'python',
    bad: `# Bad: string concatenation → SQL injection
def delete_user(user_id):
    query = "DELETE FROM users WHERE id = " + user_id
    cursor.execute(query)
    # user_id = "1 OR 1=1" deletes ALL users!`,
    good: `# Good: parameterized query
def delete_user(user_id: int):
    cursor.execute(
        "DELETE FROM users WHERE id = ?",
        (user_id,)
    )
    # user_id is always treated as data, never SQL`,
  },
  'edge_cases': {
    language: 'python',
    bad: `# Bad: crashes on edge cases
def average(numbers):
    return sum(numbers) / len(numbers)

def first_word(text):
    return text.split()[0]
# average([]) → ZeroDivisionError
# first_word("") → IndexError`,
    good: `# Good: handles edge cases
def average(numbers):
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)

def first_word(text):
    words = (text or "").split()
    return words[0] if words else ""`,
  },
  'code_structure': {
    language: 'python',
    bad: `# Bad: one giant function doing everything
def process():
    data = open("f.csv").read()
    rows = data.split("\\n")
    results = []
    for r in rows:
        cols = r.split(",")
        if len(cols) > 2:
            results.append(float(cols[2]))
    total = sum(results)
    avg = total / len(results)
    print(f"Average: {avg}")`,
    good: `# Good: small focused functions
def read_csv(path):
    with open(path) as f:
        return [line.split(",") for line in f]

def extract_values(rows, col):
    return [float(r[col]) for r in rows if len(r) > col]

def main():
    rows = read_csv("f.csv")
    values = extract_values(rows, 2)
    print(f"Average: {sum(values)/len(values):.1f}")`,
  },
  'accessibility': {
    language: 'html',
    bad: '\x3c!-- Bad: inaccessible -->\n\x3cdiv onclick="submit()">Send\x3c/div>\n\x3cimg src="photo.jpg">\n\x3cinput type="text">\n\x3cdiv style="color: #ccc; background: #ddd;">\n  Light gray on lighter gray\n\x3c/div>',
    good: '\x3c!-- Good: accessible -->\n\x3cbutton onclick="submit()">Send\x3c/button>\n\x3cimg src="photo.jpg" alt="Team photo from 2024">\n\x3clabel for="name">Name\x3c/label>\n\x3cinput type="text" id="name" aria-required="true">\n\x3cdiv style="color: #333; background: #fff;">\n  High contrast text\n\x3c/div>',
  },
  'responsive_design': {
    language: 'css',
    bad: `/* Bad: fixed pixel widths */
.container { width: 1200px; }
.sidebar { width: 300px; }
.card { width: 400px; height: 300px; }
/* Breaks on mobile, overflows on tablet */`,
    good: `/* Good: responsive with relative units */
.container { max-width: 1200px; width: 100%; }
.sidebar { width: 25%; min-width: 200px; }
.card { width: 100%; aspect-ratio: 4/3; }
@media (max-width: 768px) {
  .sidebar { width: 100%; }
}`,
  },
  'comments_docs': {
    language: 'python',
    bad: `# Bad: no docs, cryptic code
def p(d, r, t):
    return d * (1 + r/100) ** t

x = p(1000, 5, 10)`,
    good: `def compound_interest(principal, annual_rate, years):
    """Calculate compound interest.

    Args:
        principal: Initial investment amount
        annual_rate: Annual interest rate (%)
        years: Number of years

    Returns:
        Final amount after compound interest
    """
    return principal * (1 + annual_rate / 100) ** years`,
  },
  'solid_principles': {
    language: 'python',
    bad: `# Bad: one class does everything (violates SRP)
class UserManager:
    def create_user(self, data): ...
    def send_email(self, to, body): ...
    def generate_report(self): ...
    def backup_database(self): ...`,
    good: `# Good: each class has one responsibility
class UserService:
    def create_user(self, data): ...

class EmailService:
    def send(self, to, body): ...

class ReportGenerator:
    def generate(self): ...

class DatabaseBackup:
    def run(self): ...`,
  },
  'api_design': {
    language: 'python',
    bad: `# Bad: inconsistent, no validation
@app.route("/getUser", methods=["POST"])
def get_user():
    id = request.json["id"]
    return str(db.query(f"SELECT * FROM users WHERE id={id}"))

@app.route("/deleteuser/<id>")
def delete(id):
    db.query(f"DELETE FROM users WHERE id={id}")
    return "ok"`,
    good: `# Good: RESTful, validated, proper responses
@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict()), 200

@app.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"status": "deleted"}), 200`,
  },
};

const codeExampleOpen = ref(false);
const codeExampleData = ref<{ name: string; example: CodeExample } | null>(null);

function openCodeExample(slug?: string) {
  if (!slug && patternInfoData.value) {
    // Derive slug from current info dialog
    slug = Object.keys(PATTERN_DESCRIPTIONS).find(
      k => PATTERN_DESCRIPTIONS[k] === patternInfoData.value!.description
    ) || '';
  }
  if (!slug) return;
  const example = PATTERN_EXAMPLES[slug];
  if (!example) return;
  const name = slug.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  codeExampleData.value = { name, example };
  patternInfoOpen.value = false;
  codeExampleOpen.value = true;
}

function openPatternInfo(patternKey: string) {
  const slug = patternKey.split(':')[0];
  const name = slug.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  patternInfoData.value = {
    name,
    slug,
    description: PATTERN_DESCRIPTIONS[slug] || `${name} is a recurring code quality pattern detected in your commits. Review the related findings on the Skills page to understand the specific issues and how to fix them.`,
  } as any;
  patternInfoOpen.value = true;
}

// Resolve pattern dialog state
const resolveDialogOpen = ref(false);
const resolveDialogData = ref<any>(null);
const resolveDialogLoading = ref(false);

async function resolvePattern(id: number) {
  resolvingId.value = id;
  resolveDialogData.value = null;
  try {
    const { data } = await api.evaluations.resolvePattern(id);

    if (data.resolved) {
      // Pattern successfully resolved
      patterns.value = patterns.value.map(p => p.id === id ? { ...p, is_resolved: true } : p);
      resolveDialogData.value = { success: true, message: data.message, skillBoost: data.skill_boost };
      resolveDialogOpen.value = true;
    } else {
      // Pattern still active — show affected files
      resolveDialogData.value = {
        success: false,
        patternId: id,
        reason: data.reason,
        affectedFiles: data.affected_files || [],
      };
      resolveDialogOpen.value = true;
    }
  } catch { /* ignore */ } finally { resolvingId.value = null; }
}

// forceResolvePattern removed alongside the "Resolve Anyway" button.
// Patterns are behavioral signals — a force-resolve undermines the
// integrity of the skill graph. The honest path when an issue still
// recurs in the last 3 commits is "fix the underlying code"; LEERA
// then auto-resolves once 10 clean commits pass.

const filteredPatterns = computed(() =>
  showResolved.value ? patterns.value : patterns.value.filter(p => !p.is_resolved)
);

const statCards = computed(() => {
  if (!overview.value) return [];
  return [
    { label: 'Totaal evaluaties', value: overview.value.total_evaluations, icon: 'analytics', color: 'primary' },
    { label: 'Totaal bevindingen', value: overview.value.total_findings, icon: 'bug_report', color: 'tertiary', sub: `${overview.value.critical_count} kritiek, ${overview.value.warning_count} waarschuwing` },
    { label: 'Fix-percentage', value: `${overview.value.fix_rate}%`, icon: 'check_circle', color: 'primary-container' },
    { label: 'Gemiddelde score', value: `${overview.value.avg_score}%`, icon: 'school', color: 'secondary' },
  ];
});

const selectedUserObj = computed(() => adminUsers.value.find(u => u.id === selectedUserId.value));
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <!-- Header -->
      <section class="flex flex-col md:flex-row justify-between items-start md:items-end mb-12 gap-6">
        <div class="space-y-2">
          <span class="text-primary font-bold uppercase tracking-[0.2em] text-xs">Skills & metrieken</span>
          <h1 class="text-5xl font-black tracking-tighter text-on-surface">
            {{ showUserList ? 'Team-skills' : 'Ontwikkelaars-dashboard' }}
          </h1>
          <p class="text-outline text-sm">
            {{ showUserList ? 'Kies een ontwikkelaar om de skill-metrieken te bekijken' : 'Volg coding-skills en voortgang in de tijd' }}
          </p>
        </div>

        <div class="flex items-center gap-3">
          <button v-if="authStore.isAdmin && selectedUserId" @click="backToList"
            class="flex items-center gap-2 px-4 py-2 bg-surface-container rounded-lg border border-outline-variant/20 text-sm text-on-surface hover:text-primary transition-colors">
            <span class="material-symbols-outlined text-sm">arrow_back</span> Alle gebruikers
          </button>
          <div v-if="selectedUserId && selectedUserObj" class="flex items-center gap-2 px-4 py-2 bg-surface-container rounded-lg border border-outline-variant/20">
            <div class="w-6 h-6 rounded-full bg-secondary-container flex items-center justify-center text-xs font-bold text-primary">
              {{ selectedUserObj.username.charAt(0).toUpperCase() }}
            </div>
            <span class="text-sm font-semibold">{{ selectedUserObj.display_name || selectedUserObj.username }}</span>
          </div>
          <div v-if="!authStore.isAdmin && projectsStore.projects.length > 1" class="flex items-center gap-2 px-3 py-2 bg-surface-container rounded-lg border border-outline-variant/20">
            <span class="material-symbols-outlined text-sm text-outline">folder</span>
            <select :value="projectsStore.selectedProjectId"
              @change="projectsStore.setSelectedProject(Number(($event.target as HTMLSelectElement).value))"
              class="bg-transparent border-none text-sm text-on-surface focus:ring-0 cursor-pointer p-0">
              <option v-for="p in projectsStore.projects" :key="p.id" :value="p.id">{{ p.displayName }}</option>
            </select>
          </div>
        </div>
      </section>

      <!-- ═══ Admin User List ═══ -->
      <template v-if="showUserList">
        <div class="flex flex-wrap items-center gap-3 mb-8">
          <input v-model="adminSearch" type="text" placeholder="Zoeken..."
            class="w-56 bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-2.5 px-4 text-sm" />
          <select v-model="adminCategoryFilter"
            class="bg-surface-container-lowest border-none rounded-lg text-sm text-on-surface focus:ring-1 focus:ring-primary/50 py-2.5 px-4">
            <option :value="null">Alle categorieën</option>
            <option v-for="c in adminCategories" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <select v-model="adminProjectFilter"
            class="bg-surface-container-lowest border-none rounded-lg text-sm text-on-surface focus:ring-1 focus:ring-primary/50 py-2.5 px-4">
            <option :value="null">Alle projecten</option>
            <option v-for="p in projectsStore.projects" :key="p.id" :value="p.id">{{ p.displayName }}</option>
          </select>
        </div>

        <div v-if="adminLoading" class="flex items-center justify-center py-16">
          <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
        </div>
        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          <div v-for="u in adminUsers" :key="u.id"
            class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 hover:border-primary/30 transition-all cursor-pointer"
            @click="selectUser(u.id)">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-10 h-10 rounded-lg bg-secondary-container flex items-center justify-center text-sm font-bold text-primary">
                {{ u.username.slice(0, 2).toUpperCase() }}
              </div>
              <div class="min-w-0">
                <div class="text-sm font-bold text-on-surface truncate">{{ u.display_name || u.username }}</div>
                <div class="text-[11px] text-outline truncate">{{ u.email }}</div>
              </div>
            </div>
            <div class="grid grid-cols-3 gap-2 text-center">
              <div class="bg-surface-container-lowest rounded-lg p-2">
                <p class="text-base font-black">{{ u.total_evaluations }}</p>
                <p class="text-[8px] text-outline uppercase">Evaluaties</p>
              </div>
              <div class="bg-surface-container-lowest rounded-lg p-2">
                <p class="text-base font-black">{{ u.total_findings }}</p>
                <p class="text-[8px] text-outline uppercase">Bevindingen</p>
              </div>
              <div class="bg-surface-container-lowest rounded-lg p-2">
                <p class="text-base font-black" :class="u.avg_score >= 70 ? 'text-green-400' : u.avg_score >= 50 ? 'text-yellow-400' : 'text-error'">{{ u.avg_score }}%</p>
                <p class="text-[8px] text-outline uppercase">Score</p>
              </div>
            </div>
          </div>
          <div v-if="!adminUsers.length" class="col-span-full text-center py-16">
            <span class="material-symbols-outlined text-6xl text-outline mb-4">group</span>
            <p class="text-outline">Geen ontwikkelaars gevonden</p>
          </div>
        </div>
      </template>

      <!-- ═══ User Dashboard (existing) ═══ -->
      <template v-else>
        <div v-if="loading" class="flex items-center justify-center py-16">
          <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
        </div>

        <template v-else>
          <section v-if="overview" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
            <div v-for="stat in statCards" :key="stat.label"
              class="bg-surface-container-low p-6 rounded-xl border-l-4" :class="`border-${stat.color}`">
              <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">{{ stat.label }}</p>
              <h3 class="text-3xl font-black">{{ stat.value }}</h3>
              <p v-if="stat.sub" class="text-xs text-outline mt-2">{{ stat.sub }}</p>
            </div>
          </section>

          <section class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">
            <SkillRadarChart :data="categoryScores" title="Skill-overzicht" />
            <ProgressChart :data="progressData" title="Wekelijkse voortgang (laatste 8 weken)" />
          </section>

          <!-- Recommendations: only shown for admin viewing a developer's skills. Developers use /recommendations page -->
          <section v-if="authStore.isAdmin" class="mb-12">
            <div class="flex items-center gap-3 mb-4">
              <span class="material-symbols-outlined text-primary text-2xl">route</span>
              <div>
                <h3 class="text-xl font-bold">Leerpad</h3>
                <p class="text-xs text-outline">Persoonlijke aanbevelingen op basis van codepatronen en kennishiaten</p>
              </div>
            </div>
            <RecommendationsWidget
              :project-id="projectsStore.selectedProjectId != null ? String(projectsStore.selectedProjectId) : undefined"
            />
          </section>

          <section class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-12">
            <div class="lg:col-span-2 max-h-[500px] overflow-y-auto"><RecentFindings :findings="recentFindings" /></div>
            <div class="bg-surface-container-low rounded-2xl p-6 border border-outline-variant/10">
              <h4 class="text-xl font-bold mb-6">Snelle stats</h4>
              <div class="space-y-4">
                <div class="flex items-center justify-between p-3 bg-surface-container-lowest rounded-lg">
                  <div class="flex items-center gap-3"><span class="material-symbols-outlined text-error">error</span><span class="text-sm">Kritiek</span></div>
                  <span class="text-xl font-black">{{ overview?.critical_count || 0 }}</span>
                </div>
                <div class="flex items-center justify-between p-3 bg-surface-container-lowest rounded-lg">
                  <div class="flex items-center gap-3"><span class="material-symbols-outlined text-yellow-500">warning</span><span class="text-sm">Waarschuwingen</span></div>
                  <span class="text-xl font-black">{{ overview?.warning_count || 0 }}</span>
                </div>
                <div class="flex items-center justify-between p-3 bg-surface-container-lowest rounded-lg">
                  <div class="flex items-center gap-3"><span class="material-symbols-outlined text-primary">check_circle</span><span class="text-sm">Opgelost</span></div>
                  <span class="text-xl font-black">{{ overview?.fixed_count || 0 }}</span>
                </div>
              </div>
            </div>
          </section>

          <section v-if="skillCategories.length" class="mb-12">
            <h4 class="text-2xl font-black tracking-tight mb-6">Skill-verdeling per categorie</h4>
            <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              <CategoryRadarChart v-for="cat in skillCategories" :key="cat.id" :category="cat" @click-skill="openSkillBreakdown" />
            </div>
          </section>

          <!-- ─── Pattern Tracker ─── -->
          <section class="mb-12">
            <div class="flex items-center justify-between mb-5">
              <div>
                <h4 class="text-2xl font-black tracking-tight">Patroon-tracker</h4>
                <p class="text-sm text-outline mt-0.5">Terugkerende codeproblemen die in jouw evaluaties zijn gedetecteerd</p>
              </div>
              <label class="flex items-center gap-2 text-sm text-outline cursor-pointer">
                <input type="checkbox" v-model="showResolved" class="accent-primary rounded" />
                Opgeloste tonen
              </label>
            </div>

            <div v-if="patternsLoading" class="flex items-center gap-3 py-8 text-outline">
              <span class="material-symbols-outlined animate-spin text-2xl">progress_activity</span>
              Patronen laden…
            </div>

            <div v-else-if="!filteredPatterns.length" class="p-8 bg-surface-container-low rounded-2xl border border-outline-variant/10 text-center">
              <span class="material-symbols-outlined text-4xl text-outline mb-2 block">verified</span>
              <p class="text-sm text-outline">{{ showResolved ? 'Geen patronen gevonden.' : 'Geen terugkerende problemen gedetecteerd.' }}</p>
            </div>

            <div v-else class="bg-surface-container-low rounded-2xl border border-outline-variant/10 overflow-hidden">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-outline-variant/10 text-xs text-outline uppercase tracking-wider">
                    <th class="px-5 py-3 text-left">Patroon</th>
                    <th class="px-5 py-3 text-center">Frequentie</th>
                    <th class="px-5 py-3 text-left hidden md:table-cell">Eerst gezien</th>
                    <th class="px-5 py-3 text-left hidden md:table-cell">Laatst gezien</th>
                    <th class="px-5 py-3 text-center">Status</th>
                    <th class="px-3 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="p in filteredPatterns"
                    :key="p.id"
                    class="border-b border-outline-variant/5 hover:bg-surface-container-lowest/40 transition-colors"
                    :class="p.is_resolved ? 'opacity-50' : ''"
                  >
                    <td class="px-5 py-3">
                      <div class="flex items-center gap-3">
                        <span class="material-symbols-outlined text-error text-base">repeat</span>
                        <div>
                          <p class="font-semibold text-on-surface capitalize">
                            {{ p.pattern_key.split(':')[0].replace(/_/g, ' ') }}
                          </p>
                          <p class="text-xs text-outline capitalize">{{ p.pattern_type }}</p>
                        </div>
                        <button @click.stop="openPatternInfo(p.pattern_key)"
                          class="p-1 rounded-full hover:bg-surface-container-highest transition-colors" title="Wat is dit?">
                          <span class="material-symbols-outlined text-sm text-outline hover:text-primary">info</span>
                        </button>
                      </div>
                    </td>
                    <td class="px-5 py-3 text-center">
                      <span class="px-2.5 py-1 rounded-full text-xs font-bold"
                        :class="p.frequency >= 5 ? 'bg-error/15 text-error' : p.frequency >= 3 ? 'bg-yellow-500/15 text-yellow-500' : 'bg-outline/10 text-outline'">
                        ×{{ p.frequency }}
                      </span>
                    </td>
                    <td class="px-5 py-3 text-outline text-xs hidden md:table-cell">
                      {{ new Date(p.first_seen).toLocaleDateString() }}
                    </td>
                    <td class="px-5 py-3 text-outline text-xs hidden md:table-cell">
                      {{ new Date(p.last_seen).toLocaleDateString() }}
                    </td>
                    <td class="px-5 py-3 text-center">
                      <span v-if="p.is_resolved" class="px-2 py-0.5 rounded-full text-xs bg-emerald-500/15 text-emerald-500 font-semibold">Opgelost</span>
                      <span v-else class="px-2 py-0.5 rounded-full text-xs bg-error/10 text-error font-semibold">Actief</span>
                    </td>
                    <td class="px-3 py-3 text-right">
                      <button
                        v-if="!p.is_resolved"
                        type="button"
                        :disabled="resolvingId === p.id"
                        class="px-3 py-1.5 rounded-lg border border-outline-variant/20 text-xs hover:border-primary/40 hover:text-primary transition-colors disabled:opacity-50"
                        @click="resolvePattern(p.id)"
                      >
                        <span v-if="resolvingId === p.id" class="material-symbols-outlined text-xs animate-spin">progress_activity</span>
                        <span v-else>Markeer als opgelost</span>
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section v-if="!overview && !loading" class="text-center py-16">
            <span class="material-symbols-outlined text-6xl text-outline mb-4">insights</span>
            <h3 class="text-xl font-bold mb-2">Nog geen dashboard-data</h3>
            <p class="text-outline">Push code om je skill-metrieken en voortgang te zien!</p>
          </section>
        </template>
      </template>
    </div>
  </AppShell>

  <SkillBreakdownDialog
    :open="breakdownOpen"
    :user-id="authStore.user?.id ?? 0"
    :skill-id="breakdownSkillId"
    :project-id="projectsStore.selectedProjectId ?? 0"
    @close="breakdownOpen = false"
  />

  <!-- Pattern Info Dialog -->
  <Teleport to="body">
    <div v-if="patternInfoOpen && patternInfoData" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" @click.self="patternInfoOpen = false">
      <div class="bg-surface-container rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
        <div class="px-6 py-4 border-b border-outline-variant/10 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-primary">school</span>
            <h3 class="text-lg font-bold capitalize">{{ patternInfoData.name }}</h3>
          </div>
          <button @click="patternInfoOpen = false" class="p-1 rounded-lg hover:bg-surface-container-highest">
            <span class="material-symbols-outlined text-outline">close</span>
          </button>
        </div>
        <div class="p-6">
          <p class="text-sm text-on-surface-variant leading-relaxed">{{ patternInfoData.description }}</p>
        </div>
        <div class="px-6 py-3 border-t border-outline-variant/10 flex justify-between">
          <button v-if="PATTERN_EXAMPLES[(patternInfoData as any)?.slug]"
            @click="openCodeExample((patternInfoData as any)?.slug)"
            class="px-4 py-2 text-sm font-bold bg-tertiary/10 text-tertiary rounded-lg hover:bg-tertiary/20 transition-colors flex items-center gap-2">
            <span class="material-symbols-outlined text-sm">code</span>
            Codevoorbeeld
          </button>
          <span v-else></span>
          <button @click="patternInfoOpen = false" class="px-4 py-2 text-sm text-primary font-bold hover:bg-primary/10 rounded-lg transition-colors">
            Begrepen
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Code Example Dialog -->
  <Teleport to="body">
    <div v-if="codeExampleOpen && codeExampleData" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" @click.self="codeExampleOpen = false">
      <div class="bg-surface-container rounded-2xl shadow-xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
        <div class="px-6 py-4 border-b border-outline-variant/10 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-tertiary">code</span>
            <h3 class="text-lg font-bold capitalize">{{ codeExampleData.name }} — Codevoorbeeld</h3>
          </div>
          <button @click="codeExampleOpen = false" class="p-1 rounded-lg hover:bg-surface-container-highest">
            <span class="material-symbols-outlined text-outline">close</span>
          </button>
        </div>

        <div class="flex-1 overflow-y-auto p-6">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <!-- Bad Example -->
            <div class="rounded-xl overflow-hidden border border-red-500/20">
              <div class="px-4 py-2 bg-red-500/10 flex items-center gap-2">
                <span class="material-symbols-outlined text-sm text-red-400">close</span>
                <span class="text-sm font-bold text-red-400">Slechte praktijk</span>
              </div>
              <pre class="p-4 bg-surface-container-lowest text-xs text-on-surface-variant overflow-x-auto whitespace-pre leading-relaxed"><code>{{ codeExampleData.example.bad }}</code></pre>
            </div>

            <!-- Good Example -->
            <div class="rounded-xl overflow-hidden border border-green-500/20">
              <div class="px-4 py-2 bg-green-500/10 flex items-center gap-2">
                <span class="material-symbols-outlined text-sm text-green-400">check</span>
                <span class="text-sm font-bold text-green-400">Goede praktijk</span>
              </div>
              <pre class="p-4 bg-surface-container-lowest text-xs text-on-surface-variant overflow-x-auto whitespace-pre leading-relaxed"><code>{{ codeExampleData.example.good }}</code></pre>
            </div>
          </div>

          <p class="text-xs text-outline text-center mt-4">
            Taal: <span class="text-on-surface font-mono">{{ codeExampleData.example.language }}</span>
          </p>
        </div>

        <div class="px-6 py-3 border-t border-outline-variant/10 flex justify-end">
          <button @click="codeExampleOpen = false" class="px-4 py-2 text-sm text-primary font-bold hover:bg-primary/10 rounded-lg transition-colors">
            Sluiten
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Pattern Resolve Dialog -->
  <Teleport to="body">
    <div v-if="resolveDialogOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" @click.self="resolveDialogOpen = false">
      <div class="bg-surface-container rounded-2xl shadow-xl w-full max-w-lg overflow-hidden">
        <div class="p-6">
          <!-- Success -->
          <template v-if="resolveDialogData?.success">
            <div class="text-center mb-4">
              <span class="material-symbols-outlined text-5xl text-green-400">check_circle</span>
            </div>
            <h3 class="text-lg font-bold text-center mb-2">Patroon opgelost!</h3>
            <p class="text-sm text-on-surface-variant text-center">{{ resolveDialogData.message }}</p>
            <div v-if="resolveDialogData.skillBoost" class="mt-3 p-3 bg-green-500/10 rounded-lg text-center">
              <p class="text-sm text-green-400 font-bold">+{{ resolveDialogData.skillBoost }} skill-punten verdiend</p>
            </div>
          </template>

          <!-- Still active — show affected files -->
          <template v-else-if="resolveDialogData">
            <div class="text-center mb-4">
              <span class="material-symbols-outlined text-5xl text-orange-400">warning</span>
            </div>
            <h3 class="text-lg font-bold text-center mb-2">Patroon nog steeds actief</h3>
            <p class="text-sm text-on-surface-variant text-center mb-4">{{ resolveDialogData.reason }}</p>

            <!-- Affected files with links -->
            <div class="space-y-2 max-h-48 overflow-y-auto">
              <div v-for="f in resolveDialogData.affectedFiles" :key="f.finding_id"
                class="flex items-center gap-3 p-3 rounded-lg bg-surface-container-lowest border border-outline-variant/10 hover:border-primary/30 cursor-pointer transition-all"
                @click="resolveDialogOpen = false; $router.push({ name: 'file-review', query: { evaluationId: f.evaluation_id, project: projectsStore.selectedProjectId } })">
                <span class="material-symbols-outlined text-sm"
                  :class="f.severity === 'critical' ? 'text-red-400' : 'text-orange-400'">{{ f.severity === 'critical' ? 'error' : 'warning' }}</span>
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium truncate">{{ f.title }}</p>
                  <p class="text-[10px] text-outline font-mono">{{ f.file_path }} · {{ f.commit_sha }}</p>
                </div>
                <span class="material-symbols-outlined text-sm text-outline">chevron_right</span>
              </div>
            </div>

            <p class="text-xs text-outline text-center mt-3">Klik op een bevinding om hem te bekijken en op te lossen via Oplossen & leren</p>
          </template>
        </div>

        <!-- Footer.
             Removed the "Resolve Anyway" button. Patterns are
             behavioral signals — a force-resolve undermines that.
             If the issue still appears in the last 3 commits, the
             dialog explains where, and the only honest path is to
             actually fix the underlying code. The pattern will
             auto-resolve on its own once 10 clean commits pass. -->
        <div class="px-6 py-4 border-t border-outline-variant/10 flex justify-end">
          <button @click="resolveDialogOpen = false" class="px-4 py-2 text-sm text-outline hover:text-on-surface">
            Sluiten
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
