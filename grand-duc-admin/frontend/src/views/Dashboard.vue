<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Tableau de bord</h1>
      <button class="btn btn-ghost btn-sm" @click="load">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
        </svg>
        Actualiser
      </button>
    </div>

    <div v-if="loading" style="color:var(--text-muted)">Chargement…</div>

    <template v-else-if="stats">
      <!-- Stat cards -->
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-label">Requêtes totales</div>
          <div class="stat-value blue">{{ fmt(stats.total_requests) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Bloquées</div>
          <div class="stat-value red">{{ fmt(stats.blocked_requests) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Autorisées</div>
          <div class="stat-value green">{{ fmt(stats.allowed_requests) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Taux de blocage</div>
          <div class="stat-value accent">{{ stats.block_rate }}%</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Requêtes aujourd'hui</div>
          <div class="stat-value blue">{{ fmt(stats.requests_today) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Règles actives</div>
          <div class="stat-value accent">{{ stats.active_rules }}</div>
        </div>
      </div>

      <!-- Tables côte à côte -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <!-- Top domaines bloqués -->
        <div class="card">
          <div class="card-title">🚫 Top domaines bloqués</div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Domaine</th><th style="text-align:right">Blocages</th></tr></thead>
              <tbody>
                <tr v-for="d in stats.top_blocked" :key="d.host">
                  <td class="mono" style="color:var(--text-muted)">{{ d.host }}</td>
                  <td style="text-align:right"><span class="badge badge-block">{{ d.count }}</span></td>
                </tr>
                <tr v-if="!stats.top_blocked.length">
                  <td colspan="2" style="color:var(--text-muted);text-align:center;padding:20px">Aucune donnée</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Top domaines visitées -->
        <div class="card">
          <div class="card-title">🌐 Top domaines visités</div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Domaine</th><th style="text-align:right">Total</th><th style="text-align:right">Bloqués</th></tr></thead>
              <tbody>
                <tr v-for="d in stats.top_domains" :key="d.host">
                  <td class="mono" style="color:var(--text-muted)">{{ d.host }}</td>
                  <td style="text-align:right">{{ d.count }}</td>
                  <td style="text-align:right">
                    <span v-if="d.blocked" class="badge badge-block">{{ d.blocked }}</span>
                    <span v-else style="color:var(--text-muted)">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { statsApi }       from '@/api'

const stats   = ref(null)
const loading = ref(false)

function fmt(n) {
  return n?.toLocaleString('fr-FR') ?? '—'
}

async function load() {
  loading.value = true
  try {
    const { data } = await statsApi.get()
    stats.value = data
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
