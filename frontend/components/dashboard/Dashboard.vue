<script setup lang="ts">
import { useUser } from '@clerk/vue';
import { useGoogleCalendarAuth } from '@/composables/useGoogleCalendarAuth';
import LoginRequiredCard from '~/components/LoginRequiredCard.vue';
import Leetcode from '~/components/dashboard/Leetcode.vue';
import News from '~/components/dashboard/News.vue';
import TaskEditModal from '~/components/tasks/TaskEditModal.vue';
import TodayTasks from '~/components/dashboard/TodayTasks.vue';
import GoogleCalendarEmbed from '~/components/dashboard/GoogleCalendarEmbed.vue';

const { calendarIds, primaryCalendarId, fetchGoogleCalendars, isConnected, awaitingFirstResult: calendarLoading, unavailable: calendarUnavailable, calendarReloadToken } = useGoogleCalendar();
const { isSignedIn } = useUser();
const { connecting: googleConnecting, connectedCount: googleConnectedCount } = useGoogleCalendarAuth();

// 未登入時不抓，否則訪客會看到一排錯誤提示
watch(isSignedIn, (signedIn) => {
  if (signedIn === undefined) return; // Clerk 還在初始化，先不動作
  if (signedIn) {
    fetchGoogleCalendars();
  }
}, { immediate: true });

// 授權在背景完成後重新查詢，卡片才會從「連接中」換成行事曆
watch(googleConnectedCount, () => {
  fetchGoogleCalendars();
});
</script>

<template>
  <div class="p-4">
    <!-- 今日卡片的「修改」要用這個視窗；訪客不掛載，它掛載時會讀需要登入的資料 -->
    <TaskEditModal v-if="isSignedIn" />
    <!-- Clerk 初始化完成前不顯示，避免已登入的人先看到「請先登入」 -->
    <div
      v-if="isSignedIn !== undefined"
      class="grid grid-cols-1 lg:grid-cols-[320px_1fr_320px] gap-6 mt-4 items-start"
    >
      <div class="space-y-6">
        <TodayTasks v-if="isSignedIn" />
        <LoginRequiredCard v-else title="今日" icon="i-lucide-calendar-check" message="登入後即可查看今天的任務" />
      </div>

      <div>
        <GoogleCalendarEmbed
          v-if="isSignedIn"
          :id="primaryCalendarId"
          :calendar-ids="calendarIds"
          :connect="isConnected"
          :connecting="googleConnecting"
          :loading="calendarLoading"
          :unavailable="calendarUnavailable"
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
