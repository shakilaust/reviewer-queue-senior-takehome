<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  applyReviewAction,
  fetchReviewItems,
  type ReviewAction,
  type ReviewItem,
  type ReviewStatus,
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

const TERMINAL_STATUSES: ReviewStatus[] = ["approved", "rejected", "escalated"];

const allowedActions = computed((): ReviewAction[] => {
  const status = selectedItem.value?.status;
  if (!status || TERMINAL_STATUSES.includes(status)) return [];
  if (status === "unassigned") return ["claim"];
  if (status === "in_review") return ["approve", "reject", "escalate"];
  return [];
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
  if (!allowedActions.value.includes(action)) return;

  pendingAction.value = action;
  errorMessage.value = null;

  try {
    const updated = await applyReviewAction(selectedItem.value.id, action, currentReviewer);

    if (TERMINAL_STATUSES.includes(updated.status)) {
      // Remove from active queue and advance to the next item in the list.
      const currentIndex = items.value.findIndex((i) => i.id === updated.id);
      items.value = items.value.filter((i) => i.id !== updated.id);
      const next = items.value[currentIndex] ?? items.value[currentIndex - 1] ?? null;
      selectedId.value = next?.id ?? null;
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
      <div class="reviewer">Signed in as {{ currentReviewer }}</div>
    </header>

    <p v-if="errorMessage" class="error-banner">{{ errorMessage }}</p>
    <p v-if="isLoading" class="loading">Loading review items...</p>

    <section v-else class="workspace">
      <aside class="queue-list" aria-label="Review queue">
        <button
          v-for="item in items"
          :key="item.id"
          class="queue-item"
          :class="{ selected: item.id === selectedItem?.id }"
          type="button"
          @click="selectedId = item.id"
        >
          <span class="queue-title">{{ item.title }}</span>
          <span class="queue-meta">{{ item.risk_level }} risk · {{ item.customer_tier }}</span>
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
          <template v-if="allowedActions.length === 0">
            <p class="terminal-notice">No further actions available — this item is {{ selectedItem.status }}.</p>
          </template>
          <template v-else>
            <button
              v-if="allowedActions.includes('claim')"
              type="button"
              :disabled="Boolean(pendingAction)"
              @click="performAction('claim')"
            >Claim</button>
            <button
              v-if="allowedActions.includes('approve')"
              type="button"
              :disabled="Boolean(pendingAction)"
              @click="performAction('approve')"
            >Approve</button>
            <button
              v-if="allowedActions.includes('reject')"
              type="button"
              :disabled="Boolean(pendingAction)"
              @click="performAction('reject')"
            >Reject</button>
            <button
              v-if="allowedActions.includes('escalate')"
              type="button"
              :disabled="Boolean(pendingAction)"
              @click="performAction('escalate')"
            >Escalate</button>
          </template>
        </div>
      </section>
    </section>
  </main>
</template>
