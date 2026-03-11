<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Certificats CA</h1>
    </div>

    <div style="max-width:860px;margin:auto;display:flex;flex-direction:column;gap:20px">

      <!-- ── Certificat actuel ──────────────────────────────────────── -->
      <div class="card">
        <div style="font-size:13px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:16px">
          Certificat actuel
        </div>

        <div v-if="loading" style="color:var(--text-muted);font-size:13px">Chargement…</div>

        <div v-else-if="!certInfo.exists" style="color:var(--text-muted);font-size:13px;padding:8px 0">
          Aucun certificat trouvé dans le répertoire configuré.
        </div>

        <div v-else>
          <!-- Alerte si expiré ou bientôt expiré -->
          <div v-if="certInfo.is_expired" style="background:rgba(248,81,73,.1);border:1px solid var(--red);border-radius:6px;padding:10px 14px;margin-bottom:14px;font-size:13px;color:var(--red)">
            Ce certificat est <strong>expiré</strong>. Générez-en un nouveau.
          </div>
          <div v-else-if="certInfo.days_left < 30" style="background:rgba(255,140,0,.1);border:1px solid #f97316;border-radius:6px;padding:10px 14px;margin-bottom:14px;font-size:13px;color:#f97316">
            Ce certificat expire dans <strong>{{ certInfo.days_left }} jours</strong>.
          </div>

          <!-- Infos -->
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
            <div style="background:var(--surface2);border-radius:6px;padding:12px 14px">
              <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">SUJET</div>
              <div style="font-size:13px;font-weight:500">{{ certInfo.subject }}</div>
            </div>
            <div style="background:var(--surface2);border-radius:6px;padding:12px 14px">
              <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">VALIDITÉ</div>
              <div style="font-size:13px">
                <span :style="certInfo.is_expired ? 'color:var(--red)' : certInfo.days_left < 30 ? 'color:#f97316' : 'color:var(--green)'">
                  {{ certInfo.days_left > 0 ? certInfo.days_left + ' jours restants' : 'Expiré' }}
                </span>
              </div>
              <div style="font-size:11px;color:var(--text-muted);margin-top:2px">
                {{ fmtDate(certInfo.not_before) }} → {{ fmtDate(certInfo.not_after) }}
              </div>
            </div>
            <div style="background:var(--surface2);border-radius:6px;padding:12px 14px;grid-column:1/-1">
              <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">EMPREINTE SHA-256</div>
              <code style="font-size:11px;word-break:break-all;color:var(--text-muted)">{{ certInfo.fingerprint }}</code>
            </div>
          </div>

          <!-- Bouton téléchargement -->
          <div style="display:flex;align-items:center;gap:10px;padding:12px 14px;background:rgba(88,166,255,.08);border:1px solid rgba(88,166,255,.25);border-radius:6px">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--blue)" stroke-width="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            <div style="flex:1;font-size:13px">
              URL publique de téléchargement (sans authentification) :
              <code style="font-size:12px;margin-left:6px;color:var(--blue)">{{ downloadUrl }}</code>
            </div>
            <a :href="downloadUrl" download="grand-duc-ca.crt" class="btn btn-primary" style="font-size:12px;padding:6px 14px;text-decoration:none">
              Télécharger
            </a>
          </div>
        </div>
      </div>

      <!-- ── Actions ────────────────────────────────────────────────── -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">

        <!-- Générer un nouveau certificat -->
        <div class="card">
          <div style="font-size:14px;font-weight:600;margin-bottom:6px">Générer un nouveau certificat</div>
          <div style="font-size:13px;color:var(--text-muted);margin-bottom:14px;line-height:1.5">
            Génère une nouvelle CA auto-signée (ECDSA P-256, 10 ans).
            <br><strong style="color:var(--text)">Attention :</strong> l'ancien certificat ne sera plus valide. Tous les postes devront installer le nouveau.
          </div>
          <button class="btn" style="background:var(--red);color:#fff;border-color:var(--red);width:100%" @click="showGenConfirm = true" :disabled="actionLoading">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
            Générer
          </button>
        </div>

        <!-- Importer un certificat existant -->
        <div class="card">
          <div style="font-size:14px;font-weight:600;margin-bottom:6px">Importer un certificat</div>
          <div style="font-size:13px;color:var(--text-muted);margin-bottom:14px;line-height:1.5">
            Importez votre propre CA. Le certificat doit être une CA (BasicConstraints CA=True) et la clé PKCS#8 DER doit correspondre.
          </div>

          <!-- Succès import -->
          <div v-if="importSuccess" style="background:rgba(46,160,67,.1);border:1px solid var(--green);border-radius:6px;padding:10px 14px;margin-bottom:12px;display:flex;align-items:center;gap:8px;font-size:13px;color:var(--green)">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
            Certificat importé avec succès.
          </div>

          <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:14px">
            <!-- Certificat -->
            <div>
              <label :style="`font-size:12px;font-weight:500;display:block;margin-bottom:5px;${importErrors.cert ? 'color:var(--red)' : 'color:var(--text-muted)'}`">
                Certificat CA (.crt / .pem)
                <span v-if="importErrors.cert" style="margin-left:6px">— {{ importErrors.cert }}</span>
              </label>
              <label style="display:block;cursor:pointer">
                <input type="file" accept=".crt,.pem" style="display:none"
                  @change="onCertFileChange" ref="certInput"/>
                <div :style="`display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:6px;border:1.5px dashed;font-size:12px;transition:.15s;
                  ${importErrors.cert ? 'border-color:var(--red);background:rgba(248,81,73,.06)' :
                    importCertFile   ? 'border-color:var(--green);background:rgba(46,160,67,.06)' :
                                       'border-color:var(--border);background:var(--surface2)'}`">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                    :stroke="importErrors.cert ? 'var(--red)' : importCertFile ? 'var(--green)' : 'var(--text-muted)'"
                    stroke-width="2">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                  <span :style="importCertFile ? 'color:var(--green);font-weight:500' : 'color:var(--text-muted)'">
                    {{ importCertFile ? importCertFile.name : 'Choisir un fichier…' }}
                  </span>
                </div>
              </label>
            </div>

            <!-- Clé privée -->
            <div>
              <label :style="`font-size:12px;font-weight:500;display:block;margin-bottom:5px;${importErrors.key ? 'color:var(--red)' : 'color:var(--text-muted)'}`">
                Clé privée (.key — PKCS#8 DER)
                <span v-if="importErrors.key" style="margin-left:6px">— {{ importErrors.key }}</span>
              </label>
              <label style="display:block;cursor:pointer">
                <input type="file" accept=".key" style="display:none"
                  @change="onKeyFileChange" ref="keyInput"/>
                <div :style="`display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:6px;border:1.5px dashed;font-size:12px;transition:.15s;
                  ${importErrors.key ? 'border-color:var(--red);background:rgba(248,81,73,.06)' :
                    importKeyFile   ? 'border-color:var(--green);background:rgba(46,160,67,.06)' :
                                      'border-color:var(--border);background:var(--surface2)'}`">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                    :stroke="importErrors.key ? 'var(--red)' : importKeyFile ? 'var(--green)' : 'var(--text-muted)'"
                    stroke-width="2">
                    <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>
                  </svg>
                  <span :style="importKeyFile ? 'color:var(--green);font-weight:500' : 'color:var(--text-muted)'">
                    {{ importKeyFile ? importKeyFile.name : 'Choisir un fichier…' }}
                  </span>
                </div>
              </label>
            </div>
          </div>

          <!-- Erreur serveur -->
          <div v-if="importError" style="background:rgba(248,81,73,.08);border:1px solid var(--red);border-radius:6px;padding:9px 12px;margin-bottom:12px;display:flex;align-items:flex-start;gap:8px;font-size:12px;color:var(--red)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0;margin-top:1px">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            {{ importError }}
          </div>

          <button class="btn btn-primary" style="width:100%" @click="doImport" :disabled="actionLoading">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            {{ actionLoading ? 'Vérification…' : 'Importer' }}
          </button>
        </div>
      </div>

      <!-- ── Avertissement redémarrage ──────────────────────────────── -->
      <div v-if="restartRequired" style="background:rgba(255,140,0,.1);border:1.5px solid #f97316;border-radius:8px;padding:14px 18px;display:flex;gap:12px;align-items:center">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f97316" stroke-width="2" style="flex-shrink:0">
          <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/><circle cx="12" cy="17" r="1" fill="#f97316" stroke="none"/>
        </svg>
        <div style="font-size:13px">
          <strong style="color:#f97316">Redémarrage du proxy requis.</strong>
          Le nouveau certificat sera pris en compte au prochain démarrage du proxy Rust.
        </div>
      </div>

      <!-- ── Historique ─────────────────────────────────────────────── -->
      <div class="card">
        <div style="font-size:13px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:14px">
          Historique des changements
        </div>

        <div v-if="history.length === 0" style="color:var(--text-muted);font-size:13px;padding:8px 0">Aucune action enregistrée.</div>

        <div v-else style="display:flex;flex-direction:column;gap:2px">
          <div
            v-for="h in history" :key="h.id"
            style="display:grid;grid-template-columns:auto auto 1fr auto;align-items:center;gap:12px;padding:9px 12px;border-radius:6px;background:var(--surface2);font-size:13px"
          >
            <!-- Badge action -->
            <span :class="h.action === 'generated' ? 'badge' : 'badge badge-allow'"
              :style="h.action === 'generated' ? 'background:rgba(248,81,73,.15);color:var(--red)' : ''">
              {{ h.action === 'generated' ? 'Généré' : 'Importé' }}
            </span>

            <!-- Utilisateur -->
            <span style="font-weight:500">{{ h.username }}</span>

            <!-- Sujet + empreinte -->
            <div style="overflow:hidden">
              <div style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ h.subject }}</div>
              <code style="font-size:10px;color:var(--text-muted)">{{ h.fingerprint?.slice(0, 24) }}…</code>
            </div>

            <!-- Date -->
            <span style="color:var(--text-muted);font-size:12px;font-family:monospace;white-space:nowrap">{{ fmtDatetime(h.created_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Modal confirmation génération ─────────────────────────── -->
    <div v-if="showGenConfirm" style="position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:1000" @click.self="showGenConfirm = false">
      <div class="card" style="width:420px;padding:28px 24px">
        <div style="font-size:16px;font-weight:700;margin-bottom:8px">Générer un nouveau certificat ?</div>
        <div style="font-size:13px;color:var(--text-muted);margin-bottom:20px;line-height:1.6">
          L'ancien certificat CA sera <strong style="color:var(--red)">remplacé définitivement</strong>.
          Tous les postes clients devront désinstaller l'ancien et installer le nouveau pour que le proxy fonctionne en HTTPS.
          <br><br>Le proxy doit être redémarré après la génération.
        </div>
        <div style="display:flex;gap:10px;justify-content:flex-end">
          <button class="btn" @click="showGenConfirm = false">Annuler</button>
          <button class="btn" style="background:var(--red);color:#fff;border-color:var(--red)" @click="doGenerate" :disabled="actionLoading">
            {{ actionLoading ? 'Génération…' : 'Confirmer' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { certificatesApi } from '@/api'

const loading       = ref(true)
const actionLoading = ref(false)
const certInfo      = ref({})
const history       = ref([])
const restartRequired = ref(false)
const showGenConfirm  = ref(false)
const importCertFile  = ref(null)
const importKeyFile   = ref(null)
const importError     = ref('')
const importErrors    = ref({ cert: '', key: '' })
const importSuccess   = ref(false)

function onCertFileChange(e) {
  importCertFile.value    = e.target.files[0] ?? null
  importErrors.value.cert = ''
  importSuccess.value     = false
}

function onKeyFileChange(e) {
  importKeyFile.value    = e.target.files[0] ?? null
  importErrors.value.key = ''
  importSuccess.value    = false
}

const downloadUrl = certificatesApi.downloadUrl()

onMounted(async () => {
  await reload()
})

async function reload() {
  loading.value = true
  const [infoRes, histRes] = await Promise.all([
    certificatesApi.info(),
    certificatesApi.history(),
  ])
  certInfo.value = infoRes.data
  history.value  = histRes.data
  loading.value  = false
}

async function doGenerate() {
  actionLoading.value = true
  try {
    const { data } = await certificatesApi.generate()
    certInfo.value    = data
    restartRequired.value = true
    showGenConfirm.value  = false
    const histRes = await certificatesApi.history()
    history.value = histRes.data
  } finally {
    actionLoading.value = false
  }
}

async function doImport() {
  // Validation locale
  importErrors.value.cert = importCertFile.value ? '' : 'Fichier requis'
  importErrors.value.key  = importKeyFile.value  ? '' : 'Fichier requis'
  importError.value   = ''
  importSuccess.value = false
  if (importErrors.value.cert || importErrors.value.key) return

  actionLoading.value = true
  try {
    const { data } = await certificatesApi.import(importCertFile.value, importKeyFile.value)
    certInfo.value        = data
    restartRequired.value = true
    importSuccess.value   = true
    importCertFile.value  = null
    importKeyFile.value   = null
    const histRes = await certificatesApi.history()
    history.value = histRes.data
  } catch (err) {
    importError.value = err.response?.data?.detail ?? 'Erreur lors de l\'import'
  } finally {
    actionLoading.value = false
  }
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('fr-FR')
}

function fmtDatetime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('fr-FR') + ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}
</script>
