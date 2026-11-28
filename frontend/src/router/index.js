// frontend/src/router/index.js
import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

// Imports statiques directs des vues principales
import LoginView from '@/views/LoginView.vue';
import DashboardView from '@/views/DashboardView.vue';
import RisksView from '@/views/RisksView.vue';
import AppsView from '@/views/AppsView.vue';
import AssetsView from '@/views/AssetsView.vue';
import SuppliersView from '@/views/SuppliersView.vue';
import IsoComplianceView from '@/views/IsoComplianceView.vue';
import DocumentsView from '@/views/DocumentsView.vue'; // ⬅️ NOUVELLE VUE BIBLIOTHÈQUE
import NotFoundView from '@/views/NotFoundView.vue';
import AppLayout from '@/components/AppLayout.vue';

const routes = [
  // --- Route Publique : LOGIN ---
  {
    path: '/login',
    name: 'Login',
    component: LoginView,
    meta: { requiresGuest: true }, // Si déjà connecté, rediriger vers dashboard
  },

  // --- Routes Protégées : LAYOUT PRINCIPAL ---
  {
    path: '/',
    component: AppLayout, // Conteneur parent (Header + Menu Navigation)
    children: [
      // Redirection racine vers Dashboard
      { path: '', redirect: '/dashboard' },

      // ✅ CHEMINS RELATIFS (SANS SLASH INITIAL CAR ENFANTS DE '/')
      { 
        path: 'dashboard', 
        name: 'Dashboard', 
        component: DashboardView, 
        meta: { requiresAuth: true, module: 'dashboard', action: 'read' } 
      },
      
      { 
        path: 'risks', 
        name: 'Risks', 
        component: RisksView, 
        meta: { requiresAuth: true, module: 'risks', action: 'read' } 
      },
      
      { 
        path: 'apps', 
        name: 'AppsInventory', 
        component: AppsView, 
        meta: { requiresAuth: true, module: 'apps', action: 'read' } 
      },
      
      { 
        path: 'assets', 
        name: 'AssetsInventory', 
        component: AssetsView, 
        meta: { requiresAuth: true, module: 'assets', action: 'read' } 
      },
      
      { path: 'suppliers', name: 'Suppliers', component: SuppliersView, meta: { requiresAuth: true, module: 'suppliers', action: 'read' } },
      { 
        path: 'compliance', 
        name: 'IsoCompliance', 
        component: IsoComplianceView, 
        meta: { requiresAuth: true, module: 'iso27002', action: 'read' } 
      },
      
      { 
        path: 'documents', // ⬅️ AJOUTÉ ICI : Bibliothèque Documentaire
        name: 'Library', 
        component: DocumentsView, 
        meta: { requiresAuth: true, module: 'documents', action: 'read' } 
      },
    ],
  },

  // --- Catch-all : PAGE 404 ---
  {
    path: '/:pathMatch(.*)*', // Attrape toute URL non définie ci-dessus
    name: 'NotFound',
    component: NotFoundView,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

/**
 * Guard Global de Sécurité & Permissions RBAC
 */
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore();

  // Restore a cookie-backed session after a page reload before evaluating guards.
  if (!authStore.isAuthenticated && (to.meta.requiresAuth || to.meta.requiresGuest)) {
    await authStore.restoreSession();
  }

  // 1. Gestion Invités (Page Login)
  if (to.meta.requiresGuest && authStore.isAuthenticated) {
    return next('/dashboard');
  }

  // 2. Gestion Authentification Obligatoire
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return next({ name: 'Login', query: { redirect: to.fullPath } });
  }

  // 3. Vérification Fine des Permissions Modules/Actions
  if (to.meta.module && authStore.isAuthenticated) {
    // S'assurer que les permissions sont chargées (évite race condition au refresh page)
    if (!authStore.permissions || Object.keys(authStore.permissions).length === 0) {
      try { 
        await authStore.fetchPermissions(); 
      } catch(e) { 
        console.warn("Impossible de charger les permissions backend.", e);
      }
    }
    
    const hasPermission = authStore.canAccessModule(to.meta.module, to.meta.action || 'read');
    
    if (!hasPermission) {
      console.warn(`Accès refusé au module '${to.meta.module}' pour l'action '${to.meta.action}'.`);
      // Option A : Rediriger vers Dashboard si pas autorisé
      return next({ name: 'Dashboard' }); 
      // Option B : Afficher une page 403 Forbidden (si tu crées cette vue plus tard)
    }
  }
  
  next();
});

export default router;