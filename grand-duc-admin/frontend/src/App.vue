<template>
  <div>
    <!-- Login : pas de sidebar -->
    <router-view v-if="!auth.isLoggedIn" />

    <!-- Interface principale -->
    <div v-else class="layout">
      <!-- ── Sidebar ─────────────────────────────────── -->
      <nav class="sidebar">
        <div class="sidebar-logo">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/>
          </svg>
          Grand-Duc
        </div>

        <div class="nav-section">Navigation</div>

        <router-link class="nav-item" :class="{ active: $route.name === 'Dashboard' }" to="/">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
            <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
          </svg>
          Tableau de bord
        </router-link>

        <router-link class="nav-item" :class="{ active: $route.name === 'Rules' }" to="/rules">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
          Règles de filtrage
        </router-link>

        <router-link class="nav-item" :class="{ active: $route.name === 'Logs' }" to="/logs">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
            <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>
          </svg>
          Journaux d'accès
        </router-link>

        <template v-if="auth.isAdmin">
          <div class="nav-section" style="margin-top:8px">Administration</div>
          <router-link class="nav-item" :class="{ active: $route.name === 'Users' }" to="/users">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>
            </svg>
            Utilisateurs
          </router-link>
        </template>

        <div class="sidebar-bottom">
          <div class="nav-item" @click="logout">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>
            </svg>
            <span>{{ auth.user?.username }} — Déconnexion</span>
          </div>
        </div>
      </nav>

      <!-- ── Contenu ─────────────────────────────────── -->
      <main class="main-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { onMounted }    from 'vue'
import { useRouter }    from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth   = useAuthStore()
const router = useRouter()

onMounted(() => auth.fetchMe())

async function logout() {
  auth.logout()
  router.push('/login')
}
</script>
