<script setup lang="ts">
import NoticeBox from '~/components/NoticeBox.vue';
import CardTitle from '~/components/CardTitle.vue';
import { computed } from 'vue';
import type { MoodleAssignment } from '~/types/moodle';
import StaleDataBanner from './StaleDataBanner.vue';
import SyncStatus from './SyncStatus.vue';
const props = defineProps<{
  assignments: MoodleAssignment[];
  loading: boolean;
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

const displayedAssignments = computed(() =>
  props.limit ? props.assignments.slice(0, props.limit) : props.assignments
);
const hasMoreAssignments = computed(() => !!props.limit && props.assignments.length > props.limit);

const openAssignment = (url: string) => {
  window.open(url, '_blank');
};
</script>


<template>
  <UCard>
    <template #header>
      <CardTitle icon="custom:moodle" title="Moodle 作業" />
    </template>

    <SyncStatus :synced-at="syncedAt ?? null" :on-sync="onSync" :syncing="syncing ?? false" />

    <StaleDataBanner
      :stale="isStale ?? false"
      :synced-at="syncedAt ?? null"
      :has-items="assignments.length > 0"
      :auth-error="authError ?? false"
      platform-label="Moodle"
    />

    <div
      v-if="unavailable"
      class="text-center text-sm text-muted py-6"
    >
      暫時無法載入，請稍後再試
    </div>

    <NoticeBox v-else-if="needsReauth" icon="i-lucide-key-round" class="my-4">
      Moodle 憑證無法讀取。點右上角的頭像，在 <strong>金鑰</strong> 頁重新連結。
    </NoticeBox>

    <NoticeBox v-else-if="notLinked" icon="i-lucide-link" class="my-4">
      尚未綁定 Moodle 帳號。點右上角的頭像，在 <strong>金鑰</strong> 頁加入。
    </NoticeBox>

    <div v-else-if="loading" class="flex justify-center items-center py-6">
      <UIcon name="i-lucide-loader" class="animate-spin w-6 h-6 text-primary" />
      <span class="ml-2 text-primary">載入中...</span>
    </div>

    <div v-else-if="assignments.length === 0" class="text-center text-sm text-muted py-6">
      目前沒有未繳作業
    </div>

    <div v-else class="grid grid-cols-1 gap-4">
      <UCard
        v-for="item in displayedAssignments"
        :key="item.url"
        class="rounded-lg bg-default ring ring-default divide-y divide-default cursor-pointer hover:shadow-lg transition-transform duration-300 ease-in-out transform scale-100 hover:scale-105"
        @click="openAssignment(item.url)"
      >
        <template #header>
          <div class="text-sm font-semibold">課程名稱 : {{ item.course_name }}</div>
        </template>

          <div class="font-medium mb-2">作業標題 : {{ item.title }}</div>

        <template #footer>
          <div class="text-sm text-muted">截止日期 : {{ item.due_date }}</div>
        </template>
      </UCard>
    </div>

    <template v-if="hasMoreAssignments" #footer>
      <NuxtLink to="/moodle" class="text-sm text-primary hover:underline">
        查看全部（{{ assignments.length }}）
      </NuxtLink>
    </template>
  </UCard>
</template>
