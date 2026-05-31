<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import api from '../api'
import LangSwitcher from '../components/LangSwitcher.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const machines = ref([])
const loading = ref(false)
const showAdd = ref(false)
const form = ref({ name: '', host: '', port: 22, username: 'root', password: '', description: '' })
const saving = ref(false)
const checking = ref({})

async function fetchMachines() {
  loading.value = true
  try {
    const { data } = await api.get('/machines')
    machines.value = data.items || []
  } catch (e) { /* pass */ }
  finally { loading.value = false }
}

async function handleAdd() {
  saving.value = true
  try {
    await api.post('/machines', form.value)
    showAdd.value = false
    form.value = { name: '', host: '', port: 22, username: 'root', password: '', description: '' }
    await fetchMachines()
  } catch (e) { alert(e.response?.data?.detail || 'Error') }
  finally { saving.value = false }
}

async function handleCheck(m) {
  checking.value[m.id] = true
  try {
    const { data } = await api.post(`/machines/${m.id}/check`)
    m.online = data.online
  } catch (e) { /* pass */ }
  finally { checking.value[m.id] = false }
}

async function handleSetDefault(m) {
  try {
    await api.post(`/machines/${m.id}/set-default`)
    await fetchMachines()
  } catch (e) { alert(e.response?.data?.detail || 'Error') }
}

async function handleDelete(m) {
  if (!confirm(`Delete ${m.name}?`)) return
  try {
    await api.delete(`/machines/${m.id}`)
    await fetchMachines()
  } catch (e) { alert(e.response?.data?.detail || 'Error') }
}

onMounted(() => fetchMachines())
function handleLogout() { authStore.logout(); router.push('/login') }
</script>

