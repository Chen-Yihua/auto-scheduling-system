<script setup lang="ts">
import { useUser } from '@clerk/vue';
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { useTaskForm } from '~/composables/useTaskForm';
import AppHeader from '~/components/header/AppHeader.vue';
import TaskEditModal from '~/components/tasks/TaskEditModal.vue';
import TaskForm from '~/components/tasks/TaskForm.vue';
import LoginRequiredCard from '~/components/LoginRequiredCard.vue';

const { isSignedIn } = useUser();
const { showEditModal } = useTaskForm();

// 不用 VueUse 的 useWindowScroll：@vueuse/core 不是 package.json 列出的依賴
const pastViewport = ref(false);
const updatePastViewport = () => {
  pastViewport.value = window.scrollY > window.innerHeight;
};
onMounted(() => window.addEventListener('scroll', updatePastViewport, { passive: true }));
onBeforeUnmount(() => window.removeEventListener('scroll', updatePastViewport));
const scrollToTop = () => window.scrollTo({ top: 0, behavior: 'smooth' });
</script>

<template>
  <div>
    <AppHeader />
    <div class="p-4 max-w-7xl mx-auto mt-4">
      <!-- 任務列表的「新增任務」「編輯」要用這個視窗；訪客不掛載，它掛載時會讀需要登入的資料 -->
      <TaskEditModal v-if="isSignedIn" />
      <TaskForm v-if="isSignedIn" />
      <LoginRequiredCard
        v-else-if="isSignedIn === false"
        title="任務列表"
        icon="i-lucide-list-todo"
        message="登入後即可查看與新增你的任務"
      />
    </div>
    <UButton
      v-if="isSignedIn && pastViewport && !showEditModal"
      class="fixed bottom-6 right-6 z-50 rounded-full"
      icon="i-lucide-arrow-up"
      size="lg"
      aria-label="回到頂端"
      @click="scrollToTop"
    />
  </div>
</template>
