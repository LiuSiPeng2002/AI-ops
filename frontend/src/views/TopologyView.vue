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

const graph = ref({ nodes: [], edges: [] })
const loading = ref(true)
const blastService = ref('')
const blastResult = ref(null)

const W = 800, H = 500

async function fetchTopology() {
  loading.value = true
  try {
    const { data } = await api.get('/topology')
    graph.value = data
  } catch (e) { /* pass */ }
  finally { loading.value = false }
}

async function checkBlast() {
  if (!blastService.value.trim()) return
  try {
    const { data } = await api.get(`/topology/blast-radius/${blastService.value}`)
    blastResult.value = data
  } catch (e) { /* pass */ }
}

function nodePos(nodes, idx) {
  const n = nodes.length || 1
  const angle = (idx / n) * 2 * Math.PI - Math.PI / 2
  const cx = W / 2 + Math.cos(angle) * (W * 0.35)
  const cy = H / 2 + Math.sin(angle) * (H * 0.35)
  return { cx, cy }
}

function edgePath(e, nodes) {
  const from = nodes.find(n => n.id === e.from)
  const to = nodes.find(n => n.id === e.to)
  if (!from || !to) return ''
  const fi = nodes.indexOf(from), ti = nodes.indexOf(to)
  const f = nodePos(nodes, fi), t = nodePos(nodes, ti)
  return `M ${f.cx} ${f.cy} C ${(f.cx+t.cx)/2} ${f.cy}, ${(f.cx+t.cx)/2} ${t.cy}, ${t.cx} ${t.cy}`
}

onMounted(() => fetchTopology())

function handleLogout() { authStore.logout(); router.push('/login') }
</script>

<template>
  <div class="topo-layout">
    <aside class="sidebar">
      <div class="sidebar-top"><div class="logo"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg><span>AI-Ops</span></div></div>
      <nav class="sidebar-nav">
        <router-link to="/chat" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span>{{ t('sidebar.chat') }}</span></router-link>
        <router-link to="/topology" class="nav-item active"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="5" r="3"/><circle cx="5" cy="19" r="3"/><circle cx="19" cy="19" r="3"/><line x1="10.5" y1="7.5" x2="6.5" y2="16.5"/><line x1="13.5" y1="7.5" x2="17.5" y2="16.5"/><line x1="8" y1="19" x2="16" y2="19"/></svg><span>{{ t('sidebar.topology') }}</span></router-link>
      </nav>
      <div class="sidebar-footer"><LangSwitcher /><router-link v-if="authStore.user" to="/profile" class="user-badge"><span class="user-avatar">{{ authStore.user.username[0].toUpperCase() }}</span><span class="user-name">{{ authStore.user.username }}</span></router-link><button class="btn-logout" @click="handleLogout">{{ t('sidebar.logout') }}</button></div>
    </aside>

    <main class="main-area">
      <header class="page-header"><h1>{{ t('topology.title') }}</h1><span class="page-desc">{{ t('topology.desc') }}</span></header>

      <div class="content-grid">
        <section class="graph-section">
          <h2 class="sec-title">{{ t('topology.dependencyGraph') }}</h2>
          <div v-if="loading" class="loading-text">{{ t('topology.loading') }}</div>
          <div v-else-if="graph.nodes.length === 0" class="empty-hint">{{ t('topology.empty') }}</div>
          <svg v-else :width="W" :height="H" class="topo-svg">
            <defs><marker id="arrowTopo" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#2a3a4e" /></marker></defs>
            <g v-for="(e, i) in graph.edges" :key="'e'+i">
              <path :d="edgePath(e, graph.nodes)" fill="none" stroke="#1e2a38" stroke-width="1.5" marker-end="url(#arrowTopo)" />
            </g>
            <g v-for="(n, i) in graph.nodes" :key="n.id">
              <circle :cx="nodePos(graph.nodes, i).cx" :cy="nodePos(graph.nodes, i).cy" r="24" fill="rgba(59,158,255,0.08)" stroke="#3b9eff" stroke-width="2" />
              <text :x="nodePos(graph.nodes, i).cx" :y="nodePos(graph.nodes, i).cy+2" text-anchor="middle" dominant-baseline="central" fill="#dce2ea" font-size="9" font-family="'Cascadia Code','Fira Code',monospace">{{ n.label }}</text>
            </g>
          </svg>
        </section>

        <section class="blast-section">
          <h2 class="sec-title">{{ t('topology.blastRadius') }}</h2>
          <div class="blast-row">
            <input v-model="blastService" class="form-input" :placeholder="t('topology.blastPlaceholder')" @keyup.enter="checkBlast" />
            <button class="btn-primary" @click="checkBlast">{{ t('topology.check') }}</button>
          </div>
          <div v-if="blastResult" class="blast-result">
            <div class="blast-header">{{ t('topology.blastResult') }} <strong>{{ blastResult.service }}</strong></div>
            <div class="blast-count">{{ t('topology.affectedCount') }}: {{ blastResult.total_affected }}</div>
            <div v-if="blastResult.affected_services.length" class="blast-list">
              <span v-for="s in blastResult.affected_services" :key="s" class="blast-tag">{{ s }}</span>
            </div>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.topo-layout { display: flex; height: 100vh; background: #0b0f15; color: #dce2ea; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; }
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
.content-grid { display: grid; grid-template-columns: 1fr; gap: 20px; }
.sec-title { font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #4e5b6e; margin: 0 0 14px; font-family: 'Cascadia Code','Fira Code',monospace; }
.graph-section { background: #131922; border: 1px solid #1e2a38; border-radius: 8px; padding: 20px; }
.topo-svg { display: block; margin: 0 auto; }
.loading-text, .empty-hint { color: #4e5b6e; text-align: center; padding: 40px; }
.blast-section { background: #131922; border: 1px solid #1e2a38; border-radius: 8px; padding: 20px; }
.blast-row { display: flex; gap: 10px; }
.form-input { flex: 1; padding: 8px 12px; background: #0b0f15; border: 1px solid #2a3a4e; color: #dce2ea; border-radius: 5px; font-size: 13px; outline: none; }
.form-input:focus { border-color: #3b9eff; }
.btn-primary { padding: 8px 16px; background: #3b9eff; color: #fff; border: none; border-radius: 5px; font-size: 12px; cursor: pointer; }
.blast-result { margin-top: 14px; padding-top: 14px; border-top: 1px solid #1e2a38; }
.blast-header { font-size: 13px; margin-bottom: 6px; }
.blast-count { font-size: 12px; color: #e5a020; margin-bottom: 8px; }
.blast-list { display: flex; flex-wrap: wrap; gap: 6px; }
.blast-tag { background: rgba(240,74,74,0.1); border: 1px solid rgba(240,74,74,0.2); color: #f04a4a; padding: 3px 10px; border-radius: 4px; font-size: 11px; }
</style>
