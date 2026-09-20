<script setup lang="ts">
// Google 授權完成後會導回 /oauth/callback?code=...（這個網址是在 Google Cloud Console
// 登記的，不能改），所以讓它跟首頁共用同一個頁面：導回來的第一眼就是完整的首頁。
// key 固定成同一個值，讓兩個網址共用同一個頁面實例——處理完把網址換成 / 時，
// 不會把整個畫面卸載再重新載入一次（所有卡片又重新抓資料）
definePageMeta({ alias: ['/oauth/callback'], key: 'dashboard' })

useGoogleOAuthCallback()
</script>

<template>
  <div>
    <TheHeader />
    <TheMain />
  </div>
</template>
