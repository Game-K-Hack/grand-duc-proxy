import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/login',     name: 'Login',     component: () => import('@/views/Login.vue'),     meta: { public: true } },
  { path: '/',          name: 'Dashboard', component: () => import('@/views/Dashboard.vue') },
  { path: '/rules',     name: 'Rules',     component: () => import('@/views/Rules.vue') },
  { path: '/logs',      name: 'Logs',      component: () => import('@/views/Logs.vue') },
  { path: '/users',     name: 'Users',     component: () => import('@/views/Users.vue'),     meta: { admin: true } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) return '/login'
  if (to.path === '/login' && auth.isLoggedIn)  return '/'
  if (to.meta.admin && !auth.isAdmin)            return '/'
})

export default router