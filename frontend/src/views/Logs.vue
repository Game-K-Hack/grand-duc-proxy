<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Journaux d'accès</h1>
      <span style="color:var(--text-muted);font-size:13px">{{ total.toLocaleString('fr-FR') }} entrée{{ total > 1 ? 's' : '' }}</span>
    </div>

    <!-- Filtres -->
    <div style="display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap">
      <div class="search-bar">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input v-model="search" placeholder="Domaine, URL ou IP…" @input="debouncedLoad" />
      </div>

      <select v-model="filterBlocked" class="form-select" style="width:160px" @change="page=0;load()">
        <option :value="null">Toutes les requêtes</option>
        <option :value="true">Bloquées uniquement</option>
        <option :value="false">Autorisées uniquement</option>
      </select>

      <!-- Filtre par poste : suit le poste à travers tous ses changements d'IP -->
      <button v-if="filterClientUserId" class="btn btn-ghost btn-sm" @click="clearClientFilter">
        Poste : {{ filterClientName || `#${filterClientUserId}` }} ✕
      </button>
    </div>

    <!-- Table -->
    <div class="card" style="padding:0">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th style="width:140px">Date</th>
              <th style="width:120px">IP Client</th>
              <th style="width:180px">Poste</th>
              <th style="width:76px">Méthode</th>
              <th>URL</th>
              <th style="width:80px">Statut</th>
              <th style="width:32px"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td colspan="7" style="text-align:center;padding:24px;color:var(--text-muted)">Chargement…</td></tr>
            <tr v-else-if="!logs.length"><td colspan="7" style="text-align:center;padding:24px;color:var(--text-muted)">Aucun résultat</td></tr>
            <template v-for="log in logs" :key="log.id">
              <tr class="log-row" :class="{ 'log-row-expanded': expanded === log.id }" @click="toggle(log.id)">
                <td class="mono" style="font-size:11px;color:var(--text-muted);white-space:nowrap">{{ fmtDate(log.accessed_at) }}</td>
                <td class="mono" style="font-size:12px">{{ log.client_ip || '—' }}</td>
                <td style="font-size:12px">
                  <!-- client_resolved : poste figé par le proxy au moment de la
                       requête. Sinon il n'est que déduit de l'IP actuelle, donc
                       potentiellement faux si cette IP a changé de main. -->
                  <span v-if="log.client_label" :style="log.client_resolved
                    ? 'color:var(--text)'
                    : 'color:var(--text-muted);font-style:italic'"
                    :title="log.client_resolved ? '' : 'Poste déduit de l’adresse IP actuelle, et non enregistré au moment de la requête'">
                    {{ log.client_label }}
                  </span>
                  <span v-else style="color:var(--text-muted)">Inconnu</span>
                </td>
                <td><span class="badge" style="background:rgba(88,166,255,.12);color:var(--blue)">{{ log.method }}</span></td>
                <td class="mono" style="font-size:11px;max-width:0">
                  <div class="url-truncate" :title="log.url">{{ log.url }}</div>
                </td>
                <td>
                  <span :class="log.blocked ? 'badge badge-block' : 'badge badge-allow'">
                    {{ log.blocked ? 'Bloqué' : 'OK' }}
                  </span>
                </td>
                <td style="text-align:center">
                  <svg class="expand-icon" :class="{ 'expand-icon-open': expanded === log.id }"
                    width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="6 9 12 15 18 9"/>
                  </svg>
                </td>
              </tr>
              <tr v-if="expanded === log.id" class="detail-row">
                <td colspan="7" style="padding:0">
                  <div class="detail-panel">
                    <div class="detail-grid">
                      <div class="detail-item">
                        <div class="detail-label">Hôte</div>
                        <div class="detail-value mono">{{ extractHost(log.url) }}</div>
                      </div>
                      <div class="detail-item">
                        <div class="detail-label">Date complète</div>
                        <div class="detail-value mono">{{ fmtDateFull(log.accessed_at) }}</div>
                      </div>
                      <div class="detail-item" style="grid-column:1/-1">
                        <div class="detail-label">URL complète</div>
                        <div class="detail-value mono" style="word-break:break-all;white-space:pre-wrap">{{ log.url }}</div>
                      </div>
                      <div class="detail-item" style="grid-column:1/-1">
                        <div class="detail-label">User-Agent</div>
                        <div class="detail-value mono" style="word-break:break-all">{{ log.user_agent || '—' }}</div>
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Pagination -->
    <div class="pagination">
      <button class="btn btn-ghost btn-sm" :disabled="page === 0" @click="page--;load()">←</button>
      <span>Page {{ page + 1 }} / {{ totalPages }}</span>
      <button class="btn btn-ghost btn-sm" :disabled="page >= totalPages - 1" @click="page++;load()">→</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter }      from 'vue-router'
import { logsApi }                  from '@/api'

const route  = useRoute()
const router = useRouter()

const logs          = ref([])
const total         = ref(0)
const page          = ref(0)
const limit         = 50
const search        = ref('')
const filterBlocked = ref(null)
const loading       = ref(false)
const expanded      = ref(null)
const filterClientUserId = ref(null)
const filterClientName   = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / limit)))

function fmtDate(iso) {
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function fmtDateFull(iso) {
  return new Date(iso).toLocaleString('fr-FR', {
    weekday: 'long', day: '2-digit', month: 'long', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function extractHost(url) {
  try {
    return new URL(url).hostname
  } catch {
    // CONNECT style: "hostname:443"
    return url.split(':')[0] || url
  }
}

function toggle(id) {
  expanded.value = expanded.value === id ? null : id
}

let debounceTimer = null
function debouncedLoad() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => { page.value = 0; load() }, 350)
}

async function load() {
  loading.value = true
  expanded.value = null
  try {
    const params = { skip: page.value * limit, limit, search: search.value }
    if (filterBlocked.value !== null) params.blocked = filterBlocked.value
    if (filterClientUserId.value) params.client_user_id = filterClientUserId.value
    const { data } = await logsApi.list(params)
    logs.value  = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function clearClientFilter() {
  filterClientUserId.value = null
  filterClientName.value   = ''
  router.replace({ path: '/logs' })
  page.value = 0
  load()
}

onMounted(async () => {
  const id = Number(route.query.client_user_id)
  if (id) filterClientUserId.value = id
  await load()
  // Le nom du poste vient des lignes retournées, pas d'un appel dédié.
  if (id) filterClientName.value = logs.value.find(l => l.client_label)?.client_label || ''
})
</script>

<style scoped>
.log-row {
  cursor: pointer;
  transition: background .1s;
}
.log-row:hover { background: var(--surface2); }
.log-row-expanded { background: var(--surface2); }

.url-truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.expand-icon {
  color: var(--text-muted);
  opacity: .5;
  transition: transform .2s, opacity .2s;
}
.log-row:hover .expand-icon { opacity: 1; }
.expand-icon-open {
  transform: rotate(180deg);
  opacity: 1;
}

.detail-row td { background: var(--surface2); }
.detail-panel {
  padding: 14px 20px 16px;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 24px;
}
.detail-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--text-muted);
  margin-bottom: 3px;
}
.detail-value {
  font-size: 12px;
  color: var(--text);
  line-height: 1.5;
}
</style>
