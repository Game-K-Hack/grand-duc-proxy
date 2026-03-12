<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Tableau de bord</h1>
      <button class="btn btn-ghost btn-sm" @click="loadAll">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
        </svg>
        Actualiser
      </button>
    </div>

    <div v-if="loading" style="color:var(--text-muted)">Chargement…</div>

    <template v-else-if="stats">

      <!-- ── Stat cards ─────────────────────────────────────────────────── -->
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-label">Requêtes aujourd'hui</div>
          <div class="stat-value blue">{{ fmt(stats.requests_today) }}</div>
          <div class="stat-delta" :class="deltaClass(stats.requests_today, stats.requests_yesterday)">
            {{ deltaText(stats.requests_today, stats.requests_yesterday) }} vs hier
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Bloquées aujourd'hui</div>
          <div class="stat-value red">{{ fmt(stats.blocked_today) }}</div>
          <div class="stat-delta" :class="deltaClass(stats.blocked_today, stats.blocked_yesterday)">
            {{ deltaText(stats.blocked_today, stats.blocked_yesterday) }} vs hier
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Taux de blocage</div>
          <div class="stat-value accent">{{ stats.block_rate_today }}%</div>
          <div class="stat-sub">{{ fmt(stats.allowed_today) }} autorisées</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Postes actifs</div>
          <div class="stat-value blue">{{ stats.active_clients }}</div>
          <div class="stat-sub">IPs uniques aujourd'hui</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Règles actives</div>
          <div class="stat-value accent">{{ stats.active_rules }}</div>
        </div>
        <div class="stat-card" :style="stats.killswitch ? 'border-color:var(--red)' : ''">
          <div class="stat-label">Killswitch</div>
          <div class="stat-value" :class="stats.killswitch ? 'red' : 'green'">
            {{ stats.killswitch ? 'ACTIF' : 'Inactif' }}
          </div>
        </div>
      </div>

      <!-- ── Graphique trafic ──────────────────────────────────────────── -->
      <div class="card" style="margin-bottom:20px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;flex-wrap:wrap;gap:10px">
          <div>
            <div class="card-title" style="margin-bottom:2px">Trafic réseau</div>
            <div style="font-size:12px;color:var(--text-muted)">
              {{ trafficMode === '24h' ? '24 dernières heures (par heure)' : 'Dernière heure (par minute)' }}
              — actualisation automatique toutes les 30s
            </div>
          </div>
          <div style="display:flex;gap:6px;align-items:center">
            <div style="display:flex;gap:14px;margin-right:12px;font-size:12px">
              <span style="display:flex;align-items:center;gap:5px">
                <span style="width:10px;height:3px;background:var(--blue);display:inline-block;border-radius:2px"></span>
                Total
              </span>
              <span style="display:flex;align-items:center;gap:5px">
                <span style="width:10px;height:3px;background:var(--green);display:inline-block;border-radius:2px"></span>
                Autorisées
              </span>
              <span style="display:flex;align-items:center;gap:5px">
                <span style="width:10px;height:3px;background:var(--red);display:inline-block;border-radius:2px"></span>
                Bloquées
              </span>
            </div>
            <button class="btn btn-sm" :class="trafficMode==='24h'?'btn-primary':'btn-ghost'" @click="setTrafficMode('24h')">24h</button>
            <button class="btn btn-sm" :class="trafficMode==='1h'?'btn-primary':'btn-ghost'"  @click="setTrafficMode('1h')">1h</button>
          </div>
        </div>

        <!-- SVG Chart -->
        <svg
          v-if="traffic.length"
          :viewBox="`0 0 ${W} ${H}`"
          style="width:100%;height:auto;display:block;overflow:visible"
        >
          <g v-for="(tick, i) in yTicks" :key="'g'+i">
            <line
              :x1="PAD_L" :y1="yScale(tick)"
              :x2="W-PAD_R" :y2="yScale(tick)"
              stroke="var(--border)" stroke-width="1"
            />
            <text
              :x="PAD_L-6" :y="yScale(tick)+3"
              text-anchor="end" font-size="8" fill="var(--text-muted)"
            >{{ fmtAxis(tick) }}</text>
          </g>

          <path :d="areaPath(traffic.map(p=>p.total))"   fill="rgba(88,166,255,0.07)" />
          <path :d="areaPath(traffic.map(p=>p.blocked))" fill="rgba(248,81,73,0.09)" />

          <polyline :points="linePath(traffic.map(p=>p.total))"
            fill="none" stroke="var(--blue)"  stroke-width="1.5"
            stroke-linejoin="round" stroke-linecap="round"/>
          <polyline :points="linePath(traffic.map(p=>p.allowed))"
            fill="none" stroke="var(--green)" stroke-width="1"
            stroke-linejoin="round" stroke-linecap="round" stroke-dasharray="3 2"/>
          <polyline :points="linePath(traffic.map(p=>p.blocked))"
            fill="none" stroke="var(--red)"   stroke-width="1"
            stroke-linejoin="round" stroke-linecap="round"/>

          <g v-for="(pt, i) in traffic" :key="'pt'+i">
            <rect
              :x="xPos(i)-colW/2" :y="PAD_T"
              :width="colW" :height="CHART_H"
              fill="transparent" style="cursor:crosshair"
              @mouseenter="hoverIdx=i" @mouseleave="hoverIdx=null"
            />
            <circle :cx="xPos(i)" :cy="yScale(pt.total)"
              :r="hoverIdx===i?3.5:2"
              fill="var(--blue)" stroke="var(--surface)" stroke-width="1"
              style="transition:r .1s;pointer-events:none"/>
            <circle v-if="pt.blocked>0"
              :cx="xPos(i)" :cy="yScale(pt.blocked)"
              :r="hoverIdx===i?3:1.5"
              fill="var(--red)" stroke="var(--surface)" stroke-width="1"
              style="transition:r .1s;pointer-events:none"/>
          </g>

          <text
            v-for="(pt, i) in traffic" :key="'lx'+i"
            v-show="showXLabel(i)"
            :x="xPos(i)" :y="H-4"
            text-anchor="middle" font-size="8" fill="var(--text-muted)"
          >{{ pt.label }}</text>

          <line :x1="PAD_L" :y1="PAD_T+CHART_H" :x2="W-PAD_R" :y2="PAD_T+CHART_H"
            stroke="var(--border)" stroke-width="1"/>

          <!-- Tooltip -->
          <g v-if="hoverIdx!==null" style="pointer-events:none">
            <line
              :x1="xPos(hoverIdx)" :y1="PAD_T"
              :x2="xPos(hoverIdx)" :y2="PAD_T+CHART_H"
              stroke="var(--text-muted)" stroke-width="1" stroke-dasharray="3 2"/>
            <g :transform="`translate(${tooltipX(hoverIdx)},${PAD_T+6})`">
              <rect x="0" y="0" width="110" height="60" rx="4"
                fill="var(--surface2)" stroke="var(--border)" stroke-width=".5"/>
              <text x="8" y="13" font-size="8" font-weight="600" fill="var(--text)">
                {{ traffic[hoverIdx].label }}
              </text>
              <circle cx="8" cy="24" r="3" fill="var(--blue)"/>
              <text x="16" y="27" font-size="8" fill="var(--text)">
                Total : {{ fmt(traffic[hoverIdx].total) }}
              </text>
              <circle cx="8" cy="37" r="3" fill="var(--green)"/>
              <text x="16" y="40" font-size="8" fill="var(--text)">
                OK : {{ fmt(traffic[hoverIdx].allowed) }}
              </text>
              <circle cx="8" cy="50" r="3" fill="var(--red)"/>
              <text x="16" y="53" font-size="8" fill="var(--text)">
                Bloquées : {{ fmt(traffic[hoverIdx].blocked) }}
              </text>
            </g>
          </g>
        </svg>

        <div v-else style="height:200px;display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:13px">
          Aucune donnée de trafic disponible
        </div>
      </div>

      <!-- ── 3 colonnes : top bloqués, top visités, top clients ──────── -->
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px">
        <div class="card">
          <div class="card-title" style="display:flex;align-items:center;gap:6px">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2">
                <path d="M15.686 15A14.5 14.5 0 0 1 12 22a14.5 14.5 0 0 1 0-20a10 10 0 1 0 9.542 13M2 12h8.5M20 6V4a2 2 0 1 0-4 0v2"/>
                <rect width="8" height="5" x="14" y="6" rx="1"/>
              </g>
            </svg>
            Domaines bloqués
            <span class="card-badge">aujourd'hui</span>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Domaine</th><th style="text-align:right">Blocages</th></tr></thead>
              <tbody>
                <tr v-for="d in stats.top_blocked" :key="d.host">
                  <td class="mono" style="color:var(--text-muted)">{{ d.host || '—' }}</td>
                  <td style="text-align:right"><span class="badge badge-block">{{ fmt(d.count) }}</span></td>
                </tr>
                <tr v-if="!stats.top_blocked.length">
                  <td colspan="2" style="color:var(--text-muted);text-align:center;padding:20px">Aucun blocage aujourd'hui</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-title" style="display:flex;align-items:center;gap:6px">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2">
                <circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20a14.5 14.5 0 0 0 0-20M2 12h20"/>
              </g>
            </svg>
            Domaines visités
            <span class="card-badge">aujourd'hui</span>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Domaine</th><th style="text-align:right">Total</th><th style="text-align:right">Bloqués</th></tr></thead>
              <tbody>
                <tr v-for="d in stats.top_domains" :key="d.host">
                  <td class="mono" style="color:var(--text-muted)">{{ d.host || '—' }}</td>
                  <td style="text-align:right">{{ fmt(d.count) }}</td>
                  <td style="text-align:right">
                    <span v-if="d.blocked" class="badge badge-block">{{ fmt(d.blocked) }}</span>
                    <span v-else style="color:var(--text-muted)">—</span>
                  </td>
                </tr>
                <tr v-if="!stats.top_domains.length">
                  <td colspan="3" style="color:var(--text-muted);text-align:center;padding:20px">Aucune donnée</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-title" style="display:flex;align-items:center;gap:6px">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2">
                <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
                <circle cx="9" cy="7" r="4"/>
                <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>
              </g>
            </svg>
            Postes les plus actifs
            <span class="card-badge">aujourd'hui</span>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Poste</th><th style="text-align:right">Requêtes</th><th style="text-align:right">Bloquées</th></tr></thead>
              <tbody>
                <tr v-for="c in stats.top_clients" :key="c.ip">
                  <td>
                    <div style="font-size:12px;font-weight:500">{{ c.label || c.ip }}</div>
                    <div v-if="c.label" class="mono" style="font-size:10px;color:var(--text-muted)">{{ c.ip }}</div>
                  </td>
                  <td style="text-align:right">{{ fmt(c.total) }}</td>
                  <td style="text-align:right">
                    <span v-if="c.blocked" class="badge badge-block">{{ fmt(c.blocked) }}</span>
                    <span v-else style="color:var(--text-muted)">—</span>
                  </td>
                </tr>
                <tr v-if="!stats.top_clients.length">
                  <td colspan="3" style="color:var(--text-muted);text-align:center;padding:20px">Aucune donnée</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { statsApi } from '@/api'

