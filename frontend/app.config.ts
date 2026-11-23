// 色階定義在 assets/css/tailwind.css
const lightSolid = (['secondary', 'info', 'success', 'warning'] as const).map((color) => ({ color, variant: 'solid' as const, class: 'text-black' }))

export default defineAppConfig({
  ui: {
    colors: {
      primary: 'steel',
      secondary: 'blush',
      info: 'haze',
      success: 'fern',
      warning: 'sand',
      error: 'cherry',
      neutral: 'ash',
    },
    // 次要色、提示、成功、提醒是淺色，實心時配黑字（其他實心色塊預設白字）
    button: { compoundVariants: lightSolid },
    badge: {
      compoundVariants: lightSolid,
      // Nuxt UI 的 xs、sm 標籤是寫死的 8px、10px，中文讀不出來
      variants: {
        size: {
          xs: { base: 'text-xs' },
          sm: { base: 'text-xs px-2 py-0.5' },
          md: { base: 'text-sm px-2.5 py-0.5' },
        },
      },
    },
    // 卡片標題和內容之間用留白分開，不畫分隔線；Nuxt UI 會把這裡的 class 接在預設值後面，所以要明確寫 divide-y-0 蓋掉
    card: {
      slots: {
        root: 'rounded-2xl',
        header: 'px-5 pt-5 pb-0 sm:px-6 sm:pt-6',
        body: 'p-5 sm:p-6',
        footer: 'px-5 pb-5 pt-0 sm:px-6 sm:pb-6',
      },
      variants: {
        variant: {
          outline: { root: 'divide-y-0' },
        },
      },
    },
  },
});
