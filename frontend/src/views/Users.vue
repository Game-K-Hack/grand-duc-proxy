<template>
  <div>
    <div style="display:flex;justify-content:flex-end;margin-bottom:16px">
      <button v-if="auth.hasPermission('users.write')" class="btn btn-primary" @click="openCreate">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        Nouvel utilisateur
      </button>
    </div>

    <div class="card" style="padding:0">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Identifiant</th>
              <th>Email</th>
              <th>Rôle</th>
              <th>Statut</th>
              <th>Dernière connexion</th>
              <th>Créé le</th>
              <th v-if="auth.hasPermission('users.write')" style="width:100px">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td :colspan="auth.hasPermission('users.write') ? 7 : 6" style="text-align:center;padding:24px;color:var(--text-muted)">Chargement…</td></tr>
            <tr v-for="u in users" :key="u.id">
              <td style="font-weight:600">{{ u.username }}</td>
              <td style="color:var(--text-muted)">{{ u.email || '—' }}</td>
              <td><span class="badge badge-role">{{ u.role_name }}</span></td>
              <td><span :class="u.enabled ? 'badge badge-on' : 'badge badge-off'">{{ u.enabled ? 'Actif' : 'Désactivé' }}</span></td>
              <td style="color:var(--text-muted);font-size:12px">{{ u.last_login ? fmtDate(u.last_login) : 'Jamais' }}</td>
              <td style="color:var(--text-muted);font-size:12px">{{ fmtDate(u.created_at) }}</td>
              <td v-if="auth.hasPermission('users.write')" style="display:flex;gap:6px;padding:8px 14px">
                <button class="btn btn-ghost btn-sm btn-icon" @click="openEdit(u)" title="Modifier">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button
                  class="btn btn-danger btn-sm btn-icon"
                  @click="confirmDelete(u)"
                  :disabled="u.id === currentUserId"
                  title="Supprimer"
                >
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

    <!-- Modal créer/modifier -->
    <div class="modal-overlay" v-if="showModal" @click.self="showModal = false">
      <div class="modal">
        <div class="modal-title">{{ editingUser ? 'Modifier l\'utilisateur' : 'Nouvel utilisateur' }}</div>

        <div v-if="formError" class="alert alert-error">{{ formError }}</div>
        <div v-if="formSuccess" class="alert alert-success">{{ formSuccess }}</div>

        <div class="form-row cols-2">
          <div class="form-group">
            <label class="form-label">Identifiant *</label>
            <input v-model="form.username" class="form-input" :disabled="!!editingUser" />
          </div>
          <div class="form-group">
            <label class="form-label">Email</label>
            <input v-model="form.email" type="email" class="form-input" />
          </div>
        </div>

        <div class="form-row cols-2">
          <div class="form-group">
            <label class="form-label">{{ editingUser ? 'Nouveau mot de passe (laisser vide = inchangé)' : 'Mot de passe *' }}</label>
            <input v-model="form.password" type="password" class="form-input" autocomplete="new-password" />
          </div>
          <div class="form-group">
            <label class="form-label">Rôle</label>
            <select v-model="form.role_id" class="form-select" :disabled="!roles.length">
              <option v-if="!roles.length" disabled value="">Aucun rôle disponible</option>
              <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.name }}</option>
            </select>
          </div>
        </div>

        <div style="display:flex;gap:20px;flex-wrap:wrap">
          <div class="form-group" style="flex-direction:row;align-items:center;gap:10px">
            <label class="toggle">
              <input type="checkbox" v-model="form.enabled" />
              <span class="toggle-slider"></span>
            </label>
            <span class="form-label" style="margin:0">Compte activé</span>
          </div>
          <div class="form-group" style="flex-direction:row;align-items:center;gap:10px">
            <label class="toggle">
              <input type="checkbox" v-model="form.must_change_password" />
              <span class="toggle-slider"></span>
            </label>
            <span class="form-label" style="margin:0">Mot de passe temporaire</span>
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
        <div class="modal-title">Supprimer l'utilisateur ?</div>
        <p style="color:var(--text-muted);margin-bottom:16px">
          Cette action est irréversible. L'utilisateur <strong style="color:var(--text)">{{ deleteTarget?.username }}</strong> sera supprimé.
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
import { ref, onMounted }   from 'vue'
import { usersApi }          from '@/api'
import { useAuthStore }     from '@/stores/auth'

const auth          = useAuthStore()
const users         = ref([])
const roles         = ref([])
const loading       = ref(false)
const saving        = ref(false)
const showModal     = ref(false)
const editingUser   = ref(null)
const deleteTarget  = ref(null)
const formError     = ref('')
const formSuccess   = ref('')
const currentUserId = ref(null)

const form = ref({ username: '', email: '', password: '', role_id: null, enabled: true, must_change_password: false })

function fmtDate(iso) {
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

async function loadRoles() {
  try {
    const { data } = await usersApi.assignableRoles()
    roles.value = data
  } catch { /* ignore */ }
}

async function load() {
  loading.value = true
  try {
    const { data } = await usersApi.list()
    users.value = data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingUser.value = null
  const defaultRole = roles.value.find(r => r.name === 'Lecteur') || roles.value[0]
  form.value        = { username: '', email: '', password: '', role_id: defaultRole?.id, enabled: true, must_change_password: false }
  formError.value   = ''
  formSuccess.value = ''
  showModal.value   = true
}

async function openEdit(u) {
  // Recharger pour avoir les données à jour (ex: must_change_password modifié par l'utilisateur)
  await load()
  const fresh = users.value.find(x => x.id === u.id) || u
  editingUser.value = fresh
  form.value        = { username: fresh.username, email: fresh.email || '', password: '', role_id: fresh.role_id, enabled: fresh.enabled, must_change_password: fresh.must_change_password }
  formError.value   = ''
  formSuccess.value = ''
  showModal.value   = true
}

async function save() {
  formError.value   = ''
  formSuccess.value = ''
  saving.value      = true
  try {
    if (editingUser.value) {
      const payload = { email: form.value.email, role_id: form.value.role_id, enabled: form.value.enabled, must_change_password: form.value.must_change_password }
      if (form.value.password) payload.password = form.value.password
      await usersApi.update(editingUser.value.id, payload)
    } else {
      if (!form.value.username || !form.value.password) {
        formError.value = 'Identifiant et mot de passe requis'
        return
      }
      await usersApi.create(form.value)
    }
    showModal.value = false
    load()
  } catch (e) {
    formError.value = e.response?.data?.detail || 'Erreur serveur'
  } finally {
    saving.value = false
  }
}

function confirmDelete(u) { deleteTarget.value = u }

async function doDelete() {
  saving.value = true
  try {
    await usersApi.delete(deleteTarget.value.id)
    deleteTarget.value = null
    load()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await Promise.all([load(), loadRoles()])
  const me = users.value.find(u => u.username === auth.user?.username)
  if (me) currentUserId.value = me.id
})
</script>
