<script setup lang="ts">
import { useUser } from '@clerk/vue'
import { usePlatformItems } from '~/composables/usePlatformItems'
import AppHeader from '~/components/header/AppHeader.vue'
import MoodleAssignmentsList from '~/components/platforms/MoodleAssignmentsList.vue'
import LoginRequiredCard from '~/components/LoginRequiredCard.vue'

const { isSignedIn } = useUser()
const { items, fetchItems, isStale, syncedAt, authError, notLinked, loading } = usePlatformItems('moodle')

watch(isSignedIn, (signedIn) => {
  if (signedIn) fetchItems()
}, { immediate: true })
</script>

<template>
  <div>
    <AppHeader />
    <div class="p-4 max-w-2xl mx-auto mt-4">
      <NuxtLink to="/" class="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4">
        <UIcon name="i-lucide-arrow-left" class="w-4 h-4" />
        返回主頁
      </NuxtLink>

      <MoodleAssignmentsList
        v-if="isSignedIn"
        :assignments="items"
        :loading="loading"
        :is-stale="isStale"
        :synced-at="syncedAt"
        :auth-error="authError"
        :not-linked="notLinked"
      />
      <LoginRequiredCard
        v-else-if="isSignedIn === false"
        title="Moodle 作業"
        icon="custom:moodle"
        message="登入後即可查看 Moodle 作業"
      />
    </div>
  </div>
</template>
