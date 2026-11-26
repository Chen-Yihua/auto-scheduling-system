<script setup lang="ts">
import NoticeBox from '~/components/NoticeBox.vue';
import CardTitle from '~/components/CardTitle.vue';
import { computed } from 'vue';
import type { JiraIssue } from '~/types/jira';
import StaleDataBanner from './StaleDataBanner.vue';
import SyncStatus from './SyncStatus.vue';

const props = defineProps<{
  issues: JiraIssue[];
  loading: boolean;
  domain?: string // 可選，從 props 傳入 Jira 網域
  isStale?: boolean;
  syncedAt?: string | null;
  authError?: boolean;
  notLinked?: boolean;
  // 已存的憑證無法讀取，要重新連結
  needsReauth?: boolean;
  // 帳號檢查失敗而且沒有已知的結果
  unavailable?: boolean;
  // 不傳則顯示全部
  limit?: number;
  // 有傳才顯示「立即同步」按鈕
  onSync?: () => void | Promise<void>;
  syncing?: boolean;
}>();

const displayedIssues = computed(() =>
  props.limit ? props.issues.slice(0, props.limit) : props.issues
);
const hasMoreIssues = computed(() => !!props.limit && props.issues.length > props.limit);

const openJiraIssue = (key: string) => {
  // 沒有 domain 時不能用寫死的網域，否則會連到別人的 Jira
  if (!props.domain) return;
  // domain 可能帶 https://
  const domain = props.domain.replace(/^https?:\/\//, '');
  window.open(`https://${domain}/browse/${key}`, '_blank');
};
</script>

<template>
  <UCard>
    <template #header>
      <CardTitle icon="mdi:jira" title="Jira 指派任務" />
    </template>

    <SyncStatus :synced-at="syncedAt ?? null" :on-sync="onSync" :syncing="syncing ?? false" />

    <StaleDataBanner
      :stale="isStale ?? false"
      :synced-at="syncedAt ?? null"
      :has-items="issues.length > 0"
      :auth-error="authError ?? false"
      platform-label="Jira"
    />

    <div v-if="loading">
      <USkeleton v-for="i in 3" :key="i" class="h-24 mb-4" />
    </div>

    <div
      v-else-if="unavailable"
      class="text-center text-sm text-muted py-6"
    >
      暫時無法載入，請稍後再試
    </div>

    <NoticeBox v-else-if="needsReauth" icon="i-lucide-key-round" class="my-4">
      Jira 憑證無法讀取。點右上角的頭像，在 <strong>金鑰</strong> 頁重新連結。
    </NoticeBox>

    <NoticeBox v-else-if="notLinked" icon="i-lucide-link" class="my-4">
      尚未綁定 Jira 帳號。點右上角的頭像，在 <strong>金鑰</strong> 頁加入。
    </NoticeBox>

    <div v-else-if="issues.length" class="grid grid-cols-1 gap-4">
      <UCard
        v-for="issue in displayedIssues"
        :key="issue.id"
        :ui="{
          root: 'cursor-pointer hover:shadow-lg transition-transform duration-300 ease-in-out transform scale-100 hover:scale-105',
        }"
        @click="openJiraIssue(issue.key)"
      >
        <template #header>
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold">{{ issue.key }}</div>
            <UBadge color="primary" variant="subtle" size="sm">
              {{ issue.status }}
            </UBadge>
          </div>
        </template>

        <div class="flex items-center gap-2 mb-1">
          <img v-if="issue.iconUrl" :src="issue.iconUrl" alt="類型" class="w-5 h-5" >
          <span class="text-sm text-toned">{{ issue.type }}</span>
        </div>

        <div class="font-medium mb-2">{{ issue.title }}</div>

        <div class="flex items-center gap-2">
          <UAvatar v-if="issue.avatar" :src="issue.avatar" size="xs" />
          <span class="text-xs text-muted">{{ issue.assignee }}</span>
        </div>

        <template v-if="issue.updated_at" #footer>
          <div class="text-xs text-dimmed">
            更新於 {{ new Date(issue.updated_at).toLocaleDateString() }}
          </div>
        </template>
      </UCard>
    </div>

    <div
      v-else
      class="text-center text-sm text-muted py-6"
    >
      尚無資料
    </div>

    <template v-if="hasMoreIssues" #footer>
      <NuxtLink to="/jira" class="text-sm text-primary hover:underline">
        查看全部（{{ issues.length }}）
      </NuxtLink>
    </template>
  </UCard>
</template>