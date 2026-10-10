<script setup lang="ts">
import { reactive } from 'vue'
import { usePlatformItems } from '@/composables/usePlatformItems'
import { useUser } from '@clerk/vue'
import { useGoogleCalendarAuth } from '@/composables/useGoogleCalendarAuth'
import GithubIssuesList from '~/components/platforms/GithubIssuesList.vue'
import LoginRequiredCard from '~/components/LoginRequiredCard.vue'
import Leetcode from '~/components/dashboard/Leetcode.vue'
import JiraIssuesList from '~/components/platforms/JiraIssuesList.vue'
import News from '~/components/dashboard/News.vue'
import TaskForm from '~/components/tasks/TaskForm.vue'
import ScheduleSuggestion from '~/components/tasks/ScheduleSuggestion.vue'
import GoogleCalendarEmbed from '~/components/dashboard/GoogleCalendarEmbed.vue'
import MoodleAssignmentsList from '~/components/platforms/MoodleAssignmentsList.vue'

// reactive 讓 template 可以直接寫 github.items
const github = reactive(usePlatformItems('github'));
const jira = reactive(usePlatformItems('jira'));
const moodle = reactive(usePlatformItems('moodle'));
const { calendarIds, primaryCalendarId, fetchGoogleCalendars, isConnected, calendarReloadToken } = useGoogleCalendar();
const { isSignedIn } = useUser();
const { connecting: googleConnecting, connectedCount: googleConnectedCount } = useGoogleCalendarAuth();

// 各自獨立抓取，一個失敗不影響其他
function loadDashboardData() {
  fetchGoogleCalendars();
  github.fetchItems();
  jira.fetchItems();
  moodle.fetchItems();
}

// 未登入時不抓，否則訪客會看到一排錯誤提示
watch(isSignedIn, (signedIn) => {
  if (signedIn === undefined) return; // Clerk 還在初始化，先不動作
  if (signedIn) {
    loadDashboardData();
  }
}, { immediate: true });

// 授權在背景完成後重新查詢，卡片才會從「連接中」換成行事曆
watch(googleConnectedCount, () => {
  fetchGoogleCalendars();
});
</script>

<template>
  <div class="p-4">
    <!-- Clerk 初始化完成前不顯示，避免已登入的人先看到「請先登入」 -->
    <div
      v-if="isSignedIn !== undefined"
      class="grid grid-cols-1 lg:grid-cols-[320px_1fr_320px] gap-6 mt-4 items-start"
    >
      <div class="space-y-6">
        <template v-if="isSignedIn">
          <TaskForm :limit="5" />
          <ScheduleSuggestion />
          <MoodleAssignmentsList :assignments="moodle.items" :loading="moodle.loading" :is-stale="moodle.isStale" :synced-at="moodle.syncedAt" :auth-error="moodle.authError" :not-linked="moodle.notLinked" :limit="5" />
          <GithubIssuesList :issues="github.items" :loading="github.loading" :is-stale="github.isStale" :synced-at="github.syncedAt" :auth-error="github.authError" :not-linked="github.notLinked" :limit="5" />
          <JiraIssuesList :issues="jira.items" :loading="jira.loading" :domain="jira.account?.domain" :is-stale="jira.isStale" :synced-at="jira.syncedAt" :auth-error="jira.authError" :not-linked="jira.notLinked" :limit="5" />
        </template>
        <template v-else>
          <LoginRequiredCard title="任務列表" icon="i-lucide-list-todo" message="登入後即可查看與新增你的任務" />
          <LoginRequiredCard title="排程建議" icon="i-lucide-calendar-clock" message="登入後即可查看排程建議" />
          <LoginRequiredCard title="Moodle 作業" icon="custom:moodle" message="登入後即可查看 Moodle 作業" />
          <LoginRequiredCard title="GitHub 參與項目" icon="mdi:github" message="登入後即可查看 GitHub 參與項目" />
          <LoginRequiredCard title="Jira 指派任務" icon="mdi:jira" icon-class="text-blue-500" message="登入後即可查看 Jira 指派任務" />
        </template>
      </div>

      <div>
        <GoogleCalendarEmbed
          v-if="isSignedIn"
          :id="primaryCalendarId"
          :calendar-ids="calendarIds"
          :connect="isConnected"
          :connecting="googleConnecting"
          :reload-token="calendarReloadToken"
        />
        <LoginRequiredCard v-else title="Google 行事曆" icon="i-lucide-calendar" message="登入後即可查看 Google 行事曆" />
      </div>

      <div class="space-y-6">
        <News />
        <Leetcode />
      </div>
    </div>
  </div>
</template>
