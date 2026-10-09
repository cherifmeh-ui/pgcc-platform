<!-- frontend/src/views/NotFoundView.vue -->
<template>
  <div class="not-found-container">
    <h1>404</h1>
    <p>Page non trouvée.</p>
    <router-link to="/" class="home-btn">Retour au tableau de bord</router-link>
  </div>
</template>

<style scoped>
.not-found-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 80vh;
  text-align: center;
}
h1 { font-size: 6rem; color: #ef4444; margin: 0; line-height: 1; }
p { font-size: 1.25rem; color: #64748b; margin-top: 1rem; }
.home-btn {
  margin-top: 2rem;
  padding: 0.75rem 1.5rem;
  background: #0ea5e9;
  color: white;
  text-decoration: none;
  border-radius: 6px;
  font-weight: 600;
  transition: background 0.2s;
}
.home-btn:hover { background: #0284c7; }
</style>