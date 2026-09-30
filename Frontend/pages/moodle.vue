<script setup lang="ts">
import { useUser } from '@clerk/vue'
import TheHeader from '~/components/TheHeader/index.vue'
import MoodleAssignments from '~/components/TheMain/MoodleAssignments.vue'
import LoginRequiredCard from '~/components/TheMain/LoginRequiredCard.vue'

const { isSignedIn } = useUser()
</script>

<template>
  <div>
    <TheHeader />
    <div class="p-4 max-w-2xl mx-auto mt-4">
      <NuxtLink to="/" class="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4">
        <UIcon name="i-lucide-arrow-left" class="w-4 h-4" />
        返回主頁
      </NuxtLink>

      <MoodleAssignments v-if="isSignedIn" />
      <LoginRequiredCard
        v-else-if="isSignedIn === false"
        title="Moodle 作業"
        icon="custom:moodle"
        message="登入後即可查看 Moodle 作業"
      />
    </div>
  </div>
</template>
