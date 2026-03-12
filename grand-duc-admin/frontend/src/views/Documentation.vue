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
            :class="['toc-link', { 'toc-active': activeSection === s.id }]"
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

        <!-- ── Exceptions TLS ──────────────────────────────────── -->
        <section class="card" id="tls-bypass">
          <h2 class="doc-title">Exceptions TLS</h2>
          <p class="doc-p">Certains sites ou services ne fonctionnent pas correctement lorsque leur trafic HTTPS est intercepté (applications bancaires, VPN, logiciels avec certificat épinglé…). La page <strong>Exceptions</strong> permet de déclarer les hôtes qui ne doivent <strong>pas être filtrés</strong> par le proxy.</p>

          <ul class="doc-list">
            <li><strong>Hôte</strong> — le nom de domaine à exclure (ex : <code>discord.com</code>)</li>
            <li><strong>Sous-domaines inclus</strong> — l'ajout de <code>discord.com</code> exclut aussi automatiquement <code>*.discord.com</code></li>
            <li><strong>Rechargement</strong> — le proxy recharge cette liste toutes les 5 minutes</li>
          </ul>

          <div class="doc-info">
            <strong>Quand ajouter une exception ?</strong> Quand un site fonctionne normalement sans le proxy mais affiche des erreurs de certificat ou refuse de se charger à travers le proxy.
          </div>
        </section>

        <!-- ── Certificats CA ──────────────────────────────────── -->
        <section class="card" id="certificates">
          <h2 class="doc-title">Certificats CA</h2>
          <p class="doc-p">Le proxy utilise une <strong>autorité de certification (CA) locale</strong> pour intercepter le trafic HTTPS. Le certificat CA doit être installé et approuvé sur chaque poste client.</p>

          <h3 class="doc-subtitle">Opérations disponibles</h3>
          <ul class="doc-list">
            <li><strong>Générer</strong> — créer un nouveau certificat CA auto-signé (remplace l'ancien)</li>
            <li><strong>Importer</strong> — uploader un certificat et sa clé privée existants (format PEM)</li>
            <li><strong>Télécharger</strong> — récupérer le fichier <code>grand-duc-ca.crt</code> pour l'installer sur les postes</li>
            <li><strong>Historique</strong> — consulter les précédents certificats générés ou importés</li>
          </ul>

          <div class="doc-warning">
            <strong>Après un changement de certificat</strong>, tous les postes clients doivent installer le nouveau CA. L'ancien certificat ne sera plus reconnu et les navigateurs afficheront des erreurs de sécurité.
          </div>

          <h3 class="doc-subtitle">Installation du certificat sur les postes</h3>
          <table class="doc-table">
            <thead><tr><th>Système</th><th>Méthode</th></tr></thead>
            <tbody>
              <tr><td>Windows</td><td>Double-clic sur le fichier <code>.crt</code> → Installer → Magasin « Autorités de certification racines de confiance »</td></tr>
              <tr><td>macOS</td><td>Double-clic → Trousseaux d'accès → Marquer comme « Toujours approuver »</td></tr>
              <tr><td>Linux / Firefox</td><td>Paramètres Firefox → Certificats → Importer → Cocher « Identifier les sites web »</td></tr>
              <tr><td>GPO (déploiement en masse)</td><td>Configuration ordinateur → Stratégies → Paramètres Windows → Sécurité → Autorités racines de confiance</td></tr>
            </tbody>
          </table>
        </section>

        <!-- ── Killswitch ──────────────────────────────────────── -->
        <section class="card" id="killswitch">
          <h2 class="doc-title">Killswitch</h2>
          <p class="doc-p">Le killswitch est un <strong>interrupteur d'urgence</strong> qui désactive instantanément tout le filtrage du proxy. Quand il est activé, toutes les requêtes sont autorisées sans vérification des règles.</p>

          <ul class="doc-list">
            <li><strong>Activation</strong> — nécessite une confirmation par mot de passe administrateur</li>
            <li><strong>Désactivation</strong> — rétablit immédiatement le filtrage normal</li>
            <li><strong>Historique</strong> — chaque activation/désactivation est enregistrée avec la date, l'heure et l'utilisateur</li>
          </ul>

          <div class="doc-warning">
            <strong>Usage</strong> : le killswitch est prévu pour les situations d'urgence (ex : un blocage empêche l'accès à un outil critique). Il ne doit pas être utilisé comme méthode de gestion courante.
          </div>
        </section>

        <!-- ── Contrôle du proxy ───────────────────────────────── -->
        <section class="card" id="proxy-control">
          <h2 class="doc-title">Contrôle du proxy</h2>
          <p class="doc-p">La page <strong>Logs proxy</strong> affiche en temps réel le flux de sortie du processus proxy (connexion SSE). Elle permet de diagnostiquer les problèmes de connectivité ou de configuration.</p>

          <h3 class="doc-subtitle">Fonctionnalités</h3>
          <ul class="doc-list">
            <li><strong>Logs en direct</strong> — flux continu des événements du proxy (connexions, blocages, erreurs)</li>
            <li><strong>Statut</strong> — état actuel du processus proxy (en cours, arrêté, PID)</li>
            <li><strong>Redémarrage</strong> — arrêter puis relancer le processus proxy. Utile après un changement de certificat CA ou de configuration réseau</li>
          </ul>

          <div class="doc-info">
            <strong>Quand redémarrer ?</strong> Après l'import ou la génération d'un nouveau certificat CA, ou si le proxy ne répond plus. Les changements de règles et d'exceptions TLS sont rechargés automatiquement (pas besoin de redémarrer).
          </div>
        </section>

        <!-- ── Comptes et rôles ────────────────────────────────── -->
        <section class="card" id="accounts">
          <h2 class="doc-title">Comptes et rôles</h2>
          <p class="doc-p">L'interface d'administration est protégée par un système de <strong>comptes avec rôles et permissions granulaires</strong>. Chaque compte est associé à un rôle qui détermine précisément les pages et actions accessibles.</p>

          <h3 class="doc-subtitle">Rôles prédéfinis</h3>
          <table class="doc-table">
            <thead><tr><th>Rôle</th><th>Type</th><th>Description</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>Administrateur</strong></td>
                <td><span class="badge badge-on" style="font-size:10px">Système</span></td>
                <td>Accès complet à toutes les fonctionnalités. Ce rôle ne peut être ni supprimé, ni modifié.</td>
              </tr>
              <tr>
                <td><strong>Lecteur</strong></td>
                <td><span class="badge badge-on" style="font-size:10px">Système</span></td>
                <td>Consultation en lecture seule de toutes les pages. Aucune possibilité de créer, modifier ou supprimer quoi que ce soit.</td>
              </tr>
            </tbody>
          </table>

          <h3 class="doc-subtitle">Rôles personnalisés</h3>
          <p class="doc-p">Depuis la page <strong>Rôles</strong>, vous pouvez créer des rôles sur mesure en combinant les permissions par section :</p>

          <table class="doc-table">
            <thead><tr><th>Section</th><th>Permissions disponibles</th></tr></thead>
            <tbody>
              <tr><td>Monitoring</td><td>Tableau de bord, Journaux d'accès, Logs proxy</td></tr>
              <tr><td>Filtrage</td><td>Règles (lecture/écriture), Groupes, Utilisateurs clients, Test d'accès</td></tr>
              <tr><td>Administration</td><td>Exceptions TLS, Certificats CA, Killswitch, Comptes, Rôles, Contrôle proxy</td></tr>
              <tr><td>Paramètres</td><td>Configuration SMTP, Intégrations RMM</td></tr>
            </tbody>
          </table>

          <p class="doc-p">Chaque fonctionnalité propose typiquement deux niveaux de permission :</p>
          <ul class="doc-list">
            <li><strong>Lecture</strong> — voir la page et ses données</li>
            <li><strong>Écriture</strong> — créer, modifier, supprimer des éléments</li>
          </ul>

          <div class="doc-info">
            <strong>Visibilité de la sidebar :</strong> les liens de navigation ne s'affichent que si l'utilisateur a la permission de lecture correspondante. Une tentative d'accès direct par URL est redirigée vers le tableau de bord.
          </div>

          <div class="doc-warning">
            <strong>Protection anti-lockout :</strong> le rôle Administrateur ne peut pas être supprimé ou privé de permissions. Au moins un compte doit toujours avoir ce rôle pour éviter de perdre l'accès à l'interface.
          </div>
        </section>

        <!-- ── Notifications ───────────────────────────────────── -->
        <section class="card" id="notifications">
          <h2 class="doc-title">Notifications par email</h2>
          <p class="doc-p">Grand-Duc peut envoyer des alertes par email lors d'événements importants. La configuration se fait en deux étapes : <strong>configurer le serveur SMTP</strong>, puis <strong>choisir ses alertes personnelles</strong>.</p>

          <h3 class="doc-subtitle">1. Configuration SMTP</h3>
          <p class="doc-p">Accessible depuis <strong>Paramètres → Configuration SMTP</strong> (nécessite la permission correspondante). Renseignez les informations de votre serveur de messagerie :</p>
          <ul class="doc-list">
            <li><strong>Serveur / Port</strong> — adresse et port du serveur SMTP (ex : <code>smtp.gmail.com:587</code>)</li>
            <li><strong>Identifiants</strong> — nom d'utilisateur et mot de passe du compte d'envoi</li>
            <li><strong>Adresse expéditeur</strong> — le champ « From » des emails envoyés</li>
            <li><strong>STARTTLS</strong> — activer le chiffrement (recommandé)</li>
          </ul>
          <div class="doc-info">
            Utilisez le bouton <strong>Tester</strong> pour envoyer un email de vérification à une adresse de votre choix avant de valider la configuration.
          </div>

          <h3 class="doc-subtitle">2. Préférences personnelles</h3>
          <p class="doc-p">Chaque utilisateur configure ses propres alertes depuis <strong>Paramètres → Mes notifications</strong> (aucune permission spéciale requise). Événements disponibles :</p>

          <table class="doc-table">
            <thead><tr><th>Événement</th><th>Description</th></tr></thead>
            <tbody>
              <tr><td>Certificat CA</td><td>Génération ou import d'un nouveau certificat</td></tr>
              <tr><td>Redémarrage proxy</td><td>Redémarrage du proxy via l'interface</td></tr>
              <tr><td>Killswitch</td><td>Activation ou désactivation du killswitch</td></tr>
              <tr><td>Nouveau compte</td><td>Création d'un compte administrateur</td></tr>
              <tr><td>Règle déclenchée</td><td>Une règle surveillée est déclenchée (vérification toutes les 5 min)</td></tr>
              <tr><td>Erreur sync RMM</td><td>Échec d'une synchronisation avec un RMM</td></tr>
            </tbody>
          </table>

          <h3 class="doc-subtitle">3. Surveillance de règles</h3>
          <p class="doc-p">Dans la section <strong>Règles à surveiller</strong>, vous pouvez sélectionner des règles de filtrage individuelles. Si une de ces règles est déclenchée dans les journaux d'accès, vous recevez un email d'alerte.</p>
          <div class="doc-warning">
            La surveillance de règles nécessite d'activer l'événement « Règle de filtrage déclenchée » dans les préférences ci-dessus. Le compte doit aussi avoir une adresse email configurée.
          </div>
        </section>

        <!-- ── Intégrations RMM ────────────────────────────────── -->
        <section class="card" id="rmm">
          <h2 class="doc-title">Intégrations RMM</h2>
          <p class="doc-p">Grand-Duc peut se synchroniser avec vos outils de gestion de parc (RMM) pour importer automatiquement les postes clients et leurs adresses IP.</p>

          <h3 class="doc-subtitle">Plateformes supportées</h3>
          <table class="doc-table">
            <thead><tr><th>RMM</th><th>Authentification</th><th>Données importées</th></tr></thead>
            <tbody>
              <tr><td>Tactical RMM</td><td>Clé API</td><td>Nom de l'agent, IP interne</td></tr>
              <tr><td>NinjaRMM</td><td>Client ID + Client Secret (OAuth2)</td><td>Nom du device, IP</td></tr>
              <tr><td>Datto RMM</td><td>Clé API + Secret API</td><td>Nom du device, IP</td></tr>
              <tr><td>Atera</td><td>Clé API</td><td>Nom de la machine, IP</td></tr>
            </tbody>
          </table>

          <h3 class="doc-subtitle">Configuration</h3>
          <ul class="doc-list">
            <li><strong>URL de base</strong> — l'adresse de votre instance RMM (ex : <code>https://rmm.example.com</code>)</li>
            <li><strong>Clé / Secret API</strong> — identifiants générés depuis votre plateforme RMM</li>
            <li><strong>Intervalle de sync</strong> — fréquence de synchronisation automatique (5 à 1440 minutes)</li>
            <li><strong>Activer/Désactiver</strong> — la synchronisation automatique peut être coupée sans supprimer l'intégration</li>
          </ul>

          <div class="doc-info">
            <strong>Synchronisation manuelle :</strong> utilisez le bouton <strong>Sync</strong> pour déclencher immédiatement une synchronisation et voir le résultat (postes créés, mis à jour, ignorés).
          </div>

          <div class="doc-info">
            Les postes importés depuis un RMM sont créés comme <strong>utilisateurs clients</strong> classiques. Ils peuvent ensuite être ajoutés à des groupes comme tout autre utilisateur.
          </div>
        </section>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const activeSection = ref('overview')
