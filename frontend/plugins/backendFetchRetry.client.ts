import { backendRetryFetchOptions } from '@/utils/fetchRetry'

// 只換瀏覽器端的 $fetch：不加 .client 會連 Nitro 伺服器端的 $fetch 一起改。不能用 app.config，ofetch 不會讀
export default defineNuxtPlugin(() => {
  const { apiBaseUrl } = useRuntimeConfig().public
  globalThis.$fetch = globalThis.$fetch.create(
    backendRetryFetchOptions(apiBaseUrl, () => window.location.href),
  ) as typeof globalThis.$fetch
})
