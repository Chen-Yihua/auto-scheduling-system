<script setup lang="ts">

let data = ref<any>(null);
let error = ref<{ message: string } | null>(null);
const toast = useToast()
const isCollapsed = ref(true)

async function fetchData() {
  try {
    error.value = null
    
    data.value = await $fetch('/api/leetcode')
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
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">

    <!-- 🕓 Skeleton Loading -->
    <USkeleton v-if="!data && !error" class="h-80 rounded-lg" />

    <!-- ❌ Error Card -->
    <UCard v-else-if="error" color="red" icon="i-lucide-alert-circle" class="mb-4">
      <template #header>
        <p class="font-semibold text-red-700">Failed to load LeetCode Daily Problem</p>
      </template>
      <p class="text-sm text-red-500">{{ error.message }}</p>
      <template #footer>
        <UButton label="Retry" color="error" variant="soft" @click="fetchData" />
      </template>
    </UCard>

    <UCard v-else class="mb-4 " :title="data?.question.title" :loading="!data && !error" :error="error">
      <template #header>
        <div class="flex justify-between items-center w-full">
          <!-- 左側：LeetCode icon + 題目名稱 -->
          <div class="flex items-center">
            <UIcon name="custom-leetcode" class="size-6" />
            <span class="ml-2 font-medium">Daily Problem: {{ data?.question.title }}</span>
          </div>

          <!-- 右側：難度與 Tags Badge -->
          <div class="flex flex-wrap items-center">
            <!-- 難度 Badge -->
            <UBadge :color="difficultyColor(data?.question.difficulty)" variant="soft" class="mx-1">
              {{ data?.question.difficulty }}
            </UBadge>

            <!-- 題目 Tags -->
            <UBadge v-for="tag in data?.question.topicTags" :key="tag.slug" color="neutral" variant="soft" class="mx-1">
              {{ tag.name }}
            </UBadge>
          </div>
        </div>
      </template>

      <!-- 主內容，截斷顯示 -->
      <div class="prose max-w-none text-sm" v-html="mainContent"></div>

      <!-- Example 區塊 -->
      <UCollapsible class="mt-4" v-model="isCollapsed">
        <UButton 
          variant="ghost" color="neutral" size="xs" 
          :icon="isCollapsed ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'"
          @click="isCollapsed = !isCollapsed"
        >
          {{ isCollapsed ? 'Show Example ' : 'Close' }}
        </UButton>

        <template #content>
          <div class="mt-2 prose max-w-none text-sm" v-html="exampleContent" />
        </template>
      </UCollapsible>
      <!-- 題目連結 -->
      <template #footer>
        <UButton :href="fullLink" label="Go to LeetCode" color="info" variant="subtle" />
      </template>
    </UCard>
  </div>

</template>