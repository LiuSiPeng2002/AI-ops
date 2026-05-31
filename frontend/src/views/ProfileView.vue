<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import api from '../api'
import LangSwitcher from '../components/LangSwitcher.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const saving = ref(false)
const message = ref('')

async function changePassword() {
  if (newPassword.value !== confirmPassword.value) { message.value = t('profile.passwordMismatch'); return }
  if (newPassword.value.length < 6) { message.value = t('profile.passwordTooShort'); return }
  saving.value = true; message.value = ''
  try {
    await api.post('/auth/change-password', { current_password: currentPassword.value, new_password: newPassword.value })
    message.value = t('profile.passwordChanged')
    currentPassword.value = ''; newPassword.value = ''; confirmPassword.value = ''
  } catch (e) { message.value = e.response?.data?.detail || 'Error' }
  finally { saving.value = false }
}

function handleLogout() { authStore.logout(); router.push('/login') }
</script>

<template>
  <div class="profile-layout">
    <aside class="sidebar">
      <div class="sidebar-top"><div class="logo"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg><span>AI-Ops</span></div></div>
      <nav class="sidebar-nav">
        <router-link to="/chat" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span>{{ t('sidebar.chat') }}</span></router-link>
        <router-link to="/dashboard" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg><span>{{ t('sidebar.dashboard') }}</span></router-link>
        <router-link to="/audit" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg><span>{{ t('sidebar.audit') }}</span></router-link>
        <router-link to="/knowledge" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg><span>{{ t('sidebar.knowledge') }}</span></router-link>
        <router-link to="/inspection" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg><span>{{ t('sidebar.inspection') }}</span></router-link>
        <router-link to="/profile" class="nav-item active"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg><span>{{ t('sidebar.profile') }}</span></router-link>
      </nav>
      <div class="sidebar-footer"><LangSwitcher /><router-link v-if="authStore.user" to="/profile" class="user-badge"><span class="user-avatar">{{ authStore.user.username[0].toUpperCase() }}</span><span class="user-name">{{ authStore.user.username }}</span></router-link><button class="btn-logout" @click="handleLogout">{{ t('sidebar.logout') }}</button></div>
    </aside>

    <main class="main-area">
      <header class="page-header"><h1>{{ t('profile.title') }}</h1></header>
      <div class="profile-card">
        <div class="info-row"><span class="info-label">{{ t('profile.username') }}</span><span class="info-val">{{ authStore.user?.username }}</span></div>
        <div class="info-row"><span class="info-label">{{ t('profile.role') }}</span><span class="role-badge" :class="'role-'+authStore.user?.role">{{ authStore.user?.role }}</span></div>
        <div class="info-row"><span class="info-label">{{ t('profile.email') }}</span><span class="info-val">{{ authStore.user?.email || '-' }}</span></div>
      </div>

      <div class="profile-card" style="margin-top:20px">
        <h3>{{ t('profile.changePassword') }}</h3>
        <div class="form-group"><label>{{ t('profile.currentPassword') }}</label><input v-model="currentPassword" type="password" class="form-input" /></div>
        <div class="form-group"><label>{{ t('profile.newPassword') }}</label><input v-model="newPassword" type="password" class="form-input" /></div>
        <div class="form-group"><label>{{ t('profile.confirmPassword') }}</label><input v-model="confirmPassword" type="password" class="form-input" /></div>
        <div v-if="message" class="msg" :class="{ ok: message.includes('成功')||message.includes('changed') }">{{ message }}</div>
        <button class="btn-primary" @click="changePassword" :disabled="saving">{{ saving ? '...' : t('profile.changePassword') }}</button>
      </div>
    </main>
  </div>
</template>

<style scoped>
.profile-layout { display: flex; height: 100vh; background: #0b0f15; color: #dce2ea; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; }
.sidebar { width: 240px; background: #0b0f15; border-right: 1px solid #1e2a38; display: flex; flex-direction: column; flex-shrink: 0; }
.sidebar-top { padding: 20px 20px 16px; border-bottom: 1px solid #1e2a38; }
.logo { display: flex; align-items: center; gap: 10px; color: #dce2ea; }
.logo span { font-size: 16px; font-weight: 700; }
.sidebar-nav { padding: 12px 14px; flex: 1; display: flex; flex-direction: column; gap: 2px; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-radius: 6px; font-size: 13px; color: #7c8b9e; text-decoration: none; transition: all 0.2s; }
.nav-item:hover,.nav-item.active { background: #1a2230; color: #dce2ea; }
.nav-item.active { border-left: 2px solid #3b9eff; }
.sidebar-footer { padding: 12px 20px; border-top: 1px solid #1e2a38; display: flex; align-items: center; gap: 10px; }
.user-badge { display: flex; align-items: center; gap: 8px; flex: 1; text-decoration: none; cursor: pointer; border-radius: 5px; padding: 4px 6px; transition: background 0.15s; }
.user-badge:hover { background: #1a2230; }
.user-avatar { width: 26px; height: 26px; border-radius: 5px; background: #1a2230; border: 1px solid #1e2a38; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; color: #7c8b9e; }
.user-name { font-size: 12px; color: #7c8b9e; }
.btn-logout { background: none; border: none; color: #4e5b6e; font-size: 11px; cursor: pointer; }
.btn-logout:hover { color: #f04a4a; }
.main-area { flex: 1; overflow-y: auto; padding: 28px 36px; min-width: 0; }
.page-header { margin-bottom: 20px; }
.page-header h1 { font-size: 22px; font-weight: 700; margin: 0; }
.profile-card { background: #131922; border: 1px solid #1e2a38; border-radius: 8px; padding: 20px; max-width: 520px; }
.profile-card h3 { margin: 0 0 14px; font-size: 14px; }
.info-row { display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #1e2a38; }
.info-label { width: 100px; font-size: 12px; color: #7c8b9e; }
.info-val { font-size: 13px; color: #dce2ea; font-weight: 600; }
.role-badge { font-size: 10px; padding: 2px 8px; border-radius: 3px; font-weight: 600; }
.role-superadmin { background: rgba(168,85,247,0.15); color: #a855f7; }
.role-admin { background: rgba(59,158,255,0.15); color: #3b9eff; }
.role-operator { background: rgba(229,160,32,0.15); color: #e5a020; }
.role-viewer { background: rgba(78,91,110,0.15); color: #7c8b9e; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 11px; color: #7c8b9e; margin-bottom: 4px; }
.form-input { width: 100%; padding: 8px 12px; background: #0b0f15; border: 1px solid #2a3a4e; color: #dce2ea; border-radius: 5px; font-size: 13px; outline: none; box-sizing: border-box; }
.form-input:focus { border-color: #3b9eff; }
.msg { padding: 8px 12px; margin-bottom: 12px; border-radius: 4px; font-size: 12px; background: rgba(240,74,74,0.1); color: #f04a4a; }
.msg.ok { background: rgba(46,204,113,0.1); color: #2ecc71; }
.btn-primary { padding: 8px 18px; background: #3b9eff; color: #fff; border: none; border-radius: 5px; font-size: 12px; cursor: pointer; }
.btn-primary:hover { background: #2d8aef; }
.btn-primary:disabled { opacity: 0.5; }
</style>
