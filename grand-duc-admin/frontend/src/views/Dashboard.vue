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
          <div class="stat-label">Requêtes totales</div>
          <div class="stat-value blue">{{ fmt(stats.total_requests) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Bloquées</div>
          <div class="stat-value red">{{ fmt(stats.blocked_requests) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Autorisées</div>
          <div class="stat-value green">{{ fmt(stats.allowed_requests) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Taux de blocage</div>
          <div class="stat-value accent">{{ stats.block_rate }}%</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Requêtes aujourd'hui</div>
          <div class="stat-value blue">{{ fmt(stats.requests_today) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Règles actives</div>
          <div class="stat-value accent">{{ stats.active_rules }}</div>
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
            <!-- Légende -->
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
          <!-- Grille + labels Y -->
          <g v-for="(tick, i) in yTicks" :key="'g'+i">
            <line
              :x1="PAD_L" :y1="yScale(tick)"
              :x2="W-PAD_R" :y2="yScale(tick)"
              stroke="var(--border)" stroke-width="1"
            />
            <text
              :x="PAD_L-8" :y="yScale(tick)+4"
              text-anchor="end" font-size="10" fill="var(--text-muted)"
            >{{ tick }}</text>
          </g>

          <!-- Zones remplies -->
          <path :d="areaPath(traffic.map(p=>p.total))"   fill="rgba(88,166,255,0.07)" />
          <path :d="areaPath(traffic.map(p=>p.blocked))" fill="rgba(248,81,73,0.09)" />

          <!-- Courbes -->
          <polyline :points="linePath(traffic.map(p=>p.total))"
            fill="none" stroke="var(--blue)"  stroke-width="2"
            stroke-linejoin="round" stroke-linecap="round"/>
          <polyline :points="linePath(traffic.map(p=>p.allowed))"
            fill="none" stroke="var(--green)" stroke-width="1.5"
            stroke-linejoin="round" stroke-linecap="round" stroke-dasharray="4 2"/>
          <polyline :points="linePath(traffic.map(p=>p.blocked))"
            fill="none" stroke="var(--red)"   stroke-width="1.5"
            stroke-linejoin="round" stroke-linecap="round"/>

          <!-- Points + zones interactives -->
          <g v-for="(pt, i) in traffic" :key="'pt'+i">
            <rect
              :x="xPos(i)-colW/2" :y="PAD_T"
              :width="colW" :height="CHART_H"
              fill="transparent" style="cursor:crosshair"
              @mouseenter="hoverIdx=i" @mouseleave="hoverIdx=null"
            />
            <circle :cx="xPos(i)" :cy="yScale(pt.total)"
              :r="hoverIdx===i?5:3"
              fill="var(--blue)" stroke="var(--surface)" stroke-width="1.5"
              style="transition:r .1s;pointer-events:none"/>
            <circle v-if="pt.blocked>0"
              :cx="xPos(i)" :cy="yScale(pt.blocked)"
              :r="hoverIdx===i?4:2.5"
              fill="var(--red)" stroke="var(--surface)" stroke-width="1.5"
              style="transition:r .1s;pointer-events:none"/>
          </g>

          <!-- Labels X -->
          <text
            v-for="(pt, i) in traffic" :key="'lx'+i"
            v-show="showXLabel(i)"
            :x="xPos(i)" :y="H-4"
            text-anchor="middle" font-size="10" fill="var(--text-muted)"
          >{{ pt.label }}</text>

          <!-- Ligne de base -->
          <line :x1="PAD_L" :y1="PAD_T+CHART_H" :x2="W-PAD_R" :y2="PAD_T+CHART_H"
            stroke="var(--border)" stroke-width="1"/>

          <!-- Tooltip -->
          <g v-if="hoverIdx!==null" style="pointer-events:none">
            <line
              :x1="xPos(hoverIdx)" :y1="PAD_T"
              :x2="xPos(hoverIdx)" :y2="PAD_T+CHART_H"
              stroke="var(--text-muted)" stroke-width="1" stroke-dasharray="3 2"/>
            <g :transform="`translate(${tooltipX(hoverIdx)},${PAD_T+8})`">
              <rect x="0" y="0" width="128" height="76" rx="6"
                fill="var(--surface2)" stroke="var(--border)" stroke-width="1"/>
              <text x="10" y="17" font-size="11" font-weight="600" fill="var(--text)">
                {{ traffic[hoverIdx].label }}
              </text>
              <circle cx="10" cy="31" r="4" fill="var(--blue)"/>
              <text x="22" y="35" font-size="11" fill="var(--text)">
                Total : {{ traffic[hoverIdx].total }}
              </text>
              <circle cx="10" cy="48" r="4" fill="var(--green)"/>
              <text x="22" y="52" font-size="11" fill="var(--text)">
                OK : {{ traffic[hoverIdx].allowed }}
              </text>
              <circle cx="10" cy="65" r="4" fill="var(--red)"/>
              <text x="22" y="69" font-size="11" fill="var(--text)">
                Bloquées : {{ traffic[hoverIdx].blocked }}
              </text>
            </g>
          </g>
        </svg>

        <div v-else style="height:200px;display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:13px">
          Aucune donnée de trafic disponible
        </div>
      </div>

      <!-- ── Tables top domaines ────────────────────────────────────────── -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div class="card">
          <div class="card-title" style="display:flex;align-items:center;gap:6px">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2">
                <path d="M15.686 15A14.5 14.5 0 0 1 12 22a14.5 14.5 0 0 1 0-20a10 10 0 1 0 9.542 13M2 12h8.5M20 6V4a2 2 0 1 0-4 0v2"/>
                <rect width="8" height="5" x="14" y="6" rx="1"/>
              </g>
            </svg>
            Top domaines bloqués</div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Domaine</th><th style="text-align:right">Blocages</th></tr></thead>
              <tbody>
                <tr v-for="d in stats.top_blocked" :key="d.host">
                  <td class="mono" style="color:var(--text-muted)">{{ d.host || '—' }}</td>
                  <td style="text-align:right"><span class="badge badge-block">{{ d.count }}</span></td>
                </tr>
                <tr v-if="!stats.top_blocked.length">
                  <td colspan="2" style="color:var(--text-muted);text-align:center;padding:20px">Aucune donnée</td>
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
            Top domaines visités</div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Domaine</th><th style="text-align:right">Total</th><th style="text-align:right">Bloqués</th></tr></thead>
              <tbody>
                <tr v-for="d in stats.top_domains" :key="d.host">
                  <td class="mono" style="color:var(--text-muted)">{{ d.host || '—' }}</td>
                  <td style="text-align:right">{{ d.count }}</td>
                  <td style="text-align:right">
                    <span v-if="d.blocked" class="badge badge-block">{{ d.blocked }}</span>
                    <span v-else style="color:var(--text-muted)">—</span>
                  </td>
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

// ── Données ───────────────────────────────────────────────────────────────────
const stats       = ref(null)
const traffic     = ref([])
const loading     = ref(false)
const trafficMode = ref('24h')
const hoverIdx    = ref(null)
let   autoRefresh = null

// ── Dimensions SVG ────────────────────────────────────────────────────────────
const W       = 900
const H       = 220
const PAD_L   = 42
const PAD_R   = 16
const PAD_T   = 14
const PAD_B   = 28
const CHART_H = H - PAD_T - PAD_B
const CHART_W = W - PAD_L - PAD_R

// ── Calculs ───────────────────────────────────────────────────────────────────
const maxVal = computed(() => {
  const m = Math.max(...traffic.value.map(p => p.total), 1)
  return Math.ceil(m / 5) * 5
})

const yTicks = computed(() => {
  const m         = maxVal.value
  const maxTicks  = 6   // nombre maximum de graduations souhaitées
  // Calcule un step "propre" (puissance de 10 ou multiple de 2/5)
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
  return x + 140 > W ? x - 138 : x + 10
}

// ── Chargement ────────────────────────────────────────────────────────────────
function fmt(n) { return n?.toLocaleString('fr-FR') ?? '—' }

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