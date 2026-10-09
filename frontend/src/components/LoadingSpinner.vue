<!-- frontend/src/components/LoadingSpinner.vue -->
<template>
  <div class="spinner-overlay">
    <div class="spinner"></div>
    <p>Chargement...</p>
  </div>
</template>

<style scoped>
.spinner-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(255, 255, 255, 0.8);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}
.spinner {
  width: 40px; height: 40px;
  border: 4px solid #e2e8f0;
  border-top-color: #0ea5e9;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
p { margin-top: 1rem; color: #475569; font-weight: 500; }
</style>