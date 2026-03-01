// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',
  devtools: { enabled: true },
  css: ['~/assets/css/tailwind.css'],
  modules: [
    '@nuxt/eslint',
    '@nuxt/test-utils',
    '@nuxt/ui',
    '@nuxt/icon',
    '@clerk/nuxt',
    '@nuxt/test-utils/module',
  ],
  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
      apiGoogleClientId: process.env.GOOGLE_CLIENT_ID,
      frontEndUrl: process.env.NUXT_PUBLIC_FRONTEND_URL || 'http://localhost:3000',
    },
    private: {
      apiGoogleSecret: process.env.GOOGLE_CLIENT_SECRET,
    },
  },
  icon: {
    customCollections: [{
      prefix: 'custom',
      dir: './assets/icons'
    }]
  }
});
