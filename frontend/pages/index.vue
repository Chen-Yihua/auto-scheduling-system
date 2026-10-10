<script setup lang="ts">
import AppHeader from '~/components/header/AppHeader.vue'
import Dashboard from '~/components/dashboard/Dashboard.vue'

// /oauth/callback 也使用這個頁面（網址已在 Google Cloud Console 登記）。
// key 固定，網址換回 / 時才不會重新掛載整個頁面
definePageMeta({ alias: ['/oauth/callback'], key: 'dashboard' })

useGoogleOAuthCallback()
</script>

<template>
  <div>
    <AppHeader />
    <Dashboard />
  </div>
</template>
