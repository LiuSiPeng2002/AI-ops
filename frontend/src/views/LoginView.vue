<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const form = ref({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    await authStore.login(form.value.username, form.value.password)
    router.push('/chat')
  } catch (e) {
    error.value = e.response?.data?.detail || t('login.loginFailed')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-bg">
    <div class="login-overlay">
      <div class="login-card">
        <div class="card-top">
          <div class="login-logo">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
              <rect x="3" y="3" width="7" height="7" rx="1.5" />
              <rect x="14" y="3" width="7" height="7" rx="1.5" />
              <rect x="3" y="14" width="7" height="7" rx="1.5" />
              <rect x="14" y="14" width="7" height="7" rx="1.5" />
            </svg>
          </div>
          <h1>{{ t('login.title') }}</h1>
          <p>{{ t('login.subtitle') }}</p>
        </div>

        <el-form @submit.prevent="handleLogin" label-position="top" class="login-form">
          <el-form-item :label="t('login.username')">
            <el-input
              v-model="form.username"
              :placeholder="t('login.usernamePlaceholder')"
              size="large"
              :disabled="loading"
            />
          </el-form-item>

          <el-form-item :label="t('login.password')">
            <el-input
              v-model="form.password"
              type="password"
              :placeholder="t('login.passwordPlaceholder')"
              size="large"
              show-password
              :disabled="loading"
            />
          </el-form-item>

          <el-alert
            v-if="error"
            :title="error"
            type="error"
            show-icon
            :closable="true"
            @close="error = ''"
            style="margin-bottom: 16px"
          />

          <el-button
            type="primary"
            native-type="submit"
            :loading="loading"
            size="large"
            class="login-btn"
          >
            {{ loading ? t('login.authenticating') : t('login.signIn') }}
          </el-button>
        </el-form>

        <div class="card-footer">
          <span class="footer-line">{{ t('login.footer') }}</span>
          <span class="footer-divider">&middot;</span>
          <span class="footer-line">{{ t('login.footerAgents') }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-bg { position: relative; min-height: 100vh; background: #0b0f15; }
.login-overlay { position: relative; z-index: 1; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 24px; }
.login-card { width: 420px; padding: 40px; background: #131922; border: 1px solid #1e2a38; border-radius: 12px; }
.card-top { text-align: center; margin-bottom: 32px; }
.login-logo { width: 52px; height: 52px; border-radius: 12px; background: rgba(59, 158, 255, 0.08); border: 1px solid rgba(59, 158, 255, 0.18); display: flex; align-items: center; justify-content: center; color: #3b9eff; margin: 0 auto 16px; }
.card-top h1 { font-size: 22px; font-weight: 700; color: #dce2ea; margin: 0 0 6px; letter-spacing: -0.02em; }
.card-top p { font-size: 12.5px; color: #6b7a8d; margin: 0; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; letter-spacing: 0.03em; }
.login-form :deep(.el-form-item__label) { color: #7c8b9e; font-size: 12px; font-weight: 500; }
.login-btn { width: 100%; height: 44px; font-size: 14px; font-weight: 600; letter-spacing: 0.02em; }
.card-footer { text-align: center; margin-top: 24px; font-size: 10px; color: #3a4556; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; letter-spacing: 0.04em; }
.footer-divider { margin: 0 8px; opacity: 0.4; }
</style>
