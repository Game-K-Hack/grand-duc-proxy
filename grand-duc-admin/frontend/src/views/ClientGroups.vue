<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Groupes de clients</h1>
    </div>

    <div style="display:grid;grid-template-columns:280px 1fr;gap:20px;align-items:start">

      <!-- ── Liste des groupes ───────────────────────────────────────── -->
      <div class="card" style="padding:0;overflow:hidden">
        <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border-bottom:1px solid var(--border)">
          <div style="font-weight:600;font-size:13px">Groupes</div>
          <button v-if="auth.isAdmin" class="btn btn-primary btn-sm" @click="openCreate">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            Nouveau
          </button>
        </div>

        <div
          v-for="g in groups" :key="g.id"
          style="padding:10px 14px;border-bottom:1px solid var(--border);cursor:pointer;border-left:3px solid transparent;transition:background .1s"
          :style="selected?.id === g.id ? 'background:var(--surface2);border-left-color:var(--accent);padding-left:11px' : 'padding-left:11px'"
          @click="selectGroup(g)"
        >
          <div style="display:flex;align-items:center;justify-content:space-between">
            <div style="min-width:0;flex:1">
              <div style="font-size:13px;font-weight:500">{{ g.name }}</div>
              <div style="font-size:11px;color:var(--text-muted);margin-top:1px">
                {{ g.member_count }} membre{{ g.member_count !== 1 ? 's' : '' }}
                · {{ g.rule_count }} règle{{ g.rule_count !== 1 ? 's' : '' }}
              </div>
            </div>
            <div v-if="selected?.id === g.id && auth.isAdmin" style="display:flex;gap:3px;flex-shrink:0;margin-left:6px">
              <button class="btn btn-ghost btn-sm btn-icon" @click.stop="openEdit(g)">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </button>
              <button class="btn btn-danger btn-sm btn-icon" @click.stop="confirmDelete(g)">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                  <path d="M10 11v6M14 11v6M9 6V4h6v2"/>
                </svg>
              </button>
            </div>
          </div>
        </div>

        <div v-if="!groups.length" style="padding:24px;text-align:center;color:var(--text-muted);font-size:13px">
          Aucun groupe
        </div>
      </div>

      <!-- ── Règles du groupe sélectionné ───────────────────────────── -->
      <div v-if="selected" class="card" style="padding:0;overflow:hidden">
        <div style="padding:12px 18px;border-bottom:1px solid var(--border)">
          <div style="font-weight:600;font-size:14px;margin-bottom:2px">{{ selected.name }}</div>
          <div style="font-size:12px;color:var(--text-muted)">
            Activez les règles à appliquer aux membres de ce groupe.
          </div>
        </div>

        <!-- Barre de filtre -->
        <div style="padding:8px 14px;border-bottom:1px solid var(--border);display:flex;gap:8px;align-items:center">
          <input v-model="ruleSearch" class="form-input" style="height:30px;font-size:12px;flex:1" placeholder="Filtrer les règles…" />
          <label style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--text-muted);white-space:nowrap;cursor:pointer">
            <input type="checkbox" v-model="showActiveOnly" style="accent-color:var(--accent)" />
            Actives uniquement
          </label>
        </div>

        <div v-if="loadingRules" style="padding:30px;text-align:center;color:var(--text-muted)">Chargement…</div>

        <div v-else class="table-wrap" style="max-height:calc(100vh - 300px);overflow-y:auto">
          <table>
            <thead>
              <tr>
                <th style="width:48px;text-align:center">Actif</th>
                <th>Pattern</th>
                <th style="width:80px;text-align:center">Priorité</th>
                <th style="width:110px">Action globale</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in filteredRules" :key="row.rule.id"
                :style="row.active ? 'background:var(--surface2)' : ''"
              >
                <!-- Toggle activer/désactiver -->
                <td style="text-align:center">
                  <label class="toggle-wrap" v-if="auth.isAdmin">
                    <input
                      type="checkbox"
                      class="toggle-input"
                      :checked="row.active"
                      :disabled="savingRow === row.rule.id"
                      @change="toggleRule(row, $event.target.checked)"
                    />
                    <span class="toggle-slider"></span>
                  </label>
                </td>

                <!-- Pattern + description -->
                <td>
                  <code class="mono" style="font-size:12px;color:var(--blue)">{{ row.rule.pattern }}</code>
                  <div v-if="row.rule.description" style="font-size:11px;color:var(--text-muted);margin-top:1px">
                    {{ row.rule.description }}
                  </div>
                </td>

                <!-- Priorité -->
                <td style="text-align:center;color:var(--text-muted);font-size:12px">{{ row.rule.priority }}</td>

                <!-- Action globale -->
                <td>
                  <span :class="row.rule.action === 'block' ? 'badge badge-block' : 'badge badge-allow'"
                    style="opacity:.65;font-size:11px">
                    {{ row.rule.action === 'block' ? '🚫 block' : '✅ allow' }}
                  </span>
                </td>

              </tr>

              <tr v-if="!filteredRules.length">
                <td colspan="4" style="text-align:center;padding:28px;color:var(--text-muted)">
                  {{ ruleSearch ? 'Aucune règle ne correspond à la recherche' : 'Aucune règle globale active' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-else class="card" style="display:flex;align-items:center;justify-content:center;min-height:200px;color:var(--text-muted);font-size:13px">
        ← Sélectionnez un groupe pour configurer ses règles
      </div>
    </div>

    <!-- ── Modal créer/modifier groupe ────────────────────────────── -->
    <div class="modal-overlay" v-if="showModal" @click.self="showModal = false">
      <div class="modal" style="width:420px">
        <div class="modal-title">{{ editing ? 'Modifier le groupe' : 'Nouveau groupe' }}</div>
        <div v-if="formError" class="alert alert-error">{{ formError }}</div>
        <div class="form-group" style="margin-bottom:14px">
          <label class="form-label">Nom *</label>
          <input v-model="form.name" class="form-input" placeholder="Ex: Directeurs" @keyup.enter="save" />
        </div>
        <div class="form-group" style="margin-bottom:20px">
          <label class="form-label">Description</label>
          <input v-model="form.description" class="form-input" placeholder="Description optionnelle" @keyup.enter="save" />
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="showModal = false">Annuler</button>
          <button class="btn btn-primary" @click="save" :disabled="saving">
            {{ saving ? 'Enregistrement…' : 'Enregistrer' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Modal confirmation suppression ─────────────────────────── -->
    <div class="modal-overlay" v-if="deleteTarget" @click.self="deleteTarget = null">
      <div class="modal" style="width:380px">
        <div class="modal-title">Supprimer le groupe ?</div>
        <p style="color:var(--text-muted);margin-bottom:16px">
          Le groupe <strong style="color:var(--text)">{{ deleteTarget.name }}</strong> sera supprimé.
          Les utilisateurs membres seront détachés.
        </p>
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
import { groupsApi, rulesApi }      from '@/api'
import { useAuthStore }             from '@/stores/auth'

const auth = useAuthStore()

const groups      = ref([])
const selected    = ref(null)
const allRules    = ref([])     // toutes les règles globales
const groupRules  = ref([])     // règles actives dans ce groupe
const loadingRules = ref(false)
const savingRow   = ref(null)
const saving      = ref(false)
const formError   = ref('')
const showModal   = ref(false)
const editing     = ref(null)
const deleteTarget = ref(null)
const ruleSearch   = ref('')
const showActiveOnly = ref(false)
const form = ref({ name: '', description: '' })

// ── Vue fusionnée ─────────────────────────────────────────────────────────────
const rulesWithState = computed(() => {
  return allRules.value.map(rule => {
    const gr = groupRules.value.find(r => r.rule_id === rule.id)
    return {
      rule,
      active:      !!gr,
      groupRuleId: gr?.id          ?? null,
      groupAction: gr?.action      ?? (rule.action === 'block' ? 'allow' : 'block'),
    }
  })
})

const filteredRules = computed(() => {
  let list = rulesWithState.value
  if (showActiveOnly.value) list = list.filter(r => r.active)
  if (ruleSearch.value) {
    const q = ruleSearch.value.toLowerCase()
    list = list.filter(r =>
      r.rule.pattern.toLowerCase().includes(q) ||
      (r.rule.description || '').toLowerCase().includes(q)
    )
  }
  return list
})

// ── Chargement ────────────────────────────────────────────────────────────────
async function loadGroups() {
  const { data } = await groupsApi.list()
  groups.value = data
}

async function selectGroup(g) {
  selected.value   = g
  loadingRules.value = true
  ruleSearch.value = ''
  try {
    const [grRes, rulesRes] = await Promise.all([
      groupsApi.listRules(g.id),
      allRules.value.length ? Promise.resolve(null) : rulesApi.list({ limit: 500 }),
    ])
    groupRules.value = grRes.data
    if (rulesRes) allRules.value = rulesRes.data.items
  } finally {
    loadingRules.value = false
  }
}

// ── Toggles ───────────────────────────────────────────────────────────────────
async function toggleRule(row, checked) {
  savingRow.value = row.rule.id
  try {
    if (checked) {
      // Active avec l'action inverse de la globale (cas d'usage le plus commun)
      const defaultAction = row.rule.action === 'block' ? 'allow' : 'block'
      await groupsApi.addRule(selected.value.id, { rule_id: row.rule.id, action: defaultAction })
    } else {
      await groupsApi.deleteRule(selected.value.id, row.groupRuleId)
    }
    const { data } = await groupsApi.listRules(selected.value.id)
    groupRules.value = data
    await loadGroups()  // met à jour rule_count
  } finally {
    savingRow.value = null
  }
}

// ── CRUD groupes ──────────────────────────────────────────────────────────────
function openCreate() {
  editing.value = null
  form.value    = { name: '', description: '' }
  formError.value = ''
  showModal.value = true
}

function openEdit(g) {
  editing.value = g
  form.value    = { name: g.name, description: g.description || '' }
  formError.value = ''
  showModal.value = true
}

async function save() {
  formError.value = ''
  if (!form.value.name.trim()) { formError.value = 'Le nom est obligatoire'; return }
  saving.value = true
  try {
    if (editing.value) {
      await groupsApi.update(editing.value.id, form.value)
    } else {
      await groupsApi.create(form.value)
    }
    showModal.value = false
    await loadGroups()
    if (editing.value && selected.value?.id === editing.value.id) {
      selected.value = groups.value.find(g => g.id === editing.value.id)
    }
  } catch (e) {
    formError.value = e.response?.data?.detail || 'Erreur serveur'
  } finally {
    saving.value = false
  }
}

function confirmDelete(g) { deleteTarget.value = g }

async function doDelete() {
  saving.value = true
  try {
    await groupsApi.delete(deleteTarget.value.id)
    if (selected.value?.id === deleteTarget.value.id) { selected.value = null; groupRules.value = [] }
    deleteTarget.value = null
    await loadGroups()
  } finally {
    saving.value = false
  }
}

onMounted(loadGroups)
</script>

<style scoped>
.toggle-wrap  { display:inline-flex;align-items:center;cursor:pointer }
.toggle-input { display:none }
.toggle-slider {
  position:relative;width:32px;height:18px;
  background:var(--border);border-radius:9px;transition:background .2s
}
.toggle-slider::after {
  content:'';position:absolute;top:3px;left:3px;
  width:12px;height:12px;background:#fff;border-radius:50%;transition:transform .2s
}
.toggle-input:checked  + .toggle-slider                { background:var(--accent) }
.toggle-input:checked  + .toggle-slider::after         { transform:translateX(14px) }
.toggle-input:disabled + .toggle-slider                { opacity:.5;cursor:not-allowed }
</style>