<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Exceptions</h1>
    </div>

    <div class="card" style="margin-bottom:16px;padding:12px 16px;font-size:12px;color:var(--text-muted);border-left:3px solid var(--accent)">
      Les hôtes listés ici ne sont <strong style="color:var(--text)">pas filtrés</strong> par le proxy.
      Leurs sous-domaines sont automatiquement inclus.
      Le proxy recharge cette liste toutes les 5 minutes.
    </div>

    <div class="card" style="padding:0;overflow:hidden">
      <!-- En-tête -->
      <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--border)">
        <div style="font-weight:600;font-size:13px">{{ entries.length }} exception{{ entries.length !== 1 ? 's' : '' }}</div>
        <button v-if="auth.isAdmin" class="btn btn-primary btn-sm" @click="openAdd">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Ajouter
        </button>
      </div>

      <!-- Table -->
      <div v-if="loading" style="padding:32px;text-align:center;color:var(--text-muted)">Chargement…</div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Hôte</th>
              <th>Description</th>
              <th style="width:48px"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in entries" :key="e.id">
              <td>
                <code class="mono" style="font-size:12px;color:var(--blue)">{{ e.host }}</code>
                <span style="font-size:11px;color:var(--text-muted);margin-left:6px">+ *.{{ e.host }}</span>
              </td>
              <td style="color:var(--text-muted);font-size:12px">{{ e.description || '—' }}</td>
              <td>
                <button v-if="auth.isAdmin" class="btn btn-danger btn-sm btn-icon" @click="confirmDelete(e)">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                    <path d="M10 11v6M14 11v6M9 6V4h6v2"/>
                  </svg>
                </button>
              </td>
            </tr>
            <tr v-if="!entries.length">
              <td colspan="3" style="text-align:center;padding:28px;color:var(--text-muted)">
                Aucune exception configurée
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Modal ajout -->
    <div class="modal-overlay" v-if="showModal" @click.self="showModal = false">
      <div class="modal" style="width:400px">
        <div class="modal-title">Ajouter une exception</div>
        <div v-if="formError" class="alert alert-error">{{ formError }}</div>
        <div class="form-group" style="margin-bottom:14px">
          <label class="form-label">Hôte *</label>
          <input
            v-model="form.host"
            class="form-input"
            placeholder="ex: discord.com"
            @keyup.enter="save"
            autofocus
          />
          <div style="font-size:11px;color:var(--text-muted);margin-top:4px">
            Les sous-domaines sont inclus automatiquement (*.discord.com)
          </div>
        </div>
        <div class="form-group" style="margin-bottom:20px">
          <label class="form-label">Description</label>
          <input v-model="form.description" class="form-input" placeholder="Optionnel" @keyup.enter="save" />
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="showModal = false">Annuler</button>
          <button class="btn btn-primary" @click="save" :disabled="saving">
            {{ saving ? 'Enregistrement…' : 'Ajouter' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Modal confirmation suppression -->
    <div class="modal-overlay" v-if="deleteTarget" @click.self="deleteTarget = null">
      <div class="modal" style="width:360px">
        <div class="modal-title">Supprimer l'exception ?</div>
        <p style="color:var(--text-muted);margin-bottom:16px">
          <strong style="color:var(--text)">{{ deleteTarget.host }}</strong> sera de nouveau filtré par le proxy.
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
import { ref, onMounted }  from 'vue'
import { tlsBypassApi }    from '@/api'
import { useAuthStore }    from '@/stores/auth'

const auth        = useAuthStore()
const entries     = ref([])
const loading     = ref(false)
const saving      = ref(false)
const showModal   = ref(false)
const deleteTarget = ref(null)
const formError   = ref('')
const form        = ref({ host: '', description: '' })

async function load() {
  loading.value = true
  try {
    const { data } = await tlsBypassApi.list()
    entries.value = data
  } finally {
    loading.value = false
  }
}

function openAdd() {
  form.value    = { host: '', description: '' }
  formError.value = ''
  showModal.value = true
}

async function save() {
  formError.value = ''
  if (!form.value.host.trim()) { formError.value = "L'hôte est obligatoire"; return }
  saving.value = true
  try {
    await tlsBypassApi.create(form.value)
    showModal.value = false
    await load()
  } catch (e) {
    formError.value = e.response?.data?.detail || 'Erreur serveur'
  } finally {
    saving.value = false
  }
}

function confirmDelete(e) { deleteTarget.value = e }

async function doDelete() {
  saving.value = true
  try {
    await tlsBypassApi.delete(deleteTarget.value.id)
    deleteTarget.value = null
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