const stats       = ref(null)
const traffic     = ref([])
const loading     = ref(false)
const trafficMode = ref('24h')
const hoverIdx    = ref(null)
let   autoRefresh = null

// ── Dimensions SVG ──────────────────────────────────────────────────────────
const W       = 960
const H       = 300
const PAD_L   = 38
const PAD_R   = 12
const PAD_T   = 12
const PAD_B   = 22
const CHART_H = H - PAD_T - PAD_B
const CHART_W = W - PAD_L - PAD_R

// ── Calculs chart ───────────────────────────────────────────────────────────
const maxVal = computed(() => {
  const m = Math.max(...traffic.value.map(p => p.total), 1)
  return Math.ceil(m / 5) * 5
})

const yTicks = computed(() => {
  const m         = maxVal.value
  const maxTicks  = 6
  const rawStep   = m / maxTicks
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)))
  const niceMult  = rawStep / magnitude <= 1 ? 1
                  : rawStep / magnitude <= 2 ? 2
                  : rawStep / magnitude <= 5 ? 5 : 10
  const step      = magnitude * niceMult

  const ticks = []
  for (let v = 0; v <= m; v += step) ticks.push(v)
  return ticks
})

const colW = computed(() =>
  traffic.value.length > 1 ? CHART_W / (traffic.value.length - 1) : CHART_W
)

