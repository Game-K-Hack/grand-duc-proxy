<template>
  <div>
    <div class="page-header">
      <div>
        <h1>Mises à jour</h1>
        <p>Version de chaque module et installation des nouvelles versions.</p>
      </div>
      <button class="btn btn-ghost" @click="check" :disabled="checking || busy">
        {{ checking ? 'Vérification…' : 'Vérifier maintenant' }}
      </button>
    </div>

    <div v-if="banner" :class="banner.ok ? 'alert alert-success' : 'alert alert-error'">
      {{ banner.text }}
    </div>

    <div v-if="loading" class="card" style="padding:24px;text-align:center;color:var(--text-muted)">
      Chargement…
    </div>

    <template v-else-if="status">
      <!-- ── Carte système ──────────────────────────────────────────── -->
      <div class="card" style="padding:18px;margin-bottom:16px">
        <div style="display:flex;align-items:flex-start;gap:24px;flex-wrap:wrap">
          <div>
            <div style="font-size:12px;color:var(--text-muted);margin-bottom:4px">Version installée</div>
            <div style="font-size:22px;font-weight:700;font-family:monospace">
              {{ status.current_version || '—' }}
            </div>
          </div>

          <div v-if="status.latest.tag">
            <div style="font-size:12px;color:var(--text-muted);margin-bottom:4px">Dernière version publiée</div>
            <div style="display:flex;align-items:center;gap:8px">
              <span style="font-size:22px;font-weight:700;font-family:monospace">{{ status.latest.tag }}</span>
              <span v-if="status.update_available" class="badge"
                style="background:rgba(210,153,34,.15);color:#d29922">DISPONIBLE</span>
              <span v-else-if="status.can_update" class="badge"
                style="background:rgba(63,185,80,.15);color:#3fb950">À JOUR</span>
            </div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:4px">
              Publiée le {{ fmtDate(status.latest.published_at) }} ·
              <a :href="status.latest.html_url" target="_blank" rel="noopener">Notes de version</a>
            </div>
          </div>

          <div style="margin-left:auto;text-align:right">
            <div style="font-size:11px;color:var(--text-muted)">
              Vérifié {{ status.latest.checked_at ? fmtDate(status.latest.checked_at) : 'jamais' }}
            </div>
          </div>
        </div>

        <!-- Raisons pour lesquelles le bouton n'est pas proposé -->
        <div v-if="status.latest.error === 'offline'" class="alert" style="margin-top:14px">
          Impossible de contacter GitHub. Les versions installées restent affichées,
          mais la disponibilité d'une mise à jour ne peut pas être vérifiée.
        </div>
        <div v-else-if="status.latest.rate_limited" class="alert" style="margin-top:14px">
          Quota de l'API GitHub atteint. Nouvelle tentative possible
          {{ status.latest.rate_reset ? 'à ' + fmtTime(status.latest.rate_reset * 1000) : 'plus tard' }}.
        </div>
        <div v-else-if="!status.can_update" class="alert" style="margin-top:14px">
          {{ status.reason }}
          <template v-if="status.mode === 'native' && bundleUrl">
            <br />
            <a :href="bundleUrl" target="_blank" rel="noopener">Télécharger le bundle {{ status.latest.tag }}</a>
          </template>
        </div>
      </div>

      <!-- ── Modules ────────────────────────────────────────────────── -->
      <div class="card" style="padding:0;overflow:hidden;margin-bottom:16px">
        <div style="padding:12px 16px;border-bottom:1px solid var(--border)">
          <div style="font-weight:600;font-size:13px">Modules</div>
        </div>
        <table class="table">
          <thead>
            <tr>
              <th style="width:150px">Module</th>
              <th>Image</th>
              <th style="width:110px">Version</th>
              <th style="width:150px">Statut</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in status.modules" :key="m.service"
              :style="m.managed ? '' : 'opacity:.62'">
              <td>
                <div style="display:flex;align-items:center;gap:8px">
                  <span :style="dotStyle(m.running)"></span>
                  {{ m.label }}
                </div>
              </td>
              <td class="mono" style="font-size:11px;color:var(--text-muted)">
                {{ m.image || '—' }}
              </td>
              <td class="mono" style="font-size:12px">{{ m.version || '—' }}</td>
              <td style="font-size:12px">
                <span :style="`color:${statusColor(m.status)}`">{{ statusLabel(m) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="spaMismatch" style="padding:10px 16px;border-top:1px solid var(--border);font-size:12px;color:var(--text-muted)">
          La page ouverte dans ce navigateur est en version <strong>{{ spaVersion }}</strong>
          alors que le serveur sert {{ frontendVersion }} — rechargez la page (Ctrl+F5).
        </div>
      </div>

      <!-- ── Action ─────────────────────────────────────────────────── -->
      <div v-if="status.can_update" class="card" style="padding:16px 18px;margin-bottom:16px">
        <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
          <div style="flex:1;min-width:240px">
            <div style="font-weight:600;font-size:13px;margin-bottom:2px">
              {{ status.update_available ? `Installer la version ${status.latest.tag}` : 'Réinstaller la version courante' }}
            </div>
            <div style="font-size:12px;color:var(--text-muted)">
              Les services sont recréés un à un. Le proxy est interrompu pendant l'opération.
            </div>
          </div>
          <button class="btn btn-primary" :disabled="busy || !canApply"
            @click="showConfirm = true">
            {{ busy ? 'Mise à jour en cours…' : 'Mettre à jour' }}
          </button>
        </div>
      </div>

      <!-- ── Progression ────────────────────────────────────────────── -->
      <div v-if="progress && progress.state !== 'idle'" class="card" style="padding:0;overflow:hidden">
        <div style="padding:12px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px">
          <span :style="dotStyle(progress.state === 'running')"></span>
          <div style="font-weight:600;font-size:13px">{{ progressTitle }}</div>
          <div v-if="progress.target" style="font-size:12px;color:var(--text-muted);margin-left:auto" class="mono">
            cible {{ progress.target }}
          </div>
        </div>

        <div v-if="reconnecting" style="padding:12px 16px;font-size:13px;color:var(--text-muted)">
          Le service redémarre… ({{ waited }} s)
        </div>

        <div v-if="progress.steps.length" style="padding:12px 16px;display:flex;flex-wrap:wrap;gap:6px">
          <span v-for="(s, i) in progress.steps" :key="i" class="badge"
            :style="s.startsWith('fail') ? 'background:rgba(248,81,73,.15);color:#f85149' : 'background:var(--surface2);color:var(--text-muted)'">
            {{ stepLabel(s) }}
          </span>
        </div>

        <pre v-if="progress.log.length" class="mono"
          style="margin:0;padding:12px 16px;border-top:1px solid var(--border);max-height:240px;overflow:auto;font-size:11px;color:var(--text-muted);white-space:pre-wrap">{{ progress.log.join('\n') }}</pre>
      </div>
    </template>

    <!-- ── Confirmation ─────────────────────────────────────────────── -->
    <div class="modal-overlay" v-if="showConfirm" @click.self="showConfirm = false">
      <div class="modal" style="width:440px">
        <div class="modal-title">Mettre à jour vers {{ status?.latest?.tag }} ?</div>
        <p style="color:var(--text-muted);margin-bottom:12px">
          Les images sont téléchargées puis les services recréés. L'interface et l'API
          seront indisponibles pendant <strong>30 secondes à 2 minutes</strong>.
        </p>
        <p style="color:var(--text-muted);margin-bottom:12px;font-size:12px">
          Le proxy étant recréé lui aussi, les postes clients perdront temporairement
          leur accès à Internet. Vous pouvez fermer cette page : l'opération se poursuit
          et son résultat sera affiché à votre retour.
        </p>
        <label style="display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text-muted);margin-bottom:16px">
          <input type="checkbox" v-model="refreshCompose" />
          Mettre aussi à jour le fichier docker-compose.yml
        </label>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="showConfirm = false">Annuler</button>
          <button class="btn btn-primary" @click="doApply" :disabled="busy">Mettre à jour</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { updatesApi, healthApi } from '@/api'

const status         = ref(null)
const progress       = ref(null)
const loading        = ref(true)
const checking       = ref(false)
const busy           = ref(false)
const reconnecting   = ref(false)
const waited         = ref(0)
const showConfirm    = ref(false)
const refreshCompose = ref(true)
const banner         = ref(null)

let pollTimer = null

const spaVersion = import.meta.env.VITE_APP_VERSION || 'dev'

const frontendVersion = computed(() =>
  status.value?.modules?.find(m => m.service === 'frontend')?.version || null
)

// Un écart signale un bundle resté en cache après une mise à jour : la page
// affichée n'est pas celle que le serveur sert. Cas réel et déroutant.
const spaMismatch = computed(() =>
  !!frontendVersion.value && frontendVersion.value !== spaVersion
)

const canApply = computed(() =>
  !!status.value?.can_update && progress.value?.state !== 'running'
)

const bundleUrl = computed(() => {
  const assets = status.value?.latest?.assets || []
  const win = assets.find(a => (a.name || '').includes('windows'))
  return (win || assets[0])?.url || status.value?.latest?.html_url || null
})

const progressTitle = computed(() => ({
  running: 'Mise à jour en cours',
  success: 'Mise à jour terminée',
  failed:  'La mise à jour a échoué',
}[progress.value?.state] || ''))

const STEP_LABELS = {
  'compose-refreshed': 'docker-compose.yml mis à jour',
  'compose-kept':      'docker-compose.yml conservé',
  'pulled':            'Images téléchargées',
  'done':              'Services recréés',
  'fail pull':         'Échec du téléchargement',
  'fail up':           'Échec de la recréation',
  'fail compose-missing': 'Fichier compose introuvable',
}
function stepLabel(s) {
  if (STEP_LABELS[s]) return STEP_LABELS[s]
  if (s.startsWith('start')) return 'Démarrage'
  if (s.startsWith('env '))  return 'Version écrite dans .env'
  if (s.startsWith('dry-run')) return `Simulation : ${s.slice(8)}`
  return s
}

function dotStyle(on) {
  const c = on ? '#3fb950' : 'var(--text-muted)'
  return `width:8px;height:8px;border-radius:50%;background:${c};flex-shrink:0;display:inline-block`
}

const STATUS_LABELS = {
  up_to_date: 'À jour',
  outdated:   'Mise à jour disponible',
  ahead:      'En avance sur la release',
  unknown:    'Version indéterminée',
  unmanaged:  'Hors périmètre',
}
function statusLabel(m) {
  if (m.kind === 'external')    return 'Image publique'
  if (m.kind === 'local-build') return 'Construite localement'
  if (m.kind === 'native')      return 'Installation native'
  return STATUS_LABELS[m.status] || m.status
}
function statusColor(s) {
  if (s === 'outdated')   return '#d29922'
  if (s === 'up_to_date') return '#3fb950'
  return 'var(--text-muted)'
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}
function fmtTime(ms) {
  return new Date(ms).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

function flash(ok, text) {
  banner.value = { ok, text }
  setTimeout(() => { banner.value = null }, 5000)
}

async function load() {
  const { data } = await updatesApi.status()
  status.value = data
  progress.value = data.updater
  // Une mise à jour lancée avant l'ouverture de la page doit être reprise.
  if (data.updater?.state === 'running' && !busy.value) {
    busy.value = true
    followProgress()
  }
}

async function check() {
  checking.value = true
  try {
    const { data } = await updatesApi.check()
    status.value = data
    progress.value = data.updater
    flash(true, data.update_available
      ? `Version ${data.latest.tag} disponible.`
      : 'Aucune nouvelle version disponible.')
  } catch (e) {
    flash(false, e.response?.data?.detail || 'Vérification impossible')
  } finally {
    checking.value = false
  }
}

async function doApply() {
  showConfirm.value = false
  busy.value = true
  try {
    await updatesApi.apply(refreshCompose.value)
    progress.value = { state: 'running', steps: [], log: [] }
    followProgress()
  } catch (e) {
    busy.value = false
    flash(false, e.response?.data?.detail || 'Lancement de la mise à jour impossible')
  }
}

/** Attend le retour du backend. L'erreur réseau est le cas NOMINAL ici. */
async function waitForBackend(maxMs = 15 * 60_000) {
  const t0 = Date.now()
  reconnecting.value = true
  while (Date.now() - t0 < maxMs) {
    waited.value = Math.round((Date.now() - t0) / 1000)
    try {
      await healthApi.ping()
      reconnecting.value = false
      return true
    } catch { /* attendu : le service est en cours de recréation */ }
    await new Promise(r => setTimeout(r, 2000))
  }
  reconnecting.value = false
  return false
}

async function followProgress() {
  // Phase 1 : le backend répond encore (pull en cours).
  while (true) {
    try {
      const { data } = await updatesApi.progress()
      progress.value = data
      if (data.state !== 'running') return finish(data)
    } catch {
      break   // le backend vient d'être recréé : on bascule en reconnexion
    }
    await new Promise(r => setTimeout(r, 2000))
  }

  // Phase 2 : attendre le retour du service, puis lire le verdict.
  const back = await waitForBackend()
  if (!back) {
    busy.value = false
    flash(false, "Le service n'a pas redémarré dans le délai imparti. " +
                 'Vérifiez `docker logs grand-duc-updater` sur le serveur.')
    return
  }
  try {
    const { data } = await updatesApi.progress()
    progress.value = data
    finish(data)
  } catch {
    busy.value = false
    flash(false, "Impossible de lire l'état de la mise à jour après redémarrage.")
  }
}

function finish(data) {
  busy.value = false
  if (data.state === 'success') {
    flash(true, `Mise à jour terminée${data.target ? ' (version ' + data.target + ')' : ''}. Rechargement…`)
    // Indispensable : nginx sert désormais un autre bundle JS que celui chargé.
    setTimeout(() => window.location.reload(), 2000)
  } else {
    flash(false, `La mise à jour a échoué (code ${data.exit_code}). Voir le journal ci-dessous.`)
  }
}

onMounted(async () => {
  try {
    await load()
  } catch (e) {
    flash(false, e.response?.data?.detail || 'Chargement impossible')
  } finally {
    loading.value = false
  }
  // Rafraîchissement discret de l'état, sauf pendant une mise à jour où
  // followProgress() pilote déjà le rythme.
  pollTimer = setInterval(() => { if (!busy.value) load().catch(() => {}) }, 30000)
})

onUnmounted(() => clearInterval(pollTimer))
</script>
