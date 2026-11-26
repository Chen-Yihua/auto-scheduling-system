<script setup lang="ts">
import CardTitle from '~/components/CardTitle.vue';
import type { DailyChallenge } from '~/types/leetcode';
import { leetcodeDifficultyLabel } from '~/utils/labels';

const data = ref<DailyChallenge | null>(null);
const error = ref<{ message: string } | null>(null);
const toast = useToast();
const isCollapsed = ref(true);

async function fetchData() {
  try {
    error.value = null;
    
    data.value = await $fetch<DailyChallenge>('/api/leetcode');
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '發生未知錯誤';
    error.value = { message: msg };
    toast.add({
      title: 'API 呼叫失敗',
      description: msg,
      icon: 'i-lucide-alert-circle',
      color: 'error',
    });
  }
}

// 只在 client side 執行，避免 SSR 序列化錯誤
onMounted(() => {
  fetchData();
});

const fullLink = computed(() =>
  data.value?.link
    ? new URL(data.value.link, 'https://leetcode.com/').href
    : '#'
)

const difficultyColor = (difficulty: string | undefined) => {
  switch (difficulty) {
    case 'Easy':
      return 'success'
    case 'Medium':
      return 'warning'
    case 'Hard':
      return 'error'
    default:
      return 'neutral'
  }
}

const SPLITTER = '<p>&nbsp;</p>'

const mainContent = computed(() => {
  const content = data.value?.question.content ?? ''
  const index = content.indexOf(SPLITTER)
  if (index === -1) return content
  return content.slice(0, index).trim()
})

const exampleContent = computed(() => {
  const content = data.value?.question.content ?? ''
  const index = content.indexOf(SPLITTER)
  if (index === -1) return ''
  return content.slice(index).trim()
})



</script>

<template>
  <UCard>
    <template #header>
      <CardTitle icon="custom-leetcode" title="LeetCode 每日一題" />
    </template>

    <USkeleton v-if="!data && !error" class="h-64 rounded-lg" />

    <template v-else-if="error">
      <p class="text-sm text-error mb-3">{{ error.message }}</p>
      <UButton label="重試" color="error" variant="soft" @click="fetchData" />
    </template>

    <template v-else>
      <div class="mb-4 space-y-2">
        <p class="text-base font-semibold text-highlighted">{{ data?.question.title }}</p>
        <div class="flex flex-wrap items-center gap-1">
          <UBadge :color="difficultyColor(data?.question.difficulty)" variant="soft">
            {{ leetcodeDifficultyLabel(data?.question.difficulty) }}
          </UBadge>
          <UBadge v-for="tag in data?.question.topicTags" :key="tag.slug" color="neutral" variant="soft">
            {{ tag.name }}
          </UBadge>
        </div>
      </div>

      <!-- v-html：LeetCode 官方 API 的題目 HTML，視為受信任來源，沒有另外過濾 -->
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div class="prose max-w-none text-sm" v-html="mainContent" />

      <UCollapsible v-model="isCollapsed" class="mt-4">
        <UButton
          variant="ghost" color="neutral" size="xs"
          :icon="isCollapsed ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'"
          @click="() => { isCollapsed = !isCollapsed }"
        >
          {{ isCollapsed ? '顯示範例' : '收合' }}
        </UButton>

        <!-- Nuxt UI 3.1.0 的 slot 型別和新版 Vue 不相容（誤報）；升級後不再報錯時 vue-tsc 會提示移除 -->
        <!-- @vue-expect-error -->
        <template #content>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div class="mt-2 prose max-w-none text-sm" v-html="exampleContent" />
        </template>
      </UCollapsible>
    </template>

    <template v-if="data && !error" #footer>
      <UButton :href="fullLink" label="前往 LeetCode" color="info" variant="subtle" />
    </template>
  </UCard>
</template>