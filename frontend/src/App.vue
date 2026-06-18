<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  applyReviewAction,
  fetchReviewItems,
  type ReviewAction,
  type ReviewItem,
} from "./api";

const currentReviewer = "alex";
const items = ref<ReviewItem[]>([]);
const selectedId = ref<string | null>(null);
const isLoading = ref(false);
const errorMessage = ref<string | null>(null);
const pendingAction = ref<ReviewAction | null>(null);

const selectedItem = computed(() =>
  items.value.find((item) => item.id === selectedId.value) ?? items.value[0] ?? null
);

const TERMINAL_STATUSES = new Set(["approved", "rejected", "escalated"]);

const stats = computed(() => ({
  highRisk: items.value.filter(i => i.risk_level === 'high').length,
  priority: items.value.filter(i => i.customer_tier === 'priority').length,
  total: items.value.length,
}));

const searchQuery = ref('');
const activeFilter = ref<'all' | 'unassigned' | 'mine' | 'priority'>('all');

const filteredItems = computed(() => {
  let result = items.value;
  if (activeFilter.value === 'unassigned') result = result.filter(i => i.status === 'unassigned');
  if (activeFilter.value === 'mine') result = result.filter(i => i.assigned_reviewer === currentReviewer);
  if (activeFilter.value === 'priority') result = result.filter(i => i.customer_tier === 'priority');
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase();
    result = result.filter(i => i.title.toLowerCase().includes(q));
  }
  return result;
});

async function loadItems() {
  isLoading.value = true;
  errorMessage.value = null;

  try {
    items.value = await fetchReviewItems();
    selectedId.value = selectedItem.value?.id ?? null;
  } catch (error) {
    errorMessage.value = "Something went wrong loading the queue.";
  } finally {
    isLoading.value = false;
  }
}

