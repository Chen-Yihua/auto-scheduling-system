<script setup lang="ts">
import { computed, ref } from 'vue'

const { data: stories, error, status } = await useLazyAsyncData('hackerNews', async () => {
  await new Promise(resolve => setTimeout(resolve, 2000))
  const ids = await $fetch<number[]>('https://hacker-news.firebaseio.com/v0/topstories.json')
  const top10 = ids.slice(0, 10)
  const items = await Promise.all(
    top10.map(id =>
      $fetch<{ title: string; url: string; time: number }>(
        `https://hacker-news.firebaseio.com/v0/item/${id}.json`
      )
    )
  )
  return items.map(item => {
    const d = new Date(item.time * 1000)
    const YYYY = d.getFullYear()
    const MM = String(d.getMonth() + 1).padStart(2, '0')
    const DD = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return {
      title: item.title,
      url: item.url,
      publishedAt: `${YYYY}-${MM}-${DD} ${hh}:${mm}`
    }
  })
  }
)

const isLoading = computed(() => status.value === 'pending')
const isCollapsed = ref(true)
</script>

<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
    <!-- Loading Skeleton -->
    <USkeleton v-if="isLoading" class="h-80 rounded-lg" />
    <!-- Error Card -->
    <UCard
      v-else-if="error || !stories || stories.length === 0"
      color="red"
      icon="i-lucide-alert-circle"
      class="mb-4"
    >
      <template #header>
        <p class="font-semibold text-red-700">
          暫時無法載入新聞，請稍後再試。
        </p>
      </template>
    </UCard>

    <!-- News List -->

    <UCard v-else class="mb-4 " :error="error">
      <template #header>
        <p class ="font-medium text-black dark:text-white">
          Hacker News
        </p>
      </template>
      <!-- 顯示前三則新聞 -->
      <ul class="space-y-4">
        <li
          v-for="(story, idx) in stories.slice(0, 3)"
          :key="idx"
          class="border-b pb-2"
        >
          <div>
            <a
              :href="story.url"
              target="_blank"
              rel="noopener"
              class="text-lg font-medium text-black dark:text-white hover:underline"
            >
              {{ story.title }}
            </a>
            <div class="text-sm text-gray-500">
              發佈時間：{{ story.publishedAt }}
            </div>
          </div>
        </li>
      </ul>

      <!-- 折疊後的其餘新聞 -->
      <UCollapsible class="mt-4" v-model="isCollapsed">
        <UButton
          variant="soft"
          color="info"
          size="sm"
          :icon="isCollapsed ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'"
          @click="isCollapsed = !isCollapsed"
        >
          {{ isCollapsed ? '顯示更多' : '收起' }}
        </UButton>

        <template #content>
          <ul class="space-y-4">
            <li
              v-for="(story, idx) in stories.slice(3)"
              :key="idx"
              class="border-b pb-2"
            >
              <div>
                <a
                  :href="story.url"
                  target="_blank"
                  rel="noopener"
                  class="text-lg font-medium text-black dark:text-white hover:underline"
                >
                  {{ story.title }}
                </a>
                <div class="text-sm text-gray-500">
                  發佈時間：{{ story.publishedAt }}
                </div>
              </div>
            </li>
          </ul>
        </template>
      </UCollapsible>
    </UCard>
  </div>

</template>