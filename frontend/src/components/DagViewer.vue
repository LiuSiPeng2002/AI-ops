<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  session: { type: Object, default: null },
  width: { type: Number, default: 800 },
  height: { type: Number, default: 420 },
})

// Node layout positions (fixed for readability)
const NODE_LAYOUT = {
  orchestrator:    { x: 0.10, y: 0.50 },
  observe:         { x: 0.28, y: 0.22 },
  diagnose:        { x: 0.28, y: 0.50 },
  knowledge:       { x: 0.28, y: 0.78 },
  remedy:          { x: 0.52, y: 0.35 },
  verify:          { x: 0.52, y: 0.65 },
  orchestrator_final: { x: 0.78, y: 0.50 },
}

const EDGES = [
  { from: 'orchestrator', to: 'observe', label: '' },
  { from: 'observe', to: 'diagnose', label: 'diagnosis', condition: 'intent=diagnosis' },
  { from: 'observe', to: 'remedy', label: 'change', condition: 'intent=change' },
  { from: 'observe', to: 'knowledge', label: 'inquiry', condition: 'intent=inquiry' },
  { from: 'diagnose', to: 'remedy', label: 'root_cause', condition: '有根因时' },
  { from: 'diagnose', to: 'orchestrator_final', label: 'no cause', condition: '无根因时' },
  { from: 'remedy', to: 'verify', label: 'exec done', condition: '' },
  { from: 'verify', to: 'remedy', label: 'retry', condition: 'failed & retry<3' },
  { from: 'verify', to: 'orchestrator_final', label: 'passed', condition: '' },
  { from: 'knowledge', to: 'orchestrator_final', label: '', condition: '' },
]

const AGENT_COLORS = {
  orchestrator: '#3b9eff',
  observe: '#00d4aa',
  diagnose: '#e5a020',
  knowledge: '#2ecc71',
  remedy: '#a855f7',
  verify: '#f04a4a',
  orchestrator_final: '#3b9eff',
}

function nodeStatus(session, agentName) {
  if (!session) return 'idle'
  // Use agent messages to determine status
  const msgs = session.messages || []
  const agentMsgs = msgs.filter(m => m.agent_name === agentName)
  if (agentMsgs.length === 0) return 'idle'
  const hasError = agentMsgs.some(m => m.message_type === 'error')
  if (hasError) return 'error'
  return 'done'
}

function statusColor(status) {
  return status === 'done' ? '#2ecc71' : status === 'active' ? '#3b9eff' : status === 'error' ? '#f04a4a' : '#2a3a4e'
}

function statusBg(status) {
  return status === 'done' ? 'rgba(46,204,113,0.12)' : status === 'active' ? 'rgba(59,158,255,0.12)' : status === 'error' ? 'rgba(240,74,74,0.12)' : 'rgba(42,58,78,0.3)'
}

const nodes = computed(() => {
  return Object.entries(NODE_LAYOUT).map(([name, pos]) => {
    const status = nodeStatus(props.session, name)
    return {
      id: name,
      label: t(`agents.${name}`) || name,
      x: pos.x * props.width,
      y: pos.y * props.height,
      color: AGENT_COLORS[name],
      status,
      statusColor: statusColor(status),
      statusBg: statusBg(status),
    }
  })
})

const edgesRendered = computed(() => {
  return EDGES.map((e, i) => {
    const fromNode = NODE_LAYOUT[e.from]
    const toNode = NODE_LAYOUT[e.to]
    if (!fromNode || !toNode) return null

    const x1 = fromNode.x * props.width
    const y1 = fromNode.y * props.height
    const x2 = toNode.x * props.width
    const y2 = toNode.y * props.height

    // For the retry edge (verify → remedy), curve it
    const isRetry = e.from === 'verify' && e.to === 'remedy'
    const midX = isRetry ? (x1 + x2) / 2 + 40 : (x1 + x2) / 2
    const midY = isRetry ? (y1 + y2) / 2 - 50 : (y1 + y2) / 2

    let path
    if (isRetry) {
      path = `M ${x1} ${y1} C ${x1+40} ${y1-70}, ${x2-40} ${y2-70}, ${x2} ${y2}`
    } else {
      path = `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`
    }

    return {
      ...e,
      x1, y1, x2, y2, path,
      midLabelX: midX,
      midLabelY: isRetry ? midY - 20 : midY - 6,
    }
  }).filter(Boolean)
})
</script>