<template>
  <div class="machines-layout">
    <aside class="sidebar">
      <div class="sidebar-top"><div class="logo"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg><span>AI-Ops</span></div></div>
      <nav class="sidebar-nav">
        <router-link to="/chat" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span>{{ t('sidebar.chat') }}</span></router-link>
        <router-link to="/dashboard" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg><span>{{ t('sidebar.dashboard') }}</span></router-link>
        <router-link to="/machines" class="nav-item active"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1" fill="currentColor"/><circle cx="6" cy="18" r="1" fill="currentColor"/></svg><span>{{ t('sidebar.machines') }}</span></router-link>
      </nav>
      <div class="sidebar-footer"><LangSwitcher /><router-link v-if="authStore.user" to="/profile" class="user-badge"><span class="user-avatar">{{ authStore.user.username[0].toUpperCase() }}</span><span class="user-name">{{ authStore.user.username }}</span></router-link><button class="btn-logout" @click="handleLogout">{{ t('sidebar.logout') }}</button></div>
    </aside>

    <main class="main-area">
      <header class="page-header"><h1>{{ t('machines.title') }}</h1><span class="page-desc">{{ t('machines.desc') }}</span></header>

      <div class="toolbar">
        <button class="btn-primary" @click="showAdd = true">{{ t('machines.addMachine') }}</button>
      </div>

      <div class="machine-list">
        <div v-for="m in machines" :key="m.id" class="machine-card">
          <div class="mc-header">
            <span class="mc-name">{{ m.name }}</span>
            <span class="mc-status" :class="m.online ? 'online' : 'offline'">{{ m.online ? '● '+t('machines.online') : '○ '+t('machines.offline') }}</span>
            <span v-if="m.is_default" class="mc-default">{{ t('machines.default') }}</span>
          </div>
          <div class="mc-info">{{ m.host }}:{{ m.port }} @ {{ m.username }}</div>
          <div v-if="m.description" class="mc-desc">{{ m.description }}</div>
          <div class="mc-actions">
            <button class="btn-sm" @click="handleCheck(m)" :disabled="checking[m.id]">{{ checking[m.id] ? '...' : t('machines.check') }}</button>
            <button class="btn-sm" @click="handleSetDefault(m)" v-if="!m.is_default">{{ t('machines.setDefault') }}</button>
            <button class="btn-sm btn-del" @click="handleDelete(m)">{{ t('machines.delete') }}</button>
          </div>
        </div>
        <div v-if="machines.length === 0 && !loading" class="empty-hint">{{ t('machines.empty') }}</div>
      </div>

      <!-- Add Modal -->
      <div v-if="showAdd" class="modal-overlay" @click.self="showAdd=false">
        <div class="modal-card">
          <h3>{{ t('machines.addMachine') }}</h3>
          <div class="form-group"><label>{{ t('machines.name') }}</label><input v-model="form.name" class="form-input" /></div>
          <div class="form-group"><label>{{ t('machines.host') }}</label><input v-model="form.host" class="form-input" /></div>
          <div class="form-group"><label>{{ t('machines.port') }}</label><input v-model.number="form.port" class="form-input" type="number" /></div>
          <div class="form-group"><label>{{ t('machines.username') }}</label><input v-model="form.username" class="form-input" /></div>
          <div class="form-group"><label>{{ t('machines.password') }}</label><input v-model="form.password" class="form-input" type="password" /></div>
          <div class="form-group"><label>{{ t('machines.description') }}</label><input v-model="form.description" class="form-input" /></div>
          <div class="modal-actions"><button class="btn-primary" @click="handleAdd" :disabled="saving">{{ saving ? '...' : t('machines.save') }}</button><button class="btn-cancel" @click="showAdd=false">{{ t('machines.cancel') }}</button></div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.machines-layout { display: flex; height: 100vh; background: #0b0f15; color: #dce2ea; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; }
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
.page-header h1 { font-size: 22px; font-weight: 700; margin: 0 0 4px; }
.page-desc { font-size: 13px; color: #7c8b9e; }
.toolbar { margin-bottom: 16px; }
.btn-primary { padding: 8px 18px; background: #3b9eff; color: #fff; border: none; border-radius: 5px; font-size: 12px; cursor: pointer; }
.btn-primary:hover { background: #2d8aef; }
.btn-primary:disabled { opacity: 0.5; }
.machine-list { display: flex; flex-direction: column; gap: 10px; max-width: 700px; }
.machine-card { background: #131922; border: 1px solid #1e2a38; border-radius: 8px; padding: 16px; }
.mc-header { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.mc-name { font-size: 14px; font-weight: 600; color: #dce2ea; }
.mc-status { font-size: 11px; }
.mc-status.online { color: #2ecc71; }
.mc-status.offline { color: #4e5b6e; }
.mc-default { font-size: 10px; background: rgba(46,204,113,0.1); color: #2ecc71; padding: 1px 8px; border-radius: 3px; }
.mc-info { font-size: 12px; color: #7c8b9e; font-family: monospace; }
.mc-desc { font-size: 11px; color: #4e5b6e; margin-top: 4px; }
.mc-actions { display: flex; gap: 6px; margin-top: 10px; }
.btn-sm { padding: 4px 10px; background: #1a2230; border: 1px solid #2a3a4e; color: #3b9eff; border-radius: 4px; font-size: 11px; cursor: pointer; }
.btn-sm:hover { border-color: #3b9eff; }
.btn-del { color: #f04a4a; border-color: rgba(240,74,74,0.3); }
.btn-del:hover { border-color: #f04a4a; }
.empty-hint { color: #4e5b6e; text-align: center; padding: 40px; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 200; display: flex; align-items: center; justify-content: center; }
.modal-card { width: 420px; background: #131922; border: 1px solid #2a3a4e; border-radius: 10px; padding: 24px; }
.modal-card h3 { margin: 0 0 16px; font-size: 16px; }
.form-group { margin-bottom: 10px; }
.form-group label { display: block; font-size: 11px; color: #7c8b9e; margin-bottom: 4px; }
.form-input { width: 100%; padding: 8px 12px; background: #0b0f15; border: 1px solid #2a3a4e; color: #dce2ea; border-radius: 5px; font-size: 13px; outline: none; box-sizing: border-box; }
.form-input:focus { border-color: #3b9eff; }
.modal-actions { display: flex; gap: 8px; margin-top: 16px; justify-content: flex-end; }
.btn-cancel { padding: 8px 16px; background: none; border: 1px solid #2a3a4e; color: #7c8b9e; border-radius: 6px; font-size: 12px; cursor: pointer; }
.btn-cancel:hover { border-color: #f04a4a; color: #f04a4a; }
</style>
