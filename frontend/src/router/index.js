// frontend/src/router/index.js
import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

// Imports statiques pour les vues principales (meilleur UX au chargement initial)
import LoginView from '@/views/LoginView.vue';
import DashboardView from '@/views/DashboardView.vue';
import RisksView from '@/views/RisksView.vue';
import AppsView from '@/views/AppsView.vue'; // ← Import direct pour éviter le flash blanc lazy-load
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
    component: AppLayout, // Conteneur parent (Header + Menu + Router-View)
    children: [
      {
        path: '', // Racine -> Redirection vers Dashboard
        redirect: '/dashboard',
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: DashboardView,
        meta: { requiresAuth: true, module: 'dashboard', action: 'read' },
      },
      {
        path: 'risks',
        name: 'Risks',
        component: RisksView,
        meta: { requiresAuth: true, module: 'risks', action: 'read' },
      },
      {
        path: 'apps', // ⚠️ Chemin relatif 'apps' car on est DANS les children du '/'
        name: 'AppsInventory',
        component: AppsView,
        meta: { requiresAuth: true, module: 'apps', action: 'read' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*', // Catch-all pour les URLs inconnues
    name: 'NotFound',
    component: NotFoundView,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// Guard global pour protéger les routes privées
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

  // 3. Vérification des permissions RBAC
  if (to.meta.module && authStore.isAuthenticated) {
    // Attente si les permissions ne sont pas encore chargées (race condition après refresh page)
    if (!authStore.permissions || Object.keys(authStore.permissions).length === 0) {
      try { 
        await authStore.fetchPermissions(); 
      } catch(e) { 
        console.error("Erreur récupération permissions:", e);
      }
    }
    
    const hasPermission = authStore.canAccessModule(to.meta.module, to.meta.action || 'read');
    
    if (!hasPermission) {
      console.warn(`Accès refusé : module=${to.meta.module}, action=${to.meta.action}`);
      return next({ name: 'Dashboard' }); // Redirige vers dashboard si accès refusé
    }
  }

  next();
});

export default router;