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

const users = ref([])
const total = ref(0)
const loading = ref(false)

const showCreate = ref(false)
const createForm = ref({ username: '', password: '', role: 'viewer', email: '' })
const creating = ref(false)

const editingUser = ref(null)
const editForm = ref({ role: '', email: '', password: '', status: '' })

async function fetchUsers() {
  loading.value = true
  try {
    const { data } = await api.get('/users', { params: { limit: 100 } })
    users.value = data.items
    total.value = data.total
  } catch (e) { /* pass */ }
  finally { loading.value = false }
}

async function handleCreate() {
  creating.value = true
  try {
    await api.post('/users', createForm.value)
    showCreate.value = false
    createForm.value = { username: '', password: '', role: 'viewer', email: '' }
    await fetchUsers()
  } catch (e) { alert(e.response?.data?.detail || 'Error') }
  finally { creating.value = false }
}

function startEdit(user) {
  editingUser.value = user.id
  editForm.value = { role: user.role, email: user.email || '', password: '', status: user.status }
}

async function saveEdit(userId) {
  try {
    const body = {}
    if (editForm.value.role) body.role = editForm.value.role
    if (editForm.value.email !== undefined) body.email = editForm.value.email
    if (editForm.value.status) body.status = editForm.value.status
    if (editForm.value.password) body.password = editForm.value.password
    await api.put(`/users/${userId}`, body)
    editingUser.value = null
    await fetchUsers()
  } catch (e) { alert(e.response?.data?.detail || 'Error') }
}

async function handleDelete(userId) {
  if (!confirm(t('users.confirmDelete'))) return
  try {
    await api.delete(`/users/${userId}`)
    await fetchUsers()
  } catch (e) { alert(e.response?.data?.detail || 'Error') }
}

onMounted(() => fetchUsers())

function handleLogout() { authStore.logout(); router.push('/login') }
</script>

