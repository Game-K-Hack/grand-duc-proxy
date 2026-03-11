<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Killswitch</h1>
    </div>

    <div style="max-width:860px;margin:auto;display:flex;flex-direction:column;gap:20px">

      <!-- ── Avertissement ──────────────────────────────────────────── -->
      <div style="background:rgba(248,81,73,.1);border:1.5px solid var(--red);border-radius:8px;padding:18px 20px;display:flex;gap:14px;align-items:flex-start">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--red)" stroke-width="2" style="flex-shrink:0;margin-top:1px">
          <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/><circle cx="12" cy="17" r="1.2" stroke-width="0" fill="var(--red)"/>
        </svg>
        <div>
          <div style="font-weight:700;color:var(--red);margin-bottom:6px;font-size:15px">Danger — Désactivation du filtrage</div>
          <div style="font-size:13px;color:var(--text-muted);line-height:1.6">
            Activer le killswitch <strong style="color:var(--text)">suspend immédiatement toutes les règles de filtrage</strong> pour l'ensemble des utilisateurs.
            Tout le trafic réseau sera autorisé sans restriction, y compris vers des sites normalement bloqués.
            <br><br>
            Cette fonctionnalité est réservée aux situations d'urgence (panne du proxy, tests critiques).
            Pensez à <strong style="color:var(--text)">désactiver le killswitch dès que possible</strong> pour rétablir la protection.
          </div>
        </div>
      </div>

      <!-- ── Diagramme réseau ────────────────────────────────────────── -->
      <div class="card" style="padding:28px 24px">
        <div style="font-size:13px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:20px">
          État actuel du système
        </div>

        <div v-if="loading" style="text-align:center;padding:40px;color:var(--text-muted);font-size:13px">Chargement…</div>

        <svg v-else viewBox="0 0 700 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:700px;display:block;margin:auto">
          <!-- PCs entreprise -->
          <g>
            <rect x="20" y="60" width="50" height="36" rx="4" fill="none" stroke="var(--blue)" stroke-width="1.8"/>
            <rect x="30" y="96" width="30" height="4" rx="1" fill="var(--blue)" opacity=".5"/>
            <rect x="25" y="100" width="40" height="3" rx="1" fill="var(--blue)" opacity=".3"/>
            <line x1="35" y1="64" x2="55" y2="64" stroke="var(--blue)" stroke-width="1" opacity=".5"/>
            <line x1="35" y1="68" x2="55" y2="68" stroke="var(--blue)" stroke-width="1" opacity=".5"/>
            <line x1="35" y1="72" x2="55" y2="72" stroke="var(--blue)" stroke-width="1" opacity=".5"/>

            <rect x="20" y="118" width="50" height="36" rx="4" fill="none" stroke="var(--blue)" stroke-width="1.8"/>
            <rect x="30" y="154" width="30" height="4" rx="1" fill="var(--blue)" opacity=".5"/>
            <rect x="25" y="158" width="40" height="3" rx="1" fill="var(--blue)" opacity=".3"/>
            <line x1="35" y1="122" x2="55" y2="122" stroke="var(--blue)" stroke-width="1" opacity=".5"/>
            <line x1="35" y1="126" x2="55" y2="126" stroke="var(--blue)" stroke-width="1" opacity=".5"/>
            <line x1="35" y1="130" x2="55" y2="130" stroke="var(--blue)" stroke-width="1" opacity=".5"/>

            <rect x="20" y="2" width="50" height="36" rx="4" fill="none" stroke="var(--blue)" stroke-width="1.8"/>
            <rect x="30" y="38" width="30" height="4" rx="1" fill="var(--blue)" opacity=".5"/>
            <rect x="25" y="42" width="40" height="3" rx="1" fill="var(--blue)" opacity=".3"/>
            <line x1="35" y1="6" x2="55" y2="6" stroke="var(--blue)" stroke-width="1" opacity=".5"/>
            <line x1="35" y1="10" x2="55" y2="10" stroke="var(--blue)" stroke-width="1" opacity=".5"/>
            <line x1="35" y1="14" x2="55" y2="14" stroke="var(--blue)" stroke-width="1" opacity=".5"/>

            <text x="45" y="175" text-anchor="middle" font-size="11" fill="var(--text-muted)">PCs</text>
          </g>

          <!-- Lignes PC → Proxy -->
          <line x1="70" y1="20"  x2="220" y2="95"  :stroke="lineColor" stroke-width="2" stroke-dasharray="6,3" opacity=".8"/>
          <line x1="70" y1="78"  x2="220" y2="100" :stroke="lineColor" stroke-width="2" stroke-dasharray="6,3" opacity=".8"/>
          <line x1="70" y1="136" x2="220" y2="105" :stroke="lineColor" stroke-width="2" stroke-dasharray="6,3" opacity=".8"/>

          <!-- Proxy -->
          <rect x="220" y="65" width="110" height="70" rx="8" :fill="proxyFill" :stroke="proxyStroke" stroke-width="2"/>
          <text x="275" y="96"  text-anchor="middle" font-size="13" font-weight="600" :fill="proxyStroke">Proxy</text>
          <text x="275" y="112" text-anchor="middle" font-size="10" :fill="proxyStroke" opacity=".8">
            {{ active ? 'filtrage OFF' : 'filtrage ON' }}
          </text>

          <!-- Ligne Proxy → Internet -->
          <line x1="330" y1="100" x2="500" y2="100" :stroke="lineColor" stroke-width="2" stroke-dasharray="6,3" opacity=".8"/>

          <!-- Icône bypass si killswitch actif -->
          <g v-if="active" transform="translate(395,86)">
            <circle cx="15" cy="14" r="13" fill="rgba(248,81,73,.15)" stroke="var(--red)" stroke-width="1.5"/>
            <line x1="7" y1="6" x2="23" y2="22" stroke="var(--red)" stroke-width="2"/>
            <text x="15" y="40" text-anchor="middle" font-size="9" fill="var(--red)">BYPASS</text>
          </g>

          <!-- Internet (globe) -->
          <circle cx="560" cy="100" r="50" fill="none" stroke="var(--text-muted)" stroke-width="1.8" opacity=".5"/>
          <ellipse cx="560" cy="100" rx="22" ry="50" fill="none" stroke="var(--text-muted)" stroke-width="1.2" opacity=".4"/>
          <line x1="510" y1="100" x2="610" y2="100" stroke="var(--text-muted)" stroke-width="1.2" opacity=".4"/>
          <line x1="515" y1="78"  x2="605" y2="78"  stroke="var(--text-muted)" stroke-width="1.2" opacity=".4"/>
          <line x1="515" y1="122" x2="605" y2="122" stroke="var(--text-muted)" stroke-width="1.2" opacity=".4"/>
          <text x="560" y="165" text-anchor="middle" font-size="11" fill="var(--text-muted)">Internet</text>

          <!-- Légende état -->
          <g transform="translate(225,140)">
            <text x="18" y="12" font-size="11" :fill="active ? 'var(--red)' : 'var(--green)'">
              {{ active ? 'Killswitch actif — filtrage désactivé' : 'Filtrage actif — protection en place' }}
            </text>
          </g>
        </svg>
      </div>

      <!-- ── Bouton killswitch ───────────────────────────────────────── -->
      <div class="card" style="display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap">
        <div>
          <div style="font-size:15px;font-weight:600;margin-bottom:4px">
            {{ active ? 'Killswitch actif' : 'Killswitch inactif' }}
          </div>
          <div style="font-size:13px;color:var(--text-muted)">
            {{ active
              ? 'Tout le trafic passe sans filtrage. Désactivez dès que possible.'
              : 'Le filtrage fonctionne normalement. Activez uniquement en cas d\'urgence.' }}
          </div>
        </div>

        <button
          class="btn"
          :style="active
            ? 'background:var(--green);color:#fff;border-color:var(--green);min-width:200px;font-size:15px;padding:12px 24px'
            : 'background:var(--red);color:#fff;border-color:var(--red);min-width:200px;font-size:15px;padding:12px 24px'"
          @click="requestToggle"
          :disabled="saving || loading"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0">
            <path d="M18.36 6.64a9 9 0 1 1-12.73 0"/>
            <line x1="12" y1="2" x2="12" y2="12"/>
          </svg>
          {{ saving ? 'En cours…' : (active ? 'Désactiver le killswitch' : 'Activer le killswitch') }}
        </button>
      </div>

      <!-- ── Historique ─────────────────────────────────────────────── -->
      <div class="card">
        <div style="font-size:13px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:14px">
          Historique des actions
        </div>

        <div v-if="history.length === 0" style="color:var(--text-muted);font-size:13px;padding:12px 0">
          Aucune action enregistrée.
        </div>

        <div v-else style="display:flex;flex-direction:column;gap:2px">
          <div
            v-for="h in history" :key="h.id"
            style="display:flex;align-items:center;gap:12px;padding:9px 12px;border-radius:6px;background:var(--surface2);font-size:13px"
          >
            <!-- Icône action -->
            <svg v-if="h.action === 'activated'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--red)" stroke-width="2" style="flex-shrink:0">
              <path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/>
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2" style="flex-shrink:0">
              <path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/>
            </svg>

            <!-- Action -->
            <span :style="h.action === 'activated' ? 'color:var(--red);font-weight:600' : 'color:var(--green);font-weight:600'">
              {{ h.action === 'activated' ? 'Activé' : 'Désactivé' }}
            </span>

            <!-- Utilisateur -->
            <span style="color:var(--text-muted)">par</span>
            <span style="font-weight:500">{{ h.username }}</span>

            <!-- Date -->
            <span style="margin-left:auto;color:var(--text-muted);font-size:12px;font-family:monospace;flex-shrink:0">
              {{ formatDate(h.created_at) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Modal confirmation mot de passe ───────────────────────── -->
    <div v-if="showConfirm" style="position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:1000" @click.self="closeConfirm">
      <div class="card" style="width:420px;padding:28px 24px">
        <div style="font-size:16px;font-weight:700;margin-bottom:6px">
          {{ pendingActive ? 'Activer le killswitch' : 'Désactiver le killswitch' }}
        </div>
        <div style="font-size:13px;color:var(--text-muted);margin-bottom:20px">
          Confirmez votre identité pour continuer.
        </div>

        <div class="form-group" style="margin-bottom:16px">
          <label class="form-label">Mot de passe</label>
          <input
            ref="pwdInput"
            v-model="confirmPassword"
            type="password"
            class="form-input"
            :class="{ 'input-error': confirmError }"
            placeholder="Votre mot de passe"
            @keyup.enter="confirmToggle"
            @input="confirmError = ''"
          />
          <div v-if="confirmError" style="font-size:12px;color:var(--red);margin-top:4px">{{ confirmError }}</div>
        </div>

        <div style="display:flex;gap:10px;justify-content:flex-end">
          <button class="btn" @click="closeConfirm" :disabled="saving">Annuler</button>
          <button
            class="btn"
            :style="pendingActive ? 'background:var(--red);color:#fff;border-color:var(--red)' : 'background:var(--green);color:#fff;border-color:var(--green)'"
            @click="confirmToggle"
            :disabled="saving || !confirmPassword"
          >
            {{ saving ? 'Vérification…' : 'Confirmer' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { killswitchApi } from '@/api'

const active  = ref(false)
const loading = ref(true)
const saving  = ref(false)
const history = ref([])

const showConfirm     = ref(false)
const pendingActive   = ref(false)
const confirmPassword = ref('')
const confirmError    = ref('')
const pwdInput        = ref(null)

const proxyFill   = computed(() => active.value ? 'rgba(248,81,73,.12)' : 'rgba(46,160,67,.12)')
const proxyStroke = computed(() => active.value ? 'var(--red)' : 'var(--green)')
const lineColor   = computed(() => active.value ? 'var(--red)' : 'var(--green)')

onMounted(async () => {
  const [ksRes, histRes] = await Promise.all([
    killswitchApi.get(),
    killswitchApi.history(),
  ])
  active.value  = ksRes.data.active
  history.value = histRes.data
  loading.value = false
})

function requestToggle() {
  pendingActive.value   = !active.value
  confirmPassword.value = ''
  confirmError.value    = ''
  showConfirm.value     = true
  nextTick(() => pwdInput.value?.focus())
}

function closeConfirm() {
  showConfirm.value = false
}

async function confirmToggle() {
  if (!confirmPassword.value || saving.value) return
  saving.value = true
  confirmError.value = ''
  try {
    await killswitchApi.verifyPassword(confirmPassword.value)
  } catch {
    confirmError.value = 'Mot de passe incorrect'
    saving.value = false
    return
  }
  try {
    const { data } = await killswitchApi.set(pendingActive.value)
    active.value = data.active
    const histRes = await killswitchApi.history()
    history.value = histRes.data
    showConfirm.value = false
  } finally {
    saving.value = false
  }
}

function formatDate(iso) {
  const d = new Date(iso)
  return d.toLocaleDateString('fr-FR') + ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
</script>

<style scoped>
.input-error {
  border-color: var(--red) !important;
  box-shadow: 0 0 0 2px rgba(248, 81, 73, .15);
}
</style>
