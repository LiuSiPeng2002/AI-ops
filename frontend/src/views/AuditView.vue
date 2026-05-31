<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import api from '../api'
import LangSwitcher from '../components/LangSwitcher.vue'
import DagViewer from '../components/DagViewer.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const sessions = ref([])
const total = ref(0)
const loading = ref(false)
const selectedSession = ref(null)
const sessionDetail = ref(null)
const detailLoading = ref(false)

const filterIntent = ref('')
const filterStatus = ref('')
const pageSize = ref(50)
const pageOffset = ref(0)

// SSE Replay
const replaying = ref(false)
const replayPaused = ref(false)
const replaySpeed = ref(1)
const replayIndex = ref(0)
let replayTimer = null

const tabActive = ref('messages')

async function fetchSessions() {
  loading.value = true
  try {
    const params = { limit: pageSize.value, offset: pageOffset.value }
    if (filterIntent.value) params.intent_type = filterIntent.value
    if (filterStatus.value) params.status = filterStatus.value
    const { data } = await api.get('/audit/sessions', { params })
    sessions.value = data.items
    total.value = data.total
  } catch (e) { /* pass */ }
  finally { loading.value = false }
}

async function viewSession(sessionId) {
  detailLoading.value = true
  selectedSession.value = sessionId
  stopReplay()
  tabActive.value = 'messages'
  try {
    const { data } = await api.get(`/audit/sessions/${sessionId}`)
    sessionDetail.value = data
  } catch (e) { /* pass */ }
  finally { detailLoading.value = false }
}

function closeDetail() {
  selectedSession.value = null
  sessionDetail.value = null
  stopReplay()
}

function startReplay() {
  if (!sessionDetail.value?.messages?.length) return
  replaying.value = true
  replayPaused.value = false
  replayIndex.value = 0
  tabActive.value = 'messages'
  scheduleNext()
}
function pauseReplay() {
  replayPaused.value = !replayPaused.value
  if (!replayPaused.value) scheduleNext()
}
function stopReplay() {
  replaying.value = false; replayPaused.value = false; replayIndex.value = 0
  if (replayTimer) { clearTimeout(replayTimer); replayTimer = null }
}
function scheduleNext() {
  if (!replaying.value || replayPaused.value) return
  const msgs = sessionDetail.value?.messages || []
  if (replayIndex.value >= msgs.length) { replaying.value = false; return }
  replayTimer = setTimeout(() => { replayIndex.value++; scheduleNext() }, 800 / replaySpeed.value)
}
function getVisibleMessages() {
  const msgs = sessionDetail.value?.messages || []
  return replaying.value ? msgs.slice(0, replayIndex.value) : msgs
}

onUnmounted(() => stopReplay())

function prevPage() { if (pageOffset.value > 0) { pageOffset.value -= pageSize.value; fetchSessions() } }
function nextPage() { if (pageOffset.value + pageSize.value < total.value) { pageOffset.value += pageSize.value; fetchSessions() } }

onMounted(() => fetchSessions())

function handleLogout() { authStore.logout(); router.push('/login') }

function statusBadge(s) {
  const map = { success: 'badge-ok', failed: 'badge-err', active: 'badge-info', escalated: 'badge-warn', cancelled: 'badge-muted' }
  return map[s] || 'badge-muted'
}
function localeStatus(s) {
  const keys = { active: 'statuses.active', completed: 'statuses.completed', escalated: 'statuses.escalated', cancelled: 'statuses.cancelled', success: 'statuses.success', failed: 'statuses.failed', partial_success: 'statuses.partial_success' }
  return keys[s] ? t(keys[s]) : (s || '-')
}

const copiedId = ref('')
function copySessionId(id) {
  navigator.clipboard.writeText(id).then(() => {
    copiedId.value = id
    setTimeout(() => { copiedId.value = '' }, 2000)
  }).catch(() => { /* pass */ })
}