async function performAction(action: ReviewAction) {
  if (!selectedItem.value) return;

  pendingAction.value = action;
  errorMessage.value = null;

  try {
    const updated = await applyReviewAction(selectedItem.value.id, action, currentReviewer);

    if (TERMINAL_STATUSES.has(updated.status)) {
      items.value = items.value.filter((item) => item.id !== updated.id);
      selectedId.value = items.value[0]?.id ?? null;
    } else {
      items.value = items.value.map((item) => (item.id === updated.id ? updated : item));
    }
  } catch (error) {
    errorMessage.value = "That action could not be completed.";
  } finally {
    pendingAction.value = null;
  }
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

onMounted(loadItems);
</script>

<template>
  <main class="page-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">Reviewer workspace</p>
        <h1>Active queue</h1>
      </div>
      <div class="reviewer-avatar" aria-label="Signed in as alex">AX</div>
    </header>

    <p v-if="errorMessage" class="error-banner">{{ errorMessage }}</p>
    <p v-if="isLoading" class="loading">Loading review items...</p>

    <section v-else class="workspace">
      <aside class="queue-list" aria-label="Review queue">
        <div class="queue-stats">
          <div class="stat-card">
            <span class="stat-number">{{ stats.highRisk }}</span>
            <span class="stat-label">High risk</span>
          </div>
          <div class="stat-card">
            <span class="stat-number">{{ stats.priority }}</span>
            <span class="stat-label">Priority</span>
          </div>
          <div class="stat-card">
            <span class="stat-number">{{ stats.total }}</span>
            <span class="stat-label">Total open</span>
          </div>
        </div>
        <div class="queue-search">
          <input
            v-model="searchQuery"
            type="search"
            placeholder="Search queue..."
            class="search-input"
            aria-label="Search queue"
          />
        </div>
        <div class="filter-tabs" role="tablist">
          <button
            v-for="tab in (['all','unassigned','mine','priority'] as const)"
            :key="tab"
            class="filter-tab"
            :class="{ active: activeFilter === tab }"
            role="tab"
            :aria-selected="activeFilter === tab"
            @click="activeFilter = tab"
          >{{ tab.charAt(0).toUpperCase() + tab.slice(1) }}</button>
        </div>
        <button
          v-for="item in filteredItems"
          :key="item.id"
          class="queue-item"
          :class="{ selected: item.id === selectedItem?.id }"
          type="button"
          @click="selectedId = item.id"
        >
          <span class="queue-title">{{ item.title }}</span>
          <span class="badge-row">
            <span class="badge" :class="'risk-' + item.risk_level">{{ item.risk_level }}</span>
            <span class="badge" :class="item.customer_tier === 'priority' ? 'tier-priority' : 'tier-standard'">{{ item.customer_tier }}</span>
          </span>
          <span class="queue-meta">{{ item.status }} · {{ item.assigned_reviewer ?? "unassigned" }}</span>
        </button>
      </aside>

      <section v-if="selectedItem" class="detail-panel">
        <div class="detail-header">
          <div>
            <p class="eyebrow">{{ selectedItem.id }}</p>
            <h2>{{ selectedItem.title }}</h2>
          </div>
          <span class="status-pill">{{ selectedItem.status }}</span>
        </div>

        <dl class="facts">
          <div>
            <dt>Submitted</dt>
            <dd>{{ formatDate(selectedItem.submitted_at) }}</dd>
          </div>
          <div>
            <dt>Risk</dt>
            <dd>{{ selectedItem.risk_level }}</dd>
          </div>
          <div>
            <dt>Customer</dt>
            <dd>{{ selectedItem.customer_tier }}</dd>
          </div>
          <div>
            <dt>Assignee</dt>
            <dd>{{ selectedItem.assigned_reviewer ?? "None" }}</dd>
          </div>
        </dl>

        <p class="summary">{{ selectedItem.summary }}</p>
        <p class="notes">{{ selectedItem.notes_count }} notes on this item</p>

        <div class="actions" aria-label="Workflow actions">
          <template v-if="selectedItem.status === 'unassigned'">
            <button type="button" :disabled="Boolean(pendingAction)" @click="performAction('claim')">Claim</button>
          </template>
          <template v-else-if="selectedItem.status === 'in_review'">
            <button type="button" :disabled="Boolean(pendingAction)" @click="performAction('approve')">Approve</button>
            <button type="button" :disabled="Boolean(pendingAction)" @click="performAction('reject')">Reject</button>
            <button type="button" :disabled="Boolean(pendingAction)" @click="performAction('escalate')">Escalate</button>
          </template>
          <template v-else>
            <p class="terminal-notice">This item is {{ selectedItem.status }}. No further actions are available.</p>
          </template>
        </div>
      </section>
    </section>
  </main>
</template>

<style scoped>
.reviewer-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #c7d9f5;
  color: #1e3a6e;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.queue-search { padding: 10px 12px 4px; }
.search-input {
  width: 100%;
  border: 1px solid #d8dee9;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
  background: #f5f7fb;
  color: #162033;
}
.search-input:focus { outline: 2px solid #4c7bd9; border-color: transparent; }
.filter-tabs {
  display: flex;
  gap: 4px;
  padding: 6px 12px 10px;
  border-bottom: 1px solid #eef1f6;
}
.filter-tab {
  border: 1px solid #d8dee9;
  border-radius: 999px;
  background: #fff;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
  color: #5c6b7e;
}
.filter-tab.active {
  background: #162033;
  color: #fff;
  border-color: #162033;
}

.queue-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid #eef1f6;
}
.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: #f5f7fb;
  border-radius: 6px;
  padding: 8px 4px;
}
.stat-number {
  font-size: 20px;
  font-weight: 700;
  color: #162033;
}
.stat-label {
  font-size: 11px;
  color: #5c6b7e;
  margin-top: 2px;
}

.terminal-notice {
  color: #66758a;
  font-style: italic;
  margin-top: 28px;
}

/* TAKEHOME: Colour-coded badges let reviewers scan risk and tier at a glance
   without reading every row — reduces time to answer "what do I work on next?" */
.badge-row { display: flex; gap: 6px; align-items: center; }
.badge {
  display: inline-block;
  border-radius: 4px;
  padding: 2px 7px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.risk-high    { background: #ffe9e6; color: #8b1d0f; }
.risk-medium  { background: #fff4e0; color: #7a4a00; }
.risk-low     { background: #e8f4e8; color: #1a5c1a; }
.tier-priority { background: #e8eef7; color: #1e55bd; }
.tier-standard { background: #f0f1f3; color: #4a5568; }
</style>
