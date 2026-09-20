<script setup lang="ts">
import { useGithub } from '@/composables/useGithub'
import { useUser } from '@clerk/vue'
import { useGoogleCalendarAuth } from '@/composables/useGoogleCalendarAuth'
import GithubIssuesList from './GithubIssuesList.vue'
import LoginRequiredCard from './LoginRequiredCard.vue'
import Leetcode from './Leetcode.vue'
import JiraIssuesList from './JiraIssuesList.vue'
import News from './News.vue'
import TaskForm from './TaskForm.vue'
import GoogleCalendarEmbed from './GoogleCalendarEmbed.vue';
import MoodleAssignments from './MoodleAssignments.vue'

const { issues: githubIssues, fetchGithubIssues, isStale: githubStale, syncedAt: githubSyncedAt, authError: githubAuthError, notLinked: githubNotLinked, loading: githubLoading } = useGithub();
const { issues: jiraIssues, fetchJiraIssues, domain, isStale: jiraStale, syncedAt: jiraSyncedAt, authError: jiraAuthError, notLinked: jiraNotLinked, loading: jiraLoading } = useJira();
const { calendarIds, primaryCalendarId, fetchGoogleCalendars, isConnected } = useGoogleCalendar();
const { isSignedIn } = useUser();
const { connecting: googleConnecting, connectedCount: googleConnectedCount } = useGoogleCalendarAuth();

// 三個各自獨立抓取、互不影響——任何一個失敗都不該卡住其他兩個
// （之前串成一條 await 鏈，其中一個丟出例外就會讓後面的都卡在 loading 動不了）
function loadDashboardData() {
  fetchGoogleCalendars();
  fetchGithubIssues();
  fetchJiraIssues();
}

// 這幾個都是需要授權才能查的個人資料，還沒登入時打了只會是 401，
// 不該讓訪客一進頁面就看到一排「抓取失敗」的錯誤提示
watch(isSignedIn, (signedIn) => {
  if (signedIn === undefined) return; // Clerk 還在初始化，先不動作
  if (signedIn) {
    loadDashboardData();
  }
}, { immediate: true });

// Google 授權是回到首頁之後才在背景完成的，完成時要重新查一次，卡片才會從「連接中」換成行事曆
watch(googleConnectedCount, () => {
  fetchGoogleCalendars();
});
</script>

<template>
  <div class="p-4">
    <!-- Clerk 還在初始化（isSignedIn 是 undefined）時先不畫，避免登入的人一進來先閃一下「請先登入」 -->
    <!-- 三欄式版面：左 待辦事項＋第三方平台任務、中 行事曆、右 動態消息／LeetCode。
    登入前後版面完全一樣：需要登入的卡片，訪客只看到標題加一句提示（LoginRequiredCard），
    位置不變；Hacker News／LeetCode 不需要登入，兩邊都照常顯示 -->
    <div
      v-if="isSignedIn !== undefined"
      class="grid grid-cols-1 lg:grid-cols-[320px_1fr_320px] gap-6 mt-4 items-start"
    >
      <div class="space-y-6">
        <template v-if="isSignedIn">
          <TaskForm />
          <MoodleAssignments />
          <GithubIssuesList :issues="githubIssues" :loading="githubLoading" :is-stale="githubStale" :synced-at="githubSyncedAt" :auth-error="githubAuthError" :not-linked="githubNotLinked" />
          <JiraIssuesList :issues="jiraIssues" :loading="jiraLoading" :domain="domain" :is-stale="jiraStale" :synced-at="jiraSyncedAt" :auth-error="jiraAuthError" :not-linked="jiraNotLinked" />
        </template>
        <template v-else>
          <LoginRequiredCard title="任務列表" icon="i-lucide-list-todo" message="登入後即可查看與新增你的任務" />
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
