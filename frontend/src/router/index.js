import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { guest: true },
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('../views/ChatView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/audit',
    name: 'Audit',
    component: () => import('../views/AuditView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: () => import('../views/KnowledgeView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/inspection',
    name: 'Inspection',
    component: () => import('../views/InspectionView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/users',
    name: 'Users',
    component: () => import('../views/UsersView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/topology',
    name: 'Topology',
    component: () => import('../views/TopologyView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/terminal',
    name: 'Terminal',
    component: () => import('../views/TerminalView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/ProfileView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/machines',
    name: 'Machines',
    component: () => import('../views/MachinesView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/',
    redirect: '/chat',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('access_token')

  if (to.meta.requiresAuth && !token) {
    return next('/login')
  }
  if (to.meta.guest && token) {
    return next('/chat')
  }

  // Auto-fetch user on refresh (token exists but user not loaded)
  if (token && to.meta.requiresAuth) {
    const { useAuthStore } = await import('../stores/auth')
    const authStore = useAuthStore()
    if (!authStore.user) {
      try {
        await authStore.fetchUser()
      } catch {
        authStore.logout()
        return next('/login')
      }
    }
  }

  next()
})

export default router