<template>
  <div class="dag-container">
    <svg :width="width" :height="height" class="dag-svg">
      <defs>
        <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="#2a3a4e" />
        </marker>
        <marker id="arrowhead-active" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="#3b9eff" />
        </marker>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      <!-- Edges -->
      <g v-for="(e, i) in edgesRendered" :key="'e'+i">
        <path
          :d="e.path"
          fill="none"
          stroke="#1e2a38"
          stroke-width="1.5"
          marker-end="url(#arrowhead)"
          :stroke-dasharray="e.from === 'verify' && e.to === 'remedy' ? '5,3' : 'none'"
        />
        <text
          v-if="e.label"
          :x="e.midLabelX"
          :y="e.midLabelY"
          text-anchor="middle"
          class="edge-label"
          :font-size="e.from === 'verify' && e.to === 'remedy' ? 10 : 9"
          :fill="e.from === 'verify' && e.to === 'remedy' ? '#e5a020' : '#4e5b6e'"
        >{{ e.label }}</text>
      </g>

      <!-- Nodes -->
      <g v-for="node in nodes" :key="node.id">
        <!-- Glow for active -->
        <circle
          v-if="node.status === 'active'"
          :cx="node.x" :cy="node.y" r="36"
          fill="none" :stroke="node.color" stroke-width="2"
          opacity="0.3" filter="url(#glow)"
          class="node-pulse"
        />
        <!-- Node circle -->
        <circle
          :cx="node.x" :cy="node.y" r="28"
          :fill="node.statusBg"
          :stroke="node.status === 'done' ? node.color : node.status === 'active' ? node.color : '#2a3a4e'"
          stroke-width="2"
          class="node-circle"
        />
        <!-- Status dot -->
        <circle
          :cx="node.x + 20" :cy="node.y - 20" r="5"
          :fill="node.statusColor"
          stroke="#0b0f15" stroke-width="1.5"
        />
        <!-- Agent label -->
        <text
          :x="node.x" :y="node.y + 2"
          text-anchor="middle" dominant-baseline="central"
          class="node-label"
          fill="#dce2ea"
          font-size="10"
          font-weight="600"
          font-family="'Cascadia Code','Fira Code','JetBrains Mono','Consolas',monospace"
        >{{ node.label }}</text>
        <!-- Label below node -->
        <text
          :x="node.x" :y="node.y + 46"
          text-anchor="middle"
          class="node-sublabel"
          fill="#4e5b6e"
          font-size="9"
        >{{ node.id === 'orchestrator_final' ? t('dag.summary') : '' }}</text>
      </g>
    </svg>

    <!-- Legend -->
    <div class="dag-legend">
      <div class="legend-item"><span class="leg-dot" style="background:#2ecc71"></span> {{ t('dag.done') }}</div>
      <div class="legend-item"><span class="leg-dot" style="background:#3b9eff"></span> {{ t('dag.active') }}</div>
      <div class="legend-item"><span class="leg-dot" style="background:#f04a4a"></span> {{ t('dag.error') }}</div>
      <div class="legend-item"><span class="leg-dot" style="background:#2a3a4e"></span> {{ t('dag.idle') }}</div>
    </div>
  </div>
</template>

<style scoped>
.dag-container {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.dag-svg {
  max-width: 100%;
}
.node-circle {
  transition: all 0.4s ease;
  cursor: pointer;
}
.node-circle:hover {
  stroke-width: 3;
  filter: brightness(1.2);
}
.node-pulse {
  animation: pulse-ring 2s ease-out infinite;
}
@keyframes pulse-ring {
  0% { opacity: 0.4; r: 34; }
  100% { opacity: 0; r: 44; }
}
.edge-label {
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
  user-select: none;
  font-size: 10px;
}
.dag-legend {
  display: flex;
  gap: 20px;
  padding: 12px 0 4px;
  font-size: 11px;
  color: #7c8b9e;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
.leg-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
</style>