function exportCSV() {
  const rows = [['Session ID','Title','Intent','Status','Final','Attempts','Started']]
  for (const s of sessions.value) {
    rows.push([s.id||'', s.title||'', s.intent_type||'', s.status||'', s.final_status||'', String(s.total_attempts||0), (s.started_at||'').slice(0,16).replace('T',' ')])
  }
  const csv = rows.map(r => r.map(c => '"'+(c||'').replace(/"/g,'""')+'"').join(',')).join('\n')
  const blob = new Blob(['﻿'+csv], {type:'text/csv;charset=utf-8'})
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'audit-sessions.csv'; a.click()
}
</script>

<template>
  <div class="audit-layout">
    <aside class="sidebar">
      <div class="sidebar-top">
        <div class="logo"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg><span>AI-Ops</span></div>
      </div>
      <nav class="sidebar-nav">
        <router-link to="/chat" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span>{{ t('sidebar.chat') }}</span></router-link>
        <router-link to="/dashboard" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg><span>{{ t('sidebar.dashboard') }}</span></router-link>
        <router-link to="/audit" class="nav-item active"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg><span>{{ t('sidebar.audit') }}</span></router-link>
        <router-link to="/knowledge" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg><span>{{ t('sidebar.knowledge') }}</span></router-link>
        <router-link to="/inspection" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg><span>{{ t('sidebar.inspection') }}</span></router-link>
      </nav>
      <div class="sidebar-footer">
        <LangSwitcher />
        <router-link v-if="authStore.user" to="/profile" class="user-badge"><span class="user-avatar">{{ authStore.user.username[0].toUpperCase() }}</span><span class="user-name">{{ authStore.user.username }}</span></router-link>
        <button class="btn-logout" @click="handleLogout">{{ t('sidebar.logout') }}</button>
      </div>
    </aside>

    <main class="main-area">
      <header class="page-header"><h1>{{ t('audit.title') }}</h1><span class="page-desc">{{ t('audit.desc') }}</span></header>

      <div class="filter-bar">
        <select v-model="filterIntent" @change="pageOffset=0;fetchSessions()" class="filter-select">
          <option value="">{{ t('audit.allIntents') }}</option>
          <option value="diagnosis">{{ t('intents.diagnosis') }}</option>
          <option value="change">{{ t('intents.change') }}</option>
          <option value="inquiry">{{ t('intents.inquiry') }}</option>
        </select>
        <select v-model="filterStatus" @change="pageOffset=0;fetchSessions()" class="filter-select">
          <option value="">{{ t('audit.allStatus') }}</option>
          <option value="active">{{ t('statuses.active') }}</option>
          <option value="completed">{{ t('statuses.completed') }}</option>
          <option value="escalated">{{ t('statuses.escalated') }}</option>
          <option value="cancelled">{{ t('statuses.cancelled') }}</option>
        </select>
        <button @click="fetchSessions" class="btn-refresh">{{ t('audit.refresh') }}</button>
        <button @click="exportCSV" class="btn-export">{{ t('audit.export') }}</button>
      </div>

      <div class="table-wrap">
        <table class="sessions-table">
          <thead><tr><th>{{ t('audit.sessionId') }}</th><th>{{ t('audit.title2') }}</th><th>{{ t('audit.intent') }}</th><th>{{ t('audit.status') }}</th><th>{{ t('audit.final') }}</th><th>{{ t('audit.attempts') }}</th><th>{{ t('audit.started') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="s in sessions" :key="s.id" class="session-row">
              <td class="sid-cell">
                <code>{{ (s.id || '').slice(0, 8) }}...</code>
                <button class="btn-copy" @click.stop="copySessionId(s.id)" :title="copiedId === s.id ? 'Copied!' : 'Copy'">
                  <svg v-if="copiedId !== s.id" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                  <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#2ecc71" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                </button>
              </td>
              <td>{{ s.title || '-' }}</td>
              <td>{{ s.intent_type ? t(`intents.${s.intent_type}`) : '-' }}</td>
              <td><span class="status-badge" :class="statusBadge(s.status)">{{ localeStatus(s.status) }}</span></td>
              <td><span class="status-badge" :class="statusBadge(s.final_status)">{{ localeStatus(s.final_status) }}</span></td>
              <td>{{ s.total_attempts || 0 }}</td>
              <td class="mono time-cell">{{ s.started_at ? s.started_at.slice(0, 16).replace('T', ' ') : '-' }}</td>
              <td><button class="btn-view" @click="viewSession(s.id)">{{ t('audit.view') }}</button></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="pager">
        <button :disabled="pageOffset === 0" @click="prevPage" class="btn-page">{{ t('audit.previous') }}</button>
        <span class="page-info">{{ pageOffset + 1 }}–{{ Math.min(pageOffset + pageSize, total) }} {{ t('audit.of') }} {{ total }}</span>
        <button :disabled="pageOffset + pageSize >= total" @click="nextPage" class="btn-page">{{ t('audit.next') }}</button>
      </div>

      <!-- Detail Drawer -->
      <div v-if="selectedSession" class="detail-overlay" @click.self="closeDetail">
        <div class="detail-panel">
          <div class="detail-header">
            <div>
              <h3>{{ sessionDetail?.title || t('audit.sessionId') + ' ' + (selectedSession || '').slice(0, 8) }}</h3>
              <span class="detail-meta-text">{{ (selectedSession || '').slice(0, 12) }} &middot; {{ sessionDetail?.started_at ? sessionDetail.started_at.slice(0, 16).replace('T', ' ') : '' }}</span>
              <button class="btn-copy-sm" @click.stop="copySessionId(selectedSession)" :title="copiedId === selectedSession ? 'Copied!' : 'Copy session ID'">
                <svg v-if="copiedId !== selectedSession" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                <svg v-else width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#2ecc71" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              </button>
            </div>
            <div class="detail-tabs">
              <button :class="{ active: tabActive === 'messages' }" @click="tabActive = 'messages'">{{ t('audit.messages') }}</button>
              <button :class="{ active: tabActive === 'dag' }" @click="tabActive = 'dag'">{{ t('audit.dagView') }}</button>
              <button @click="closeDetail" class="btn-close">X</button>
            </div>
          </div>

          <div v-if="detailLoading" class="detail-loading">{{ t('audit.loading') }}</div>
          <div v-else-if="sessionDetail" class="detail-body">
            <!-- DAG Tab -->
            <div v-if="tabActive === 'dag'" class="dag-panel">
              <DagViewer :session="sessionDetail" :width="660" :height="340" />
            </div>

            <!-- Messages Tab with Replay -->
            <div v-else class="msg-panel">
              <div class="detail-meta">
                <div><strong>{{ t('audit.title3') }}:</strong> {{ sessionDetail.title }}</div>
                <div><strong>{{ t('audit.intent') }}:</strong> {{ sessionDetail.intent_type ? t(`intents.${sessionDetail.intent_type}`) : '-' }}</div>
                <div><strong>{{ t('audit.status') }}:</strong> {{ localeStatus(sessionDetail.final_status) }}</div>
                <div><strong>{{ t('audit.attempts') }}:</strong> {{ sessionDetail.total_attempts }}</div>
              </div>

              <!-- Replay Controls -->
              <div class="replay-bar" v-if="sessionDetail.messages?.length">
                <button v-if="!replaying" class="replay-btn play" @click="startReplay()">&#9654; {{ t('audit.play') }}</button>
                <button v-else class="replay-btn pause" @click="pauseReplay()">{{ replayPaused ? '&#9654;' : '&#10074;&#10074;' }} {{ replayPaused ? t('audit.play') : t('audit.pause') }}</button>
                <button v-if="replaying" class="replay-btn stop" @click="stopReplay()">&#9632; {{ t('audit.stop') }}</button>
                <span class="speed-label">{{ t('audit.speed') }}:</span>
                <select v-model.number="replaySpeed" class="speed-select"><option :value="0.5">0.5x</option><option :value="1">1x</option><option :value="2">2x</option><option :value="5">5x</option></select>
                <div v-if="replaying" class="replay-progress">
                  <div class="progress-bar"><div class="progress-fill" :style="{ width: (replayIndex / sessionDetail.messages.length * 100) + '%' }"></div></div>
                  <span class="progress-text">{{ replayIndex }} / {{ sessionDetail.messages.length }}</span>
                </div>
              </div>

              <div class="detail-msgs">
                <div v-for="(m, i) in getVisibleMessages()" :key="m.id || i" class="msg-item">
                  <div class="msg-head">
                    <span class="msg-role" :class="'role-' + m.role">{{ m.role }}</span>
                    <span v-if="m.agent_name" class="msg-agent">{{ m.agent_name }}</span>
                    <span class="msg-type">{{ m.message_type }}</span>
                    <span class="msg-seq">#{{ m.sequence_num || i+1 }}</span>
                  </div>
                  <pre class="msg-content">{{ typeof m.content === 'string' ? m.content : JSON.stringify(m.content, null, 2) }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.audit-layout { display: flex; height: 100vh; background: #0b0f15; color: #dce2ea; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; }
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
.page-header h1 { font-size: 22px; font-weight: 700; margin: 0 0 4px; letter-spacing: -0.02em; }
.page-desc { font-size: 13px; color: #7c8b9e; }

.filter-bar { display: flex; gap: 12px; margin-bottom: 20px; }
.filter-select { background: #1a2230; border: 1px solid #2a3a4e; color: #dce2ea; padding: 8px 14px; border-radius: 6px; font-size: 12px; outline: none; cursor: pointer; }
.filter-select:focus { border-color: #3b9eff; }
.btn-refresh { background: #1a2230; border: 1px solid #2a3a4e; color: #dce2ea; padding: 8px 18px; border-radius: 6px; font-size: 12px; cursor: pointer; transition: all 0.2s; }
.btn-refresh:hover { border-color: #3b9eff; color: #3b9eff; }

.table-wrap { background: #131922; border: 1px solid #1e2a38; border-radius: 8px; overflow: hidden; }
.sessions-table { width: 100%; border-collapse: collapse; }
.sessions-table th { text-align: left; padding: 12px 14px; font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #4e5b6e; border-bottom: 1px solid #1e2a38; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.sessions-table td { padding: 10px 14px; font-size: 12.5px; color: #dce2ea; border-bottom: 1px solid rgba(30,42,56,0.5); }
.session-row { cursor: pointer; transition: background 0.15s; }
.session-row:hover { background: rgba(59,158,255,0.04); }
.mono { font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; font-size: 11px; }
.sid-cell { display: flex; align-items: center; gap: 6px; }
.sid-cell code { font-size: 11px; color: #00d4aa; background: #131922; padding: 2px 6px; border-radius: 3px; }
.btn-copy { background: none; border: none; color: #4e5b6e; cursor: pointer; padding: 2px; display: flex; align-items: center; border-radius: 3px; transition: all 0.15s; flex-shrink: 0; }
.btn-copy:hover { color: #3b9eff; background: rgba(59,158,255,0.08); }
.btn-copy-sm { background: none; border: 1px solid #2a3a4e; color: #4e5b6e; cursor: pointer; padding: 3px 6px; display: flex; align-items: center; border-radius: 4px; transition: all 0.15s; flex-shrink: 0; margin-left: 8px; }
.btn-copy-sm:hover { color: #3b9eff; border-color: #3b9eff; background: rgba(59,158,255,0.06); }
.time-cell { color: #7c8b9e !important; }
.btn-view { padding: 4px 12px; background: #1a2230; border: 1px solid #2a3a4e; color: #3b9eff; border-radius: 4px; font-size: 11px; cursor: pointer; }
.btn-view:hover { border-color: #3b9eff; }

.status-badge { font-size: 10px; font-weight: 700; letter-spacing: 0.05em; padding: 2px 8px; border-radius: 3px; text-transform: uppercase; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.badge-ok { background: rgba(46,204,113,0.15); color: #2ecc71; }
.badge-err { background: rgba(240,74,74,0.15); color: #f04a4a; }
.badge-info { background: rgba(59,158,255,0.15); color: #3b9eff; }
.badge-warn { background: rgba(229,160,32,0.15); color: #e5a020; }
.badge-muted { background: rgba(78,91,110,0.15); color: #7c8b9e; }

.pager { display: flex; align-items: center; justify-content: center; gap: 16px; padding: 16px 0; }
.btn-page { background: #1a2230; border: 1px solid #2a3a4e; color: #dce2ea; padding: 6px 16px; border-radius: 5px; font-size: 12px; cursor: pointer; transition: all 0.2s; }
.btn-page:disabled { opacity: 0.3; cursor: default; }
.btn-page:hover:not(:disabled) { border-color: #3b9eff; color: #3b9eff; }
.page-info { font-size: 12px; color: #7c8b9e; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }

/* Detail Drawer */
.detail-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); z-index: 100; display: flex; justify-content: flex-end; }
.detail-panel { width: 780px; max-width: 92vw; background: #131922; border-left: 1px solid #2a3a4e; height: 100vh; overflow-y: auto; display: flex; flex-direction: column; }
.detail-header { display: flex; justify-content: space-between; align-items: flex-start; padding: 20px 24px; border-bottom: 1px solid #1e2a38; }
.detail-header h3 { margin: 0 0 4px; font-size: 16px; color: #dce2ea; }
.detail-meta-text { font-size: 11px; color: #4e5b6e; }
.detail-tabs { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.detail-tabs button { padding: 5px 12px; background: #1a2230; border: 1px solid #2a3a4e; color: #7c8b9e; border-radius: 4px; font-size: 11px; cursor: pointer; transition: all 0.2s; }
.detail-tabs button.active { background: #3b9eff; color: #fff; border-color: #3b9eff; }
.btn-close { padding: 5px 10px !important; font-size: 13px !important; background: none !important; border: none !important; color: #7c8b9e !important; cursor: pointer; }
.btn-close:hover { color: #f04a4a !important; }
.detail-loading { padding: 24px; color: #7c8b9e; }
.detail-body { padding: 20px 24px; }
.detail-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12.5px; color: #7c8b9e; margin-bottom: 16px; }
.detail-meta strong { color: #dce2ea; }

.dag-panel { display: flex; justify-content: center; padding-top: 10px; }

/* Replay Bar */
.replay-bar { display: flex; align-items: center; gap: 8px; padding: 10px 14px; background: #0b0f15; border: 1px solid #1e2a38; border-radius: 6px; margin-bottom: 16px; flex-wrap: wrap; }
.replay-btn { padding: 4px 12px; border-radius: 4px; font-size: 11px; cursor: pointer; border: 1px solid #2a3a4e; background: #1a2230; color: #dce2ea; transition: all 0.2s; font-family: inherit; }
.replay-btn.play:hover { border-color: #2ecc71; color: #2ecc71; }
.replay-btn.pause:hover { border-color: #e5a020; color: #e5a020; }
.replay-btn.stop:hover { border-color: #f04a4a; color: #f04a4a; }
.speed-label { font-size: 11px; color: #7c8b9e; margin-left: 6px; }
.speed-select { background: #1a2230; border: 1px solid #2a3a4e; color: #dce2ea; padding: 3px 6px; border-radius: 3px; font-size: 11px; outline: none; }
.replay-progress { flex: 1; display: flex; align-items: center; gap: 8px; margin-left: 6px; }
.progress-bar { flex: 1; height: 4px; background: #1e2a38; border-radius: 2px; overflow: hidden; }
.progress-fill { height: 100%; background: #3b9eff; border-radius: 2px; transition: width 0.3s; }
.progress-text { font-size: 10px; color: #7c8b9e; font-family: monospace; white-space: nowrap; }

.detail-msgs { display: flex; flex-direction: column; gap: 10px; }
.msg-item { background: #0b0f15; border: 1px solid #1e2a38; border-radius: 6px; padding: 12px; }
.msg-head { display: flex; gap: 10px; margin-bottom: 8px; font-size: 11px; align-items: center; }
.msg-role { font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; padding: 1px 6px; border-radius: 3px; font-size: 10px; }
.role-user { background: rgba(59,158,255,0.15); color: #3b9eff; }
.role-agent { background: rgba(0,212,170,0.15); color: #00d4aa; }
.role-system { background: rgba(78,91,110,0.15); color: #7c8b9e; }
.msg-agent { color: #00d4aa; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.msg-type { color: #7c8b9e; }
.msg-seq { color: #4e5b6e; margin-left: auto; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.msg-content { margin: 0; font-size: 11px; color: #7c8b9e; white-space: pre-wrap; word-break: break-all; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; max-height: 200px; overflow-y: auto; }
</style>
