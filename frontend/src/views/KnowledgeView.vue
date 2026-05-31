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

const searchQuery = ref('')
const searchLimit = ref(5)
const searchResults = ref([])
const searching = ref(false)

const documents = ref([])
const docTotal = ref(0)
const listLoading = ref(false)

const uploadTitle = ref('')
const uploadContent = ref('')
const uploadTags = ref('')
const uploading = ref(false)

const autoSessionId = ref('')
const generating = ref(false)

async function doSearch() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  try {
    const { data } = await api.post('/knowledge/search', {
      query: searchQuery.value,
      limit: searchLimit.value,
    })
    searchResults.value = data.results
  } catch (e) { /* pass */ }
  finally { searching.value = false }
}

async function fetchDocuments() {
  listLoading.value = true
  try {
    const { data } = await api.get('/knowledge/list', { params: { limit: 100 } })
    documents.value = data.items
    docTotal.value = data.total
  } catch (e) { /* pass */ }
  finally { listLoading.value = false }
}

async function doUpload() {
  if (!uploadContent.value.trim()) return
  uploading.value = true
  try {
    await api.post('/knowledge/upload', {
      title: uploadTitle.value,
      content: uploadContent.value,
      source: 'manual',
      tags: uploadTags.value.split(',').map(t => t.trim()).filter(Boolean),
    })
    uploadTitle.value = ''
    uploadContent.value = ''
    uploadTags.value = ''
    await fetchDocuments()
  } catch (e) { /* pass */ }
  finally { uploading.value = false }
}

async function doDelete(docId) {
  try {
    await api.delete(`/knowledge/${docId}`)
    await fetchDocuments()
  } catch (e) { /* pass */ }
}

async function doAutoGenerate() {
  if (!autoSessionId.value.trim()) return
  generating.value = true
  try {
    await api.post('/knowledge/auto-generate', { session_id: autoSessionId.value })
    autoSessionId.value = ''
    await fetchDocuments()
  } catch (e) { /* pass */ }
  finally { generating.value = false }
}

onMounted(() => fetchDocuments())

function handleLogout() { authStore.logout(); router.push('/login') }

function scoreColor(s) {
  if (s >= 0.8) return '#2ecc71'
  if (s >= 0.5) return '#e5a020'
  return '#7c8b9e'
}
</script>

