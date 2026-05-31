<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import ChatPanel from '../components/chat/ChatPanel.vue'
import LangSwitcher from '../components/LangSwitcher.vue'
import SessionHistory from '../components/SessionHistory.vue'
import NotificationBell from '../components/NotificationBell.vue'
import MachineSelector from '../components/MachineSelector.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const chatStore = useChatStore()
const historyRef = ref(null)

const input = ref('')

function handleSend() {
  if (chatStore.loading) { chatStore.stopGeneration(); return }
  const content = input.value.trim()
  if (!content) return
  input.value = ''
  chatStore.sendMessage(content)
}

function handleSelectSession(sessionId) {
  chatStore.restoreSession(sessionId)
}
function handleNewSession() {
  chatStore.clearMessages()
  if (historyRef.value) historyRef.value.refresh()
}

function onMachineSelect(machine) {
  chatStore.selectedMachine = machine
}
function handleLogout() { authStore.logout(); router.push('/login') }

// Keyboard shortcut: Ctrl+Enter to send
function onKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    handleSend()
  }
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="chat-layout">
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
        <div class="version">v2.0</div>
      </div>

      <div class="sidebar-actions">
        <button class="btn-new-session" @click="handleNewSession">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M12 5v14M5 12h14" />
          </svg>
          {{ t('sidebar.newSession') }}
        </button>
      </div>

      <SessionHistory ref="historyRef" @select="handleSelectSession" />

      <div class="sidebar-nav">
        <div class="nav-label">{{ t('sidebar.agentPipeline') }}</div>
        <div class="agent-list">
          <div class="agent-item"><span class="agent-dot blue"></span><span>{{ t('agents.orchestrator') }}</span></div>
          <div class="agent-item"><span class="agent-dot cyan"></span><span>{{ t('agents.observe') }}</span></div>
          <div class="agent-item"><span class="agent-dot amber"></span><span>{{ t('agents.diagnose') }}</span></div>
          <div class="agent-item"><span class="agent-dot green"></span><span>{{ t('agents.knowledge') }}</span></div>
          <div class="agent-item"><span class="agent-dot red"></span><span>{{ t('agents.remedy') }}</span></div>
          <div class="agent-item"><span class="agent-dot purple"></span><span>{{ t('agents.verify') }}</span></div>
        </div>
      </div>

      <nav class="sidebar-links">
        <router-link to="/dashboard" class="side-link">{{ t('sidebar.dashboard') }}</router-link>
        <router-link to="/audit" class="side-link">{{ t('sidebar.audit') }}</router-link>
        <router-link to="/knowledge" class="side-link">{{ t('sidebar.knowledge') }}</router-link>
        <router-link to="/inspection" class="side-link">{{ t('sidebar.inspection') }}</router-link>
        <router-link to="/machines" class="side-link">{{ t('sidebar.machines') }}</router-link>
      </nav>

      <div class="sidebar-footer">
        <NotificationBell />
        <LangSwitcher />
        <router-link v-if="authStore.user" to="/profile" class="user-badge">
          <span class="user-avatar">{{ authStore.user.username[0].toUpperCase() }}</span>
          <span class="user-name">{{ authStore.user.username }}</span>
          <span class="user-role-badge" :class="'role-'+authStore.user.role">{{ authStore.user.role }}</span>
        </router-link>
        <button class="btn-logout" @click="handleLogout">{{ t('sidebar.logout') }}</button>
      </div>
    </aside>

    <main class="main-area">
      <ChatPanel />

      <div class="input-zone">
        <div class="input-row">
          <div class="input-top-bar">
            <MachineSelector @select="onMachineSelect" />
          </div>
          <div class="input-shell">
            <span class="prompt">$</span>
            <input
              v-model="input"
              class="cmd-input"
              :placeholder="t('chat.placeholder')"
              @keyup.enter="handleSend"
              :disabled="chatStore.loading"
            />
            <!-- Token display -->
            <span v-if="chatStore.totalTokens > 0 && !chatStore.loading" class="token-display">{{ (chatStore.totalTokens / 1000).toFixed(1) }}K tokens</span>
            <button
              class="btn-send"
              :class="{ 'btn-stop': chatStore.loading }"
              :disabled="!chatStore.loading && !input.trim()"
              @click="handleSend"
              :title="chatStore.loading ? 'Stop (Ctrl+Enter)' : 'Send (Ctrl+Enter)'"
            >
              <svg v-if="!chatStore.loading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
              <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <rect x="4" y="4" width="16" height="16" rx="2" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style>
.chat-layout {
  --bg-deep: #0b0f15; --bg-surface: #131922; --bg-raised: #1a2230;
  --border: #1e2a38; --border-active: #2a3a4e;
  --text-primary: #dce2ea; --text-secondary: #7c8b9e; --text-muted: #4e5b6e;
  --blue: #3b9eff; --amber: #e5a020; --red: #f04a4a; --green: #2ecc71;
  --cyan: #00d4aa; --muted: #6b7a8d;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
}
</style>

<style scoped>
.chat-layout { display: flex; height: 100vh; background: var(--bg-deep); color: var(--text-primary); }

