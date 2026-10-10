<script setup lang="ts">
import { computed, ref } from 'vue'

const { data: stories, error, status } = await useLazyAsyncData('hackerNews', async () => {
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
  <UCard>
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon name="i-lucide-flame" class="w-5 h-5 text-orange-500" />
        <span class="text-lg font-semibold text-gray-900 dark:text-white">Hacker News</span>
      </div>
    </template>

    <USkeleton v-if="isLoading" class="h-64 rounded-lg" />

    <p
      v-else-if="error || !stories || stories.length === 0"
      class="text-sm text-gray-500 dark:text-gray-400 text-center py-6"
    >
      暫時無法載入新聞，請稍後再試。
    </p>

    <template v-else>
      <ul class="space-y-1">
        <li
          v-for="(story, idx) in stories.slice(0, 3)"
          :key="idx"
          class="flex items-start gap-3 rounded-lg px-2 py-2 -mx-2 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/60"
        >
          <span class="mt-0.5 shrink-0 text-xs font-semibold text-gray-400 dark:text-gray-500 w-4 text-right">
            {{ idx + 1 }}
          </span>
          <div class="min-w-0">
            <a
              :href="story.url"
              target="_blank"
              rel="noopener"
              class="block text-sm font-medium text-gray-900 dark:text-white hover:underline line-clamp-2"
            >
              {{ story.title }}
            </a>
            <div class="text-xs text-gray-400 dark:text-gray-500 mt-1">
              {{ story.publishedAt }}
            </div>
          </div>
        </li>
      </ul>

      <UCollapsible v-model="isCollapsed" class="mt-2">
        <UButton
          variant="soft"
          color="info"
          size="sm"
          :icon="isCollapsed ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'"
          @click="() => { isCollapsed = !isCollapsed }"
        >
          {{ isCollapsed ? '顯示更多' : '收起' }}
        </UButton>

        <!-- Nuxt UI 3.1.0 的 slot 型別和新版 Vue 不相容（誤報）；升級後不再報錯時 vue-tsc 會提示移除 -->
        <!-- @vue-expect-error -->
        <template #content>
          <ul class="space-y-1 mt-2">
            <li
              v-for="(story, idx) in stories.slice(3)"
              :key="idx"
              class="flex items-start gap-3 rounded-lg px-2 py-2 -mx-2 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/60"
            >
              <span class="mt-0.5 shrink-0 text-xs font-semibold text-gray-400 dark:text-gray-500 w-4 text-right">
                {{ idx + 4 }}
              </span>
              <div class="min-w-0">
                <a
                  :href="story.url"
                  target="_blank"
                  rel="noopener"
                  class="block text-sm font-medium text-gray-900 dark:text-white hover:underline line-clamp-2"
                >
                  {{ story.title }}
                </a>
                <div class="text-xs text-gray-400 dark:text-gray-500 mt-1">
                  {{ story.publishedAt }}
                </div>
              </div>
            </li>
          </ul>
        </template>
      </UCollapsible>
    </template>
  </UCard>
</template>