let observer = null

onMounted(() => {
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          activeSection.value = entry.target.id
        }
      }
    },
    { rootMargin: '-10% 0px -80% 0px' }
  )
  sections.forEach(s => {
    const el = document.getElementById(s.id)
    if (el) observer.observe(el)
  })
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})

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
  {
    id: 'tls-bypass', label: 'Exceptions TLS',
    icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M4.93 4.93l14.14 14.14"/></svg>`,
  },
  {
    id: 'certificates', label: 'Certificats CA',
    icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`,
  },
  {
    id: 'killswitch', label: 'Killswitch',
    icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>`,
  },
  {
    id: 'proxy-control', label: 'Contrôle proxy',
    icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>`,
  },
  {
    id: 'accounts', label: 'Comptes et rôles',
    icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>`,
  },
  {
    id: 'notifications', label: 'Notifications',
    icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>`,
  },
  {
    id: 'rmm', label: 'Intégrations RMM',
    icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>`,
  },
]
</script>

<style scoped>
.toc-link {
  font-size: 13px;
  padding: 5px 8px;
  border-radius: 6px;
  color: var(--text-muted);
  text-decoration: none;
  transition: background .15s, color .15s;
  display: flex;
  align-items: center;
  gap: 7px;
}
.toc-link:hover {
  background: var(--surface2);
}
.toc-active {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  color: var(--accent);
}
.toc-active:hover {
  background: color-mix(in srgb, var(--accent) 18%, transparent);
}

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
