<!-- frontend/src/components/AppLayout.vue -->
<template>
  <div class="layout-container">
    <!-- Header fixe -->
    <header class="app-header">
      <div class="logo-area">
        <span class="shield-icon">🛡️</span>
        <h1>PGCC <small>v0.5</small></h1>
      </div>
      
      <nav class="main-nav" v-if="authStore.isAuthenticated">
        <router-link 
          v-for="item in visibleMenuItems" 
          :key="item.path" 
          :to="item.path" 
          class="nav-item"
        >
          {{ item.label }}
        </router-link>
      </nav>

      <div class="user-area" v-if="authStore.isAuthenticated">
        <span class="user-role">{{ authStore.role }}</span>
        <button @click="handleLogout" class="logout-btn">Déconnexion</button>
      </div>
    </header>

    <!-- Contenu principal : utilise router-view au lieu de slot -->
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
const router = useRouter();

// Menu dynamique basé sur les permissions backend
const allMenuItems = [
  { path: '/dashboard', label: 'Tableau de bord', module: 'dashboard' },
  { path: '/risks', label: 'Registre des risques', module: 'risks' },
];

const visibleMenuItems = computed(() =>
  allMenuItems.filter(item => authStore.canAccessModule(item.module))
);

function handleLogout() {
  authStore.logout();
}
</script>

<style scoped>
.layout-container { display: flex; flex-direction: column; height: 100vh; background: #f8fafc; }
.app-header { 
  display: flex; justify-content: space-between; align-items: center; 
  padding: 0.75rem 1.5rem; background: #fff; border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.logo-area { display: flex; align-items: center; gap: 0.5rem; }
.shield-icon { font-size: 1.5rem; color: #0ea5e9; }
.main-nav { display: flex; gap: 1.5rem; }
.nav-item { text-decoration: none; color: #475569; font-weight: 500; transition: color 0.2s; }
.nav-item:hover, .nav-item.router-link-active { color: #0ea5e9; font-weight: 600; }
.user-area { display: flex; align-items: center; gap: 1rem; }
.user-role { font-size: 0.85rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
.logout-btn { 
  padding: 0.4rem 0.8rem; background: #fee2e2; color: #dc2626; 
  border: none; border-radius: 4px; cursor: pointer; font-size: 0.85rem; font-weight: 600;
}
.logout-btn:hover { background: #fecaca; }
.app-main { flex: 1; overflow-y: auto; padding: 1.5rem; }
</style>