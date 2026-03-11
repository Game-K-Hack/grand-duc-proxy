<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Test d'accès</h1>
    </div>

    <div style="max-width:760px">

      <!-- ── Formulaire de test ──────────────────────────────────────── -->
      <div class="card" style="margin-bottom:20px">
        <div class="card-title" style="margin-bottom:16px">Simuler une requête</div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px">
          <!-- Sélection utilisateur -->
          <div class="form-group">
            <label class="form-label" :style="errors.user ? 'color:var(--red)' : ''">Utilisateur (IP)</label>
            <select v-model="selectedUserId" class="form-select" :class="{ 'input-error': errors.user }" @change="errors.user = false">
              <option value="">— Choisir un utilisateur —</option>
              <option v-for="u in users" :key="u.id" :value="u.id">
                {{ u.label || u.ip_address }}
                {{ u.label ? `(${u.ip_address})` : '' }}
              </option>
            </select>
          </div>

          <!-- Groupes de l'utilisateur sélectionné (lecture seule) -->
          <div class="form-group">
            <label class="form-label">Groupes assignés</label>
            <div style="display:flex;flex-wrap:wrap;gap:4px;padding:6px 10px;background:var(--surface2);border:1px solid var(--border);border-radius:6px;min-height:36px;align-items:center">
              <template v-if="selectedUser">
                <span
                  v-for="g in selectedUser.groups" :key="g.id"
                  style="font-size:12px;padding:2px 8px;border-radius:10px;background:var(--surface);border:1px solid var(--border)"
                >{{ g.name }}</span>
                <span v-if="!selectedUser.groups.length" style="font-size:12px;color:var(--text-muted)">Sans groupe</span>
              </template>
              <span v-else style="font-size:12px;color:var(--text-muted)">—</span>
            </div>
          </div>
        </div>

        <!-- URL à tester -->
        <div class="form-group" style="margin-bottom:16px">
          <label class="form-label" :style="errors.url ? 'color:var(--red)' : ''">URL à tester</label>
          <input
            v-model="testUrl"
            class="form-input"
            :class="{ 'input-error': errors.url }"
            placeholder="https://www.youtube.com/watch?v=..."
            @keyup.enter="runTest"
            @input="errors.url = false"
          />
        </div>

        <button
          class="btn btn-primary"
          @click="runTest"
          :disabled="testing"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          {{ testing ? 'Test en cours…' : 'Tester l\'accès' }}
        </button>
      </div>

      <!-- ── Résultat ────────────────────────────────────────────────── -->
      <div v-if="result" class="card" style="border:2px solid"
        :style="result.blocked ? 'border-color:var(--red)' : 'border-color:var(--green)'"
      >
        <!-- Verdict -->
        <div style="display:flex;align-items:center;gap:14px;margin-bottom:18px">
          <div style="line-height:1">
            <svg v-if="result.blocked" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--red)" stroke-width="1.8">
              <circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
            </svg>
            <svg v-else width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="1.8">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          </div>
          <div>
            <div style="font-size:20px;font-weight:700"
              :style="result.blocked ? 'color:var(--red)' : 'color:var(--green)'">
              {{ result.blocked ? 'BLOQUÉE' : 'AUTORISÉE' }}
            </div>
            <div style="font-size:13px;color:var(--text-muted);margin-top:2px;font-family:monospace;word-break:break-all">
              {{ result.url }}
            </div>
          </div>
        </div>

        <!-- Contexte utilisateur -->
        <div style="display:flex;gap:20px;margin-bottom:16px;padding:12px 14px;background:var(--surface2);border-radius:6px;flex-wrap:wrap">
          <div>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:2px">UTILISATEUR</div>
            <div style="font-size:13px;font-weight:500">{{ result.user_label || result.user_ip }}</div>
            <div style="font-size:11px;font-family:monospace;color:var(--text-muted)">{{ result.user_ip }}</div>
          </div>
          <div>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">GROUPES</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px">
              <span
                v-for="g in result.groups" :key="g"
                style="font-size:12px;padding:2px 8px;border-radius:10px;background:var(--surface);border:1px solid var(--border)"
              >{{ g }}</span>
              <span v-if="!result.groups.length" style="font-size:12px;color:var(--text-muted)">Sans groupe</span>
            </div>
          </div>
        </div>

        <!-- Règle déclenchée -->
        <div v-if="result.reason">
          <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;font-weight:600;text-transform:uppercase;letter-spacing:.05em">
            Règle déclenchée
          </div>
          <div style="padding:12px 14px;border-radius:6px;border:1px solid var(--border);display:flex;flex-wrap:wrap;gap:16px;align-items:flex-start">
            <div style="flex:1;min-width:200px">
              <div style="font-size:11px;color:var(--text-muted);margin-bottom:3px">PATTERN</div>
              <code style="font-size:13px;color:var(--blue)">{{ result.reason.pattern }}</code>
            </div>
            <div>
              <div style="font-size:11px;color:var(--text-muted);margin-bottom:3px">ACTION</div>
              <span :class="result.reason.action === 'block' ? 'badge badge-block' : 'badge badge-allow'">
                {{ result.reason.action === 'block' ? 'bloqué' : 'autorisé' }}
              </span>
            </div>
            <div>
              <div style="font-size:11px;color:var(--text-muted);margin-bottom:3px">SOURCE</div>
              <span
                class="badge"
                :style="result.reason.source === 'group'
                  ? 'background:rgba(139,92,246,.15);color:#a78bfa'
                  : 'background:var(--surface2)'"
              >
                {{ result.reason.source === 'group'
                    ? `Groupe : ${result.reason.group_name}`
                    : 'Règle globale' }}
              </span>
            </div>
          </div>
        </div>

        <!-- Aucune règle -->
        <div v-else style="padding:12px 14px;border-radius:6px;border:1px solid var(--border);color:var(--text-muted);font-size:13px">
          Aucune règle ne correspond à cette URL — accès autorisé par défaut.
        </div>

        <!-- Historique des tests -->
        <div v-if="history.length > 1" style="margin-top:18px;border-top:1px solid var(--border);padding-top:14px">
          <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;font-weight:600">Historique</div>
          <div style="display:flex;flex-direction:column;gap:4px;max-height:160px;overflow-y:auto">
            <div
              v-for="(h, i) in history.slice(1)" :key="i"
              style="display:flex;align-items:center;gap:10px;padding:6px 10px;border-radius:4px;background:var(--surface2);font-size:12px;cursor:pointer"
              @click="result = h"
            >
              <svg v-if="h.blocked" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--red)" stroke-width="2">
                <circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
              </svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              <span style="font-family:monospace;color:var(--text-muted);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                {{ h.url }}
              </span>
              <span style="color:var(--text-muted);flex-shrink:0">
                {{ h.user_label || h.user_ip }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Placeholder avant premier test -->
      <div v-else class="card" style="display:flex;align-items:center;justify-content:center;min-height:140px;color:var(--text-muted);font-size:13px;flex-direction:column;gap:8px">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity:.3">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        Sélectionnez un utilisateur et entrez une URL pour simuler un accès
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { clientUsersApi }           from '@/api'

const users          = ref([])
const selectedUserId = ref('')
const testUrl        = ref('')
const result         = ref(null)
const testing        = ref(false)
const history        = ref([])
const errors         = ref({ user: false, url: false })

const selectedUser = computed(() =>
  users.value.find(u => u.id === Number(selectedUserId.value)) ?? null
)

async function runTest() {
  errors.value.user = !selectedUserId.value
  errors.value.url  = !testUrl.value.trim()
  if (errors.value.user || errors.value.url) return
  testing.value = true
  try {
    const { data } = await clientUsersApi.testAccess({
      user_id: Number(selectedUserId.value),
      url:     testUrl.value.trim(),
    })
    result.value = data
    history.value.unshift(data)
    if (history.value.length > 20) history.value.pop()
  } finally {
    testing.value = false
  }
}

onMounted(async () => {
  const { data } = await clientUsersApi.list()
  users.value = data
})
</script>

<style scoped>
.input-error {
  border-color: var(--red) !important;
  box-shadow: 0 0 0 2px rgba(248, 81, 73, .15);
}
</style>