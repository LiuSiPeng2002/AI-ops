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

const tasks = ref([])
const results = ref([])
const schedulerRunning = ref(false)
const tasksLoading = ref(true)
const resultsLoading = ref(true)

async function fetchTasks() {
  tasksLoading.value = true
  try {
    const { data } = await api.get('/inspection/tasks')
    tasks.value = data.tasks
    schedulerRunning.value = data.running
  } catch (e) { /* pass */ }
  finally { tasksLoading.value = false }
}

async function fetchResults() {
  resultsLoading.value = true
  try {
    const { data } = await api.get('/inspection/results', { params: { limit: 30 } })
    results.value = data.results
  } catch (e) { /* pass */ }
  finally { resultsLoading.value = false }
}

async function toggleTask(taskId, enabled) {
  try {
    await api.put(`/inspection/tasks/${taskId}`, { enabled })
    await fetchTasks()
  } catch (e) { /* pass */ }
}

async function runTask(taskId) {
  try {
    await api.post(`/inspection/run/${taskId}`)
    await fetchResults()
  } catch (e) { /* pass */ }
}

async function toggleScheduler() {
  try {
    if (schedulerRunning.value) {
      await api.post('/inspection/stop')
    } else {
      await api.post('/inspection/start')
    }
    schedulerRunning.value = !schedulerRunning.value
  } catch (e) { /* pass */ }
}

onMounted(() => {
  fetchTasks()
  fetchResults()
})

function handleLogout() { authStore.logout(); router.push('/login') }

function formatTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString()
}

function alertBadge(hasAlert) {
  return hasAlert ? t('inspection.alert') : t('inspection.normal')
}
</script>

