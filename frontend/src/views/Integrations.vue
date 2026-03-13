<template>
  <div class="page-container">

    <!-- ── En-tête ────────────────────────────────────────────────────────── -->
    <div class="page-header" style="justify-content:space-between">
      <div style="display:flex;flex-direction:column;gap:2px">
        <h1 class="page-title">Intégrations RMM</h1>
        <p style="margin:0;font-size:12px;color:var(--text-muted)">
          Synchronisation automatique des agents depuis vos outils de gestion (RMM).
        </p>
      </div>
      <button class="btn btn-primary" @click="openCreate">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        Ajouter
      </button>
    </div>

    <!-- ── Types supportés ────────────────────────────────────────────────── -->
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:4px">
      <div v-for="t in RMM_TYPES" :key="t.key"
        style="display:flex;align-items:center;gap:6px;padding:4px 10px;border-radius:6px;border:1px solid var(--border);font-size:11px;color:var(--text-muted)">
        <span :style="`color:${t.color}`">●</span> {{ t.label }}
      </div>
    </div>

    <!-- ── Tableau ────────────────────────────────────────────────────────── -->
    <div class="card" style="padding:0;overflow:hidden">
      <div v-if="loading" style="padding:32px;text-align:center;color:var(--text-muted)">Chargement…</div>
      <div v-else-if="integrations.length === 0"
        style="padding:40px;text-align:center;color:var(--text-muted);font-size:13px">
        Aucune intégration configurée. Ajoutez votre premier RMM.
      </div>
      <table v-else class="data-table" style="width:100%">
        <thead>
          <tr>
            <th>Nom</th>
            <th>Type</th>
            <th>URL</th>
            <th>Statut</th>
            <th>Dernière sync</th>
            <th style="text-align:right">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="intg in integrations" :key="intg.id">
            <td style="font-weight:500">{{ intg.name }}</td>
            <td>
              <span class="badge" :style="`background:${typeColor(intg.type)}22;color:${typeColor(intg.type)}`">
                {{ typeLabel(intg.type) }}
              </span>
            </td>
            <td style="font-family:monospace;font-size:11px;color:var(--text-muted);max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
              {{ intg.url }}
            </td>
            <td>
              <span v-if="!intg.enabled" class="badge badge-muted">Désactivé</span>
              <span v-else-if="intg.last_sync_status?.startsWith('OK')" class="badge badge-green">Actif</span>
              <span v-else-if="intg.last_sync_status?.startsWith('Erreur')" class="badge badge-red">Erreur</span>
              <span v-else class="badge badge-muted">En attente</span>
            </td>
            <td style="font-size:11px">
              <div v-if="intg.last_sync_at" style="display:flex;flex-direction:column;gap:2px">
                <span>{{ fmtDate(intg.last_sync_at) }}</span>
                <span style="color:var(--text-muted);font-size:10px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                  {{ intg.last_sync_status }}
                </span>
              </div>
              <span v-else style="color:var(--text-muted)">Jamais</span>
            </td>
            <td style="text-align:right;white-space:nowrap">
              <button class="btn" style="font-size:11px;padding:3px 9px;margin-right:4px"
                :disabled="syncing === intg.id"
                @click="doSync(intg)">
                <svg v-if="syncing !== intg.id" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                </svg>
                <span v-else style="display:inline-block;width:10px;height:10px;border:2px solid currentColor;border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite"></span>
                {{ syncing === intg.id ? 'Sync…' : 'Sync' }}
              </button>
              <button class="btn" style="font-size:11px;padding:3px 9px;margin-right:4px"
                @click="openEdit(intg)">Modifier</button>
              <button class="btn" style="font-size:11px;padding:3px 9px;color:var(--red);border-color:var(--red)"
                @click="confirmDelete(intg)">Supprimer</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── Résultat de sync ────────────────────────────────────────────────── -->
    <transition name="fade">
      <div v-if="syncResult"
        :style="`padding:10px 14px;border-radius:6px;font-size:12px;border:1px solid;${
          syncResult.error
            ? 'background:rgba(248,81,73,.1);border-color:var(--red);color:var(--red)'
            : 'background:rgba(46,160,67,.1);border-color:var(--green);color:var(--green)'
        }`">
        <strong>{{ syncResult.error ? 'Erreur' : 'Synchronisation réussie' }}</strong>
        <span v-if="!syncResult.error"> — {{ syncResult.created }} créés, {{ syncResult.updated }} mis à jour, {{ syncResult.skipped }} ignorés</span>
        <span v-else> — {{ syncResult.error }}</span>
      </div>
    </transition>

    <!-- ── Modal ajout / édition ──────────────────────────────────────────── -->
    <div v-if="showModal"
      style="position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;z-index:1000"
      @click.self="showModal = false">
      <div class="card" style="width:480px;max-width:95vw;padding:28px 24px;max-height:90vh;overflow-y:auto">
        <div style="font-size:16px;font-weight:700;margin-bottom:18px">
          {{ editing ? 'Modifier l\'intégration' : 'Nouvelle intégration RMM' }}
        </div>

        <div style="display:flex;flex-direction:column;gap:14px">

          <!-- Nom -->
          <div>
            <label class="form-label">Nom <span style="color:var(--red)">*</span></label>
            <input v-model="form.name" class="form-input" placeholder="Mon RMM" />
          </div>

          <!-- Type -->
          <div>
            <label class="form-label">Type <span style="color:var(--red)">*</span></label>
            <select v-model="form.type" class="form-input" :disabled="!!editing">
              <option value="">— Choisir —</option>
              <option v-for="t in RMM_TYPES" :key="t.key" :value="t.key">{{ t.label }}</option>
            </select>
            <div v-if="form.type" style="margin-top:6px;font-size:11px;color:var(--text-muted)">
              {{ RMM_TYPES.find(t => t.key === form.type)?.hint }}
            </div>
          </div>

          <!-- URL -->
          <div>
            <label class="form-label">URL de base <span style="color:var(--red)">*</span></label>
            <input v-model="form.url" class="form-input" placeholder="https://rmm.example.com" />
          </div>

          <!-- API Key -->
          <div>
            <label class="form-label">{{ apiKeyLabel }} <span style="color:var(--red)">*</span></label>
            <input v-model="form.api_key" class="form-input" type="password"
              :placeholder="apiKeyPlaceholder" autocomplete="new-password" />
          </div>

          <!-- API Secret (NinjaRMM / Datto) -->
          <div v-if="needsSecret">
            <label class="form-label">{{ apiSecretLabel }} <span style="color:var(--red)">*</span></label>
            <input v-model="form.api_secret" class="form-input" type="password"
              :placeholder="apiSecretPlaceholder" autocomplete="new-password" />
          </div>

          <!-- Intervalle -->
          <div>
            <label class="form-label">Intervalle de synchronisation (minutes)</label>
            <input v-model.number="form.sync_interval_minutes" class="form-input" type="number" min="5" max="1440" />
          </div>

          <!-- Activé -->
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px">
            <input type="checkbox" v-model="form.enabled" />
            Activer la synchronisation automatique
          </label>

          <!-- Erreur -->
          <div v-if="formError"
            style="padding:8px 12px;border-radius:5px;background:rgba(248,81,73,.1);border:1px solid var(--red);color:var(--red);font-size:12px">
            {{ formError }}
          </div>
        </div>

        <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:22px">
          <button class="btn" @click="showModal = false">Annuler</button>
          <button class="btn btn-primary" @click="saveIntegration" :disabled="saving">
            {{ saving ? 'Enregistrement…' : (editing ? 'Mettre à jour' : 'Créer') }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Confirmation suppression ───────────────────────────────────────── -->
    <div v-if="deleteTarget"
      style="position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;z-index:1000"
      @click.self="deleteTarget = null">
      <div class="card" style="width:400px;padding:26px 24px">
        <div style="font-size:16px;font-weight:700;margin-bottom:8px">Supprimer l'intégration ?</div>
        <div style="font-size:13px;color:var(--text-muted);margin-bottom:20px;line-height:1.5">
          L'intégration <strong>{{ deleteTarget.name }}</strong> sera supprimée. Les utilisateurs clients importés depuis ce RMM ne seront pas supprimés, mais perdront leur lien.
        </div>
        <div style="display:flex;gap:10px;justify-content:flex-end">
          <button class="btn" @click="deleteTarget = null">Annuler</button>
          <button class="btn" style="background:var(--red);color:#fff;border-color:var(--red)"
            @click="doDelete">Supprimer</button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { integrationsApi } from '@/api'

// ── Config types RMM ──────────────────────────────────────────────────────────
const RMM_TYPES = [
  {
    key: 'tactical', label: 'Tactical RMM', color: '#58a6ff',
    hint: 'URL de votre instance Tactical RMM (ex : https://rmm.example.com). Clé API générée dans Paramètres > API.',
  },
  {
    key: 'ninja', label: 'NinjaRMM', color: '#7ee787',
    hint: 'URL de l\'API NinjaRMM (ex : https://app.ninjarmm.com). Client ID et Client Secret OAuth2.',
  },
  {
    key: 'datto', label: 'Datto RMM', color: '#e3b341',
    hint: 'URL de l\'API Datto (ex : https://zinfandel-api.centrastage.net). Clé et Secret API depuis Datto RMM > Setup > API.',
  },
  {
    key: 'atera', label: 'Atera', color: '#ff7b72',
    hint: 'URL https://app.atera.com. Clé API depuis Atera > Admin > API.',
  },
]

// ── État ──────────────────────────────────────────────────────────────────────
const integrations = ref([])
const loading      = ref(true)
const showModal    = ref(false)
const editing      = ref(null)   // intégration en cours d'édition
const saving       = ref(false)
const formError    = ref('')
const syncing      = ref(null)   // id en cours de sync
const syncResult   = ref(null)
const deleteTarget = ref(null)

const emptyForm = () => ({
  name: '', type: '', url: '', api_key: '', api_secret: '',
  sync_interval_minutes: 60, enabled: true,
})
const form = ref(emptyForm())

// ── Labels dynamiques selon le type ──────────────────────────────────────────
const needsSecret = computed(() => ['ninja', 'datto'].includes(form.value.type))

const apiKeyLabel = computed(() => ({
  ninja: 'Client ID (OAuth2)',
  datto: 'Clé API publique',
}[form.value.type] ?? 'Clé API'))

const apiKeyPlaceholder = computed(() => ({
  tactical: 'xxxxxxxxxxxxxxxxxxxxxxxx',
  ninja:    'ni_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
  datto:    'xxxxxxxxxxxxxxxxxxxxxxxx',
  atera:    'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
}[form.value.type] ?? ''))

const apiSecretLabel = computed(() => form.value.type === 'ninja' ? 'Client Secret (OAuth2)' : 'Secret API')
const apiSecretPlaceholder = computed(() => 'xxxxxxxxxxxxxxxxxxxx')

// ── Helpers ───────────────────────────────────────────────────────────────────
function typeColor(type) {
  return RMM_TYPES.find(t => t.key === type)?.color ?? '#8b949e'
}
function typeLabel(type) {
  return RMM_TYPES.find(t => t.key === type)?.label ?? type
}
function fmtDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}

// ── Chargement ────────────────────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const { data } = await integrationsApi.list()
    integrations.value = data
  } finally {
    loading.value = false
  }
}

// ── Modal ─────────────────────────────────────────────────────────────────────
function openCreate() {
  editing.value  = null
  form.value     = emptyForm()
  formError.value = ''
  showModal.value = true
}

function openEdit(intg) {
  editing.value = intg
  form.value = {
    name:                  intg.name,
    type:                  intg.type,
    url:                   intg.url,
    api_key:               intg.api_key,
    api_secret:            intg.api_secret ?? '',
    sync_interval_minutes: intg.sync_interval_minutes,
    enabled:               intg.enabled,
  }
  formError.value = ''
  showModal.value = true
}

async function saveIntegration() {
  formError.value = ''
  if (!form.value.name.trim())     { formError.value = 'Le nom est requis.'; return }
  if (!form.value.type)            { formError.value = 'Choisissez un type.'; return }
  if (!form.value.url.trim())      { formError.value = 'L\'URL est requise.'; return }
  if (!form.value.api_key.trim())  { formError.value = 'La clé API est requise.'; return }
  if (needsSecret.value && !form.value.api_secret?.trim()) {
    formError.value = `${apiSecretLabel.value} est requis pour ${typeLabel(form.value.type)}.`
    return
  }

  saving.value = true
  try {
    const payload = { ...form.value }
    if (!payload.api_secret) delete payload.api_secret

    if (editing.value) {
      const { data } = await integrationsApi.update(editing.value.id, payload)
      const idx = integrations.value.findIndex(i => i.id === editing.value.id)
      if (idx >= 0) integrations.value[idx] = data
    } else {
      const { data } = await integrationsApi.create(payload)
      integrations.value.push(data)
    }
    showModal.value = false
  } catch (err) {
    formError.value = err.response?.data?.detail ?? 'Erreur lors de l\'enregistrement.'
  } finally {
    saving.value = false
  }
}

// ── Sync manuelle ─────────────────────────────────────────────────────────────
async function doSync(intg) {
  syncing.value    = intg.id
  syncResult.value = null
  try {
    const { data } = await integrationsApi.sync(intg.id)
    syncResult.value = data
    // Mettre à jour le statut affiché
    await load()
  } catch (err) {
    syncResult.value = { error: err.response?.data?.detail ?? 'Erreur de synchronisation.' }
  } finally {
    syncing.value = null
    setTimeout(() => { syncResult.value = null }, 8000)
  }
}

// ── Suppression ───────────────────────────────────────────────────────────────
function confirmDelete(intg) {
  deleteTarget.value = intg
}

async function doDelete() {
  if (!deleteTarget.value) return
  await integrationsApi.delete(deleteTarget.value.id)
  integrations.value = integrations.value.filter(i => i.id !== deleteTarget.value.id)
  deleteTarget.value = null
}

// ── Init ──────────────────────────────────────────────────────────────────────
onMounted(load)
</script>

<style scoped>
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}
.badge-green  { background: rgba(46,160,67,.15); color: var(--green); }
.badge-red    { background: rgba(248,81,73,.15);  color: var(--red); }
.badge-muted  { background: rgba(139,148,158,.15); color: var(--text-muted); }

.fade-enter-active, .fade-leave-active { transition: opacity .3s; }
.fade-enter-from, .fade-leave-to       { opacity: 0; }

@keyframes spin { to { transform: rotate(360deg); } }
</style>
