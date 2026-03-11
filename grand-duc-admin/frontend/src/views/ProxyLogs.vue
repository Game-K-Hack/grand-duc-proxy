<template>
  <div style="display:flex;flex-direction:column;height:calc(100vh - 48px);gap:10px">

    <!-- ── Header ──────────────────────────────────────────────────── -->
    <div class="page-header" style="flex-shrink:0;display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding-bottom:0">
      <h1 class="page-title" style="margin:0">Logs proxy</h1>

      <!-- Statut -->
      <div style="display:flex;align-items:center;gap:6px;font-size:12px;padding:3px 10px;border-radius:20px;border:1px solid"
        :style="running
          ? 'background:rgba(46,160,67,.1);border-color:var(--green);color:var(--green)'
          : 'background:rgba(248,81,73,.1);border-color:var(--red);color:var(--red)'">
        <span style="width:7px;height:7px;border-radius:50%;flex-shrink:0"
          :style="running ? 'background:var(--green)' : 'background:var(--red)'"
          :class="{ pulse: running }"/>
        {{ running ? 'En ligne' : 'Arrêté' }}
      </div>

      <!-- Filtre texte -->
      <input
        v-model="textFilter"
        class="form-input"
        placeholder="Rechercher…"
        style="width:180px;font-size:12px;padding:5px 10px;font-family:monospace"
      />

      <!-- Filtres niveau -->
      <div style="display:flex;gap:4px">
        <button
          v-for="lvl in LEVELS" :key="lvl.key"
          class="btn"
          :style="levelFilter === lvl.key
            ? `background:${lvl.color};color:#fff;border-color:${lvl.color};font-size:11px;padding:3px 9px`
            : `font-size:11px;padding:3px 9px;color:${lvl.color};border-color:${lvl.color};background:transparent`"
          @click="levelFilter = lvl.key"
        >{{ lvl.label }}</button>
      </div>

      <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
        <!-- Compteur -->
        <span style="font-size:12px;color:var(--text-muted)">{{ filteredLines.length }} lignes</span>

        <!-- Auto-scroll -->
        <label style="display:flex;align-items:center;gap:5px;font-size:12px;color:var(--text-muted);cursor:pointer">
          <input type="checkbox" v-model="autoScroll"/> Scroll auto
        </label>

        <!-- Effacer -->
        <button class="btn" style="font-size:12px;padding:5px 10px" @click="lines = []">Effacer</button>

        <!-- Redémarrer -->
        <button class="btn"
          style="font-size:12px;padding:5px 12px;background:var(--red);color:#fff;border-color:var(--red)"
          @click="showRestartConfirm = true" :disabled="restarting">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
          </svg>
          {{ restarting ? 'Redémarrage…' : 'Redémarrer' }}
        </button>
      </div>
    </div>

    <!-- ── Terminal ─────────────────────────────────────────────────── -->
    <div
      ref="terminal"
      @scroll="onScroll"
      style="flex:1;overflow-y:auto;background:#0d1117;border-radius:8px;padding:10px 14px;font-family:'Consolas','Courier New',monospace;font-size:11.5px;line-height:1.55;min-height:0"
    >
      <div v-if="filteredLines.length === 0" style="color:#484f58;padding:16px 0">
        {{ lines.length === 0 ? 'En attente de logs…' : 'Aucun log ne correspond aux filtres.' }}
      </div>

      <div
        v-for="(l, i) in filteredLines"
        :key="i"
        :style="lineStyle(l)"
        style="white-space:pre-wrap;word-break:break-all;padding:0.5px 0"
      >{{ l }}</div>
    </div>

    <!-- ── Modal redémarrage ────────────────────────────────────────── -->
    <div v-if="showRestartConfirm"
      style="position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;z-index:1000"
      @click.self="showRestartConfirm = false">
      <div class="card" style="width:400px;padding:26px 24px">
        <div style="font-size:16px;font-weight:700;margin-bottom:8px">Redémarrer le proxy ?</div>
        <div style="font-size:13px;color:var(--text-muted);margin-bottom:20px;line-height:1.5">
          Le proxy sera arrêté puis relancé. Les connexions en cours seront interrompues (~1–2 secondes).
        </div>
        <div style="display:flex;gap:10px;justify-content:flex-end">
          <button class="btn" @click="showRestartConfirm = false">Annuler</button>
          <button class="btn"
            style="background:var(--red);color:#fff;border-color:var(--red)"
            @click="doRestart" :disabled="restarting">
            Confirmer
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { proxyApi } from '@/api'