<template>
  <div class="inspect-layout">
    <aside class="sidebar">
      <div class="sidebar-top">
        <div class="logo">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" />
            <rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" />
          </svg>
          <span>AI-Ops</span>
        </div>
      </div>
      <nav class="sidebar-nav">
        <router-link to="/chat" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span>{{ t('sidebar.chat') }}</span></router-link>
        <router-link to="/dashboard" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg><span>{{ t('sidebar.dashboard') }}</span></router-link>
        <router-link to="/audit" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg><span>{{ t('sidebar.audit') }}</span></router-link>
        <router-link to="/knowledge" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg><span>{{ t('sidebar.knowledge') }}</span></router-link>
        <router-link to="/inspection" class="nav-item active"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg><span>{{ t('sidebar.inspection') }}</span></router-link>
      </nav>
      <div class="sidebar-footer">
        <LangSwitcher />
        <router-link v-if="authStore.user" to="/profile" class="user-badge">
          <span class="user-avatar">{{ authStore.user.username[0].toUpperCase() }}</span>
          <span class="user-name">{{ authStore.user.username }}</span>
        </router-link>
        <button class="btn-logout" @click="handleLogout">{{ t('sidebar.logout') }}</button>
      </div>
    </aside>

    <main class="main-area">
      <header class="page-header">
        <div class="header-row">
          <div>
            <h1>{{ t('inspection.title') }}</h1>
            <span class="page-desc">{{ t('inspection.desc') }}</span>
          </div>
          <button class="btn-scheduler" :class="{ running: schedulerRunning }" @click="toggleScheduler">
            <span class="sched-dot" :class="schedulerRunning ? 'dot-run' : 'dot-stop'"></span>
            {{ schedulerRunning ? t('inspection.stopScheduler') : t('inspection.startScheduler') }}
          </button>
        </div>
      </header>

      <div class="content-grid">
        <!-- Inspection Tasks -->
        <section class="section-full">
          <h2 class="section-title">{{ t('inspection.inspectionTasks') }}</h2>
          <div v-if="tasksLoading" class="loading-text">{{ t('inspection.loading') }}</div>
          <div v-else class="task-table-wrap">
            <table class="task-table">
              <thead>
                <tr>
                  <th>{{ t('inspection.taskName') }}</th>
                  <th>{{ t('inspection.tool') }}</th>
                  <th>{{ t('inspection.interval') }}</th>
                  <th>{{ t('inspection.command') }}</th>
                  <th>{{ t('inspection.alertPattern') }}</th>
                  <th>{{ t('inspection.status') }}</th>
                  <th>{{ t('inspection.actions') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="task in tasks" :key="task.id" :class="{ disabled: !task.enabled }">
                  <td class="task-name">{{ task.name }}</td>
                  <td><code>{{ task.tool }}</code></td>
                  <td>{{ task.interval_minutes }}min</td>
                  <td><code class="cmd-text">{{ task.command }}</code></td>
                  <td><code v-if="task.alert_on" class="alert-pat">{{ task.alert_on }}</code><span v-else class="no-alert">-</span></td>
                  <td>
                    <label class="toggle-switch">
                      <input type="checkbox" :checked="task.enabled" @change="toggleTask(task.id, !task.enabled)" />
                      <span class="toggle-slider"></span>
                    </label>
                  </td>
                  <td>
                    <button class="btn-run" @click="runTask(task.id)" :disabled="!task.enabled">{{ t('inspection.runNow') }}</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- Recent Results -->
        <section class="section-full">
          <h2 class="section-title">{{ t('inspection.recentResults') }}</h2>
          <div v-if="resultsLoading" class="loading-text">{{ t('inspection.loading') }}</div>
          <div v-else-if="results.length === 0" class="empty-hint">{{ t('inspection.noResults') }}</div>
          <div v-else class="results-list">
            <div v-for="r in results" :key="r.task_id + r.timestamp" class="result-row" :class="{ alert: r.alert }">
              <div class="res-header">
                <span class="res-name">{{ r.name }}</span>
                <span v-if="r.alert" class="res-alert-badge">{{ t('inspection.alert') }}</span>
                <span v-else class="res-ok-badge">{{ t('inspection.normal') }}</span>
                <span class="res-time">{{ formatTime(r.timestamp) }}</span>
              </div>
              <pre class="res-output">{{ r.output }}</pre>
            </div>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.inspect-layout { display: flex; height: 100vh; background: #0b0f15; color: #dce2ea; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; }
.sidebar { width: 240px; background: #0b0f15; border-right: 1px solid #1e2a38; display: flex; flex-direction: column; flex-shrink: 0; }
.sidebar-top { padding: 20px 20px 16px; border-bottom: 1px solid #1e2a38; }
.logo { display: flex; align-items: center; gap: 10px; color: #dce2ea; }
.logo span { font-size: 16px; font-weight: 700; letter-spacing: -0.02em; }
.sidebar-nav { padding: 12px 14px; flex: 1; display: flex; flex-direction: column; gap: 2px; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-radius: 6px; font-size: 13px; color: #7c8b9e; text-decoration: none; transition: all 0.2s; }
.nav-item:hover, .nav-item.active { background: #1a2230; color: #dce2ea; }
.nav-item.active { border-left: 2px solid #3b9eff; }
.sidebar-footer { padding: 12px 20px; border-top: 1px solid #1e2a38; display: flex; align-items: center; gap: 10px; }
.user-badge { display: flex; align-items: center; gap: 8px; flex: 1; text-decoration: none; cursor: pointer; border-radius: 5px; padding: 4px 6px; transition: background 0.15s; }
.user-badge:hover { background: #1a2230; }
.user-avatar { width: 26px; height: 26px; border-radius: 5px; background: #1a2230; border: 1px solid #1e2a38; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; color: #7c8b9e; }
.user-name { font-size: 12px; color: #7c8b9e; }
.btn-logout { background: none; border: none; color: #4e5b6e; font-size: 11px; cursor: pointer; white-space: nowrap; }
.btn-logout:hover { color: #f04a4a; }

.main-area { flex: 1; overflow-y: auto; padding: 28px 36px; min-width: 0; }
.page-header { margin-bottom: 24px; }
.header-row { display: flex; justify-content: space-between; align-items: flex-start; }
.header-row h1 { font-size: 22px; font-weight: 700; margin: 0 0 4px; letter-spacing: -0.02em; }
.page-desc { font-size: 13px; color: #7c8b9e; }
.btn-scheduler { display: flex; align-items: center; gap: 8px; padding: 8px 18px; background: #1a2230; border: 1px solid #2a3a4e; color: #dce2ea; border-radius: 6px; font-size: 12px; cursor: pointer; transition: all 0.2s; }
.btn-scheduler.running { border-color: rgba(46,204,113,0.4); }
.btn-scheduler:hover { border-color: #3b9eff; }
.sched-dot { width: 7px; height: 7px; border-radius: 50%; }
.dot-run { background: #2ecc71; box-shadow: 0 0 6px rgba(46,204,113,0.4); }
.dot-stop { background: #4e5b6e; }
.content-grid { display: flex; flex-direction: column; gap: 20px; }
.section-title { font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #4e5b6e; margin: 0 0 14px; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.loading-text, .empty-hint { color: #4e5b6e; padding: 16px; font-size: 12px; text-align: center; }

.task-table-wrap { overflow-x: auto; }
.task-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.task-table th { text-align: left; padding: 10px 12px; border-bottom: 1px solid #1e2a38; color: #4e5b6e; font-weight: 600; white-space: nowrap; font-size: 10px; letter-spacing: 0.06em; text-transform: uppercase; }
.task-table td { padding: 10px 12px; border-bottom: 1px solid #131922; vertical-align: middle; }
.task-table tr.disabled { opacity: 0.45; }
.task-name { font-weight: 600; color: #dce2ea; font-size: 13px; }
code { font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; font-size: 11px; color: #00d4aa; background: #131922; padding: 2px 6px; border-radius: 3px; }
.cmd-text { font-size: 10.5px; color: #dce2ea; word-break: break-all; display: inline-block; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.alert-pat { color: #e5a020; font-size: 10px; }
.no-alert { color: #4e5b6e; }

.toggle-switch { position: relative; display: inline-block; width: 38px; height: 20px; cursor: pointer; }
.toggle-switch input { display: none; }
.toggle-slider { position: absolute; inset: 0; background: #1e2a38; border-radius: 10px; transition: 0.2s; }
.toggle-switch input:checked + .toggle-slider { background: #2ecc71; }
.toggle-slider::after { content: ''; position: absolute; width: 16px; height: 16px; border-radius: 50%; background: #dce2ea; top: 2px; left: 2px; transition: 0.2s; }
.toggle-switch input:checked + .toggle-slider::after { transform: translateX(18px); }

.btn-run { padding: 5px 12px; background: #1a2230; border: 1px solid #2a3a4e; color: #3b9eff; border-radius: 4px; font-size: 11px; cursor: pointer; transition: all 0.2s; font-family: inherit; }
.btn-run:hover { border-color: #3b9eff; background: rgba(59,158,255,0.08); }
.btn-run:disabled { opacity: 0.3; cursor: default; }

.results-list { display: flex; flex-direction: column; gap: 8px; }
.result-row { background: #131922; border: 1px solid #1e2a38; border-radius: 6px; padding: 12px 16px; }
.result-row.alert { border-color: rgba(240,74,74,0.3); background: rgba(240,74,74,0.03); }
.res-header { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.res-name { font-size: 13px; font-weight: 600; color: #dce2ea; }
.res-time { margin-left: auto; font-size: 10px; color: #4e5b6e; font-family: monospace; }
.res-alert-badge { font-size: 10px; font-weight: 700; color: #f04a4a; background: rgba(240,74,74,0.12); padding: 2px 8px; border-radius: 3px; }
.res-ok-badge { font-size: 10px; color: #2ecc71; background: rgba(46,204,113,0.1); padding: 2px 8px; border-radius: 3px; }
.res-output { margin: 0; font-size: 11px; color: #7c8b9e; white-space: pre-wrap; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; max-height: 200px; overflow-y: auto; line-height: 1.4; }
</style>