<template>
  <div class="users-layout">
    <aside class="sidebar">
      <div class="sidebar-top"><div class="logo"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg><span>AI-Ops</span></div></div>
      <nav class="sidebar-nav">
        <router-link to="/chat" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span>{{ t('sidebar.chat') }}</span></router-link>
        <router-link to="/dashboard" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg><span>{{ t('sidebar.dashboard') }}</span></router-link>
        <router-link to="/users" class="nav-item active"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg><span>{{ t('sidebar.users') }}</span></router-link>
      </nav>
      <div class="sidebar-footer"><LangSwitcher /><router-link v-if="authStore.user" to="/profile" class="user-badge"><span class="user-avatar">{{ authStore.user.username[0].toUpperCase() }}</span><span class="user-name">{{ authStore.user.username }}</span></router-link><button class="btn-logout" @click="handleLogout">{{ t('sidebar.logout') }}</button></div>
    </aside>

    <main class="main-area">
      <header class="page-header"><h1>{{ t('users.title') }}</h1><span class="page-desc">{{ t('users.desc') }}</span></header>

      <div class="toolbar">
        <button class="btn-primary" @click="showCreate = true">{{ t('users.createUser') }}</button>
      </div>

      <table class="users-table">
        <thead><tr><th>ID</th><th>{{ t('users.username') }}</th><th>{{ t('users.role') }}</th><th>{{ t('users.email') }}</th><th>{{ t('users.status') }}</th><th>{{ t('users.actions') }}</th></tr></thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td class="mono">{{ u.id }}</td>
            <td class="fw">{{ u.username }}</td>
            <td><span class="role-badge" :class="'role-'+u.role">{{ u.role }}</span></td>
            <td>{{ u.email || '-' }}</td>
            <td><span class="status-dot" :class="u.status === 'active' ? 'dot-on' : 'dot-off'"></span> {{ u.status }}</td>
            <td class="actions-cell">
              <button class="btn-sm" @click="startEdit(u)" :disabled="u.role==='superadmin' && authStore.user?.role!=='superadmin'">{{ t('users.edit') }}</button>
              <button class="btn-sm btn-del" @click="handleDelete(u.id)" v-if="authStore.user?.role === 'superadmin' && u.id !== authStore.user?.id">{{ t('users.delete') }}</button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Edit Modal -->
      <div v-if="editingUser" class="modal-overlay" @click.self="editingUser=null">
        <div class="modal-card">
          <h3>{{ t('users.editUser') }}</h3>
          <div class="form-group"><label>{{ t('users.role') }}</label><select v-model="editForm.role" class="form-input"><option value="viewer">viewer</option><option value="operator">operator</option><option value="admin">admin</option><option value="superadmin">superadmin</option></select></div>
          <div class="form-group"><label>{{ t('users.status') }}</label><select v-model="editForm.status" class="form-input"><option value="active">active</option><option value="disabled">disabled</option></select></div>
          <div class="form-group"><label>{{ t('users.email') }}</label><input v-model="editForm.email" class="form-input" /></div>
          <div class="form-group"><label>{{ t('users.newPassword') }}</label><input v-model="editForm.password" class="form-input" type="password" :placeholder="t('users.passwordHint')" /></div>
          <div class="modal-actions"><button class="btn-primary" @click="saveEdit(editingUser)">{{ t('users.save') }}</button><button class="btn-cancel" @click="editingUser=null">{{ t('users.cancel') }}</button></div>
        </div>
      </div>

      <!-- Create Modal -->
      <div v-if="showCreate" class="modal-overlay" @click.self="showCreate=false">
        <div class="modal-card">
          <h3>{{ t('users.createUser') }}</h3>
          <div class="form-group"><label>{{ t('users.username') }}</label><input v-model="createForm.username" class="form-input" /></div>
          <div class="form-group"><label>{{ t('users.password') }}</label><input v-model="createForm.password" class="form-input" type="password" /></div>
          <div class="form-group"><label>{{ t('users.role') }}</label><select v-model="createForm.role" class="form-input"><option value="viewer">viewer</option><option value="operator">operator</option><option value="admin">admin</option><option value="superadmin">superadmin</option></select></div>
          <div class="form-group"><label>{{ t('users.email') }}</label><input v-model="createForm.email" class="form-input" /></div>
          <div class="modal-actions"><button class="btn-primary" @click="handleCreate" :disabled="creating">{{ creating ? t('users.creating') : t('users.createUser') }}</button><button class="btn-cancel" @click="showCreate=false">{{ t('users.cancel') }}</button></div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.users-layout { display: flex; height: 100vh; background: #0b0f15; color: #dce2ea; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; }
.sidebar { width: 240px; background: #0b0f15; border-right: 1px solid #1e2a38; display: flex; flex-direction: column; flex-shrink: 0; }
.sidebar-top { padding: 20px 20px 16px; border-bottom: 1px solid #1e2a38; }
.logo { display: flex; align-items: center; gap: 10px; color: #dce2ea; }
.logo span { font-size: 16px; font-weight: 700; }
.sidebar-nav { padding: 12px 14px; flex: 1; display: flex; flex-direction: column; gap: 2px; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-radius: 6px; font-size: 13px; color: #7c8b9e; text-decoration: none; transition: all 0.2s; }
.nav-item:hover, .nav-item.active { background: #1a2230; color: #dce2ea; }
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
.btn-primary { padding: 8px 18px; background: #3b9eff; color: #fff; border: none; border-radius: 6px; font-size: 12px; cursor: pointer; }
.btn-primary:hover { background: #2d8aef; }
.btn-primary:disabled { opacity: 0.5; }

.users-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.users-table th { text-align: left; padding: 10px 12px; border-bottom: 1px solid #1e2a38; color: #4e5b6e; font-weight: 600; font-size: 10px; letter-spacing: 0.06em; text-transform: uppercase; }
.users-table td { padding: 9px 12px; border-bottom: 1px solid #131922; }
.mono { font-family: 'Cascadia Code','Fira Code',monospace; font-size: 11px; color: #7c8b9e; }
.fw { font-weight: 600; }
.time-cell { color: #4e5b6e !important; }
.actions-cell { display: flex; gap: 6px; }
.btn-sm { padding: 4px 10px; background: #1a2230; border: 1px solid #2a3a4e; color: #3b9eff; border-radius: 4px; font-size: 11px; cursor: pointer; }
.btn-sm:hover { border-color: #3b9eff; }
.btn-del { color: #f04a4a; border-color: rgba(240,74,74,0.3); }
.btn-del:hover { border-color: #f04a4a; background: rgba(240,74,74,0.08); }
.role-badge { font-size: 10px; padding: 2px 8px; border-radius: 3px; font-weight: 600; }
.role-superadmin { background: rgba(168,85,247,0.15); color: #a855f7; }
.role-admin { background: rgba(59,158,255,0.15); color: #3b9eff; }
.role-operator { background: rgba(229,160,32,0.15); color: #e5a020; }
.role-viewer { background: rgba(78,91,110,0.15); color: #7c8b9e; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; margin-right: 4px; }
.dot-on { background: #2ecc71; }
.dot-off { background: #4e5b6e; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 200; display: flex; align-items: center; justify-content: center; }
.modal-card { width: 420px; background: #131922; border: 1px solid #2a3a4e; border-radius: 10px; padding: 24px; }
.modal-card h3 { margin: 0 0 16px; font-size: 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 11px; color: #7c8b9e; margin-bottom: 4px; font-weight: 600; }
.form-input { width: 100%; padding: 8px 12px; background: #0b0f15; border: 1px solid #2a3a4e; color: #dce2ea; border-radius: 5px; font-size: 13px; outline: none; box-sizing: border-box; }
.form-input:focus { border-color: #3b9eff; }
select.form-input { cursor: pointer; }
.modal-actions { display: flex; gap: 8px; margin-top: 16px; justify-content: flex-end; }
.btn-cancel { padding: 8px 16px; background: none; border: 1px solid #2a3a4e; color: #7c8b9e; border-radius: 6px; font-size: 12px; cursor: pointer; }
.btn-cancel:hover { border-color: #f04a4a; color: #f04a4a; }
</style>
