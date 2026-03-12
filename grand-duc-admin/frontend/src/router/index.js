import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/login',         name: 'Login',        component: () => import('@/views/Login.vue'),        meta: { public: true } },
  { path: '/',              name: 'Dashboard',    component: () => import('@/views/Dashboard.vue'),    meta: { permissions: ['dashboard.read'] } },
  { path: '/rules',         name: 'Rules',        component: () => import('@/views/Rules.vue'),        meta: { permissions: ['rules.read'] } },
  { path: '/logs',          name: 'Logs',         component: () => import('@/views/Logs.vue'),         meta: { permissions: ['logs.read'] } },
  { path: '/client-groups', name: 'ClientGroups', component: () => import('@/views/ClientGroups.vue'), meta: { permissions: ['client_groups.read'] } },
  { path: '/client-users',  name: 'ClientUsers',  component: () => import('@/views/ClientUsers.vue'),  meta: { permissions: ['client_users.read'] } },
  { path: '/test-access',   name: 'TestAccess',   component: () => import('@/views/TestAccess.vue'),   meta: { permissions: ['test_access.use'] } },
  { path: '/users',         name: 'Users',        component: () => import('@/views/Users.vue'),        meta: { permissions: ['users.read'] } },
  { path: '/tls-bypass',    name: 'TlsBypass',    component: () => import('@/views/TlsBypass.vue'),    meta: { permissions: ['tls_bypass.read'] } },
  { path: '/killswitch',    name: 'Killswitch',   component: () => import('@/views/Killswitch.vue'),   meta: { permissions: ['killswitch.read'] } },
  { path: '/certificates',  name: 'Certificates', component: () => import('@/views/Certificates.vue'), meta: { permissions: ['certificates.read'] } },
  { path: '/proxy-logs',    name: 'ProxyLogs',    component: () => import('@/views/ProxyLogs.vue'),    meta: { permissions: ['proxy_logs.read'] } },
  { path: '/roles',         name: 'Roles',        component: () => import('@/views/Roles.vue'),        meta: { permissions: ['roles.read'] } },
  { path: '/settings',      name: 'Settings',     component: () => import('@/views/Settings.vue') },
  { path: '/documentation', name: 'Documentation', component: () => import('@/views/Documentation.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) return '/login'
  if (to.path === '/login' && auth.isLoggedIn) return '/'
  // Attendre que les permissions soient chargées avant de vérifier
  if (to.meta.permissions && !auth.user && auth.isLoggedIn) {
    await auth.fetchMe()
  }
  if (to.meta.permissions && !auth.hasAnyPermission(...to.meta.permissions)) return '/'
})

export default router