<template>
  <div class="kb-layout">
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
        <router-link to="/knowledge" class="nav-item active"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg><span>{{ t('sidebar.knowledge') }}</span></router-link>
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
        <h1>{{ t('knowledge.title') }}</h1>
        <span class="page-desc">{{ t('knowledge.desc') }}</span>
      </header>

      <div class="content-grid">
        <section class="section-full">
          <h2 class="section-title">{{ t('knowledge.semanticSearch') }}</h2>
          <div class="search-row">
            <input v-model="searchQuery" class="search-input" :placeholder="t('knowledge.searchPlaceholder')" @keyup.enter="doSearch" />
            <select v-model.number="searchLimit" class="filter-select">
              <option :value="5">5</option><option :value="10">10</option><option :value="20">20</option>
            </select>
            <button @click="doSearch" :disabled="searching" class="btn-search">{{ t('knowledge.search') }}</button>
          </div>
          <div v-if="searchResults.length" class="search-results">
            <div v-for="r in searchResults" :key="r.id" class="result-card">
              <div class="result-header">
                <span class="result-id">{{ r.id }}</span>
                <span class="result-score" :style="{ color: scoreColor(r.score) }">{{ t('knowledge.score') }}: {{ r.score }}</span>
              </div>
              <div class="result-content">{{ r.content }}</div>
              <div v-if="r.metadata" class="result-meta">
                <span v-if="r.metadata.title" class="meta-tag">{{ r.metadata.title }}</span>
                <span v-if="r.metadata.source" class="meta-tag">{{ r.metadata.source }}</span>
              </div>
            </div>
          </div>
        </section>

        <section class="section-half">
          <h2 class="section-title">{{ t('knowledge.manualUpload') }}</h2>
          <div class="upload-form">
            <input v-model="uploadTitle" class="form-input" :placeholder="t('knowledge.docTitle')" />
            <textarea v-model="uploadContent" class="form-textarea" :placeholder="t('knowledge.docContent')" rows="6"></textarea>
            <div class="form-row">
              <input v-model="uploadTags" class="form-input flex-1" :placeholder="t('knowledge.tags')" />
              <button @click="doUpload" :disabled="uploading" class="btn-primary">
                {{ uploading ? t('knowledge.uploading') : t('knowledge.upload') }}
              </button>
            </div>
          </div>
        </section>

        <section class="section-half">
          <h2 class="section-title">{{ t('knowledge.autoGenerate') }}</h2>
          <div class="auto-form">
            <input v-model="autoSessionId" class="form-input" :placeholder="t('knowledge.sessionId')" />
            <button @click="doAutoGenerate" :disabled="generating" class="btn-primary" style="margin-top:10px;">
              {{ generating ? t('knowledge.generating') : t('knowledge.generateCase') }}
            </button>
            <p class="help-text">{{ t('knowledge.autoHelp') }}</p>
          </div>
        </section>

        <section class="section-full">
          <h2 class="section-title">{{ t('knowledge.allDocs') }} ({{ docTotal }})</h2>
          <div class="doc-list">
            <div v-for="doc in documents" :key="doc.id" class="doc-row">
              <div class="doc-main">
                <div class="doc-title">{{ doc.metadata?.title || doc.id }}</div>
                <div class="doc-content">{{ doc.content }}</div>
                <div class="doc-meta">
                  <span v-if="doc.metadata?.source" class="meta-tag">{{ doc.metadata.source }}</span>
                  <span v-if="doc.metadata?.intent_type" class="meta-tag">{{ doc.metadata.intent_type }}</span>
                </div>
              </div>
              <button @click="doDelete(doc.id)" class="btn-delete">{{ t('knowledge.delete') }}</button>
            </div>
            <div v-if="!listLoading && documents.length === 0" class="empty-hint">{{ t('knowledge.empty') }}</div>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.kb-layout { display: flex; height: 100vh; background: #0b0f15; color: #dce2ea; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; }
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
.content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.section-full { grid-column: 1 / -1; }
.section-title { font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #4e5b6e; margin: 0 0 14px; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }

.search-row { display: flex; gap: 10px; }
.search-input { flex: 1; background: #131922; border: 1px solid #1e2a38; color: #dce2ea; padding: 10px 14px; border-radius: 6px; font-size: 13px; outline: none; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.search-input:focus { border-color: #3b9eff; }
.filter-select { background: #1a2230; border: 1px solid #2a3a4e; color: #dce2ea; padding: 8px 14px; border-radius: 6px; font-size: 12px; outline: none; cursor: pointer; width: 100px; }
.btn-search { background: #3b9eff; color: #fff; border: none; padding: 10px 22px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
.btn-search:hover { background: #2d8aef; }
.btn-search:disabled { opacity: 0.5; }
.search-results { margin-top: 14px; display: flex; flex-direction: column; gap: 10px; }
.result-card { background: #131922; border: 1px solid #1e2a38; border-radius: 6px; padding: 14px; }
.result-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
.result-id { font-size: 11px; color: #4e5b6e; font-family: monospace; }
.result-score { font-size: 11px; font-weight: 600; font-family: monospace; }
.result-content { font-size: 12.5px; color: #dce2ea; white-space: pre-wrap; line-height: 1.5; margin-bottom: 6px; }
.result-meta { display: flex; gap: 12px; }
.meta-tag { font-size: 10px; color: #7c8b9e; background: #0b0f15; padding: 2px 8px; border-radius: 3px; }

.upload-form, .auto-form { display: flex; flex-direction: column; gap: 10px; }
.form-input { background: #131922; border: 1px solid #1e2a38; color: #dce2ea; padding: 10px 14px; border-radius: 6px; font-size: 13px; outline: none; }
.form-input:focus { border-color: #3b9eff; }
.form-textarea { background: #131922; border: 1px solid #1e2a38; color: #dce2ea; padding: 10px 14px; border-radius: 6px; font-size: 13px; outline: none; resize: vertical; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.form-textarea:focus { border-color: #3b9eff; }
.form-row { display: flex; gap: 10px; }
.flex-1 { flex: 1; }
.btn-primary { background: #3b9eff; color: #fff; border: none; padding: 10px 22px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s; white-space: nowrap; }
.btn-primary:hover { background: #2d8aef; }
.btn-primary:disabled { opacity: 0.5; }
.help-text { font-size: 11px; color: #4e5b6e; margin: 6px 0 0; line-height: 1.4; }

.doc-list { display: flex; flex-direction: column; gap: 8px; }
.doc-row { display: flex; align-items: flex-start; gap: 12px; background: #131922; border: 1px solid #1e2a38; border-radius: 6px; padding: 12px 16px; }
.doc-main { flex: 1; min-width: 0; }
.doc-title { font-size: 13px; font-weight: 600; color: #dce2ea; margin-bottom: 4px; }
.doc-content { font-size: 11.5px; color: #7c8b9e; white-space: pre-wrap; line-height: 1.45; max-height: 60px; overflow: hidden; }
.doc-meta { display: flex; gap: 8px; margin-top: 6px; }
.btn-delete { background: none; border: 1px solid rgba(240,74,74,0.3); color: #f04a4a; padding: 6px 14px; border-radius: 5px; font-size: 11px; cursor: pointer; transition: all 0.2s; flex-shrink: 0; margin-top: 4px; }
.btn-delete:hover { background: rgba(240,74,74,0.1); border-color: #f04a4a; }
.empty-hint { color: #4e5b6e; font-size: 12px; text-align: center; padding: 24px 0; }
</style>