function xPos(i) {
  if (traffic.value.length <= 1) return PAD_L + CHART_W / 2
  return PAD_L + (i / (traffic.value.length - 1)) * CHART_W
}

function yScale(v) {
  return PAD_T + CHART_H - (v / maxVal.value) * CHART_H
}

function linePath(values) {
  return values.map((v, i) => `${xPos(i)},${yScale(v)}`).join(' ')
}

function areaPath(values) {
  const base = PAD_T + CHART_H
  const pts  = values.map((v, i) => `${xPos(i)},${yScale(v)}`).join(' L ')
  return `M ${xPos(0)},${base} L ${pts} L ${xPos(values.length-1)},${base} Z`
}

function showXLabel(i) {
  const n = traffic.value.length
  if (n <= 12) return true
  if (n <= 24) return i % 2 === 0
  return i % 5 === 0
}

function tooltipX(i) {
  const x = xPos(i)
  return x + 120 > W ? x - 118 : x + 8
}

// ── Formatage ───────────────────────────────────────────────────────────────
function fmt(n) { return n?.toLocaleString('fr-FR') ?? '—' }

function fmtAxis(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace('.0', '') + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace('.0', '') + 'k'
  return String(n)
}

function deltaText(today, yesterday) {
  if (yesterday === 0) return today > 0 ? '+100%' : '='
  const pct = Math.round(((today - yesterday) / yesterday) * 100)
  if (pct > 0) return `+${pct}%`
  if (pct < 0) return `${pct}%`
  return '='
}

