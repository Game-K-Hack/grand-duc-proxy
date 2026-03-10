<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <h1>🦉 Grand-Duc</h1>
        <p>Interface d'administration</p>
      </div>

      <div v-if="auth.error" class="alert alert-error">{{ auth.error }}</div>

      <div class="form-group" style="margin-bottom:14px">
        <label class="form-label">Identifiant</label>
        <input
          v-model="username"
          class="form-input"
          type="text"
          placeholder="admin"
          autocomplete="username"
          @keyup.enter="submit"
        />
      </div>

      <div class="form-group" style="margin-bottom:20px">
        <label class="form-label">Mot de passe</label>
        <input
          v-model="password"
          class="form-input"
          type="password"
          placeholder="••••••••"
          autocomplete="current-password"
          @keyup.enter="submit"
        />
      </div>

      <button class="btn btn-primary" style="width:100%;justify-content:center" @click="submit" :disabled="auth.loading">
        {{ auth.loading ? 'Connexion…' : 'Se connecter' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref }          from 'vue'
import { useRouter }    from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth     = useAuthStore()
const router   = useRouter()
const username = ref('')
const password = ref('')

async function submit() {
  if (!username.value || !password.value) return
  try {
    await auth.login(username.value, password.value)
    router.push('/')
  } catch {}
}
</script>