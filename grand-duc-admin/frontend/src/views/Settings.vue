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
    <div v-if="activeTab === 'smtp' && auth.hasPermission('settings.smtp.read')">

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

        <div v-if="auth.hasPermission('settings.smtp.write')" style="display:flex;gap:10px;margin-top:20px;flex-wrap:wrap">
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
        Votre compte n'a pas d'adresse email configurée. Les alertes ne pourront pas être envoyées.
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
            Préférences enregistrées
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
                  {{ r.pattern }} ({{ r.action }}){{ r.description ? ' — ' + r.description : '' }}
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
                  <div style="font-size:10px;color:var(--text-muted)">
                    {{ r.action }}{{ r.description ? ' — ' + r.description : '' }}
                  </div>
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

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- Onglet 3 : Apparence                                                  -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'appearance'">

      <!-- Themes predefinis -->
      <div style="margin-bottom:28px">
        <div style="font-size:15px;font-weight:700;margin-bottom:4px">Themes</div>
        <div style="font-size:12px;color:var(--text-muted);margin-bottom:16px">
          Choisissez un theme predefini. Les couleurs s'appliquent immediatement.
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px">
          <div
            v-for="preset in PRESETS" :key="preset.id"
            class="theme-card"
            :class="{ selected: theme.state.presetId === preset.id && !theme.state.customColors }"
            @click="theme.selectPreset(preset.id)"
          >
            <!-- Preview barre -->
            <div style="display:flex;gap:4px;margin-bottom:10px">
              <div :style="`width:100%;height:32px;border-radius:4px;background:${preset.colors.bg};border:1px solid ${preset.colors.border};display:flex;align-items:center;padding:0 8px;gap:6px`">
                <div :style="`width:8px;height:8px;border-radius:50%;background:${preset.colors.accent}`"></div>
                <div :style="`flex:1;height:4px;border-radius:2px;background:${preset.colors.surface2}`"></div>
              </div>
            </div>
            <!-- Couleurs preview -->
            <div style="display:flex;gap:3px;margin-bottom:8px">
              <div v-for="c in ['accent', 'green', 'blue', 'red', 'yellow']" :key="c"
                :style="`width:16px;height:16px;border-radius:50%;background:${preset.colors[c]}`"
              ></div>
            </div>
            <div style="font-size:13px;font-weight:600">{{ preset.name }}</div>
            <div style="font-size:11px;color:var(--text-muted)">{{ preset.description }}</div>
          </div>
        </div>
      </div>

      <!-- Personnalisation des couleurs -->
      <div class="card" style="max-width:680px;padding:24px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
          <div style="font-size:15px;font-weight:700">Personnaliser les couleurs</div>
          <div style="display:flex;gap:8px">
            <button v-if="theme.state.customColors" class="btn btn-ghost btn-sm" @click="theme.resetCustom()">
              Reinitialiser
            </button>
            <button v-if="theme.state.customColors" class="btn btn-primary btn-sm" @click="saveCustomColors" :disabled="themeSaving">
              {{ themeSaving ? 'Enregistrement...' : 'Enregistrer' }}
            </button>
          </div>
        </div>
        <div style="font-size:12px;color:var(--text-muted);margin-bottom:20px">
          Modifiez individuellement chaque couleur du theme actif. Cliquez sur un carre de couleur pour la changer.
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px">
          <div v-for="(label, key) in COLOR_LABELS" :key="key"
            style="display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--surface2)">
            <label :for="'color-'+key" style="display:flex;align-items:center;cursor:pointer">
              <input :id="'color-'+key" type="color"
                :value="currentColors[key]"
                @input="theme.setColor(key, $event.target.value)"
                style="width:32px;height:32px;border:2px solid var(--border);border-radius:6px;cursor:pointer;padding:0;background:transparent"
              />
            </label>
            <div style="flex:1;min-width:0">
              <div style="font-size:12px;font-weight:500">{{ label }}</div>
              <div style="font-size:11px;font-family:'JetBrains Mono',monospace;color:var(--text-muted)">
                {{ currentColors[key] }}
              </div>
            </div>
            <div v-if="theme.state.customColors?.[key]"
              style="font-size:10px;padding:1px 6px;border-radius:4px;background:rgba(240,136,62,.15);color:var(--accent)">
              modifie
            </div>
          </div>
        </div>

        <div v-if="themeSaved" style="margin-top:14px;font-size:12px;color:var(--green)">
          Theme personnalise enregistre.
        </div>
      </div>

    </div>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- Onglet 4 : Intégrations RMM (admin uniquement)                        -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'rmm' && auth.hasPermission('settings.rmm.read')">

      <!-- En-tête + bouton ajouter -->
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
        <div>
          <div style="font-size:15px;font-weight:700;margin-bottom:2px">Intégrations RMM</div>
          <div style="font-size:12px;color:var(--text-muted)">
            Synchronisation automatique des agents depuis vos outils de gestion (RMM).
          </div>
        </div>
        <button v-if="auth.hasPermission('settings.rmm.write')" class="btn btn-primary" @click="openCreate">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Ajouter
        </button>
      </div>

      <!-- Types supportés -->
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
        <div v-for="t in RMM_TYPES" :key="t.key"
          style="display:flex;align-items:center;gap:6px;padding:4px 10px;border-radius:6px;border:1px solid var(--border);font-size:11px;color:var(--text-muted)">
          <span :style="`color:${t.color}`">&#9679;</span> {{ t.label }}
        </div>
      </div>

      <!-- Tableau -->
      <div class="card" style="padding:0;overflow:hidden">
        <div v-if="rmmLoading" style="padding:32px;text-align:center;color:var(--text-muted)">Chargement…</div>
        <div v-else-if="integrations.length === 0"
          style="padding:40px;text-align:center;color:var(--text-muted);font-size:13px">
          Aucune intégration configurée. Ajoutez votre premier RMM.
        </div>
        <table v-else class="data-table" style="width:100%">
          <thead>
            <tr>
              <th>Nom</th>
              <th>Type</th>
              <th>URL</th>
              <th>Statut</th>
              <th>Dernière sync</th>
              <th v-if="auth.hasPermission('settings.rmm.write')" style="text-align:right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="intg in integrations" :key="intg.id">
              <td style="font-weight:500">{{ intg.name }}</td>
              <td>
                <span class="badge" :style="`background:${typeColor(intg.type)}22;color:${typeColor(intg.type)}`">
                  {{ typeLabel(intg.type) }}
                </span>
              </td>
              <td style="font-family:monospace;font-size:11px;color:var(--text-muted);max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                {{ intg.url }}
              </td>
              <td>
                <span v-if="!intg.enabled" class="badge badge-muted">Désactivé</span>
                <span v-else-if="intg.last_sync_status?.startsWith('OK')" class="badge badge-green">Actif</span>
                <span v-else-if="intg.last_sync_status?.startsWith('Erreur')" class="badge badge-red">Erreur</span>
                <span v-else class="badge badge-muted">En attente</span>
              </td>
              <td style="font-size:11px">
                <div v-if="intg.last_sync_at" style="display:flex;flex-direction:column;gap:2px">
                  <span>{{ fmtDate(intg.last_sync_at) }}</span>
                  <span style="color:var(--text-muted);font-size:10px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                    {{ intg.last_sync_status }}
                  </span>
                </div>
                <span v-else style="color:var(--text-muted)">Jamais</span>
              </td>
              <td v-if="auth.hasPermission('settings.rmm.write')" style="text-align:right;white-space:nowrap">
                <button class="btn" style="font-size:11px;padding:3px 9px;margin-right:4px"
                  :disabled="syncing === intg.id"
                  @click="doSync(intg)">
                  <svg v-if="syncing !== intg.id" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                  </svg>
                  <span v-else style="display:inline-block;width:10px;height:10px;border:2px solid currentColor;border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite"></span>
                  {{ syncing === intg.id ? 'Sync…' : 'Sync' }}
                </button>
                <button class="btn" style="font-size:11px;padding:3px 9px;margin-right:4px"
                  @click="openEdit(intg)">Modifier</button>
                <button class="btn" style="font-size:11px;padding:3px 9px;color:var(--red);border-color:var(--red)"
                  @click="confirmDelete(intg)">Supprimer</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Résultat de sync -->
      <transition name="fade">
        <div v-if="syncResult"
          :style="`margin-top:12px;padding:10px 14px;border-radius:6px;font-size:12px;border:1px solid;${
            syncResult.error
              ? 'background:rgba(248,81,73,.1);border-color:var(--red);color:var(--red)'
              : 'background:rgba(46,160,67,.1);border-color:var(--green);color:var(--green)'
          }`">
          <strong>{{ syncResult.error ? 'Erreur' : 'Synchronisation réussie' }}</strong>
          <span v-if="!syncResult.error"> — {{ syncResult.created }} créés, {{ syncResult.updated }} mis à jour, {{ syncResult.skipped }} ignorés{{ syncResult.groups_created ? `, ${syncResult.groups_created} groupes créés` : '' }}</span>
          <span v-else> — {{ syncResult.error }}</span>
        </div>
      </transition>

    </div>

    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <!-- Modals RMM : ajout / édition                                          -->
    <!-- ══════════════════════════════════════════════════════════════════════ -->
    <div v-if="showRmmModal"
      style="position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;z-index:1000"
      @click.self="showRmmModal = false">
      <div class="card" style="width:480px;max-width:95vw;padding:28px 24px;max-height:90vh;overflow-y:auto">
        <div style="font-size:16px;font-weight:700;margin-bottom:18px">
          {{ rmmEditing ? 'Modifier l\'intégration' : 'Nouvelle intégration RMM' }}
        </div>

        <div style="display:flex;flex-direction:column;gap:14px">

          <div>
            <label class="form-label">Nom <span style="color:var(--red)">*</span></label>
            <input v-model="rmmForm.name" class="form-input" placeholder="Mon RMM" />
          </div>

          <div>
            <label class="form-label">Type <span style="color:var(--red)">*</span></label>
            <select v-model="rmmForm.type" class="form-input" :disabled="!!rmmEditing">
              <option value="">— Choisir —</option>
              <option v-for="t in RMM_TYPES" :key="t.key" :value="t.key">{{ t.label }}</option>
            </select>
            <div v-if="rmmForm.type" style="margin-top:6px;font-size:11px;color:var(--text-muted)">
              {{ RMM_TYPES.find(t => t.key === rmmForm.type)?.hint }}
            </div>
          </div>

          <div>
            <label class="form-label">URL de base <span style="color:var(--red)">*</span></label>
            <input v-model="rmmForm.url" class="form-input" placeholder="https://rmm.example.com" />
          </div>

          <div>
            <label class="form-label">{{ rmmApiKeyLabel }} <span style="color:var(--red)">*</span></label>
            <input v-model="rmmForm.api_key" class="form-input" type="password"
              :placeholder="rmmApiKeyPlaceholder" autocomplete="new-password" />
          </div>

          <div v-if="rmmNeedsSecret">
            <label class="form-label">{{ rmmApiSecretLabel }} <span style="color:var(--red)">*</span></label>
            <input v-model="rmmForm.api_secret" class="form-input" type="password"
              :placeholder="'xxxxxxxxxxxxxxxxxxxx'" autocomplete="new-password" />
          </div>

          <div>
            <label class="form-label">Intervalle de synchronisation (minutes)</label>
            <input v-model.number="rmmForm.sync_interval_minutes" class="form-input" type="number" min="5" max="1440" />
          </div>

          <div>
            <label class="form-label">Auto-assignation aux groupes</label>
            <select v-model="rmmForm.auto_group_by" class="form-input">
              <option value="none">Désactivée</option>
              <option value="client">Par Client</option>
              <option value="site">Par Site</option>
              <option value="client_site">Par Client — Site</option>
            </select>
            <div style="margin-top:4px;font-size:11px;color:var(--text-muted)">
              <template v-if="rmmForm.auto_group_by === 'client'">Les agents seront assignés à un groupe portant le nom de leur Client RMM.</template>
              <template v-else-if="rmmForm.auto_group_by === 'site'">Les agents seront assignés à un groupe portant le nom de leur Site RMM.</template>
              <template v-else-if="rmmForm.auto_group_by === 'client_site'">Les agents seront assignés à un groupe « Client — Site ».</template>
              <template v-else>Les agents ne seront pas assignés automatiquement à des groupes.</template>
            </div>
          </div>

          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px">
            <input type="checkbox" v-model="rmmForm.enabled" />
            Activer la synchronisation automatique
          </label>

          <div v-if="rmmFormError"
            style="padding:8px 12px;border-radius:5px;background:rgba(248,81,73,.1);border:1px solid var(--red);color:var(--red);font-size:12px">
            {{ rmmFormError }}
          </div>
        </div>

        <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:22px">
          <button class="btn" @click="showRmmModal = false">Annuler</button>
          <button class="btn btn-primary" @click="saveIntegration" :disabled="rmmSaving">
            {{ rmmSaving ? 'Enregistrement…' : (rmmEditing ? 'Mettre à jour' : 'Créer') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Confirmation suppression RMM -->
    <div v-if="deleteTarget"
      style="position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;z-index:1000"
      @click.self="deleteTarget = null">
      <div class="card" style="width:400px;padding:26px 24px">
        <div style="font-size:16px;font-weight:700;margin-bottom:8px">Supprimer l'intégration ?</div>
        <div style="font-size:13px;color:var(--text-muted);margin-bottom:20px;line-height:1.5">
          L'intégration <strong>{{ deleteTarget.name }}</strong> sera supprimée. Les utilisateurs clients importés depuis ce RMM ne seront pas supprimés, mais perdront leur lien.
        </div>
        <div style="display:flex;gap:10px;justify-content:flex-end">
          <button class="btn" @click="deleteTarget = null">Annuler</button>
          <button class="btn" style="background:var(--red);color:#fff;border-color:var(--red)"
            @click="doDelete">Supprimer</button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { settingsApi, integrationsApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useTheme, PRESETS, COLOR_LABELS } from '@/composables/useTheme'

const auth = useAuthStore()
const theme = useTheme()

// ── Onglets ───────────────────────────────────────────────────────────────────
const tabs = computed(() => {
  const t = [{ key: 'notifications', label: 'Mes notifications' }]
  if (auth.hasPermission('settings.smtp.read')) {
    t.unshift({ key: 'smtp', label: 'Configuration SMTP' })
  }
  t.push({ key: 'appearance', label: 'Apparence' })
  if (auth.hasPermission('settings.rmm.read')) {
    t.push({ key: 'rmm', label: 'Intégrations RMM' })
  }
  return t
})
const activeTab = ref(auth.hasPermission('settings.smtp.read') ? 'smtp' : 'notifications')

// ══════════════════════════════════════════════════════════════════════════════
// SMTP
// ══════════════════════════════════════════════════════════════════════════════
const smtp = ref({ host: '', port: 587, user: '', password: '', from_: '', tls: true })
const smtpSaving = ref(false)
const smtpMsg    = ref(null)
const testEmail  = ref('')
const testSending = ref(false)

async function loadSmtp() {
  if (!auth.hasPermission('settings.smtp.read')) return
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

// ══════════════════════════════════════════════════════════════════════════════
// Notifications
// ══════════════════════════════════════════════════════════════════════════════
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

// ══════════════════════════════════════════════════════════════════════════════
// Apparence
// ══════════════════════════════════════════════════════════════════════════════
const currentColors = computed(() => theme.activeColors())
const themeSaving   = ref(false)
const themeSaved    = ref(false)

async function saveCustomColors() {
  themeSaving.value = true
  try {
    await theme.saveCustom()
    themeSaved.value = true
    setTimeout(() => { themeSaved.value = false }, 3000)
  } finally {
    themeSaving.value = false
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// Intégrations RMM
// ══════════════════════════════════════════════════════════════════════════════
const RMM_TYPES = [
  {
    key: 'tactical', label: 'Tactical RMM', color: '#58a6ff',
    hint: 'URL de votre instance Tactical RMM (ex : https://rmm.example.com). Clé API générée dans Paramètres > API.',
  },
  {
    key: 'ninja', label: 'NinjaRMM', color: '#7ee787',
    hint: 'URL de l\'API NinjaRMM (ex : https://app.ninjarmm.com). Client ID et Client Secret OAuth2.',
  },
  {
    key: 'datto', label: 'Datto RMM', color: '#e3b341',
    hint: 'URL de l\'API Datto (ex : https://zinfandel-api.centrastage.net). Clé et Secret API depuis Datto RMM > Setup > API.',
  },
  {
    key: 'atera', label: 'Atera', color: '#ff7b72',
    hint: 'URL https://app.atera.com. Clé API depuis Atera > Admin > API.',
  },
]

const integrations  = ref([])
const rmmLoading    = ref(true)
const showRmmModal  = ref(false)
const rmmEditing    = ref(null)
const rmmSaving     = ref(false)
const rmmFormError  = ref('')
const syncing       = ref(null)
const syncResult    = ref(null)
const deleteTarget  = ref(null)

const emptyRmmForm = () => ({
  name: '', type: '', url: '', api_key: '', api_secret: '',
  sync_interval_minutes: 60, auto_group_by: 'none', enabled: true,
})
const rmmForm = ref(emptyRmmForm())

const rmmNeedsSecret = computed(() => ['ninja', 'datto'].includes(rmmForm.value.type))

const rmmApiKeyLabel = computed(() => ({
  ninja: 'Client ID (OAuth2)',
  datto: 'Clé API publique',
}[rmmForm.value.type] ?? 'Clé API'))

const rmmApiKeyPlaceholder = computed(() => ({
  tactical: 'xxxxxxxxxxxxxxxxxxxxxxxx',
  ninja:    'ni_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
  datto:    'xxxxxxxxxxxxxxxxxxxxxxxx',
  atera:    'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
}[rmmForm.value.type] ?? ''))

const rmmApiSecretLabel = computed(() => rmmForm.value.type === 'ninja' ? 'Client Secret (OAuth2)' : 'Secret API')

function typeColor(type) {
  return RMM_TYPES.find(t => t.key === type)?.color ?? '#8b949e'
}
function typeLabel(type) {
  return RMM_TYPES.find(t => t.key === type)?.label ?? type
}
function fmtDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}

async function loadIntegrations() {
  if (!auth.hasPermission('settings.rmm.read')) return
  rmmLoading.value = true
  try {
    const { data } = await integrationsApi.list()
    integrations.value = data
  } finally {
    rmmLoading.value = false
  }
}

function openCreate() {
  rmmEditing.value  = null
  rmmForm.value     = emptyRmmForm()
  rmmFormError.value = ''
  showRmmModal.value = true
}

function openEdit(intg) {
  rmmEditing.value = intg
  rmmForm.value = {
    name:                  intg.name,
    type:                  intg.type,
    url:                   intg.url,
    api_key:               intg.api_key,
    api_secret:            intg.api_secret ?? '',
    sync_interval_minutes: intg.sync_interval_minutes,
    auto_group_by:         intg.auto_group_by ?? 'none',
    enabled:               intg.enabled,
  }
  rmmFormError.value = ''
  showRmmModal.value = true
}

async function saveIntegration() {
  rmmFormError.value = ''
  if (!rmmForm.value.name.trim())     { rmmFormError.value = 'Le nom est requis.'; return }
  if (!rmmForm.value.type)            { rmmFormError.value = 'Choisissez un type.'; return }
  if (!rmmForm.value.url.trim())      { rmmFormError.value = 'L\'URL est requise.'; return }
  if (!rmmForm.value.api_key.trim())  { rmmFormError.value = 'La clé API est requise.'; return }
  if (rmmNeedsSecret.value && !rmmForm.value.api_secret?.trim()) {
    rmmFormError.value = `${rmmApiSecretLabel.value} est requis pour ${typeLabel(rmmForm.value.type)}.`
    return
  }

  rmmSaving.value = true
  try {
    const payload = { ...rmmForm.value }
    if (!payload.api_secret) delete payload.api_secret

    if (rmmEditing.value) {
      const { data } = await integrationsApi.update(rmmEditing.value.id, payload)
      const idx = integrations.value.findIndex(i => i.id === rmmEditing.value.id)
      if (idx >= 0) integrations.value[idx] = data
    } else {
      const { data } = await integrationsApi.create(payload)
      integrations.value.push(data)
    }
    showRmmModal.value = false
  } catch (err) {
    rmmFormError.value = err.response?.data?.detail ?? 'Erreur lors de l\'enregistrement.'
  } finally {
    rmmSaving.value = false
  }
}

async function doSync(intg) {
  syncing.value    = intg.id
  syncResult.value = null
  try {
    const { data } = await integrationsApi.sync(intg.id)
    syncResult.value = data
    await loadIntegrations()
  } catch (err) {
    syncResult.value = { error: err.response?.data?.detail ?? 'Erreur de synchronisation.' }
  } finally {
    syncing.value = null
    setTimeout(() => { syncResult.value = null }, 8000)
  }
}

function confirmDelete(intg) {
  deleteTarget.value = intg
}

async function doDelete() {
  if (!deleteTarget.value) return
  await integrationsApi.delete(deleteTarget.value.id)
  integrations.value = integrations.value.filter(i => i.id !== deleteTarget.value.id)
  deleteTarget.value = null
}

// ── Init ──────────────────────────────────────────────────────────────────────
const loadedTabs = new Set()

async function loadTab(tab) {
  if (loadedTabs.has(tab)) return
  loadedTabs.add(tab)
  if (tab === 'smtp')          return loadSmtp()
  if (tab === 'notifications') return Promise.all([loadPrefs(), loadRules()])
  if (tab === 'appearance')    return                // theme deja charge globalement
  if (tab === 'rmm')           return loadIntegrations()
}

watch(activeTab, (tab) => loadTab(tab))

onMounted(() => loadTab(activeTab.value))
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

.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}
.badge-green  { background: rgba(46,160,67,.15); color: var(--green); }
.badge-red    { background: rgba(248,81,73,.15);  color: var(--red); }
.badge-muted  { background: rgba(139,148,158,.15); color: var(--text-muted); }

.theme-card {
  padding: 14px 16px;
  border-radius: 8px;
  border: 2px solid var(--border);
  background: var(--surface);
  cursor: pointer;
  transition: border-color .15s, transform .1s;
}
.theme-card:hover { border-color: var(--text-muted); transform: translateY(-1px); }
.theme-card.selected { border-color: var(--accent); background: var(--surface2); }

.fade-enter-active, .fade-leave-active { transition: opacity .3s; }
.fade-enter-from, .fade-leave-to       { opacity: 0; }

@keyframes spin { to { transform: rotate(360deg); } }
</style>