function deltaClass(today, yesterday) {
  if (yesterday === 0 && today === 0) return 'delta-neutral'
  if (yesterday === 0) return 'delta-up'
  const diff = today - yesterday
  if (diff > 0) return 'delta-up'
  if (diff < 0) return 'delta-down'
  return 'delta-neutral'
}

// ── Chargement ──────────────────────────────────────────────────────────────
async function loadStats() {
  const { data } = await statsApi.get()
  stats.value = data
}

async function loadTraffic() {
  const { data } = await statsApi.traffic(trafficMode.value)
  traffic.value = data.points
}

async function loadAll() {
  loading.value = true
  try { await Promise.all([loadStats(), loadTraffic()]) }
  finally { loading.value = false }
}

async function setTrafficMode(mode) {
  trafficMode.value = mode
  await loadTraffic()
}

onMounted(() => {
  loadAll()
  autoRefresh = setInterval(loadTraffic, 30_000)
})
onUnmounted(() => clearInterval(autoRefresh))
</script>

<style scoped>
.stat-delta {
  font-size: 11px;
  margin-top: 4px;
  font-weight: 600;
}
.delta-up   { color: var(--blue); }
.delta-down { color: var(--green); }
.delta-neutral { color: var(--text-muted); }
.stat-sub {
  font-size: 11px;
  margin-top: 4px;
  color: var(--text-muted);
}
.card-badge {
  font-size: 10px;
  font-weight: 500;
  padding: 1px 7px;
  border-radius: 10px;
  background: var(--surface2);
  color: var(--text-muted);
  border: 1px solid var(--border);
}
</style>
