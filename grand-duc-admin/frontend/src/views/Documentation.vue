<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Documentation</h1>
      <span style="color:var(--text-muted);font-size:13px">Guide de configuration du proxy Grand-Duc</span>
    </div>

    <div style="display:grid;grid-template-columns:220px 1fr;gap:24px;align-items:start">

      <!-- Sommaire -->
      <div class="card" style="position:sticky;top:20px;padding:16px">
        <div style="font-size:12px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">Sommaire</div>
        <nav style="display:flex;flex-direction:column;gap:2px">
          <a v-for="s in sections" :key="s.id" :href="'#'+s.id"
            style="font-size:13px;padding:5px 8px;border-radius:6px;color:var(--text-muted);text-decoration:none;transition:background .1s;display:flex;align-items:center;gap:7px"
            @mouseover="e => e.currentTarget.style.background='var(--surface2)'"
            @mouseout="e => e.currentTarget.style.background=''"
          >
            <span class="nav-icon" v-html="s.icon"></span>
            {{ s.label }}
          </a>
        </nav>
      </div>

      <!-- Contenu -->
      <div style="display:flex;flex-direction:column;gap:20px">

        <!-- ── Vue d'ensemble ─────────────────────────────────── -->
        <section class="card" id="overview">
          <h2 class="doc-title">Vue d'ensemble</h2>
          <p class="doc-p">Grand-Duc est un proxy HTTP/HTTPS qui filtre le trafic réseau selon des règles configurables. Il intercepte toutes les connexions et décide, pour chaque requête, si elle doit être <span class="badge badge-block">bloquée</span> ou <span class="badge badge-allow">autorisée</span>.</p>

          <div class="doc-schema">
            <div class="schema-box schema-client">Navigateur</div>
            <div class="schema-arrow">→</div>
            <div class="schema-box schema-proxy">Proxy Grand-Duc<br><small>évalue les règles</small></div>
            <div class="schema-arrow">→ autorisé →</div>
            <div class="schema-box schema-inet">Internet</div>
            <br style="flex-basis:100%">
            <div style="flex:1"></div>
            <div style="flex:1"></div>
            <div style="text-align:center;color:var(--red);font-size:12px;margin-top:4px">↓ bloqué ↓<br>Page de blocage</div>
          </div>

          <div class="doc-info">
            <strong>Interception HTTPS :</strong> le proxy déchiffre et réchiffre le trafic HTTPS via une autorité de certification (CA) locale. Le certificat <code>grand-duc-ca.crt</code> doit être installé sur chaque poste client.
          </div>
        </section>

        <!-- ── Règles globales ─────────────────────────────────── -->
        <section class="card" id="rules">
          <h2 class="doc-title">Règles globales</h2>
          <p class="doc-p">Les règles globales sont la base du filtrage. Chaque règle définit :</p>
          <ul class="doc-list">
            <li><strong>Pattern (regex)</strong> — expression régulière testée contre l'URL complète de la requête</li>
            <li><strong>Action</strong> — <span class="badge badge-block">bloqué</span> ou <span class="badge badge-allow">autorisé</span></li>
            <li><strong>Priorité</strong> — ordre d'évaluation (plus petit = testé en premier)</li>
            <li><strong>Activée</strong> — une règle désactivée est ignorée par le proxy</li>
          </ul>

          <div class="doc-info">
            <strong>Ordre d'évaluation :</strong> les règles sont testées dans l'ordre de priorité croissant. La <strong>première règle qui correspond</strong> à l'URL est appliquée, les suivantes sont ignorées.
          </div>

          <h3 class="doc-subtitle">Syntaxe regex courante</h3>
          <table class="doc-table">
            <thead><tr><th>Pattern</th><th>Correspond à</th></tr></thead>
            <tbody>
              <tr><td><code>youtube\.com</code></td><td>Toute URL contenant <em>youtube.com</em></td></tr>
              <tr><td><code>.*</code></td><td>Toute URL (joker universel)</td></tr>
              <tr><td><code>^https://ads\.</code></td><td>URLs commençant par <em>https://ads.</em></td></tr>
              <tr><td><code>\.(mp4|avi|mkv)</code></td><td>URLs se terminant par ces extensions</td></tr>
              <tr><td><code>social\.(facebook|instagram|twitter)\.com</code></td><td>Sous-domaines social de ces réseaux</td></tr>
            </tbody>
          </table>

          <div class="doc-warning">
            Les points <code>.</code> dans les noms de domaine doivent être échappés avec <code>\.</code>, sinon ils correspondent à n'importe quel caractère.
          </div>
        </section>

        <!-- ── Groupes ─────────────────────────────────────────── -->
        <section class="card" id="groups">
          <h2 class="doc-title">Groupes de clients</h2>
          <p class="doc-p">Un groupe est un ensemble de postes clients (identifiés par leur adresse IP) auquel on applique une sélection de règles. Les groupes permettent d'avoir des politiques différentes selon les utilisateurs.</p>

          <p class="doc-p">Dans un groupe, chaque règle activée s'applique avec la <strong>même action</strong> que la règle globale. Activer une règle dans un groupe signifie : "cette règle s'applique aux membres de ce groupe".</p>

          <table class="doc-table">
            <thead><tr><th>Règle globale</th><th>Activée dans le groupe ?</th><th>Résultat pour le groupe</th></tr></thead>
            <tbody>
              <tr><td><code>youtube.com</code> → <span class="badge badge-block">bloqué</span></td><td>Oui</td><td><span class="badge badge-block">bloqué</span> pour ce groupe</td></tr>
              <tr><td><code>youtube.com</code> → <span class="badge badge-block">bloqué</span></td><td>Non</td><td><span class="badge badge-allow">autorisé</span> (règle ignorée pour ce groupe)</td></tr>
              <tr><td><code>.*</code> → <span class="badge badge-allow">autorisé</span></td><td>Oui</td><td><span class="badge badge-allow">autorisé</span> pour ce groupe</td></tr>
            </tbody>
          </table>

          <div class="doc-info">
            <strong>Si aucune règle du groupe ne correspond</strong> à une URL, l'accès est autorisé pour les membres de ce groupe. Les règles non activées dans le groupe sont simplement ignorées.
          </div>

          <div class="doc-info">
            <strong>Un utilisateur peut appartenir à plusieurs groupes.</strong> Si plusieurs groupes ont une règle pour la même URL, le premier groupe correspondant gagne.
          </div>
        </section>

        <!-- ── Groupe par défaut ───────────────────────────────── -->
        <section class="card" id="default-group">
          <h2 class="doc-title">Groupe par défaut</h2>
          <p class="doc-p">Le groupe <strong>Défaut</strong> est un groupe spécial appliqué automatiquement à :</p>
          <ul class="doc-list">
            <li>Tout utilisateur enregistré <strong>sans groupe explicite</strong></li>
            <li>Toute IP <strong>inconnue</strong> (non enregistrée dans le système)</li>
          </ul>

          <div class="doc-info">
            Contrairement aux autres groupes, les règles du groupe Défaut utilisent l'<strong>action de la règle globale</strong> (pas l'inverse). Activer une règle de blocage dans le groupe Défaut bloque effectivement cette URL pour tous les utilisateurs sans groupe.
          </div>

          <div class="doc-warning">
            Le groupe Défaut <strong>ne peut pas être supprimé</strong>. Si un utilisateur rejoint un groupe explicite, le groupe Défaut ne lui est plus appliqué.
          </div>
        </section>

        <!-- ── Priorités ───────────────────────────────────────── -->
        <section class="card" id="priority">
          <h2 class="doc-title">Ordre de priorité du proxy</h2>
          <p class="doc-p">Pour chaque requête, le proxy applique les règles dans cet ordre :</p>

          <div style="display:flex;flex-direction:column;gap:10px;margin:16px 0">
            <div class="priority-step">
              <div class="priority-num">1</div>
              <div>
                <strong>Groupes explicites de l'utilisateur</strong><br>
                <span style="font-size:12px;color:var(--text-muted)">Si l'utilisateur est dans un ou plusieurs groupes, leurs règles s'appliquent. Si aucun groupe ne couvre cette URL → <span class="badge badge-allow" style="font-size:10px">autorisé</span>.</span>
              </div>
            </div>
            <div class="priority-step">
              <div class="priority-num">2</div>
              <div>
                <strong>Groupe par défaut</strong><br>
                <span style="font-size:12px;color:var(--text-muted)">Si l'utilisateur n'a aucun groupe (ou IP inconnue), les règles du groupe Défaut s'appliquent avec l'action globale. Si la règle n'est pas dans le groupe Défaut → <span class="badge badge-allow" style="font-size:10px">autorisé</span>.</span>
              </div>
            </div>
            <div class="priority-step">
              <div class="priority-num">3</div>
              <div>
                <strong>Règle globale</strong><br>
                <span style="font-size:12px;color:var(--text-muted)">Uniquement si aucun groupe par défaut n'est configuré. L'action de la règle globale s'applique directement.</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ── Cas d'exemple ──────────────────────────────────── -->
        <section class="card" id="examples">
          <h2 class="doc-title">Cas d'exemples</h2>

          <!-- Exemple 1 -->
          <h3 class="doc-subtitle">Exemple 1 — Bloquer tout par défaut, libérer un groupe</h3>
          <p class="doc-p">Objectif : bloquer tout internet pour tous, sauf le groupe "Professeurs" qui accède librement.</p>

          <div class="doc-example">
            <div class="example-step">
              <span class="example-badge">1</span>
              Créer la règle globale <code>.*</code> → <span class="badge badge-block">bloqué</span>, priorité 100
            </div>
            <div class="example-step">
              <span class="example-badge">2</span>
              Dans le groupe <strong>Défaut</strong>, activer la règle <code>.*</code> → tout le monde sans groupe est bloqué
            </div>
            <div class="example-step">
              <span class="example-badge">3</span>
              Créer le groupe "Professeurs", y ajouter leurs IPs — <strong>ne pas activer de règle dedans</strong>
            </div>
          </div>

          <table class="doc-table" style="margin-top:12px">
            <thead><tr><th>Utilisateur</th><th>Groupe</th><th>Résultat</th></tr></thead>
            <tbody>
              <tr><td>Marie (IP inconnue)</td><td>Défaut</td><td><span class="badge badge-block">bloqué</span></td></tr>
              <tr><td>Jean (sans groupe)</td><td>Défaut</td><td><span class="badge badge-block">bloqué</span></td></tr>
              <tr><td>Paul (Professeurs)</td><td>Professeurs</td><td><span class="badge badge-allow">autorisé</span> — aucune règle active dans son groupe</td></tr>
            </tbody>
          </table>

          <!-- Exemple 2 -->
          <h3 class="doc-subtitle" style="margin-top:24px">Exemple 2 — Accès libre, restrictions par groupe</h3>
          <p class="doc-p">Objectif : internet libre pour tous, mais les "Élèves" ne peuvent pas accéder aux réseaux sociaux ni à YouTube.</p>

          <div class="doc-example">
            <div class="example-step">
              <span class="example-badge">1</span>
              Créer les règles globales :<br>
              &nbsp;&nbsp;• <code>youtube\.com</code> → <span class="badge badge-block">bloqué</span>, priorité 10<br>
              &nbsp;&nbsp;• <code>(facebook|instagram|tiktok)\.com</code> → <span class="badge badge-block">bloqué</span>, priorité 20
            </div>
            <div class="example-step">
              <span class="example-badge">2</span>
              Ne rien activer dans le groupe Défaut → les inconnus ne sont pas affectés par ces règles
            </div>
            <div class="example-step">
              <span class="example-badge">3</span>
              Créer le groupe "Élèves", y ajouter leurs IPs
            </div>
            <div class="example-step">
              <span class="example-badge">4</span>
              Dans le groupe "Élèves", activer les deux règles → YouTube et réseaux sociaux bloqués pour les élèves
            </div>
          </div>

          <table class="doc-table" style="margin-top:12px">
            <thead><tr><th>Utilisateur</th><th>URL</th><th>Résultat</th></tr></thead>
            <tbody>
              <tr><td>Élève (groupe Élèves)</td><td>youtube.com</td><td><span class="badge badge-block">bloqué</span></td></tr>
              <tr><td>Élève (groupe Élèves)</td><td>wikipedia.org</td><td><span class="badge badge-allow">autorisé</span> (règle non activée dans le groupe)</td></tr>
              <tr><td>Professeur (sans groupe)</td><td>youtube.com</td><td><span class="badge badge-allow">autorisé</span> (groupe Défaut sans règle YouTube)</td></tr>
            </tbody>
          </table>

          <!-- Exemple 3 -->
          <h3 class="doc-subtitle" style="margin-top:24px">Exemple 3 — Liste blanche stricte</h3>
          <p class="doc-p">Objectif : bloquer tout internet sauf une liste de sites autorisés pour tout le monde.</p>

          <div class="doc-example">
            <div class="example-step">
              <span class="example-badge">1</span>
              Créer les règles globales pour les sites autorisés :<br>
              &nbsp;&nbsp;• <code>wikipedia\.org</code> → <span class="badge badge-allow">autorisé</span>, priorité 10<br>
              &nbsp;&nbsp;• <code>education\.gouv\.fr</code> → <span class="badge badge-allow">autorisé</span>, priorité 20<br>
              &nbsp;&nbsp;• <code>.*</code> → <span class="badge badge-block">bloqué</span>, priorité 999
            </div>
            <div class="example-step">
              <span class="example-badge">2</span>
              Dans le groupe Défaut, activer toutes ces règles → les sites autorisés restent <span class="badge badge-allow">autorisés</span>, le reste est <span class="badge badge-block">bloqué</span>
            </div>
          </div>

          <div class="doc-info" style="margin-top:12px">
            <strong>Astuce :</strong> la règle <code>.*</code> à priorité 999 sert de "filet" final. Les règles avec une priorité plus petite (10, 20…) sont évaluées avant et autorisent les exceptions.
          </div>
        </section>

        <!-- ── Test d'accès ───────────────────────────────────── -->
        <section class="card" id="test">
          <h2 class="doc-title">Tester une configuration</h2>
          <p class="doc-p">La page <strong>Test d'accès</strong> permet de simuler le filtrage sans avoir à passer par le proxy. Elle reproduit exactement la logique d'évaluation des règles.</p>
          <ul class="doc-list">
            <li>Sélectionner un utilisateur client</li>
            <li>Entrer une URL à tester</li>
            <li>Le résultat indique si la requête serait bloquée ou autorisée, et quelle règle a déclenché la décision</li>
          </ul>
          <div class="doc-info">
            Utiliser le test d'accès avant de déployer une nouvelle configuration pour valider que les règles se comportent comme attendu.
          </div>
        </section>

        <!-- ── Gestion des utilisateurs ───────────────────────── -->
        <section class="card" id="users">
          <h2 class="doc-title">Gestion des utilisateurs clients</h2>
          <p class="doc-p">Les utilisateurs clients sont identifiés par leur <strong>adresse IP</strong>. Le proxy enregistre automatiquement l'IP de chaque machine qui passe par lui.</p>
          <ul class="doc-list">
            <li><strong>Label</strong> — nom affiché dans les journaux et le test d'accès (ex : "PC-Marie", "Salle-Info-01")</li>
            <li><strong>Groupes</strong> — un utilisateur peut être dans zéro, un ou plusieurs groupes</li>
            <li>Sans groupe → groupe Défaut appliqué</li>
          </ul>
          <div class="doc-warning">
            Si l'adresse IP d'un poste change (DHCP), l'entrée ne sera plus associée à ce poste. Préférer des adresses IP statiques ou des baux DHCP fixes pour les postes gérés.
          </div>
        </section>

      </div>
    </div>
  </div>
