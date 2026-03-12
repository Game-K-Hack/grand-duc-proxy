<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Utilisateurs clients</h1>
    </div>

    <div style="display:grid;grid-template-columns:300px 1fr;gap:20px;align-items:start">

      <!-- ── Liste des utilisateurs ──────────────────────────────────── -->
      <div class="card" style="padding:0;overflow:hidden">
        <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border-bottom:1px solid var(--border)">
          <div style="font-weight:600;font-size:13px">Utilisateurs</div>
          <button v-if="auth.hasPermission('client_users.write')" class="btn btn-primary btn-sm" @click="openCreate">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            Ajouter
          </button>
        </div>

        <!-- Recherche -->
        <div style="padding:8px 10px;border-bottom:1px solid var(--border)">
          <input v-model="search" class="form-input" style="height:30px;font-size:12px" placeholder="Filtrer…" />
        </div>

        <!-- Liste -->
        <div style="max-height:calc(100vh - 240px);overflow-y:auto">
          <div
            v-for="u in filteredUsers" :key="u.id"
            style="padding:10px 14px;border-bottom:1px solid var(--border);cursor:pointer;transition:background .1s;border-left:3px solid transparent"
            :style="selected?.id === u.id ? 'background:var(--surface2);border-left-color:var(--accent);padding-left:11px' : 'padding-left:11px'"
            @click="selectUser(u)"
          >
            <div style="display:flex;align-items:center;justify-content:space-between">
              <div style="min-width:0">
                <div style="display:flex;align-items:center;gap:6px">
                  <div style="font-size:13px;font-weight:500">{{ u.label || u.ip_address }}</div>
                  <span v-if="u.source === 'rmm'"
                    style="font-size:9px;padding:1px 5px;border-radius:8px;background:rgba(88,166,255,.15);color:#58a6ff;font-weight:600;flex-shrink:0">
                    RMM
                  </span>
                </div>
                <div style="font-size:11px;color:var(--text-muted);font-family:monospace;margin-top:1px">
                  {{ u.label ? u.ip_address : '' }}
                </div>
                <div v-if="u.hostname && u.hostname !== u.label" style="font-size:10px;color:var(--text-muted);margin-top:1px">
                  {{ u.hostname }}
                </div>
                <div style="display:flex;flex-wrap:wrap;gap:3px;margin-top:4px">
                  <span
                    v-for="g in u.groups" :key="g.id"
                    style="font-size:10px;padding:1px 6px;border-radius:10px;background:var(--surface2);border:1px solid var(--border)"
                  >{{ g.name }}</span>
                  <span v-if="!u.groups.length" style="font-size:10px;color:var(--text-muted)">Sans groupe</span>
                </div>
              </div>
              <div v-if="selected?.id === u.id && auth.hasPermission('client_users.write')" style="display:flex;gap:3px;flex-shrink:0;margin-left:6px">
                <button class="btn btn-ghost btn-sm btn-icon" @click.stop="openEdit(u)">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button class="btn btn-danger btn-sm btn-icon" @click.stop="confirmDelete(u)">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                    <path d="M10 11v6M14 11v6M9 6V4h6v2"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
          <div v-if="!filteredUsers.length" style="padding:24px;text-align:center;color:var(--text-muted);font-size:13px">
            {{ search ? 'Aucun résultat' : 'Aucun utilisateur' }}
          </div>
        </div>
      </div>

      <!-- ── Panneau droite : groupes de l'utilisateur sélectionné ──── -->
      <div v-if="selected">
        <!-- Carte info utilisateur -->
        <div class="card" style="padding:14px 18px;margin-bottom:16px">
          <div style="display:flex;align-items:flex-start;gap:16px">
            <div style="flex:1">
              <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                <div style="font-size:16px;font-weight:700">{{ selected.label || selected.ip_address }}</div>
                <span v-if="selected.source === 'rmm'"
                  style="font-size:10px;padding:2px 7px;border-radius:10px;background:rgba(88,166,255,.15);color:#58a6ff;font-weight:600">
                  RMM
                </span>
              </div>
              <div style="font-family:monospace;font-size:13px;color:var(--text-muted);margin-top:2px">
                {{ selected.label ? selected.ip_address : '' }}
              </div>
              <div v-if="selected.hostname || selected.os" style="display:flex;gap:16px;margin-top:8px;flex-wrap:wrap">
                <div v-if="selected.hostname" style="font-size:12px;color:var(--text-muted)">
                  <span style="color:var(--text-muted)">Hôte :</span>
                  <strong style="color:var(--text);margin-left:4px">{{ selected.hostname }}</strong>
                </div>
                <div v-if="selected.os" style="font-size:12px;color:var(--text-muted)">
                  <span>OS :</span>
                  <strong style="color:var(--text);margin-left:4px">{{ selected.os }}</strong>
                </div>
                <div v-if="selected.last_seen_rmm" style="font-size:12px;color:var(--text-muted)">
                  <span>Vu :</span>
                  <strong style="color:var(--text);margin-left:4px">{{ fmtDate(selected.last_seen_rmm) }}</strong>
                </div>
              </div>
            </div>
            <button v-if="auth.hasPermission('client_users.write')" class="btn btn-ghost btn-sm" @click="openEdit(selected)">
              Modifier
            </button>
          </div>
        </div>

        <!-- Gestion des groupes -->
        <div class="card" style="padding:0;overflow:hidden">
          <div style="padding:12px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;gap:12px">
            <div>
              <div style="font-weight:600;font-size:13px;margin-bottom:2px">Groupes assignés</div>
              <div style="font-size:12px;color:var(--text-muted)">Les règles s'appliquent cumulativement dans l'ordre de priorité.</div>
            </div>
            <div v-if="auth.hasPermission('client_users.write')" style="flex-shrink:0">
              <button ref="addBtnRef" class="btn btn-primary btn-sm" @click="toggleDropdown" :disabled="savingGroups">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
                Ajouter
              </button>
              <Teleport to="body">
                <template v-if="showAddDropdown">
                  <div style="position:fixed;inset:0;z-index:999" @click="closeDropdown" />
                  <div :style="`position:fixed;top:${ddPos.top}px;right:${ddPos.right}px;z-index:1000;background:var(--surface);border:1px solid var(--border);border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.3);width:260px`">
                    <div style="padding:8px;border-bottom:1px solid var(--border)">
                      <input v-model="searchGroup" class="form-input" style="height:30px;font-size:12px" placeholder="Rechercher un groupe…" @click.stop />
                    </div>
                    <div style="max-height:220px;overflow-y:auto;padding:4px">
                      <div v-if="!filteredDropdownGroups.length" style="padding:10px 12px;font-size:13px;color:var(--text-muted)">
                        {{ availableGroups.length ? 'Aucun résultat' : 'Tous les groupes sont déjà assignés' }}
                      </div>
                      <button v-for="g in filteredDropdownGroups" :key="g.id" class="dropdown-item" @click="addGroup(g.id)">
                        <div style="font-size:13px;font-weight:500">{{ g.name }}</div>
                        <div style="font-size:11px;color:var(--text-muted);margin-top:1px">
                          {{ g.description || `${g.rule_count} règle${g.rule_count !== 1 ? 's' : ''}` }}
                        </div>
                      </button>
                    </div>
                  </div>
                </template>
              </Teleport>
            </div>
          </div>

          <!-- Liste des groupes assignés -->
          <div>
            <div v-if="!assignedGroups.length" style="padding:20px;text-align:center;font-size:13px;color:var(--text-muted)">
              Aucun groupe — groupe Défaut appliqué
            </div>
            <div
              v-for="g in assignedGroups" :key="g.id"
              class="group-row"
            >
              <div style="flex:1;min-width:0">
                <div style="font-size:13px;font-weight:500">{{ g.name }}</div>
                <div v-if="g.description" style="font-size:11px;color:var(--text-muted);margin-top:1px">{{ g.description }}</div>
                <div v-else style="font-size:11px;color:var(--text-muted);margin-top:1px">{{ g.rule_count }} règle{{ g.rule_count !== 1 ? 's' : '' }}</div>
              </div>
              <button v-if="auth.hasPermission('client_users.write')" class="btn btn-danger btn-sm btn-icon group-row-del" @click="removeGroup(g.id)" :disabled="savingGroups">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                  <path d="M10 11v6M14 11v6M9 6V4h6v2"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="card" style="display:flex;align-items:center;justify-content:center;min-height:180px;color:var(--text-muted);font-size:13px">
        ← Sélectionnez un utilisateur
      </div>
    </div>

    <!-- ── Modal créer/modifier ──────────────────────────────────────── -->
    <div class="modal-overlay" v-if="showModal" @click.self="showModal = false">
      <div class="modal" style="width:400px">
        <div class="modal-title">{{ editing ? 'Modifier l\'utilisateur' : 'Ajouter une IP' }}</div>
        <div v-if="formError" class="alert alert-error">{{ formError }}</div>

        <div v-if="!editing" class="form-group" style="margin-bottom:14px">
          <label class="form-label">Adresse IP *</label>
          <input v-model="form.ip_address" class="form-input" placeholder="192.168.1.42" @keyup.enter="save" />
        </div>

        <div class="form-group" style="margin-bottom:14px">
          <label class="form-label">Nom / étiquette</label>
          <input v-model="form.label" class="form-input" placeholder="Ex: Poste Jean-Marie" @keyup.enter="save" />
        </div>

        <div class="form-group" style="margin-bottom:14px">
          <label class="form-label">Nom d'hôte</label>
          <input v-model="form.hostname" class="form-input" placeholder="PC-JMARIE" @keyup.enter="save" />
        </div>

        <div class="form-group" style="margin-bottom:20px">
          <label class="form-label">Système d'exploitation</label>
          <input v-model="form.os" class="form-input" placeholder="Windows 10 Pro" @keyup.enter="save" />
        </div>

        <div class="modal-footer">
          <button class="btn btn-ghost" @click="showModal = false">Annuler</button>
          <button class="btn btn-primary" @click="save" :disabled="saving">
            {{ saving ? 'Enregistrement…' : 'Enregistrer' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Modal confirmation suppression ────────────────────────────── -->
    <div class="modal-overlay" v-if="deleteTarget" @click.self="deleteTarget = null">
      <div class="modal" style="width:360px">
        <div class="modal-title">Supprimer cet utilisateur ?</div>
        <p style="color:var(--text-muted);margin-bottom:16px">
          L'IP <strong style="font-family:monospace;color:var(--text)">{{ deleteTarget.ip_address }}</strong>
          {{ deleteTarget.label ? `(${deleteTarget.label})` : '' }} sera supprimée ainsi que ses associations de groupes.
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
import { clientUsersApi, groupsApi } from '@/api'
import { useAuthStore }              from '@/stores/auth'

const auth = useAuthStore()

const users       = ref([])
const allGroups   = ref([])
const selected    = ref(null)
const search      = ref('')
const savingGroups     = ref(false)
const saving           = ref(false)
const formError        = ref('')
const showModal        = ref(false)
const editing          = ref(null)
const deleteTarget     = ref(null)
const form             = ref({ ip_address: '', label: '', hostname: '', os: '' })
const showAddDropdown  = ref(false)
const addBtnRef        = ref(null)
const ddPos            = ref({ top: 0, right: 0 })
const searchGroup      = ref('')

const filteredDropdownGroups = computed(() => {
  const q = searchGroup.value.toLowerCase()
  return availableGroups.value.filter(g =>
    !q || g.name.toLowerCase().includes(q) || (g.description || '').toLowerCase().includes(q)
  )
})

function toggleDropdown() {
  if (!showAddDropdown.value) {
    const rect = addBtnRef.value.getBoundingClientRect()
    ddPos.value = { top: rect.bottom + 6, right: window.innerWidth - rect.right }
    searchGroup.value = ''
  }
  showAddDropdown.value = !showAddDropdown.value
}

function closeDropdown() {
  showAddDropdown.value = false
  searchGroup.value = ''
}

const assignedGroups = computed(() => {
  if (!selected.value) return []
  return selected.value.groups
    .map(g => allGroups.value.find(ag => ag.id === g.id) ?? g)
    .filter(g => !g.is_default)
})

const availableGroups = computed(() =>
  allGroups.value.filter(g => !g.is_default && !isInGroup(g.id))
)

const filteredUsers = computed(() => {
  const q = search.value.toLowerCase()
  if (!q) return users.value
  return users.value.filter(u =>
    u.ip_address.includes(q) ||
    (u.label    || '').toLowerCase().includes(q) ||
    (u.hostname || '').toLowerCase().includes(q) ||
    (u.os       || '').toLowerCase().includes(q)
  )
})

function fmtDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}

function isInGroup(gid) {
  return selected.value?.groups?.some(g => g.id === gid) ?? false
}

async function loadUsers() {
  const { data } = await clientUsersApi.list()
  users.value = data
}

async function selectUser(u) {
  selected.value = u
}

async function toggleGroup(gid, checked) {
  if (!selected.value) return
  savingGroups.value = true
  try {
    const current = selected.value.groups.map(g => g.id)
    const updated = checked
      ? [...new Set([...current, gid])]
      : current.filter(id => id !== gid)
    const { data } = await clientUsersApi.setGroups(selected.value.id, updated)
    // Met à jour les groupes affichés
    selected.value = { ...selected.value, groups: data }
    // Met à jour aussi la liste
    const idx = users.value.findIndex(u => u.id === selected.value.id)
    if (idx !== -1) users.value[idx] = { ...users.value[idx], groups: data }
  } finally {
    savingGroups.value = false
  }
}

async function addGroup(gid) {
  closeDropdown()
  await toggleGroup(gid, true)
}

async function removeGroup(gid) {
  await toggleGroup(gid, false)
}

function openCreate() {
  editing.value = null
  form.value    = { ip_address: '', label: '', hostname: '', os: '' }
  formError.value = ''
  showModal.value = true
}

function openEdit(u) {
  editing.value = u
  form.value    = { ip_address: u.ip_address, label: u.label || '', hostname: u.hostname || '', os: u.os || '' }
  formError.value = ''
  showModal.value = true
}

async function save() {
  formError.value = ''
  if (!editing.value && !form.value.ip_address.trim()) {
    formError.value = 'L\'adresse IP est obligatoire'; return
  }
  saving.value = true
  try {
    if (editing.value) {
      const { data } = await clientUsersApi.update(editing.value.id, {
        label:    form.value.label    || null,
        hostname: form.value.hostname || null,
        os:       form.value.os       || null,
      })
      const idx = users.value.findIndex(u => u.id === editing.value.id)
      if (idx !== -1) users.value[idx] = data
      if (selected.value?.id === editing.value.id) selected.value = data
    } else {
      await clientUsersApi.create({
        ip_address: form.value.ip_address,
        label:      form.value.label    || null,
        hostname:   form.value.hostname || null,
        os:         form.value.os       || null,
      })
      await loadUsers()
    }
    showModal.value = false
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
    await clientUsersApi.delete(deleteTarget.value.id)
    if (selected.value?.id === deleteTarget.value.id) selected.value = null
    deleteTarget.value = null
    await loadUsers()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadUsers(), groupsApi.list().then(r => { allGroups.value = r.data })])
})
</script>

<style scoped>
.group-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  transition: background .1s;
}
.group-row:last-child { border-bottom: none; }
.group-row:hover { background: var(--surface2); }
.group-row-del { opacity: 0; transition: opacity .15s; }
.group-row:hover .group-row-del { opacity: 1; }

.dropdown-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 12px;
  border-radius: 6px;
  border: none;
  background: none;
  cursor: pointer;
  color: var(--text);
  transition: background .1s;
}
.dropdown-item:hover { background: var(--surface2); }
</style>