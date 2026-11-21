<script setup lang="ts">
import { useUser } from '@clerk/vue';
import AppHeader from '~/components/header/AppHeader.vue';
import ScheduleSuggestion from '~/components/tasks/ScheduleSuggestion.vue';
import LoginRequiredCard from '~/components/LoginRequiredCard.vue';

const { isSignedIn } = useUser();
</script>

<template>
  <div>
    <AppHeader />
    <div class="p-4 max-w-2xl mx-auto mt-4">
      <ScheduleSuggestion v-if="isSignedIn" />
      <LoginRequiredCard
        v-else-if="isSignedIn === false"
        title="排程建議"
        icon="i-lucide-calendar-clock"
        message="登入後即可查看排程建議"
      />
    </div>
  </div>
</template>
