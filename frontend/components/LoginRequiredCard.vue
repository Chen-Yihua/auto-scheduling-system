<script setup lang="ts">
import CardTitle from '~/components/CardTitle.vue';
// 訪客看到的卡片，標題和登入後相同，讓版面不變
defineProps<{
  title: string;
  icon: string;
  iconClass?: string;
  message: string;
}>();
</script>

<template>
  <UCard>
    <template #header>
      <CardTitle :title="title" :icon="icon" :icon-class="iconClass" />
    </template>

    <div class="text-center text-sm text-muted py-6">
      {{ message }}
    </div>
  </UCard>
</template>
