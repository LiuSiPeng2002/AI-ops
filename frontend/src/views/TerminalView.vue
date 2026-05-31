<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import { Terminal } from 'xterm'
import { FitAddon } from '@xterm/addon-fit'
import 'xterm/css/xterm.css'
import LangSwitcher from '../components/LangSwitcher.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const terminalEl = ref(null)
let term = null
let ws = null
const commandHistory = ref([])
const historyIdx = ref(-1)
const currentInput = ref('')

function initTerminal() {
  const fitAddon = new FitAddon()
  term = new Terminal({
    cursorBlink: true,
    fontSize: 13,
    fontFamily: "'Cascadia Code','Fira Code','JetBrains Mono','Consolas',monospace",
    theme: {
      background: '#0b0f15',
      foreground: '#dce2ea',
      cursor: '#3b9eff',
      selectionBackground: 'rgba(59,158,255,0.3)',
      green: '#2ecc71',
      red: '#f04a4a',
      yellow: '#e5a020',
      cyan: '#00d4aa',
    },
  })
  term.loadAddon(fitAddon)
  term.open(terminalEl.value)
  fitAddon.fit()

  term.writeln('\x1b[1;36m╔══════════════════════════════════════╗\x1b[0m')
  term.writeln('\x1b[1;36m║   AI-Ops Web Terminal v2.0          ║\x1b[0m')
  term.writeln('\x1b[1;36m║   Type commands to interact         ║\x1b[0m')
  term.writeln('\x1b[1;36m╚══════════════════════════════════════╝\x1b[0m')
  term.writeln('')

  // Connect WebSocket
  const token = localStorage.getItem('access_token')
  const wsUrl = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/terminal/ws?token=${token}`
  ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    term.writeln('\x1b[32m✓ Connected\x1b[0m\n')
    promptLine()
  }

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.error) {
        term.writeln(`\x1b[31m${msg.error}\x1b[0m`)
      }
      if (msg.output) {
        term.writeln(msg.output)
      }
      promptLine()
    } catch (e) {
      term.writeln(event.data)
    }
  }

  ws.onclose = () => {
    term.writeln('\n\x1b[33mConnection closed\x1b[0m')
  }

  ws.onerror = () => {
    term.writeln('\x1b[31mWebSocket error\x1b[0m')
  }

  // Handle keyboard input
  let inputLine = ''
  term.onData((data) => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return

    if (data === '\r') {
      // Enter — send command
      term.writeln('')
      const cmd = inputLine.trim()
      if (cmd) {
        commandHistory.value.push(cmd)
        historyIdx.value = commandHistory.value.length
        if (cmd === 'clear' || cmd === 'cls') {
          term.clear()
          inputLine = ''
          promptLine()
          return
        }
        if (cmd === 'exit') {
          ws.close()
          return
        }
        ws.send(JSON.stringify({ command: cmd, type: 'linux' }))
      } else {
        promptLine()
      }
      inputLine = ''
    } else if (data === '\x7f') {
      // Backspace
      if (inputLine.length > 0) {
        inputLine = inputLine.slice(0, -1)
        term.write('\b \b')
      }
    } else if (data === '\x1b[A') {
      // Up arrow — history
      if (commandHistory.value.length > 0 && historyIdx.value > 0) {
        historyIdx.value--
        const hist = commandHistory.value[historyIdx.value]
        clearLine(inputLine)
        inputLine = hist
        term.write(hist)
      }
    } else if (data === '\x1b[B') {
      // Down arrow — history
      if (historyIdx.value < commandHistory.value.length - 1) {
        historyIdx.value++
        const hist = commandHistory.value[historyIdx.value]
        clearLine(inputLine)
        inputLine = hist
        term.write(hist)
      } else {
        historyIdx.value = commandHistory.value.length
        clearLine(inputLine)
        inputLine = ''
      }
    } else if (data.length === 1 && data.charCodeAt(0) >= 32) {
      inputLine += data
      term.write(data)
    }
  })
}

function promptLine() {
  term.write('\x1b[32m$ \x1b[0m')
}

function clearLine(str) {
  term.write('\r\x1b[K\x1b[32m$ \x1b[0m')
}

onMounted(() => {
  nextTick(() => initTerminal())
})

onUnmounted(() => {
  if (ws) ws.close()
  if (term) term.dispose()
})

function handleLogout() { authStore.logout(); router.push('/login') }
</script>

<template>
  <div class="term-layout">
    <aside class="sidebar">
      <div class="sidebar-top"><div class="logo"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg><span>AI-Ops</span></div></div>
      <nav class="sidebar-nav">
        <router-link to="/chat" class="nav-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span>{{ t('sidebar.chat') }}</span></router-link>
        <router-link to="/terminal" class="nav-item active"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg><span>{{ t('sidebar.terminal') }}</span></router-link>
      </nav>
      <div class="sidebar-footer"><LangSwitcher /><router-link v-if="authStore.user" to="/profile" class="user-badge"><span class="user-avatar">{{ authStore.user.username[0].toUpperCase() }}</span><span class="user-name">{{ authStore.user.username }}</span></router-link><button class="btn-logout" @click="handleLogout">{{ t('sidebar.logout') }}</button></div>
    </aside>

    <main class="main-area">
      <div ref="terminalEl" class="terminal-container"></div>
    </main>
  </div>
</template>

<style scoped>
.term-layout { display: flex; height: 100vh; background: #0b0f15; color: #dce2ea; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; }
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
.main-area { flex: 1; padding: 0; min-width: 0; overflow: hidden; }
.terminal-container { height: 100%; }
.terminal-container :deep(.xterm) { height: 100%; padding: 12px; }
.terminal-container :deep(.xterm-viewport) { scrollbar-width: thin; scrollbar-color: #1e2a38 transparent; }
</style>
