<template>
  <div class="ops-dashboard">
    <header class="ops-header">
      <h1>Ops Dashboard</h1>
      <p class="ops-sub">Platform operations — superuser only</p>
    </header>

    <nav class="ops-tabs" role="tablist">
      <button
        v-for="t in tabs"
        :key="t.id"
        :class="['tab-btn', { active: activeTab === t.id }]"
        @click="activeTab = t.id"
        :data-testid="`tab-${t.id}`"
      >
        {{ t.label }}
      </button>
    </nav>

    <div v-if="loading" class="ops-loading">Loading…</div>
    <div v-else-if="error" class="ops-error">{{ error }}</div>

    <!-- Summary -->
    <section v-show="activeTab === 'summary' && summary" class="ops-section">
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-value">{{ summary?.platform_totals.orgs ?? '—' }}</div>
          <div class="stat-label">Organizations</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ summary?.platform_totals.classrooms ?? '—' }}</div>
          <div class="stat-label">Classrooms</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ summary?.platform_totals.teachers ?? '—' }}</div>
          <div class="stat-label">Teachers</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ summary?.platform_totals.students ?? '—' }}</div>
          <div class="stat-label">Students</div>
        </div>
      </div>

      <h3>Activity (rolling 7 days)</h3>
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-value">{{ summary?.activity_7d.sessions_created ?? 0 }}</div>
          <div class="stat-label">Grading sessions created</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ summary?.activity_7d.sessions_posted ?? 0 }}</div>
          <div class="stat-label">Sessions posted to GitHub</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">€{{ formatEur(summary?.activity_7d.cost_eur) }}</div>
          <div class="stat-label">LLM cost (7d)</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">€{{ formatEur(summary?.activity_30d.cost_eur) }}</div>
          <div class="stat-label">LLM cost (30d)</div>
        </div>
      </div>

      <h3>
        Teachers over €{{ formatEur(summary?.alerts.weekly_threshold_eur) }} weekly threshold
      </h3>
      <div
        v-if="(summary?.alerts.docents_over_threshold?.length ?? 0) === 0"
        class="ops-empty"
      >
        No teachers over threshold.
      </div>
      <table v-else class="ops-table">
        <thead>
          <tr><th>Teacher</th><th class="num">Cost (7d)</th></tr>
        </thead>
        <tbody>
          <tr v-for="d in summary!.alerts.docents_over_threshold" :key="d.docent_id">
            <td>{{ d.docent__email }}</td>
            <td class="num">€{{ formatEur(d.total) }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Orgs -->
    <section v-show="activeTab === 'orgs'" class="ops-section">
      <table class="ops-table">
        <thead>
          <tr>
            <th>Name</th>
            <th class="num">Classrooms</th>
            <th class="num">Teachers</th>
            <th class="num">Students</th>
            <th class="num">Cost (7d)</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in orgs" :key="o.id">
            <td>{{ o.name }}</td>
            <td class="num">{{ o.classrooms }}</td>
            <td class="num">{{ o.teachers }}</td>
            <td class="num">{{ o.students }}</td>
            <td class="num">€{{ formatEur(o.cost_7d_eur) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="orgs.length === 0" class="ops-empty">No organizations yet.</div>
    </section>

    <!-- Classrooms -->
    <section v-show="activeTab === 'classrooms'" class="ops-section">
      <table class="ops-table">
        <thead>
          <tr>
            <th>Classroom</th>
            <th>Org</th>
            <th>Teacher</th>
            <th class="num">Students</th>
            <th class="num">Sessions (open / total)</th>
            <th class="num">Cost (7d)</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in classrooms" :key="c.id">
            <td>{{ c.name }}</td>
            <td>{{ c.org_name }}</td>
            <td>{{ c.owner_email }}</td>
            <td class="num">{{ c.students }}</td>
            <td class="num">{{ c.sessions_open }} / {{ c.sessions_total }}</td>
            <td class="num">€{{ formatEur(c.cost_7d_eur) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="classrooms.length === 0" class="ops-empty">No classrooms yet.</div>
    </section>

    <!-- Teachers / docents -->
    <section v-show="activeTab === 'teachers'" class="ops-section">
      <table class="ops-table">
        <thead>
          <tr>
            <th>Teacher</th>
            <th>Org</th>
            <th class="num">Classrooms</th>
            <th class="num">Posted (7d)</th>
            <th class="num">Cost (7d)</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="t in teachers"
            :key="t.id"
            :class="{ 'row-alert': t.over_threshold }"
          >
            <td>{{ t.email }}</td>
            <td>{{ t.org_name || '—' }}</td>
            <td class="num">{{ t.classrooms }}</td>
            <td class="num">{{ t.sessions_posted_7d }}</td>
            <td class="num">€{{ formatEur(t.cost_7d_eur) }}</td>
            <td>
              <span v-if="t.over_threshold" class="badge alert">over threshold</span>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="teachers.length === 0" class="ops-empty">No teachers yet.</div>
    </section>

    <!-- LLM log -->
    <section v-show="activeTab === 'llm-log'" class="ops-section">
      <div class="llm-filters">
        <label>
          <span>Tier</span>
          <select v-model="llmTier" @change="loadLlmLog">
            <option value="">All</option>
            <option value="cheap">Cheap</option>
            <option value="premium">Premium</option>
          </select>
        </label>
      </div>
      <table class="ops-table">
        <thead>
          <tr>
            <th>When</th>
            <th>Tier</th>
            <th>Model</th>
            <th>Teacher</th>
            <th>Classroom</th>
            <th class="num">In</th>
            <th class="num">Out</th>
            <th class="num">Cost</th>
            <th class="num">ms</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in llmLog" :key="r.id" :class="{ 'row-alert': r.ceiling_rejected }">
            <td>{{ formatTime(r.occurred_at) }}</td>
            <td>{{ r.tier }}</td>
            <td>{{ r.model_name }}</td>
            <td>{{ r.docent_email || '—' }}</td>
            <td>{{ r.classroom_name || '—' }}</td>
            <td class="num">{{ r.tokens_in }}</td>
            <td class="num">{{ r.tokens_out }}</td>
            <td class="num">€{{ formatEur(r.cost_eur) }}</td>
            <td class="num">{{ r.latency_ms ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="llmLog.length === 0" class="ops-empty">No LLM calls yet.</div>
    </section>

    <!-- LLM config -->
    <section v-show="activeTab === 'llm-config'" class="ops-section">
      <p class="ops-note">
        Primary LLM configuration surface (migrated from Settings → LLM Config).
        For v1, manage configs via the existing Settings page
        <router-link to="/settings?tab=llm" class="link">Settings → LLM Config</router-link>.
        Full inline editor ships in v1.1.
      </p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { api } from '@/composables/useApi';

type TabId = 'summary' | 'orgs' | 'classrooms' | 'teachers' | 'llm-log' | 'llm-config';

const tabs: { id: TabId; label: string }[] = [
  { id: 'summary', label: 'Summary' },
  { id: 'orgs', label: 'Orgs' },
  { id: 'classrooms', label: 'Classrooms' },
  { id: 'teachers', label: 'Teachers' },
  { id: 'llm-log', label: 'LLM Log' },
  { id: 'llm-config', label: 'LLM Config' },
];

const activeTab = ref<TabId>('summary');
const loading = ref(false);
const error = ref<string | null>(null);

const summary = ref<any>(null);
const orgs = ref<any[]>([]);
const classrooms = ref<any[]>([]);
const teachers = ref<any[]>([]);
const llmLog = ref<any[]>([]);
const llmTier = ref('');

async function loadActiveTab() {
  loading.value = true;
  error.value = null;
  try {
    switch (activeTab.value) {
      case 'summary': {
        const { data } = await api.grading.ops.summary();
        summary.value = data;
        break;
      }
      case 'orgs': {
        const { data } = await api.grading.ops.orgs();
        orgs.value = data.results ?? [];
        break;
      }
      case 'classrooms': {
        const { data } = await api.grading.ops.classrooms();
        classrooms.value = data.results ?? [];
        break;
      }
      case 'teachers': {
        const { data } = await api.grading.ops.teachers();
        teachers.value = data.results ?? [];
        break;
      }
      case 'llm-log': {
        await loadLlmLog();
        break;
      }
      // llm-config has no fetch yet
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || 'Failed to load';
  } finally {
    loading.value = false;
  }
}

async function loadLlmLog() {
  loading.value = true;
  try {
    const params: Record<string, unknown> = { limit: 100 };
    if (llmTier.value) params.tier = llmTier.value;
    const { data } = await api.grading.ops.llmLog(params);
    llmLog.value = data.results ?? [];
  } finally {
    loading.value = false;
  }
}

function formatEur(v: string | number | null | undefined): string {
  if (v === null || v === undefined) return '0.00';
  const n = Number(v);
  if (Number.isNaN(n)) return '0.00';
  return n.toFixed(2);
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString();
}

onMounted(loadActiveTab);
watch(activeTab, loadActiveTab);
</script>

<style scoped>
.ops-dashboard {
  max-width: 1300px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
}

.ops-header h1 {
  font-size: 1.5rem;
  color: rgb(226 232 240);
  margin: 0;
}

.ops-sub {
  font-size: 0.875rem;
  color: rgb(148 163 184);
  margin: 0.25rem 0 1.5rem;
}

.ops-tabs {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid rgb(30 41 59);
  margin-bottom: 1.5rem;
  overflow-x: auto;
}

.tab-btn {
  background: transparent;
  border: none;
  color: rgb(148 163 184);
  padding: 0.75rem 1rem;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  font-size: 0.9rem;
  white-space: nowrap;
}

.tab-btn:hover {
  color: rgb(226 232 240);
}

.tab-btn.active {
  color: rgb(147 197 253);
  border-bottom-color: rgb(99 102 241);
}

.ops-section {
  padding: 0.25rem 0 2rem;
}

.ops-section h3 {
  color: rgb(203 213 225);
  margin: 1.5rem 0 0.75rem;
  font-size: 0.95rem;
  font-weight: 600;
}

.ops-loading,
.ops-error,
.ops-empty,
.ops-note {
  color: rgb(148 163 184);
  padding: 1rem;
  font-size: 0.9rem;
}

.ops-error {
  background: rgb(127 29 29 / 0.3);
  border: 1px solid rgb(185 28 28);
  border-radius: 0.5rem;
  color: rgb(254 202 202);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.stat-card {
  background: rgb(15 23 42);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.5rem;
  padding: 1rem;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 600;
  color: rgb(226 232 240);
  line-height: 1.2;
}

.stat-label {
  font-size: 0.8rem;
  color: rgb(148 163 184);
  margin-top: 0.25rem;
}

.ops-table {
  width: 100%;
  border-collapse: collapse;
  background: rgb(15 23 42);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.5rem;
  overflow: hidden;
  font-size: 0.9rem;
}

.ops-table th,
.ops-table td {
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid rgb(30 41 59);
  color: rgb(203 213 225);
}

.ops-table th {
  background: rgb(2 6 23);
  color: rgb(148 163 184);
  text-transform: uppercase;
  font-size: 0.7rem;
  letter-spacing: 0.05em;
}

.ops-table td.num,
.ops-table th.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.ops-table tr.row-alert td {
  background: rgb(127 29 29 / 0.15);
}

.badge {
  padding: 0.1rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.7rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  background: rgb(30 41 59);
  color: rgb(203 213 225);
}

.badge.alert {
  background: rgb(239 68 68 / 0.2);
  color: rgb(252 165 165);
}

.link {
  color: rgb(147 197 253);
}

.llm-filters {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.llm-filters label {
  display: flex;
  flex-direction: column;
  font-size: 0.75rem;
  color: rgb(148 163 184);
}

.llm-filters select {
  background: rgb(30 41 59);
  border: 1px solid rgb(51 65 85);
  color: rgb(226 232 240);
  padding: 0.3rem 0.6rem;
  border-radius: 0.25rem;
}
</style>