/* Sidebar */
.sidebar { width: 240px; background: var(--bg-deep); border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; }
.sidebar-top { padding: 20px 20px 16px; border-bottom: 1px solid var(--border); }
.logo { display: flex; align-items: center; gap: 10px; color: var(--text-primary); margin-bottom: 4px; }
.logo span { font-size: 16px; font-weight: 700; letter-spacing: -0.02em; }
.version { font-size: 10px; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; color: var(--text-muted); letter-spacing: 0.06em; margin-left: 32px; }
.sidebar-actions { padding: 16px 20px; }
.btn-new-session { width: 100%; display: flex; align-items: center; justify-content: center; gap: 8px; background: var(--bg-raised); border: 1px solid var(--border); color: var(--text-primary); padding: 10px 0; border-radius: 6px; font-size: 12px; font-weight: 500; cursor: pointer; transition: all 0.2s; letter-spacing: 0.02em; }
.btn-new-session:hover { border-color: var(--blue); background: rgba(59, 158, 255, 0.06); color: var(--blue); }
.sidebar-nav { padding: 0 20px; flex: 1; }
.nav-label { font-size: 10px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 10px; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.agent-list { display: flex; flex-direction: column; gap: 2px; }
.agent-item { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 5px; font-size: 12.5px; color: var(--text-secondary); cursor: default; }
.agent-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.agent-dot.blue { background: var(--blue); } .agent-dot.cyan { background: var(--cyan); }
.agent-dot.amber { background: var(--amber); } .agent-dot.green { background: var(--green); }
.agent-dot.red { background: var(--red); } .agent-dot.purple { background: #a855f7; }

.sidebar-links { padding: 8px 20px 12px; display: flex; flex-direction: column; gap: 1px; }
.side-link { padding: 7px 10px; font-size: 12px; color: var(--text-muted); text-decoration: none; border-radius: 5px; transition: all 0.2s; }
.side-link:hover, .side-link.router-link-active { color: var(--text-primary); background: var(--bg-raised); }

.sidebar-footer { padding: 12px 20px; border-top: 1px solid var(--border); display: flex; align-items: center; gap: 10px; }
.user-badge { display: flex; align-items: center; gap: 8px; flex: 1; text-decoration: none; cursor: pointer; border-radius: 5px; padding: 4px 6px; transition: background 0.15s; }
.user-badge:hover { background: var(--bg-raised); }
.user-avatar { width: 26px; height: 26px; border-radius: 5px; background: var(--bg-raised); border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; color: var(--text-secondary); }
.user-name { font-size: 12px; color: var(--text-secondary); }
.user-role-badge { font-size: 9px; font-weight: 600; padding: 1px 6px; border-radius: 3px; letter-spacing: 0.04em; }
.role-superadmin { background: rgba(168,85,247,0.15); color: #a855f7; }
.role-admin { background: rgba(59,158,255,0.15); color: #3b9eff; }
.role-operator { background: rgba(229,160,32,0.15); color: #e5a020; }
.role-viewer { background: rgba(78,91,110,0.15); color: #7c8b9e; }
.btn-logout { background: none; border: none; color: var(--text-muted); font-size: 11px; cursor: pointer; transition: color 0.2s; letter-spacing: 0.03em; white-space: nowrap; }
.btn-logout:hover { color: var(--red); }

/* Main */
.main-area { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.input-zone { padding: 16px 24px 20px; background: var(--bg-deep); border-top: 1px solid var(--border); }
.input-row { max-width: 900px; margin: 0 auto; }
.input-top-bar { margin-bottom: 8px; }
.input-shell { display: flex; align-items: center; gap: 10px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px; padding: 4px 4px 4px 14px; transition: border-color 0.2s; }
.input-shell:focus-within { border-color: var(--border-active); }
.prompt { font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; font-size: 14px; color: var(--green); flex-shrink: 0; }
.cmd-input { flex: 1; background: none; border: none; outline: none; color: var(--text-primary); font-size: 13.5px; padding: 10px 0; }
.cmd-input::placeholder { color: var(--text-muted); }
.btn-send { background: none; border: 1px solid var(--border); color: var(--text-muted); width: 38px; height: 38px; border-radius: 6px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; flex-shrink: 0; }
.btn-send:hover:not(:disabled) { border-color: var(--blue); color: var(--blue); background: rgba(59, 158, 255, 0.08); }
.btn-send:disabled { opacity: 0.3; cursor: default; }
.btn-stop { border-color: rgba(240,74,74,0.4) !important; color: var(--red) !important; animation: pulse-stop 1.4s infinite; }
.btn-stop:hover { background: rgba(240,74,74,0.1) !important; }
@keyframes pulse-stop { 0%,100% { box-shadow: 0 0 0 rgba(240,74,74,0); } 50% { box-shadow: 0 0 10px rgba(240,74,74,0.3); } }
.token-display { font-size: 10px; color: #4e5b6e; font-family: 'Cascadia Code','Fira Code',monospace; white-space: nowrap; padding: 0 4px; }
</style>
