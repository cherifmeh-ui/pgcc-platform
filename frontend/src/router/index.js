// frontend/src/router/index.js
import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

// IMPORTS STATIQUES DIRECTS (Pas de lazy loading pour l'instant, pour debug)
import LoginView from '@/views/LoginView.vue';
import DashboardView from '@/views/DashboardView.vue';
import RisksView from '@/views/RisksView.vue';
import NotFoundView from '@/views/NotFoundView.vue';
import AppLayout from '@/components/AppLayout.vue';

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: LoginView,
    meta: { requiresGuest: true },
  },
  {
    path: '/',
    component: AppLayout, // Conteneur parent
    children: [
      {
        path: '', // Redirige racine vers dashboard
        redirect: '/dashboard',
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: DashboardView, // Enfant injecté dans <slot /> de AppLayout
        meta: { requiresAuth: true, module: 'dashboard' },
      },
      {
        path: 'risks',
        name: 'Risks',
        component: RisksView, // Enfant injecté dans <slot /> de AppLayout
        meta: { requiresAuth: true, module: 'risks', action: 'read' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: NotFoundView,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// Guard global simplifié pour éviter blocages silencieux
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore();

  // 1. Route publique (Login) -> Si déjà connecté, aller au Dashboard
  if (to.meta.requiresGuest && authStore.isAuthenticated) {
    return next('/dashboard');
  }

  // 2. Route privée -> Si non connecté, aller au Login
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return next({ name: 'Login', query: { redirect: to.fullPath } });
  }

  // 3. Vérification permissions (si store prêt)
  if (to.meta.module && authStore.isAuthenticated) {
    // Petite attente si les permissions ne sont pas encore chargées (race condition)
    if (!authStore.permissions || Object.keys(authStore.permissions).length === 0) {
       try { await authStore.fetchPermissions(); } catch(e) {}
    }
    
    const hasPermission = authStore.canAccessModule(to.meta.module, to.meta.action || 'read');
    if (!hasPermission) {
      console.warn(`Accès refusé module ${to.meta.module}`);
      return next({ name: 'Dashboard' }); 
    }
  }

  next();
});

export default router;