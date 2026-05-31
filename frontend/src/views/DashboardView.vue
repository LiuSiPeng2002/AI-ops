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

const overview = ref(null)
const cluster = ref(null)
const agentStatus = ref(null)
const loading = ref({ overview: true, cluster: true, agents: true })

async function fetchOverview() {
  try {
    const { data } = await api.get('/dashboard/overview')
    overview.value = data
  } catch (e) { /* pass */ }
  finally { loading.value.overview = false }
}

async function fetchCluster() {
  try {
    const { data } = await api.get('/dashboard/cluster')
    cluster.value = data
  } catch (e) { /* pass */ }
  finally { loading.value.cluster = false }
}

async function fetchAgentStatus() {
  try {
    const { data } = await api.get('/dashboard/agent-status')
    agentStatus.value = data
  } catch (e) { /* pass */ }
  finally { loading.value.agents = false }
}

let _timer = null
onMounted(() => {
  fetchOverview(); fetchCluster(); fetchAgentStatus()
  _timer = setInterval(() => { fetchOverview(); fetchCluster(); fetchAgentStatus() }, 30000)
})
import { onUnmounted } from 'vue'
onUnmounted(() => { if (_timer) clearInterval(_timer) })

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<template>
  <div class="dashboard-layout">
    <aside class="sidebar">
      <div class="sidebar-top">
        <div class="logo">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <rect x="3" y="3" width="7" height="7" rx="1.5" />
            <rect x="14" y="3" width="7" height="7" rx="1.5" />
            <rect x="3" y="14" width="7" height="7" rx="1.5" />
            <rect x="14" y="14" width="7" height="7" rx="1.5" />
          </svg>
          <span>AI-Ops</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <router-link to="/chat" class="nav-item">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <span>{{ t('sidebar.chat') }}</span>
        </router-link>
        <router-link to="/dashboard" class="nav-item active">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
          <span>{{ t('sidebar.dashboard') }}</span>
        </router-link>
        <router-link to="/audit" class="nav-item">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          <span>{{ t('sidebar.audit') }}</span>
        </router-link>
        <router-link to="/knowledge" class="nav-item">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
          <span>{{ t('sidebar.knowledge') }}</span>
        </router-link>
        <router-link to="/inspection" class="nav-item">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          <span>{{ t('sidebar.inspection') }}</span>
        </router-link>
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
        <h1>{{ t('dashboard.title') }}</h1>
        <span class="page-desc">{{ t('dashboard.desc') }}</span>
      </header>

      <div class="content-grid">
        <section class="section-full">
          <h2 class="section-title">{{ t('dashboard.sessionOverview') }}</h2>
          <div v-if="loading.overview" class="loading-skel">{{ t('dashboard.loading') }}</div>
          <div v-else-if="overview" class="stat-cards">
            <div class="stat-card">
              <div class="stat-val">{{ overview.sessions.total }}</div>
              <div class="stat-label">{{ t('dashboard.totalSessions') }}</div>
            </div>
            <div class="stat-card active">
              <div class="stat-val">{{ overview.sessions.active }}</div>
              <div class="stat-label">{{ t('dashboard.active') }}</div>
            </div>
            <div class="stat-card success">
              <div class="stat-val">{{ overview.sessions.success }}</div>
              <div class="stat-label">{{ t('dashboard.success') }}</div>
            </div>
            <div class="stat-card failed">
              <div class="stat-val">{{ overview.sessions.failed }}</div>
              <div class="stat-label">{{ t('dashboard.failed') }}</div>
            </div>
            <div class="stat-card escalated">
              <div class="stat-val">{{ overview.sessions.escalated }}</div>
              <div class="stat-label">{{ t('dashboard.escalated') }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-val">{{ overview.avg_attempts }}</div>
              <div class="stat-label">{{ t('dashboard.avgAttempts') }}</div>
            </div>
          </div>
        </section>

        <section class="section-half">
          <h2 class="section-title">{{ t('dashboard.byIntent') }}</h2>
          <div v-if="overview && overview.by_intent" class="intent-list">
            <div v-for="(cnt, intent) in overview.by_intent" :key="intent" class="intent-row">
              <span class="intent-name">{{ t(`intents.${intent}`) }}</span>
              <span class="intent-bar-bg">
                <span class="intent-bar-fill" :style="{ width: Math.min(cnt / overview.sessions.total * 100, 100) + '%' }"></span>
              </span>
              <span class="intent-cnt">{{ cnt }}</span>
            </div>
          </div>
        </section>

        <section class="section-half">
          <h2 class="section-title">{{ t('dashboard.agentActivity') }}</h2>
          <div v-if="loading.agents" class="loading-skel">{{ t('dashboard.loading') }}</div>
          <div v-else-if="agentStatus" class="agent-list">
            <div v-for="a in agentStatus.agents" :key="a.agent" class="agent-row">
              <span class="agent-dot" :class="a.active ? 'dot-on' : 'dot-off'"></span>
              <span class="agent-name">{{ a.agent }}</span>
              <span class="agent-count">{{ a.message_count }} {{ t('dashboard.msgs') }}</span>
            </div>
          </div>
        </section>

        <section class="section-full">
          <h2 class="section-title">{{ t('dashboard.clusterHealth') }}</h2>
          <div v-if="loading.cluster" class="loading-skel">{{ t('dashboard.loading') }}</div>
          <div v-else-if="cluster" class="cluster-grid">
            <div class="cluster-section">
              <h3>{{ t('dashboard.kubernetes') }}</h3>
              <div v-if="cluster.k8s.error" class="cluster-error">{{ t('dashboard.failedToQuery') }}</div>
              <div v-else>
                <div class="k8s-nodes"><pre>{{ cluster.k8s.nodes }}</pre></div>
                <div class="problem-pods">
                  <span class="pp-label">{{ t('dashboard.problemPods') }}:</span>
                  <pre>{{ cluster.k8s.problem_pods }}</pre>
                </div>
              </div>
            </div>
            <div class="cluster-section">
              <h3>{{ t('dashboard.systemResources') }}</h3>
              <div v-if="cluster.system.error" class="cluster-error">{{ t('dashboard.queryFailed') }}</div>
              <div v-else>
                <div class="sys-row"><span>{{ t('dashboard.disk') }}</span><pre>{{ cluster.system.disk }}</pre></div>
                <div class="sys-row"><span>{{ t('dashboard.memory') }}</span><pre>{{ cluster.system.memory }}</pre></div>
                <div class="sys-row"><span>{{ t('dashboard.load') }}</span><pre>{{ cluster.system.load }}</pre></div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.dashboard-layout { display: flex; height: 100vh; background: #0b0f15; color: #dce2ea; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; }
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
.page-header { margin-bottom: 28px; }
.page-header h1 { font-size: 22px; font-weight: 700; margin: 0 0 4px; letter-spacing: -0.02em; }
.page-desc { font-size: 13px; color: #7c8b9e; }
.content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.section-full { grid-column: 1 / -1; }
.section-title { font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #4e5b6e; margin: 0 0 14px; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.loading-skel { color: #4e5b6e; padding: 20px; }

.stat-cards { display: grid; grid-template-columns: repeat(6, 1fr); gap: 14px; }
.stat-card { background: #131922; border: 1px solid #1e2a38; border-radius: 8px; padding: 18px 16px; text-align: center; }
.stat-card.active { border-color: rgba(59,158,255,0.3); background: rgba(59,158,255,0.04); }
.stat-card.success { border-color: rgba(46,204,113,0.3); background: rgba(46,204,113,0.04); }
.stat-card.failed { border-color: rgba(240,74,74,0.3); background: rgba(240,74,74,0.04); }
.stat-card.escalated { border-color: rgba(229,160,32,0.3); background: rgba(229,160,32,0.04); }
.stat-val { font-size: 28px; font-weight: 700; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.stat-label { font-size: 11px; color: #7c8b9e; margin-top: 4px; }

.intent-list { display: flex; flex-direction: column; gap: 10px; }
.intent-row { display: flex; align-items: center; gap: 10px; }
.intent-name { width: 80px; font-size: 12px; color: #7c8b9e; text-transform: capitalize; }
.intent-bar-bg { flex: 1; height: 6px; background: #1a2230; border-radius: 3px; overflow: hidden; }
.intent-bar-fill { height: 100%; background: #3b9eff; border-radius: 3px; transition: width 0.5s; }
.intent-cnt { font-size: 12px; color: #dce2ea; font-weight: 600; width: 30px; text-align: right; }

.agent-list { display: flex; flex-direction: column; gap: 8px; }
.agent-row { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: #131922; border-radius: 6px; }
.agent-dot { width: 8px; height: 8px; border-radius: 50%; }
.dot-on { background: #2ecc71; box-shadow: 0 0 6px rgba(46,204,113,0.4); }
.dot-off { background: #4e5b6e; }
.agent-name { font-size: 13px; color: #dce2ea; flex: 1; text-transform: capitalize; }
.agent-count { font-size: 11px; color: #7c8b9e; }

.cluster-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.cluster-section { background: #131922; border: 1px solid #1e2a38; border-radius: 8px; padding: 16px; }
.cluster-section h3 { font-size: 13px; font-weight: 600; margin: 0 0 10px; color: #dce2ea; }
.cluster-section pre { margin: 0; font-size: 11px; color: #7c8b9e; white-space: pre-wrap; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; max-height: 200px; overflow-y: auto; }
.cluster-error { color: #f04a4a; font-size: 12px; }
.pp-label { font-size: 11px; color: #e5a020; font-weight: 600; }
.sys-row { display: flex; gap: 12px; padding: 4px 0; font-size: 12px; color: #7c8b9e; }
.sys-row span { width: 60px; font-weight: 600; color: #dce2ea; flex-shrink: 0; }
</style>
