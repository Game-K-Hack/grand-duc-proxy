import { reactive, watch } from 'vue'
import { settingsApi } from '@/api'

// ── Palettes des themes predefinis ──────────────────────────────────────────

const THEME_COLORS = {
  bg: '#0d1117',
  surface: '#161b22',
  surface2: '#21262d',
  border: '#30363d',
  text: '#e6edf3',
  'text-muted': '#8b949e',
  accent: '#f0883e',
  'accent-dim': '#b46914',
  green: '#3fb950',
  red: '#f85149',
  blue: '#58a6ff',
  yellow: '#d29922',
}

export const PRESETS = [
  {
    id: 'grand-duc',
    name: 'Grand-Duc',
    description: 'Sombre avec accent orange',
    colors: { ...THEME_COLORS },
  },
  {
    id: 'nuit-bleue',
    name: 'Nuit Bleue',
    description: 'Sombre avec accent bleu',
    colors: {
      ...THEME_COLORS,
      accent: '#58a6ff',
      'accent-dim': '#1f6feb',
    },
  },
  {
    id: 'foret',
    name: 'Foret',
    description: 'Sombre avec accent vert',
    colors: {
      ...THEME_COLORS,
      accent: '#3fb950',
      'accent-dim': '#238636',
    },
  },
  {
    id: 'crepuscule',
    name: 'Crepuscule',
    description: 'Sombre avec accent violet',
    colors: {
      ...THEME_COLORS,
      accent: '#bc8cff',
      'accent-dim': '#8b5cf6',
      blue: '#a78bfa',
    },
  },
  {
    id: 'rose',
    name: 'Rose',
    description: 'Sombre avec accent rose',
    colors: {
      ...THEME_COLORS,
      accent: '#f778ba',
      'accent-dim': '#db61a2',
      blue: '#f0abfc',
    },
  },
  {
    id: 'nord',
    name: 'Nord',
    description: 'Palette nordique apaisante',
    colors: {
      bg: '#2e3440',
      surface: '#3b4252',
      surface2: '#434c5e',
      border: '#4c566a',
      text: '#eceff4',
      'text-muted': '#d8dee9',
      accent: '#88c0d0',
      'accent-dim': '#5e81ac',
      green: '#a3be8c',
      red: '#bf616a',
      blue: '#81a1c1',
      yellow: '#ebcb8b',
    },
  },
  {
    id: 'arctique',
    name: 'Arctique',
    description: 'Theme clair',
    colors: {
      bg: '#f0f2f5',
      surface: '#ffffff',
      surface2: '#e8eaed',
      border: '#d0d7de',
      text: '#1f2328',
      'text-muted': '#656d76',
      accent: '#cf5418',
      'accent-dim': '#a3410c',
      green: '#1a7f37',
      red: '#cf222e',
      blue: '#0969da',
      yellow: '#9a6700',
    },
  },
  {
    id: 'abysse',
    name: 'Abysse',
    description: 'Tres sombre avec accent cyan',
    colors: {
      bg: '#030712',
      surface: '#0a0f1a',
      surface2: '#111827',
      border: '#1e293b',
      text: '#e2e8f0',
      'text-muted': '#94a3b8',
      accent: '#22d3ee',
      'accent-dim': '#0891b2',
      green: '#34d399',
      red: '#fb7185',
      blue: '#60a5fa',
      yellow: '#fbbf24',
    },
  },
]

// ── Cles editables (pour l'UI) ──────────────────────────────────────────────

export const COLOR_LABELS = {
  bg:           'Arriere-plan',
  surface:      'Surface (cartes)',
  surface2:     'Surface secondaire',
  border:       'Bordures',
  text:         'Texte principal',
  'text-muted': 'Texte secondaire',
  accent:       'Accent principal',
  'accent-dim': 'Accent sombre',
  green:        'Vert (succes)',
  red:          'Rouge (erreur)',
  blue:         'Bleu (info)',
  yellow:       'Jaune (alerte)',
}

// ── Etat global ─────────────────────────────────────────────────────────────

const state = reactive({
  presetId: 'grand-duc',
  customColors: null,   // null = utiliser le preset tel quel
  loaded: false,
})

// ── Helpers ─────────────────────────────────────────────────────────────────

function getPreset(id) {
  return PRESETS.find(p => p.id === id) || PRESETS[0]
}

function activeColors() {
  const base = getPreset(state.presetId).colors
  if (!state.customColors) return { ...base }
  return { ...base, ...state.customColors }
}

function applyToDOM(colors) {
  const root = document.documentElement
  for (const [key, value] of Object.entries(colors)) {
    root.style.setProperty(`--${key}`, value)
  }
}

// ── Persistence locale (pour chargement instantane) ─────────────────────────

const STORAGE_KEY = 'grand-duc-theme'

function saveLocal() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    presetId: state.presetId,
    customColors: state.customColors,
  }))
}

function loadLocal() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return false
    const data = JSON.parse(raw)
    if (data.presetId) state.presetId = data.presetId
    state.customColors = data.customColors || null
    return true
  } catch { return false }
}

// ── API sync ────────────────────────────────────────────────────────────────

async function loadFromServer() {
  try {
    const { data } = await settingsApi.getTheme()
    if (data.theme) {
      state.presetId = data.theme.presetId || 'grand-duc'
      state.customColors = data.theme.customColors || null
      saveLocal()
      applyToDOM(activeColors())
    }
  } catch { /* ignore — pas de colonne theme encore */ }
  state.loaded = true
}

async function saveToServer() {
  saveLocal()
  applyToDOM(activeColors())
  try {
    await settingsApi.setTheme({
      presetId: state.presetId,
      customColors: state.customColors,
    })
  } catch { /* silencieux */ }
}

// ── Composable public ───────────────────────────────────────────────────────

export function useTheme() {
  return {
    state,
    PRESETS,
    COLOR_LABELS,

    /** Initialise le theme (appele une fois au montage de l'app) */
    init() {
      loadLocal()
      applyToDOM(activeColors())
    },

    /** Charge depuis le serveur (apres login) */
    loadFromServer,

    /** Selectionne un preset et sauvegarde */
    selectPreset(presetId) {
      state.presetId = presetId
      state.customColors = null
      saveToServer()
    },

    /** Met a jour une couleur custom */
    setColor(key, value) {
      if (!state.customColors) {
        state.customColors = {}
      }
      state.customColors[key] = value
      applyToDOM(activeColors())
      // La sauvegarde serveur se fera au clic "Enregistrer" pour eviter du spam
      saveLocal()
    },

    /** Sauvegarde les couleurs custom sur le serveur */
    saveCustom() {
      return saveToServer()
    },

    /** Reset les customisations (retour au preset pur) */
    resetCustom() {
      state.customColors = null
      saveToServer()
    },

    /** Couleurs actuellement actives */
    activeColors,

    /** Couleurs du preset de base (sans custom) */
    presetColors() {
      return { ...getPreset(state.presetId).colors }
    },
  }
}
