<script setup lang="ts">
import { useGithub } from '@/composables/useGithub'
import { SignedIn, SignedOut, useUser } from '@clerk/vue'
import GithubIssuesList from './GithubIssuesList.vue'
import Leetcode from './Leetcode.vue'
import JiraIssuesList from './JiraIssuesList.vue'
import News from './News.vue'
import TaskForm from './TaskForm.vue'
import GoogleCalendarEmbed from './GoogleCalendarEmbed.vue';
import MoodleAssignments from './MoodleAssignments.vue'

const { issues: githubIssues, fetchGithubIssues, isStale: githubStale, syncedAt: githubSyncedAt } = useGithub();
const { issues: jiraIssues, fetchJiraIssues, domain, isStale: jiraStale, syncedAt: jiraSyncedAt } = useJira();
const { calendarIds, primaryCalendarId, fetchGoogleCalendars, isConnected } = useGoogleCalendar();
const { isSignedIn } = useUser();

const loading = ref(true);

async function loadDashboardData() {
  loading.value = true;
  await fetchGoogleCalendars();
  await fetchGithubIssues();
  await fetchJiraIssues();
  loading.value = false;
}

// 這幾個都是需要授權才能查的個人資料，還沒登入時打了只會是 401，
// 不該讓訪客一進頁面就看到一排「抓取失敗」的錯誤提示
watch(isSignedIn, (signedIn) => {
  if (signedIn === undefined) return; // Clerk 還在初始化，先不動作
  if (signedIn) {
    loadDashboardData();
  } else {
    loading.value = false;
  }
}, { immediate: true });
</script>

<template>

  <div class="flex justify-end p-6">
    <TaskForm />
  </div>

  <div class="p-4">
    <Leetcode />
    <News />

    <SignedIn>
      <MoodleAssignments />
      <GithubIssuesList :issues="githubIssues" :loading="loading" :is-stale="githubStale" :synced-at="githubSyncedAt" />
      <JiraIssuesList :issues="jiraIssues" :loading="loading" :domain="domain" :is-stale="jiraStale" :synced-at="jiraSyncedAt" />
      <GoogleCalendarEmbed
        :id="primaryCalendarId"
        :calendar-ids="calendarIds"
        :connect="isConnected"
      />
    </SignedIn>

    <SignedOut>
      <div class="text-center py-16 text-gray-500 dark:text-gray-400">
        <UIcon name="i-lucide-lock" class="w-10 h-10 mx-auto mb-3" />
        <p class="text-lg font-medium">登入後即可查看你的任務、行事曆與整合服務</p>
        <p class="text-sm mt-1">點右上角「登入」開始使用</p>
      </div>
    </SignedOut>
  </div>
</template>
