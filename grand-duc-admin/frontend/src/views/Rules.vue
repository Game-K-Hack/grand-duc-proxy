<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Règles de filtrage</h1>
      <button v-if="auth.isAdmin" class="btn btn-primary" @click="openCreate">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        Nouvelle règle
      </button>
    </div>

    <!-- Barre de recherche -->
    <div style="display:flex;gap:12px;margin-bottom:16px;align-items:center">
      <div class="search-bar">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input v-model="search" placeholder="Filtrer par pattern…" @input="debouncedLoad" />
      </div>
      <span style="color:var(--text-muted);font-size:12px">{{ total }} règle{{ total > 1 ? 's' : '' }}</span>
    </div>

    <!-- Table -->
    <div class="card" style="padding:0">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th style="width:50px">Prio.</th>
              <th>Pattern (Regex)</th>
              <th style="width:90px">Action</th>
              <th>Description</th>
              <th style="width:80px">Actif</th>
              <th style="width:110px" v-if="auth.isAdmin">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td colspan="6" style="text-align:center;padding:24px;color:var(--text-muted)">Chargement…</td></tr>
            <tr v-else-if="!rules.length"><td colspan="6" style="text-align:center;padding:24px;color:var(--text-muted)">Aucune règle</td></tr>
            <tr v-for="rule in rules" :key="rule.id">
              <td style="color:var(--text-muted);text-align:center">{{ rule.priority }}</td>
              <td><code class="mono" style="font-size:12px;color:var(--blue)">{{ rule.pattern }}</code></td>
              <td><span :class="rule.action === 'block' ? 'badge badge-block' : 'badge badge-allow'">{{ rule.action === 'block' ? 'bloqué' : 'autorisé' }}</span></td>
              <td style="color:var(--text-muted)">{{ rule.description || '—' }}</td>
              <td>
                <label class="toggle" v-if="auth.isAdmin">
                  <input type="checkbox" :checked="rule.enabled" @change="toggle(rule)" />
                  <span class="toggle-slider"></span>
                </label>
                <span v-else :class="rule.enabled ? 'badge badge-on' : 'badge badge-off'">
                  {{ rule.enabled ? 'Oui' : 'Non' }}
                </span>
              </td>
              <td v-if="auth.isAdmin" style="display:flex;gap:6px;padding:8px 14px">
                <button class="btn btn-ghost btn-sm btn-icon" title="Modifier" @click="openEdit(rule)">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button class="btn btn-danger btn-sm btn-icon" title="Supprimer" @click="confirmDelete(rule)">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                    <path d="M10 11v6M14 11v6M9 6V4h6v2"/>
                  </svg>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Pagination -->
    <div class="pagination">
      <button class="btn btn-ghost btn-sm" :disabled="page === 0" @click="page--; load()">←</button>
      <span>Page {{ page + 1 }} / {{ totalPages }}</span>
      <button class="btn btn-ghost btn-sm" :disabled="page >= totalPages - 1" @click="page++; load()">→</button>
    </div>

    <!-- Modal créer/modifier -->
    <div class="modal-overlay" v-if="showModal" @click.self="showModal = false">
      <div class="modal">
        <div class="modal-title">{{ editingRule ? 'Modifier la règle' : 'Nouvelle règle' }}</div>

        <div v-if="formError" class="alert alert-error">{{ formError }}</div>

        <div class="form-row cols-2">
          <div class="form-group">
            <label class="form-label">Action *</label>
            <select v-model="form.action" class="form-select">
              <option value="block">Bloqué</option>
              <option value="allow">Autorisé</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Priorité</label>
            <input v-model.number="form.priority" type="number" class="form-input" min="1" max="9999" />
          </div>
        </div>

        <div class="form-group" style="margin-bottom:14px">
          <label class="form-label">Pattern Regex *</label>
          <textarea v-model="form.pattern" class="form-textarea" placeholder="^https?://(www\.)?example\.com" rows="2"></textarea>
          <div v-if="regexError" style="color:var(--red);font-size:11px;margin-top:4px">{{ regexError }}</div>
        </div>

        <div class="form-group" style="margin-bottom:14px">
          <label class="form-label">Description</label>
          <input v-model="form.description" class="form-input" placeholder="Ex: Réseaux sociaux" />
        </div>

        <div class="form-group" style="flex-direction:row;align-items:center;gap:10px">
          <label class="toggle">
            <input type="checkbox" v-model="form.enabled" />
            <span class="toggle-slider"></span>
          </label>
          <span class="form-label" style="margin:0">Règle activée</span>
        </div>

        <div class="modal-footer">
          <button class="btn btn-ghost" @click="showModal = false">Annuler</button>
          <button class="btn btn-primary" @click="save" :disabled="saving">
            {{ saving ? 'Enregistrement…' : 'Enregistrer' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Modal confirmer suppression -->
    <div class="modal-overlay" v-if="deleteTarget" @click.self="deleteTarget = null">
      <div class="modal" style="width:400px">
        <div class="modal-title">Confirmer la suppression</div>
        <p style="color:var(--text-muted);margin-bottom:12px">
          Supprimer définitivement la règle&nbsp;:
        </p>
        <code class="mono" style="color:var(--red)">{{ deleteTarget?.pattern }}</code>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="deleteTarget = null">Annuler</button>
          <button class="btn btn-danger" @click="doDelete" :disabled="saving">Supprimer</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { rulesApi }                 from '@/api'
import { useAuthStore }             from '@/stores/auth'

const auth  = useAuthStore()
const rules = ref([])
const total = ref(0)
const page  = ref(0)
const limit = 20
const search      = ref('')
const loading     = ref(false)
const saving      = ref(false)
const showModal   = ref(false)
const editingRule = ref(null)
const deleteTarget = ref(null)
const formError   = ref('')
const regexError  = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / limit)))

const form = ref({ pattern: '', action: 'block', description: '', priority: 100, enabled: true })

let debounceTimer = null
function debouncedLoad() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => { page.value = 0; load() }, 350)
}

async function load() {
  loading.value = true
  try {
    const { data } = await rulesApi.list({ skip: page.value * limit, limit, search: search.value })
    rules.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingRule.value = null
  form.value = { pattern: '', action: 'block', description: '', priority: 100, enabled: true }
  formError.value = ''
  regexError.value = ''
  showModal.value  = true
}

function openEdit(rule) {
  editingRule.value = rule
  form.value = { ...rule }
  formError.value = ''
  regexError.value = ''
  showModal.value  = true
}

function validateRegex(pattern) {
  try { new RegExp(pattern); return true }
  catch (e) { regexError.value = e.message; return false }
}

async function save() {
  formError.value  = ''
  regexError.value = ''
  if (!form.value.pattern) { formError.value = 'Le pattern est obligatoire'; return }
  if (!validateRegex(form.value.pattern)) return

  saving.value = true
  try {
    if (editingRule.value) {
      await rulesApi.update(editingRule.value.id, form.value)
    } else {
      await rulesApi.create(form.value)
    }
    showModal.value = false
    load()
  } catch (e) {
    formError.value = e.response?.data?.detail || 'Erreur serveur'
  } finally {
    saving.value = false
  }
}

async function toggle(rule) {
  await rulesApi.toggle(rule.id)
  load()
}

function confirmDelete(rule) { deleteTarget.value = rule }

async function doDelete() {
  saving.value = true
  try {
    await rulesApi.delete(deleteTarget.value.id)
    deleteTarget.value = null
    load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
