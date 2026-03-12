<template>
  <div class="page-container">

    <div class="page-header">
      <h1 class="page-title">Paramètres</h1>
    </div>

    <!-- ── Onglets ─────────────────────────────────────────────────────────── -->
    <div style="display:flex;gap:0;border-bottom:1px solid var(--border);margin-bottom:20px">
      <button
        v-for="tab in tabs" :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >{{ tab.label }}</button>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- Onglet 1 : Configuration SMTP                                         -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'smtp' && auth.isAdmin">

      <div class="card" style="max-width:560px;padding:24px">
        <div style="font-size:15px;font-weight:700;margin-bottom:4px">Serveur d'envoi (SMTP)</div>
        <div style="font-size:12px;color:var(--text-muted);margin-bottom:20px">
          Configurez la boîte mail depuis laquelle les alertes seront envoyées.
        </div>

        <div style="display:flex;flex-direction:column;gap:14px">

          <div style="display:grid;grid-template-columns:1fr auto;gap:10px">
            <div>
              <label class="form-label">Serveur SMTP <span style="color:var(--red)">*</span></label>
              <input v-model="smtp.host" class="form-input" placeholder="smtp.gmail.com" />
            </div>
            <div style="width:80px">
              <label class="form-label">Port</label>
              <input v-model.number="smtp.port" class="form-input" type="number" placeholder="587" />
            </div>
          </div>

          <div>
            <label class="form-label">Nom d'utilisateur</label>
            <input v-model="smtp.user" class="form-input" placeholder="alert@example.com" autocomplete="off" />
          </div>

          <div>
            <label class="form-label">Mot de passe</label>
            <input v-model="smtp.password" class="form-input" type="password"
              placeholder="Laisser vide pour ne pas modifier" autocomplete="new-password" />
          </div>

          <div>
            <label class="form-label">Adresse expéditeur (From)</label>
            <input v-model="smtp.from_" class="form-input" placeholder="Grand-Duc <alert@example.com>" />
          </div>

          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px">
            <input type="checkbox" v-model="smtp.tls" />
            Utiliser STARTTLS (recommandé)
          </label>

          <div v-if="smtpMsg"
            :style="`padding:8px 12px;border-radius:5px;font-size:12px;border:1px solid;${
              smtpMsg.ok
                ? 'background:rgba(46,160,67,.1);border-color:var(--green);color:var(--green)'
                : 'background:rgba(248,81,73,.1);border-color:var(--red);color:var(--red)'
            }`">
            {{ smtpMsg.text }}
          </div>
        </div>

        <div style="display:flex;gap:10px;margin-top:20px;flex-wrap:wrap">
          <button class="btn btn-primary" @click="saveSmtp" :disabled="smtpSaving">
            {{ smtpSaving ? 'Enregistrement…' : 'Enregistrer' }}
          </button>
          <div style="display:flex;gap:8px;align-items:center;margin-left:auto">
            <input v-model="testEmail" class="form-input" style="width:200px;font-size:12px"
              placeholder="Adresse de test" />
            <button class="btn" @click="sendTest" :disabled="testSending || !smtp.host">
              {{ testSending ? 'Envoi…' : 'Tester' }}
            </button>
          </div>
        </div>
      </div>

    </div>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- Onglet 2 : Mes notifications                                          -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'notifications'">

      <div v-if="!auth.user?.email"
        style="padding:12px 16px;border-radius:6px;border:1px solid var(--red);background:rgba(248,81,73,.08);color:var(--red);font-size:13px;margin-bottom:16px;max-width:560px">
        ⚠️ Votre compte n'a pas d'adresse email configurée. Les alertes ne pourront pas être envoyées.
        <br><a href="/users" style="color:inherit;text-decoration:underline">Modifier mon compte</a>
      </div>

      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;max-width:900px">

        <!-- Événements -->
        <div class="card" style="padding:20px">
          <div style="font-size:14px;font-weight:700;margin-bottom:4px">Événements à surveiller</div>
          <div style="font-size:12px;color:var(--text-muted);margin-bottom:16px">
            Recevez un email lors de ces événements.
          </div>

          <div style="display:flex;flex-direction:column;gap:12px">
            <label
              v-for="pref in prefs" :key="pref.event_type"
              style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:8px 10px;border-radius:6px;border:1px solid var(--border);transition:background .1s"
              :style="pref.enabled ? 'border-color:var(--accent);background:rgba(88,166,255,.06)' : ''"
            >
              <input type="checkbox" v-model="pref.enabled" @change="savePrefs" style="flex-shrink:0" />
              <div>
                <div style="font-size:13px;font-weight:500">{{ pref.label }}</div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:1px">
                  {{ eventDesc[pref.event_type] }}
                </div>
              </div>
            </label>
          </div>

          <div v-if="prefsSaved" style="margin-top:12px;font-size:12px;color:var(--green)">
            ✓ Préférences enregistrées
          </div>
        </div>

        <!-- Règles surveillées -->
        <div class="card" style="padding:20px">
          <div style="font-size:14px;font-weight:700;margin-bottom:4px">Règles à surveiller</div>
          <div style="font-size:12px;color:var(--text-muted);margin-bottom:16px">
            Recevez un email quand une de ces règles est déclenchée dans les logs d'accès.
            Nécessite d'activer « Règle de filtrage déclenchée » ci-contre.
          </div>

          <div v-if="loadingRules" style="color:var(--text-muted);font-size:12px">Chargement…</div>

          <div v-else>
            <!-- Sélecteur -->
            <div style="margin-bottom:10px">
              <select v-model="selectedRuleId" class="form-input" style="font-size:12px">
                <option value="">— Ajouter une règle —</option>
                <option
                  v-for="r in availRules.filter(r => !watchedIds.has(r.rule_id))"
                  :key="r.rule_id" :value="r.rule_id"
                >
                  {{ r.pattern }} ({{ r.action }})
                </option>
              </select>
              <button class="btn" style="margin-top:6px;font-size:12px;width:100%"
                :disabled="!selectedRuleId" @click="addRuleWatch">
                Surveiller cette règle
              </button>
            </div>

            <!-- Liste des règles surveillées -->
            <div style="display:flex;flex-direction:column;gap:6px">
              <div v-if="!watchedRules.length" style="font-size:12px;color:var(--text-muted)">
                Aucune règle surveillée.
              </div>
              <div
                v-for="r in watchedRules" :key="r.rule_id"
                style="display:flex;align-items:center;gap:8px;padding:6px 10px;border-radius:5px;border:1px solid var(--border);background:var(--surface2)"
              >
                <div style="flex:1;min-width:0">
                  <div style="font-size:12px;font-family:monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                    {{ r.pattern }}
                  </div>
                  <div style="font-size:10px;color:var(--text-muted)">action : {{ r.action }}</div>
                </div>
                <button class="btn btn-ghost btn-sm btn-icon" @click="removeRuleWatch(r.rule_id)">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { settingsApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

// ── Onglets ───────────────────────────────────────────────────────────────────
const tabs = computed(() => {
  const t = [{ key: 'notifications', label: 'Mes notifications' }]
  if (auth.isAdmin) t.unshift({ key: 'smtp', label: 'Configuration SMTP' })
  return t
})
const activeTab = ref(auth.isAdmin ? 'smtp' : 'notifications')

// ── SMTP ──────────────────────────────────────────────────────────────────────
const smtp = ref({ host: '', port: 587, user: '', password: '', from_: '', tls: true })
const smtpSaving = ref(false)
const smtpMsg    = ref(null)
const testEmail  = ref('')
const testSending = ref(false)

async function loadSmtp() {
  if (!auth.isAdmin) return
  const { data } = await settingsApi.getSmtp()
  smtp.value = { host: data.host, port: data.port, user: data.user, password: data.password, from_: data.from_, tls: data.tls }
  testEmail.value = auth.user?.email || ''
}

async function saveSmtp() {
  smtpSaving.value = true
  smtpMsg.value = null
  try {
    await settingsApi.updateSmtp(smtp.value)
    smtpMsg.value = { ok: true, text: 'Configuration enregistrée.' }
  } catch (e) {
    smtpMsg.value = { ok: false, text: e.response?.data?.detail ?? 'Erreur lors de l\'enregistrement.' }
  } finally {
    smtpSaving.value = false
    setTimeout(() => { smtpMsg.value = null }, 5000)
  }
}

async function sendTest() {
  if (!testEmail.value) return
  testSending.value = true
  smtpMsg.value = null
  try {
    await settingsApi.testSmtp(testEmail.value)
    smtpMsg.value = { ok: true, text: `Email de test envoyé à ${testEmail.value}.` }
  } catch (e) {
    smtpMsg.value = { ok: false, text: e.response?.data?.detail ?? 'Envoi échoué.' }
  } finally {
    testSending.value = false
    setTimeout(() => { smtpMsg.value = null }, 7000)
  }
}

// ── Préférences de notification ────────────────────────────────────────────────
const prefs      = ref([])
const prefsSaved = ref(false)

const eventDesc = {
  certificate:    'Génération ou import d\'un nouveau certificat CA.',
  proxy_restart:  'Redémarrage du proxy (via l\'interface admin).',
  killswitch:     'Activation ou désactivation du killswitch.',
  new_account:    'Création d\'un nouveau compte administrateur.',
  rule_triggered: 'Une règle de filtrage surveillée est déclenchée (vérification toutes les 5 min).',
  rmm_sync_error: 'Échec d\'une synchronisation avec un RMM.',
}

async function loadPrefs() {
  const { data } = await settingsApi.getNotifications()
  prefs.value = data
}

async function savePrefs() {
  await settingsApi.setNotifications(prefs.value)
  prefsSaved.value = true
  setTimeout(() => { prefsSaved.value = false }, 2500)
}

// ── Règles surveillées ─────────────────────────────────────────────────────────
const watchedRules   = ref([])
const availRules     = ref([])
const loadingRules   = ref(true)
const selectedRuleId = ref('')

const watchedIds = computed(() => new Set(watchedRules.value.map(r => r.rule_id)))

async function loadRules() {
  loadingRules.value = true
  const [w, a] = await Promise.all([settingsApi.getRuleWatches(), settingsApi.getAvailRules()])
  watchedRules.value = w.data
  availRules.value   = a.data
  loadingRules.value = false
}

async function addRuleWatch() {
  if (!selectedRuleId.value) return
  const newIds = [...watchedIds.value, Number(selectedRuleId.value)]
  await settingsApi.setRuleWatches(newIds)
  selectedRuleId.value = ''
  await loadRules()
}

async function removeRuleWatch(ruleId) {
  const newIds = [...watchedIds.value].filter(id => id !== ruleId)
  await settingsApi.setRuleWatches(newIds)
  await loadRules()
}

// ── Init ──────────────────────────────────────────────────────────────────────
onMounted(async () => {
  await Promise.all([loadSmtp(), loadPrefs(), loadRules()])
})
</script>

<style scoped>
.tab-btn {
  padding: 8px 18px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  margin-bottom: -1px;
  transition: color .15s, border-color .15s;
}
.tab-btn:hover  { color: var(--text); }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
</style>
