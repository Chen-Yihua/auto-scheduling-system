<script setup lang="ts">
import type { DailyChallenge } from '~/types/leetcode'

const data = ref<DailyChallenge | null>(null);
const error = ref<{ message: string } | null>(null);
const toast = useToast()
const isCollapsed = ref(true)

async function fetchData() {
  try {
    error.value = null
    
    data.value = await $fetch<DailyChallenge>('/api/leetcode')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : 'Unknown error occurred'
    error.value = { message: msg }
    toast.add({
      title: 'API 呼叫失敗',
      description: msg,
      icon: 'i-lucide-alert-circle',
      color: 'error',
    })
  }
}

// 只在 client side 執行，避免 SSR 序列化錯誤
onMounted(() => {
  fetchData()
})

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
      <div class="flex items-center gap-2">
        <UIcon name="custom-leetcode" class="w-5 h-5" />
        <span class="text-lg font-semibold text-gray-900 dark:text-white">LeetCode 每日一題</span>
      </div>
    </template>

    <!-- Skeleton Loading -->
    <USkeleton v-if="!data && !error" class="h-64 rounded-lg" />

    <!-- 錯誤訊息 -->
    <template v-else-if="error">
      <p class="text-sm text-red-500 mb-3">{{ error.message }}</p>
      <UButton label="Retry" color="error" variant="soft" @click="fetchData" />
    </template>

    <!-- 題目內容 -->
    <template v-else>
      <div class="flex justify-between items-center w-full gap-2 mb-3">
        <span class="text-sm font-semibold truncate">{{ data?.question.title }}</span>
        <div class="flex flex-wrap items-center gap-1">
          <UBadge :color="difficultyColor(data?.question.difficulty)" variant="soft">
            {{ data?.question.difficulty }}
          </UBadge>
          <UBadge v-for="tag in data?.question.topicTags" :key="tag.slug" color="neutral" variant="soft">
            {{ tag.name }}
          </UBadge>
        </div>
      </div>

      <!-- 主內容，截斷顯示 -->
      <!-- v-html：內容是 LeetCode 官方 API 回傳的題目 HTML（第三方，但屬受信任來源），目前沒有另外過濾。
           若日後要顯示不受信任的內容，需先用 DOMPurify 清理 -->
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div class="prose max-w-none text-sm" v-html="mainContent" />

      <!-- Example 區塊 -->
      <UCollapsible v-model="isCollapsed" class="mt-4">
        <UButton
          variant="ghost" color="neutral" size="xs"
          :icon="isCollapsed ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'"
          @click="() => { isCollapsed = !isCollapsed }"
        >
          {{ isCollapsed ? 'Show Example ' : 'Close' }}
        </UButton>

        <!-- Nuxt UI 3.1.0 的 slot 型別寫法跟新版 Vue 型別檢查不相容（誤報，執行時正常）；升級 @nuxt/ui 後若檢查不再報錯，vue-tsc 會提示可以移除下面這行 -->
        <!-- @vue-expect-error -->
        <template #content>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div class="mt-2 prose max-w-none text-sm" v-html="exampleContent" />
        </template>
      </UCollapsible>
    </template>

    <!-- 題目連結 -->
    <template v-if="data && !error" #footer>
      <UButton :href="fullLink" label="Go to LeetCode" color="info" variant="subtle" />
    </template>
  </UCard>
</template>