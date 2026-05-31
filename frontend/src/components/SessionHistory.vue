<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const { t } = useI18n()
const authStore = useAuthStore()
const emit = defineEmits(['select'])

const sessions = ref([])
const loading = ref(false)

async function fetchSessions() {
  loading.value = true
  try {
    const params = { limit: 20 }
    // Non-admin users can only see their own sessions (enforced by backend)
    // Admin+ see all by default
    const { data } = await api.get('/audit/sessions', { params })
    sessions.value = data.items || []
  } catch (e) { /* pass */ }
  finally { loading.value = false }
}

function selectSession(sessionId) {
  emit('select', sessionId)
}

defineExpose({ refresh: fetchSessions })

onMounted(() => fetchSessions())
</script>

<template>
  <div class="session-history">
    <div class="sh-header">
      <span>{{ t('sidebar.history') }}</span>
      <button class="sh-refresh" @click="fetchSessions" :disabled="loading">{{ loading ? '...' : '↻' }}</button>
    </div>
    <div class="sh-list">
      <div v-if="sessions.length === 0 && !loading" class="sh-empty">{{ t('sidebar.noHistory') }}</div>
      <div
        v-for="s in sessions" :key="s.id"
        class="sh-item"
        @click="selectSession(s.id)"
      >
        <div class="sh-title">{{ s.title || (s.id || '').slice(0, 8) }}</div>
        <div class="sh-meta">{{ (s.id || '').slice(0, 12) }} &middot; {{ s.intent_type || '-' }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.session-history { display: flex; flex-direction: column; max-height: 260px; }
.sh-header { display: flex; justify-content: space-between; align-items: center; padding: 8px 20px 6px; font-size: 10px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #4e5b6e; font-family: 'Cascadia Code','Fira Code',monospace; }
.sh-refresh { background: none; border: none; color: #4e5b6e; cursor: pointer; font-size: 13px; }
.sh-refresh:hover { color: #3b9eff; }
.sh-list { overflow-y: auto; flex: 1; }
.sh-empty { padding: 12px 20px; font-size: 11px; color: #4e5b6e; text-align: center; }
.sh-item { padding: 8px 20px; cursor: pointer; border-left: 2px solid transparent; transition: all 0.15s; }
.sh-item:hover { background: rgba(59,158,255,0.04); border-left-color: #2a3a4e; }
.sh-title { font-size: 12px; color: #dce2ea; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sh-meta { font-size: 10px; color: #4e5b6e; margin-top: 2px; font-family: 'Cascadia Code','Fira Code',monospace; }
</style>
