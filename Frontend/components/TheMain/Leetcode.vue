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
  <div class="space-y-4">
    <h2 class="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-white">
      <UIcon name="custom-leetcode" class="w-5 h-5" />
      LeetCode 每日一題
    </h2>

    <!-- 這裡永遠只放一張卡片，而且固定嵌在右側窄欄位裡——sm/lg 那些多欄
    斷點是照「瀏覽器視窗」寬度判斷，不是這個容器的寬度，桌面版視窗一寬就會
    被硬切成 3 欄、字擠成一長條，所以這裡不用任何響應式多欄設定 -->
    <div class="grid grid-cols-1 gap-4">
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
          <!-- 標題已經在區塊標題（LeetCode 每日一題）交代過了，卡片本身的
          header 只需要跟 GitHub/Jira 的單張卡片一樣，顯示這筆資料自己的
          標題＋標籤，不用再重複 icon 或「Daily Problem」字樣 -->
          <div class="flex justify-between items-center w-full gap-2">
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
  </div>
</template>