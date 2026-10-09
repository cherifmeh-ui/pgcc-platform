<!-- frontend/src/App.vue -->
<template>
  <div id="pgcc-app">
    <LoadingSpinner v-if="isLoadingGlobal" />
    <ToastNotification />
    <router-view />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import LoadingSpinner from '@/components/LoadingSpinner.vue';
import ToastNotification from '@/components/ToastNotification.vue';

const router = useRouter();
const isLoadingGlobal = ref(false);

// Écouter changements de route pour spinner global
router.beforeResolve(() => { isLoadingGlobal.value = true; });
router.afterEach(() => { setTimeout(() => { isLoadingGlobal.value = false; }, 300); });
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; background: #f5f7fa; color: #1a1a1a; }
#pgcc-app { min-height: 100vh; }
</style>