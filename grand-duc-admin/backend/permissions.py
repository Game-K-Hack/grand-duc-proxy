# ── Permissions granulaires ────────────────────────────────────────────────────
# Chaque clé représente une action vérifiable sur une page / onglet / fonction.
# Convention : <section>.<action>   (read | write | use | restart)

ALL_PERMISSIONS: list[str] = [
    "dashboard.read",
    "rules.read",
    "rules.write",
    "logs.read",
    "proxy_logs.read",
    "client_groups.read",
    "client_groups.write",
    "client_users.read",
    "client_users.write",
    "test_access.use",
    "users.read",
    "users.write",
    "tls_bypass.read",
    "tls_bypass.write",
    "killswitch.read",
    "killswitch.write",
    "certificates.read",
    "certificates.write",
    "settings.smtp.read",
    "settings.smtp.write",
    "settings.templates.read",
    "settings.templates.write",
    "settings.appearance.read",
    "settings.appearance.write",
    "settings.rmm.read",
    "settings.rmm.write",
    "roles.read",
    "roles.write",
    "proxy.restart",
]

# ── Jeux de permissions pour les rôles built-in ──────────────────────────────

ADMIN_PERMISSIONS: dict[str, bool] = {p: True for p in ALL_PERMISSIONS}

VIEWER_PERMISSIONS: dict[str, bool] = {p: True for p in ALL_PERMISSIONS if p.endswith(".read")}

# ── Labels FR pour l'interface de gestion des rôles ──────────────────────────

PERMISSION_LABELS: dict[str, dict] = {
    "dashboard.read":        {"section": "Monitoring",      "feature": "Tableau de bord",       "action": "Lecture"},
    "logs.read":             {"section": "Monitoring",      "feature": "Journaux d'accès",      "action": "Lecture"},
    "proxy_logs.read":       {"section": "Monitoring",      "feature": "Logs proxy",            "action": "Lecture"},
    "rules.read":            {"section": "Filtrage",        "feature": "Règles",                "action": "Lecture"},
    "rules.write":           {"section": "Filtrage",        "feature": "Règles",                "action": "Écriture"},
    "client_groups.read":    {"section": "Filtrage",        "feature": "Groupes",               "action": "Lecture"},
    "client_groups.write":   {"section": "Filtrage",        "feature": "Groupes",               "action": "Écriture"},
    "client_users.read":     {"section": "Filtrage",        "feature": "Utilisateurs clients",  "action": "Lecture"},
    "client_users.write":    {"section": "Filtrage",        "feature": "Utilisateurs clients",  "action": "Écriture"},
    "test_access.use":       {"section": "Filtrage",        "feature": "Test d'accès",          "action": "Utiliser"},
    "tls_bypass.read":       {"section": "Administration",  "feature": "Exceptions TLS",        "action": "Lecture"},
    "tls_bypass.write":      {"section": "Administration",  "feature": "Exceptions TLS",        "action": "Écriture"},
    "certificates.read":     {"section": "Administration",  "feature": "Certificats CA",        "action": "Lecture"},
    "certificates.write":    {"section": "Administration",  "feature": "Certificats CA",        "action": "Écriture"},
    "killswitch.read":       {"section": "Administration",  "feature": "Killswitch",            "action": "Lecture"},
    "killswitch.write":      {"section": "Administration",  "feature": "Killswitch",            "action": "Écriture"},
    "users.read":            {"section": "Administration",  "feature": "Comptes",               "action": "Lecture"},
    "users.write":           {"section": "Administration",  "feature": "Comptes",               "action": "Écriture"},
    "roles.read":            {"section": "Administration",  "feature": "Rôles",                 "action": "Lecture"},
    "roles.write":           {"section": "Administration",  "feature": "Rôles",                 "action": "Écriture"},
    "proxy.restart":         {"section": "Administration",  "feature": "Contrôle proxy",        "action": "Redémarrer"},
    "settings.smtp.read":       {"section": "Paramètres",      "feature": "Configuration SMTP",    "action": "Lecture"},
    "settings.smtp.write":      {"section": "Paramètres",      "feature": "Configuration SMTP",    "action": "Écriture"},
    "settings.templates.read":  {"section": "Paramètres",      "feature": "Templates (e-mail & page de blocage)", "action": "Lecture"},
    "settings.templates.write": {"section": "Paramètres",      "feature": "Templates (e-mail & page de blocage)", "action": "Écriture"},
    "settings.appearance.read": {"section": "Paramètres",      "feature": "Apparence & thèmes",   "action": "Lecture"},
    "settings.appearance.write":{"section": "Paramètres",      "feature": "Apparence & thèmes",   "action": "Écriture"},
    "settings.rmm.read":        {"section": "Paramètres",      "feature": "Intégrations RMM",     "action": "Lecture"},
    "settings.rmm.write":       {"section": "Paramètres",      "feature": "Intégrations RMM",     "action": "Écriture"},
}
