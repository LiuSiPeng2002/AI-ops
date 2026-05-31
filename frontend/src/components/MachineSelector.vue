<script setup>
import { ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '../api'

const { t } = useI18n()

const machines = ref([])
const selectedId = ref(localStorage.getItem('selectedMachine') || '')
const loading = ref(false)
const emit = defineEmits(['select'])

async function fetchMachines() {
  loading.value = true
  try {
    const { data } = await api.get('/machines')
    machines.value = data.items || []
    // Auto-select default if none saved
    if (!selectedId.value && machines.value.length) {
      const def = machines.value.find(m => m.is_default) || machines.value[0]
      selectedId.value = String(def.id)
      emit('select', def)
    }
  } catch (e) { /* pass */ }
  finally { loading.value = false }
}

function selectMachine() {
  const m = machines.value.find(m => String(m.id) === selectedId.value)
  if (m) {
    localStorage.setItem('selectedMachine', selectedId.value)
    emit('select', m)
  }
}

watch(selectedId, selectMachine)

onMounted(async () => {
  await fetchMachines()
  if (selectedId.value) selectMachine()
})
</script>

<template>
  <div class="machine-selector">
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1" fill="currentColor"/><circle cx="6" cy="18" r="1" fill="currentColor"/></svg>
    <select v-model="selectedId" class="machine-select" @change="selectMachine">
      <option value="">{{ t('machines.selectMachine') }}</option>
      <option v-for="m in machines" :key="m.id" :value="String(m.id)">
        {{ m.name }} ({{ m.host }}) {{ m.online ? '●' : '○' }}
      </option>
    </select>
    <span v-if="selectedId" class="status-dot" :class="machines.find(m=>String(m.id)===selectedId)?.online ? 'dot-on' : 'dot-off'" :title="machines.find(m=>String(m.id)===selectedId)?.online ? 'Online' : 'Offline'"></span>
  </div>
</template>

<style scoped>
.machine-selector { display: flex; align-items: center; gap: 6px; padding: 6px 10px; background: var(--bg-surface, #131922); border: 1px solid var(--border, #1e2a38); border-radius: 6px; font-size: 12px; }
.machine-select { background: none; border: none; color: #dce2ea; font-size: 12px; outline: none; cursor: pointer; font-family: inherit; min-width: 140px; }
.machine-select option { background: #131922; color: #dce2ea; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.dot-on { background: #2ecc71; box-shadow: 0 0 4px rgba(46,204,113,0.4); }
.dot-off { background: #4e5b6e; }
</style>