</template>

<script setup>
const sections = [
  {
    id: 'overview', label: "Vue d'ensemble",
    icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`,
  },
  {
    id: 'rules', label: 'Règles globales',
    icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>`,
  },
  {
    id: 'groups', label: 'Groupes',
    icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
  },
  {
    id: 'default-group', label: 'Groupe par défaut',
    icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
  },
  {
    id: 'priority', label: 'Ordre de priorité',
    icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="14" y2="12"/><line x1="4" y1="18" x2="8" y2="18"/></svg>`,
  },
  {
    id: 'examples', label: 'Exemples',
    icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
  },
  {
    id: 'test', label: "Test d'accès",
    icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>`,
  },
  {
    id: 'users', label: 'Utilisateurs clients',
    icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`,
  },
]
</script>

<style scoped>
.doc-title {
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 12px;
  color: var(--text);
}
.doc-subtitle {
  font-size: 14px;
  font-weight: 600;
  margin: 18px 0 8px;
  color: var(--text);
}
.doc-p {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text);
  margin: 0 0 10px;
}
.doc-list {
  font-size: 13px;
  line-height: 1.9;
  color: var(--text);
  margin: 0 0 10px;
  padding-left: 20px;
}
.doc-info {
  background: rgba(88,166,255,.08);
  border-left: 3px solid var(--blue);
  border-radius: 0 6px 6px 0;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--text);
  margin: 12px 0;
  line-height: 1.6;
}
.doc-warning {
  background: rgba(255,165,0,.08);
  border-left: 3px solid var(--yellow, #f0a500);
  border-radius: 0 6px 6px 0;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--text);
  margin: 12px 0;
  line-height: 1.6;
}
.doc-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin: 10px 0;
}
.doc-table th {
  text-align: left;
  padding: 8px 12px;
  background: var(--surface2);
  color: var(--text-muted);
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .04em;
}
.doc-table td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
  line-height: 1.5;
}
.doc-table code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  background: var(--surface2);
  padding: 2px 5px;
  border-radius: 3px;
}
code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  background: var(--surface2);
  padding: 2px 5px;
  border-radius: 3px;
}
.doc-schema {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin: 16px 0;
  padding: 16px;
  background: var(--surface2);
  border-radius: 8px;
}
.schema-box {
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  text-align: center;
  line-height: 1.4;
}
.schema-client { background: rgba(88,166,255,.15); color: var(--blue); }
.schema-proxy  { background: rgba(255,165,0,.15); color: var(--yellow, #f0a500); }
.schema-inet   { background: rgba(63,185,80,.15); color: var(--green); }
.schema-arrow  { font-size: 13px; color: var(--text-muted); }
.priority-step {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 12px 14px;
  background: var(--surface2);
  border-radius: 8px;
}
.priority-num {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.doc-example {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 10px 0;
}
.example-step {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  font-size: 13px;
  line-height: 1.6;
  padding: 8px 12px;
  background: var(--surface2);
  border-radius: 6px;
}
.nav-icon {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  opacity: .7;
}
.example-badge {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--border);
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}
</style>
