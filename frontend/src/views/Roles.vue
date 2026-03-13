<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Gestion des rôles</h1>
      <button v-if="auth.hasPermission('roles.write')" class="btn btn-primary" @click="openCreate">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        Nouveau rôle
      </button>
    </div>

    <div class="card" style="padding:0">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Nom</th>
              <th>Description</th>
              <th>Permissions</th>
              <th>Utilisateurs</th>
              <th>Type</th>
              <th v-if="auth.hasPermission('roles.write')" style="width:100px">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td :colspan="auth.hasPermission('roles.write') ? 6 : 5" style="text-align:center;padding:24px;color:var(--text-muted)">Chargement…</td></tr>
            <tr v-for="r in roles" :key="r.id">
              <td style="font-weight:600">{{ r.name }}</td>
              <td style="color:var(--text-muted)">{{ r.description || '—' }}</td>
              <td>
                <span class="badge badge-role">{{ countPerms(r.permissions) }} / {{ totalPerms }}</span>
              </td>
              <td>{{ r.user_count }}</td>
              <td>
                <span v-if="r.is_builtin" class="badge badge-on">Système</span>
                <span v-else class="badge" style="background:var(--bg-tertiary);color:var(--text-muted)">Personnalisé</span>
              </td>
              <td v-if="auth.hasPermission('roles.write')" style="display:flex;gap:6px;padding:8px 14px">
                <button v-if="!(r.is_builtin && r.name === 'Administrateur')" class="btn btn-ghost btn-sm btn-icon" @click="openEdit(r)" title="Modifier">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button v-if="!(r.is_builtin || r.user_count > 0)" class="btn btn-danger btn-sm btn-icon" @click="confirmDelete(r)" title="Supprimer">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                    <path d="M10 11v6M14 11v6M9 6V4h6v2"/>
                  </svg>
                </button>
                <span v-if="(r.is_builtin && r.name === 'Administrateur') && (r.is_builtin || r.user_count > 0)" style="height: calc(14px + 13px);"></span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Modal créer/modifier -->
    <div class="modal-overlay" v-if="showModal" @click.self="showModal = false">
      <div class="modal" style="width:640px;max-height:85vh;overflow-y:auto">
        <div class="modal-title">{{ editingRole ? 'Modifier le rôle' : 'Nouveau rôle' }}</div>

        <div v-if="formError" class="alert alert-error">{{ formError }}</div>

        <div class="form-row cols-2">
          <div class="form-group">
            <label class="form-label">Nom *</label>
            <input v-model="form.name" class="form-input" :disabled="editingRole?.is_builtin" />
          </div>
          <div class="form-group">
            <label class="form-label">Description</label>
            <input v-model="form.description" class="form-input" />
          </div>
        </div>

        <div class="form-group">
          <label class="form-label" style="margin-bottom:12px">
            Permissions
            <span style="color:var(--text-muted);font-weight:400;margin-left:8px">
              {{ countPerms(form.permissions) }} / {{ totalPerms }} sélectionnées
            </span>
          </label>

          <div v-for="(features, section) in permSections" :key="section" style="margin-bottom:16px">
            <div class="section-title">{{ section }}</div>

            <div v-for="(actions, feature) in features" :key="feature" class="feature-row">
              <span class="feature-name">{{ feature }}</span>
              <div class="feature-actions">
                <label v-for="a in actions" :key="a.key" class="action-item">
                  <span class="perm-toggle">
                    <input type="checkbox" v-model="form.permissions[a.key]" />
                    <span class="perm-toggle-slider"></span>
                  </span>
                  <span class="action-label">{{ a.action }}</span>
                </label>
              </div>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn btn-ghost" @click="showModal = false">Annuler</button>
          <button class="btn btn-primary" @click="save" :disabled="saving">
            {{ saving ? 'Enregistrement…' : 'Enregistrer' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Confirmer suppression -->
    <div class="modal-overlay" v-if="deleteTarget" @click.self="deleteTarget = null">
      <div class="modal" style="width:380px">
        <div class="modal-title">Supprimer le rôle ?</div>
        <p style="color:var(--text-muted);margin-bottom:16px">
          Le rôle <strong style="color:var(--text)">{{ deleteTarget?.name }}</strong> sera supprimé définitivement.
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
import { ref, onMounted, computed } from 'vue'
import { rolesApi }                 from '@/api'
import { useAuthStore }             from '@/stores/auth'

const auth         = useAuthStore()
const roles        = ref([])
const permSections = ref({})
const loading      = ref(false)
const saving       = ref(false)
const showModal    = ref(false)
const editingRole  = ref(null)
const deleteTarget = ref(null)
const formError    = ref('')

const form = ref({ name: '', description: '', permissions: {} })

const totalPerms = computed(() => {
  let n = 0
  for (const features of Object.values(permSections.value)) {
    for (const actions of Object.values(features)) n += actions.length
  }
  return n
})

function countPerms(permsObj) {
  return Object.values(permsObj || {}).filter(Boolean).length
}

async function loadPermissions() {
  try {
    const { data } = await rolesApi.permissions()
    permSections.value = data
  } catch { /* ignore */ }
}

async function load() {
  loading.value = true
  try {
    const { data } = await rolesApi.list()
    roles.value = data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingRole.value = null
  form.value = { name: '', description: '', permissions: {} }
  formError.value = ''
  showModal.value = true
}

function openEdit(r) {
  editingRole.value = r
  form.value = {
    name: r.name,
    description: r.description || '',
    permissions: { ...r.permissions },
  }
  formError.value = ''
  showModal.value = true
}

async function save() {
  formError.value = ''
  saving.value = true
  try {
    if (!form.value.name.trim()) {
      formError.value = 'Le nom est requis'
      return
    }
    const payload = {
      name: form.value.name,
      description: form.value.description,
      permissions: form.value.permissions,
    }
    if (editingRole.value) {
      await rolesApi.update(editingRole.value.id, payload)
    } else {
      await rolesApi.create(payload)
    }
    showModal.value = false
    load()
  } catch (e) {
    formError.value = e.response?.data?.detail || 'Erreur serveur'
  } finally {
    saving.value = false
  }
}

function confirmDelete(r) { deleteTarget.value = r }

async function doDelete() {
  saving.value = true
  try {
    await rolesApi.delete(deleteTarget.value.id)
    deleteTarget.value = null
    load()
  } catch (e) {
    formError.value = e.response?.data?.detail || 'Erreur serveur'
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadPermissions()
  load()
})
</script>

<style scoped>
.section-title {
  font-weight: 700;
  font-size: 13px;
  color: var(--text);
  padding: 10px 0 6px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 2px;
}

.feature-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 7px 0;
  border-bottom: 1px solid color-mix(in srgb, var(--border) 40%, transparent);
}
.feature-row:last-child {
  border-bottom: none;
}

.feature-name {
  font-size: 12px;
  color: var(--text-secondary);
  flex: 1;
  min-width: 0;
}

.feature-actions {
  display: flex;
  gap: 14px;
  flex-shrink: 0;
}

.action-item {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
}

.action-label {
  font-size: 11px;
  color: var(--text-muted);
}

.perm-toggle {
  position: relative;
  display: inline-block;
  width: 28px;
  height: 16px;
  flex-shrink: 0;
}
.perm-toggle input {
  display: none;
}
.perm-toggle-slider {
  position: absolute;
  inset: 0;
  background: var(--border);
  border-radius: 8px;
  transition: background .2s;
}
.perm-toggle-slider::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  background: #fff;
  border-radius: 50%;
  transition: transform .2s;
}
.perm-toggle input:checked + .perm-toggle-slider {
  background: var(--accent);
}
.perm-toggle input:checked + .perm-toggle-slider::after {
  transform: translateX(12px);
}
</style>
