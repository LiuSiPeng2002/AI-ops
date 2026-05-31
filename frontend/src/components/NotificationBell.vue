<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '../api'

const { t } = useI18n()

const alerts = ref([])
const show = ref(false)
const unread = ref(0)

async function fetchAlerts() {
  try {
    const { data } = await api.get('/inspection/results', { params: { limit: 20 } })
    alerts.value = (data.results || []).filter(r => r.alert)
    unread.value = alerts.value.length
  } catch (e) { /* pass */ }
}

function toggle() { show.value = !show.value; if (show.value) fetchAlerts() }

onMounted(() => fetchAlerts())
const timer = setInterval(fetchAlerts, 60000)
import { onUnmounted } from 'vue'
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="notif-bell">
    <button class="bell-btn" @click="toggle" :title="t('sidebar.notifications')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
      </svg>
      <span v-if="unread" class="bell-badge">{{ unread }}</span>
    </button>
    <div v-if="show" class="notif-dropdown" @click.self="show=false">
      <div class="notif-head">{{ t('sidebar.notifications') }}</div>
      <div v-if="alerts.length === 0" class="notif-empty">{{ t('sidebar.noNotifications') }}</div>
      <div v-for="a in alerts.slice(0, 10)" :key="a.timestamp" class="notif-item alert">
        <div class="notif-name">{{ a.name }}</div>
        <div class="notif-time">{{ (a.timestamp || '').slice(0, 16).replace('T', ' ') }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.notif-bell { position: relative; }
.bell-btn { background: none; border: none; color: #7c8b9e; cursor: pointer; padding: 4px; position: relative; }
.bell-btn:hover { color: #dce2ea; }
.bell-badge { position: absolute; top: -2px; right: -4px; background: #f04a4a; color: #fff; font-size: 9px; font-weight: 700; width: 16px; height: 16px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.notif-dropdown { position: absolute; top: 100%; right: 0; width: 300px; max-height: 360px; overflow-y: auto; background: #131922; border: 1px solid #2a3a4e; border-radius: 8px; z-index: 300; box-shadow: 0 8px 32px rgba(0,0,0,0.4); }
.notif-head { padding: 12px 14px; font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: #4e5b6e; border-bottom: 1px solid #1e2a38; }
.notif-empty { padding: 16px; font-size: 12px; color: #4e5b6e; text-align: center; }
.notif-item { padding: 10px 14px; border-bottom: 1px solid #1e2a38; cursor: pointer; }
.notif-item.alert { border-left: 2px solid #f04a4a; }
.notif-item:hover { background: #1a2230; }
.notif-name { font-size: 12px; color: #dce2ea; }
.notif-time { font-size: 10px; color: #4e5b6e; margin-top: 2px; font-family: monospace; }
</style>