// ── Config niveaux ────────────────────────────────────────────────────────────
const LEVELS = [
  { key: 'ALL',   label: 'Tous',   color: '#8b949e' },
  { key: 'ERROR', label: 'ERROR',  color: '#ff7b72' },
  { key: 'WARN',  label: 'WARN',   color: '#e3b341' },
  { key: 'INFO',  label: 'INFO',   color: '#7ee787' },
  { key: 'DEBUG', label: 'DEBUG',  color: '#484f58' },
]

// ── État ──────────────────────────────────────────────────────────────────────
const lines       = ref([])
const textFilter  = ref('')
const levelFilter = ref('ALL')
const autoScroll  = ref(true)
const running     = ref(false)
const restarting  = ref(false)
const showRestartConfirm = ref(false)
const terminal    = ref(null)

// ── Filtre ────────────────────────────────────────────────────────────────────
const filteredLines = computed(() => {
  let result = lines.value

  if (levelFilter.value !== 'ALL') {
    result = result.filter(l => new RegExp(`\\b${levelFilter.value}\\b`).test(l))
  }

  const q = textFilter.value.trim().toLowerCase()
  if (q) result = result.filter(l => l.toLowerCase().includes(q))

  return result
})

// ── Coloration ────────────────────────────────────────────────────────────────
function lineStyle(line) {
  // Nettoyer les éventuelles séquences ANSI résiduelles visuellement
  if (/\bERROR\b/.test(line)) return 'color:#ff7b72'
  if (/\bWARN\b/.test(line))  return 'color:#e3b341'
  if (/\bINFO\b/.test(line))  return 'color:#7ee787'
  if (/\bDEBUG\b/.test(line)) return 'color:#6e7681'
  return 'color:#c9d1d9'
}

// ── Auto-scroll ───────────────────────────────────────────────────────────────
function scrollToBottom() {
  if (!terminal.value) return
  terminal.value.scrollTop = terminal.value.scrollHeight
}

function onScroll() {
  if (!terminal.value) return
  const { scrollTop, scrollHeight, clientHeight } = terminal.value
  // L'utilisateur est en bas si < 60px de la fin
  autoScroll.value = scrollHeight - scrollTop - clientHeight < 60
}

// ── SSE ───────────────────────────────────────────────────────────────────────
let es = null

function connectSSE() {
  es = new EventSource(proxyApi.logsUrl())

  es.onmessage = (e) => {
    let { line } = JSON.parse(e.data)
    if (!line) return

    // Supprimer les séquences ANSI résiduelles (ex: \x1b[2m ... \x1b[0m)
    // eslint-disable-next-line no-control-regex
    line = line.replace(/\x1b\[[0-9;]*m/g, '')

    lines.value.push(line)
    if (lines.value.length > 5000) lines.value.splice(0, 500)

    if (autoScroll.value) {
      nextTick(scrollToBottom)
    }
  }

  es.onerror = () => {
    es?.close()
    es = null
    setTimeout(connectSSE, 3000)
  }
}

// Quand le filtre change et qu'on est en mode auto-scroll, revenir en bas
watch([textFilter, levelFilter], () => {
  if (autoScroll.value) nextTick(scrollToBottom)
})

// ── Statut ────────────────────────────────────────────────────────────────────
let statusInterval = null

async function fetchStatus() {
  try {
    const { data } = await proxyApi.status()
    running.value = data.running
  } catch {
    running.value = false
  }
}

// ── Restart ───────────────────────────────────────────────────────────────────
async function doRestart() {
  restarting.value = true
  showRestartConfirm.value = false
  try {
    await proxyApi.restart()
    await new Promise(r => setTimeout(r, 1500))
    await fetchStatus()
  } finally {
    restarting.value = false
  }
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(() => {
  fetchStatus()
  connectSSE()
  statusInterval = setInterval(fetchStatus, 5000)
})

onUnmounted(() => {
  es?.close()
  clearInterval(statusInterval)
})
</script>

<style scoped>
.pulse {
  animation: pulse 1.8s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.35; }
}
</style>
