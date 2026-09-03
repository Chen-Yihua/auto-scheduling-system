<script setup lang="ts">
import { useGithub } from '@/composables/useGithub'
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

const loading = ref(true);

onMounted(async () => {
  loading.value = true;
  await fetchGoogleCalendars();
  await fetchGithubIssues();
  await fetchJiraIssues();

  loading.value = false;
});
</script>

<template>

  <div class="flex justify-end p-6">
    <TaskForm />
  </div>

  <div class="p-4">
    <MoodleAssignments />
    <Leetcode />
    <News />
    <GithubIssuesList :issues="githubIssues" :loading="loading" :is-stale="githubStale" :synced-at="githubSyncedAt" />
    <JiraIssuesList :issues="jiraIssues" :loading="loading" :domain="domain" :is-stale="jiraStale" :synced-at="jiraSyncedAt" />
    <GoogleCalendarEmbed
      :id="primaryCalendarId"
      :calendar-ids="calendarIds"
      :connect="isConnected"
    />
  </div>
</template>
