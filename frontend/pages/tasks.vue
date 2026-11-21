<script setup lang="ts">
import { useUser } from '@clerk/vue';
import AppHeader from '~/components/header/AppHeader.vue';
import TaskForm from '~/components/tasks/TaskForm.vue';
import LoginRequiredCard from '~/components/LoginRequiredCard.vue';

const { isSignedIn } = useUser();
</script>

<template>
  <div>
    <AppHeader />
    <div class="p-4 max-w-5xl mx-auto mt-4">
      <TaskForm v-if="isSignedIn" />
      <LoginRequiredCard
        v-else-if="isSignedIn === false"
        title="任務列表"
        icon="i-lucide-list-todo"
        message="登入後即可查看與新增你的任務"
      />
    </div>
  </div>
</template>
