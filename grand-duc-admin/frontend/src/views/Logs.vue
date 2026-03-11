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
    </div>

    <!-- Table -->
    <div class="card" style="padding:0">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th style="width:150px">Date</th>
              <th style="width:150px">IP Client</th>
              <th style="width:300px">Utilisateur</th>
              <th style="width:100px">Méthode</th>
              <th>Hôte</th>
              <th>URL</th>
              <th style="width:90px">Statut</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td colspan="7" style="text-align:center;padding:24px;color:var(--text-muted)">Chargement…</td></tr>
            <tr v-else-if="!logs.length"><td colspan="7" style="text-align:center;padding:24px;color:var(--text-muted)">Aucun résultat</td></tr>
            <tr v-for="log in logs" :key="log.id">
              <td class="mono" style="font-size:11px;color:var(--text-muted);white-space:nowrap">{{ fmtDate(log.accessed_at) }}</td>
              <td class="mono" style="font-size:12px">{{ log.client_ip || '—' }}</td>
              <td style="font-size:12px">
                <span v-if="log.client_label" style="color:var(--text)">{{ log.client_label }}</span>
                <span v-else style="color:var(--text-muted)">Inconnu</span>
              </td>
              <td><span class="badge" style="background:rgba(88,166,255,.12);color:var(--blue)">{{ log.method }}</span></td>
              <td class="mono" style="font-size:12px">{{ log.host }}</td>
              <td class="url-cell mono" style="font-size:11px" :title="log.url">{{ log.url }}</td>
              <td>
                <span :class="log.blocked ? 'badge badge-block' : 'badge badge-allow'">
                  {{ log.blocked ? 'Bloqué' : 'OK' }}
                </span>
              </td>
            </tr>
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
import { logsApi }                  from '@/api'

const logs          = ref([])
const total         = ref(0)
const page          = ref(0)
const limit         = 50
const search        = ref('')
const filterBlocked = ref(null)
const loading       = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / limit)))

function fmtDate(iso) {
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

let debounceTimer = null
function debouncedLoad() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => { page.value = 0; load() }, 350)
}

async function load() {
  loading.value = true
  try {
    const params = { skip: page.value * limit, limit, search: search.value }
    if (filterBlocked.value !== null) params.blocked = filterBlocked.value
    const { data } = await logsApi.list(params)
    logs.value  = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
