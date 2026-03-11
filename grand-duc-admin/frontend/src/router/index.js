import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/login',         name: 'Login',        component: () => import('@/views/Login.vue'),        meta: { public: true } },
  { path: '/',              name: 'Dashboard',    component: () => import('@/views/Dashboard.vue') },
  { path: '/rules',         name: 'Rules',        component: () => import('@/views/Rules.vue') },
  { path: '/logs',          name: 'Logs',         component: () => import('@/views/Logs.vue') },
  { path: '/client-groups', name: 'ClientGroups', component: () => import('@/views/ClientGroups.vue'), meta: { admin: true } },
  { path: '/client-users',  name: 'ClientUsers',  component: () => import('@/views/ClientUsers.vue'),  meta: { admin: true } },
  { path: '/test-access',   name: 'TestAccess',   component: () => import('@/views/TestAccess.vue'),   meta: { admin: true } },
  { path: '/users',         name: 'Users',        component: () => import('@/views/Users.vue'),        meta: { admin: true } },
  { path: '/tls-bypass',   name: 'TlsBypass',    component: () => import('@/views/TlsBypass.vue'),    meta: { admin: true } },
  { path: '/killswitch',    name: 'Killswitch',    component: () => import('@/views/Killswitch.vue'),    meta: { admin: true } },
  { path: '/certificates', name: 'Certificates', component: () => import('@/views/Certificates.vue'), meta: { admin: true } },
  { path: '/documentation',  name: 'Documentation', component: () => import('@/views/Documentation.vue') },
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