import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Import direct — l'app fait ~200 KB, pas besoin de lazy loading
import Login         from '@/views/Login.vue'
import Dashboard     from '@/views/Dashboard.vue'
import Rules         from '@/views/Rules.vue'
import Logs          from '@/views/Logs.vue'
import ClientGroups  from '@/views/ClientGroups.vue'
import ClientUsers   from '@/views/ClientUsers.vue'
import TestAccess    from '@/views/TestAccess.vue'
import Users         from '@/views/Users.vue'
import TlsBypass     from '@/views/TlsBypass.vue'
import Killswitch    from '@/views/Killswitch.vue'
import Certificates  from '@/views/Certificates.vue'
import ProxyLogs     from '@/views/ProxyLogs.vue'
import Roles         from '@/views/Roles.vue'
import Settings      from '@/views/Settings.vue'
import Documentation from '@/views/Documentation.vue'

const routes = [
  { path: '/login',         name: 'Login',        component: Login,         meta: { public: true } },
  { path: '/',              name: 'Dashboard',    component: Dashboard,     meta: { permissions: ['dashboard.read'] } },
  { path: '/rules',         name: 'Rules',        component: Rules,         meta: { permissions: ['rules.read'] } },
  { path: '/logs',          name: 'Logs',         component: Logs,          meta: { permissions: ['logs.read'] } },
  { path: '/client-groups', name: 'ClientGroups', component: ClientGroups,  meta: { permissions: ['client_groups.read'] } },
  { path: '/client-users',  name: 'ClientUsers',  component: ClientUsers,   meta: { permissions: ['client_users.read'] } },
  { path: '/test-access',   name: 'TestAccess',   component: TestAccess,    meta: { permissions: ['test_access.use'] } },
  { path: '/users',         name: 'Users',        component: Users,         meta: { permissions: ['users.read'] } },
  { path: '/tls-bypass',    name: 'TlsBypass',    component: TlsBypass,     meta: { permissions: ['tls_bypass.read'] } },
  { path: '/killswitch',    name: 'Killswitch',   component: Killswitch,    meta: { permissions: ['killswitch.read'] } },
  { path: '/certificates',  name: 'Certificates', component: Certificates,  meta: { permissions: ['certificates.read'] } },
  { path: '/proxy-logs',    name: 'ProxyLogs',    component: ProxyLogs,     meta: { permissions: ['proxy_logs.read'] } },
  { path: '/roles',         name: 'Roles',        component: Roles,         meta: { permissions: ['roles.read'] } },
  { path: '/settings',      name: 'Settings',     component: Settings },
  { path: '/documentation', name: 'Documentation', component: Documentation },
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
