<script setup>
import { ref, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useChatStore } from '../../stores/chat'
import MarkdownRenderer from '../MarkdownRenderer.vue'

const { t } = useI18n()
const chatStore = useChatStore()
const container = ref(null)
const copiedIdx = ref(-1)

function copyToolOutput(idx, text) {
  navigator.clipboard.writeText(text).then(() => {
    copiedIdx.value = idx
    setTimeout(() => { copiedIdx.value = -1 }, 2000)
  }).catch(() => {})
}

const AGENT_ORDER = ['orchestrator', 'observe', 'diagnose', 'remedy', 'verify', 'orchestrator_final']

watch(
  () => chatStore.messages.length,
  async () => {
    await nextTick()
    if (container.value) {
      container.value.scrollTop = container.value.scrollHeight
    }
  }
)

function formatToolCall(msg) {
  if (msg.type === 'tool_call') {
    return `$ ${msg.content} ${msg.args ? JSON.stringify(msg.args) : ''}`
  }
  return msg.content
}

function severityColor(severity) {
  return severity === 'critical' ? 'var(--red)' : severity === 'warning' ? 'var(--amber)' : 'var(--muted)'
}

function severityBg(severity) {
  return severity === 'critical' ? 'rgba(240,74,74,0.12)' : severity === 'warning' ? 'rgba(229,160,32,0.12)' : 'rgba(107,122,141,0.08)'
}

function agentStepClass(name) {
  const idx = AGENT_ORDER.indexOf(chatStore.activeAgent)
  const stepIdx = AGENT_ORDER.indexOf(name)
  if (stepIdx === idx) return 'stage active'
  if (stepIdx < idx) return 'stage done'
  return 'stage'
}

function handleApprove(sessionId) {
  chatStore.sendApproval(sessionId, true, 'Approved by user')
}

function handleReject(sessionId) {
  chatStore.sendApproval(sessionId, false, 'Rejected by user')
  chatStore.approvalRequired = false
}

function riskBadgeClass(level) {
  const l = level || 'L0'
  if (l === 'L0' || l === 'L1') return 'risk-low'
  if (l === 'L2') return 'risk-med'
  if (l === 'L3') return 'risk-high'
  return 'risk-critical'
}

const AGENT_LABEL_KEYS = {
  orchestrator: 'agents.router',
  observe: 'agents.observe',
  diagnose: 'agents.diagnose',
  knowledge: 'agents.knowledge',
  remedy: 'agents.remedy',
  verify: 'agents.verify',
  orchestrator_final: 'agents.summary',
}
</script>

<template>
  <div class="chat-panel" ref="container">
    <!-- Agent stage pipeline -->
    <div v-if="chatStore.loading && chatStore.activeAgent" class="stage-pipeline">
      <div v-for="(name, i) in AGENT_ORDER" :key="name" :class="agentStepClass(name)">
        <span class="stage-dot"></span>
        <span v-if="i < AGENT_ORDER.length - 1" class="stage-line"></span>
        <span class="stage-label">{{ t(AGENT_LABEL_KEYS[name]) }}</span>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="chatStore.messages.length === 0" class="empty-state">
      <div class="empty-icon">
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
          <rect x="4" y="8" width="40" height="32" rx="3" stroke="currentColor" stroke-width="1.5" />
          <rect x="7" y="12" width="12" height="5" rx="1" stroke="currentColor" stroke-width="1.2" />
          <rect x="22" y="12" width="19" height="5" rx="1" stroke="currentColor" stroke-width="1.2" />
          <rect x="7" y="21" width="34" height="4" rx="1" stroke="currentColor" stroke-width="1.2" />
          <rect x="7" y="28" width="28" height="4" rx="1" stroke="currentColor" stroke-width="1.2" />
          <circle cx="34" cy="35" r="6" stroke="currentColor" stroke-width="1.5" />
          <path d="M37 35l-2-2m0 4l-2-2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
        </svg>
      </div>
      <h3>{{ t('chat.emptyTitle') }}</h3>
      <p>{{ t('chat.emptyDesc') }}</p>
      <div class="suggestions">
        <button
          v-for="s in [t('chat.suggestion1'), t('chat.suggestion2'), t('chat.suggestion3')]"
          :key="s"
          class="suggestion-chip"
          @click="chatStore.sendMessage(s)"
        >
          {{ s }}
        </button>
      </div>
    </div>

    <!-- Messages -->
    <template v-for="(msg, i) in chatStore.messages" :key="i">
      <!-- User message -->
      <div v-if="msg.type === 'user_input'" class="msg-row msg-user">
        <div class="bubble bubble-user">{{ msg.content }}</div>
      </div>

      <!-- Tool call -->
      <div v-else-if="msg.type === 'tool_call'" class="msg-row msg-tool-call">
        <div class="tool-cmd">{{ formatToolCall(msg) }}</div>
      </div>

      <!-- Tool result -->
      <div v-else-if="msg.type === 'tool_result'" class="msg-row msg-tool-result">
        <div class="tool-out">
          <pre>{{ msg.content }}</pre>
          <button class="btn-copy-out" @click="copyToolOutput(i, msg.content)" :title="copiedIdx === i ? 'Copied!' : 'Copy'">
            <svg v-if="copiedIdx !== i" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#2ecc71" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
          </button>
        </div>
      </div>

      <!-- Anomaly card -->
      <div v-else-if="msg.type === 'anomaly'" class="msg-row">
        <div class="card-anomaly" :style="{ borderColor: severityColor(msg.severity), background: severityBg(msg.severity) }">
          <div class="anomaly-head">
            <span class="anomaly-dot" :style="{ background: severityColor(msg.severity) }"></span>
            <span class="anomaly-sev" :style="{ color: severityColor(msg.severity) }">{{ msg.severity }}</span>
            <span class="anomaly-label">{{ t('cards.anomaly') }}</span>
          </div>
          <div class="anomaly-body">{{ msg.content }}</div>
        </div>
      </div>

      <!-- Hypothesis card -->
      <div v-else-if="msg.type === 'hypothesis'" class="msg-row">
        <div class="card-hypothesis">
          <div class="hypo-head">
            <span class="hypo-tag">{{ t('cards.hypothesisTag') }}</span>
            <span class="hypo-conf">{{ (msg.confidence * 100).toFixed(0) }}% {{ t('cards.confidence') }}</span>
          </div>
          <div class="hypo-bar">
            <div class="hypo-fill" :style="{ width: (msg.confidence * 100) + '%' }"></div>
          </div>
          <div class="hypo-text">{{ msg.content }}</div>
          <div v-if="msg.evidence" class="hypo-evidence">
            <span class="ev-label">{{ t('cards.evidence') }}</span>
            <span>{{ msg.evidence }}</span>
          </div>
        </div>
      </div>

      <!-- Root cause panel -->
      <div v-else-if="msg.type === 'root_cause'" class="msg-row">
        <div class="card-root-cause">
          <div class="rc-head">{{ t('cards.rootCause') }}</div>
          <div class="rc-body">{{ msg.content }}</div>
          <div class="rc-conf">{{ t('cards.confidence') }} {{ (msg.confidence * 100).toFixed(0) }}%</div>
        </div>
      </div>

      <!-- RAG reference -->
      <div v-else-if="msg.type === 'rag_context'" class="msg-row">
        <div class="card-rag">
          <div class="rag-head">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
            <span>{{ t('cards.knowledgeRef') }}</span>
          </div>
          <div class="rag-body">{{ msg.content }}</div>
        </div>
      </div>

      <!-- Remedy Plan -->
      <div v-else-if="msg.type === 'remedy_plan'" class="msg-row">
        <div class="card-remedy">
          <div class="rp-head">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/></svg>
            <span>{{ t('cards.repairPlan') }}</span>
          </div>
          <div v-if="msg.content" class="rp-strategy">{{ msg.content }}</div>
          <div v-for="(cmd, ci) in (msg.commands || [])" :key="ci" class="rp-cmd">
            <span class="rp-risk" :class="riskBadgeClass(cmd.risk_level)">{{ cmd.risk_level }}</span>
            <code>$ {{ cmd.tool || 'kubectl' }} {{ cmd.command }}</code>
          </div>
        </div>
      </div>

      <!-- Approval Required -->
      <div v-else-if="msg.type === 'approval_required'" class="msg-row">
        <div class="card-approval">
          <div class="ap-head">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            <span>{{ t('cards.approvalRequired') }}</span>
            <span class="ap-risk" :class="riskBadgeClass(msg.content.risk_level)">{{ msg.content.risk_level }}</span>
          </div>
          <div class="ap-body">
            <p class="ap-reason">{{ msg.content.reason || t('cards.operationRequiresApproval') }}</p>
            <div class="ap-cmds">
              <div v-for="(cmd, ci) in (msg.content.commands || [])" :key="ci" class="ap-cmd-line">
                <span class="rp-risk" :class="riskBadgeClass(cmd.risk_level)">{{ cmd.risk_level }}</span>
                <code>$ {{ cmd.tool || 'kubectl' }} {{ cmd.command }}</code>
              </div>
            </div>
          </div>
          <div v-if="chatStore.approvalRequired" class="ap-actions">
            <button class="btn-approve" @click="handleApprove(msg.session_id)">
              <span class="btn-icon">&#10003;</span> {{ t('cards.approve') }}
            </button>
            <button class="btn-reject" @click="handleReject(msg.session_id)">
              <span class="btn-icon">&#10007;</span> {{ t('cards.reject') }}
            </button>
          </div>
          <div v-else class="ap-resolved">
            <span class="resolved-text">{{ t('cards.decisionSubmitted') }}</span>
          </div>
        </div>
      </div>

      <!-- Verification -->
      <div v-else-if="msg.type === 'verification'" class="msg-row">
        <div class="card-verify">
          <span class="v-icon" :class="msg.content.status === 'passed' ? 'v-pass' : msg.content.status === 'failed' ? 'v-fail' : 'v-pending'">
            {{ msg.content.status === 'passed' ? '✓' : msg.content.status === 'failed' ? '✗' : '⋯' }}
          </span>
          <span class="v-label">{{ msg.content.check_type }}</span>
          <span v-if="msg.content.detail" class="v-detail">{{ msg.content.detail }}</span>
        </div>
      </div>

      <!-- Retry notification -->
      <div v-else-if="msg.type === 'retry'" class="msg-row">
        <div class="card-retry">
          <span class="retry-icon">&#x21BA;</span>
          <span class="retry-label">{{ t('cards.retry') }} {{ msg.content.attempt || 0 }} / {{ msg.content.max_attempts || 3 }}</span>
          <span v-if="msg.content.reason" class="retry-reason">{{ msg.content.reason }}</span>
        </div>
      </div>

      <!-- Error -->
      <div v-else-if="msg.type === 'error'" class="msg-row msg-error">
        <div class="bubble bubble-error">{{ msg.content }}</div>
      </div>

      <!-- Agent response with Markdown -->
      <div v-else-if="msg.type === 'agent_response'" class="msg-row msg-agent">
        <div class="bubble bubble-agent">
          <div v-if="msg.agent" class="agent-tag">{{ msg.agent }}</div>
          <MarkdownRenderer :content="msg.content" />
        </div>
      </div>

      <!-- Generic agent message -->
      <div v-else class="msg-row msg-agent">
        <div class="bubble bubble-agent">
          <div v-if="msg.agent" class="agent-tag">{{ msg.agent }}</div>
          <div class="agent-text">{{ msg.content }}</div>
        </div>
      </div>
    </template>

    <!-- Loading / reasoning area -->
    <div v-if="chatStore.loading" class="loading-zone">
      <div v-if="chatStore.agentReasoning" class="reasoning-box">
        <button class="reasoning-toggle" @click="chatStore.showReasoning = !chatStore.showReasoning">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            :style="{ transform: chatStore.showReasoning ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }">
            <path d="M9 18l6-6-6-6"/>
          </svg>
          <span>{{ t('chat.reasoningTrace') }}</span>
        </button>
        <div v-if="chatStore.showReasoning" class="reasoning-content">{{ chatStore.agentReasoning }}</div>
      </div>

      <div class="thinking-row">
        <span class="thinking-dot"></span>
        <span class="thinking-dot"></span>
        <span class="thinking-dot"></span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-panel { flex: 1; overflow-y: auto; padding: 24px 32px; background: var(--bg-deep); }

:root {
  --bg-deep: #0b0f15; --bg-surface: #131922; --bg-raised: #1a2230;
  --border: #1e2a38; --border-active: #2a3a4e;
  --text-primary: #dce2ea; --text-secondary: #7c8b9e; --text-muted: #4e5b6e;
  --blue: #3b9eff; --amber: #e5a020; --red: #f04a4a; --green: #2ecc71;
  --cyan: #00d4aa; --muted: #6b7a8d;
}

/* Stage Pipeline */
.stage-pipeline { display: flex; align-items: center; justify-content: center; gap: 0; padding: 14px 24px; margin-bottom: 24px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px; position: sticky; top: 0; z-index: 10; backdrop-filter: blur(8px); }
.stage { display: flex; align-items: center; gap: 0; font-size: 11px; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; letter-spacing: 0.04em; text-transform: uppercase; color: var(--text-muted); position: relative; }
.stage.active { color: var(--blue); }
.stage.done { color: var(--green); }
.stage-dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; flex-shrink: 0; }
.stage.active .stage-dot { box-shadow: 0 0 8px currentColor; animation: pulse-dot 1.2s infinite; }
@keyframes pulse-dot { 0%, 100% { box-shadow: 0 0 6px currentColor; } 50% { box-shadow: 0 0 16px currentColor, 0 0 24px currentColor; } }
.stage-line { width: 28px; height: 1px; background: var(--border); margin: 0 8px; flex-shrink: 0; }
.stage.done .stage-line { background: var(--green); }
.stage.active ~ .stage .stage-line { background: var(--border); }
.stage-label { position: absolute; top: 14px; left: 50%; transform: translateX(-50%); white-space: nowrap; font-size: 10px; letter-spacing: 0.06em; }

/* Empty State */
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 60vh; text-align: center; }
.empty-icon { color: var(--text-muted); margin-bottom: 24px; opacity: 0.6; }
.empty-state h3 { font-size: 20px; font-weight: 600; color: var(--text-primary); margin: 0 0 6px 0; letter-spacing: -0.02em; }
.empty-state p { font-size: 13px; color: var(--text-secondary); margin: 0 0 28px 0; }
.suggestions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }
.suggestion-chip { background: var(--bg-raised); border: 1px solid var(--border); color: var(--text-secondary); padding: 8px 16px; border-radius: 6px; font-size: 12px; cursor: pointer; transition: all 0.2s; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; letter-spacing: 0.02em; }
.suggestion-chip:hover { border-color: var(--blue); color: var(--blue); background: rgba(59, 158, 255, 0.06); }

/* Messages */
.msg-row { display: flex; margin-bottom: 6px; }
.msg-user { justify-content: flex-end; }
.bubble { max-width: 72%; padding: 10px 16px; border-radius: 8px; font-size: 13.5px; line-height: 1.55; word-break: break-word; }
.bubble-user { background: var(--blue); color: #fff; border-radius: 10px 10px 2px 10px; }
.bubble-agent { background: var(--bg-surface); border: 1px solid var(--border); color: var(--text-primary); border-radius: 10px 10px 10px 2px; }
.bubble-error { background: rgba(240, 74, 74, 0.1); border: 1px solid rgba(240, 74, 74, 0.25); color: var(--red); font-size: 12.5px; }
.agent-tag { font-size: 10px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 4px; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.agent-text { white-space: pre-wrap; }

/* Tool */
.tool-cmd { font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; font-size: 12px; color: var(--cyan); padding: 4px 12px; background: rgba(0, 212, 170, 0.06); border-left: 2px solid rgba(0, 212, 170, 0.3); border-radius: 0 4px 4px 0; }
.tool-out { font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; font-size: 11.5px; color: var(--text-secondary); padding: 6px 14px; max-width: 90%; background: var(--bg-deep); border: 1px solid var(--border); border-radius: 4px; overflow-x: auto; }
.tool-out pre { margin: 0; white-space: pre-wrap; word-break: break-all; flex: 1; }
.tool-out { display: flex; align-items: flex-start; gap: 8px; }
.btn-copy-out { background: none; border: none; color: #4e5b6e; cursor: pointer; padding: 2px; flex-shrink: 0; border-radius: 3px; opacity: 0; transition: opacity 0.15s; margin-top: 2px; }
.tool-out:hover .btn-copy-out, .btn-copy-out:hover { opacity: 1; }
.btn-copy-out:hover { color: #3b9eff; background: rgba(59,158,255,0.08); }

/* Anomaly */
.card-anomaly { border-left: 3px solid; border-radius: 0 6px 6px 0; padding: 12px 16px; max-width: 75%; }
.anomaly-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.anomaly-dot { width: 6px; height: 6px; border-radius: 50%; }
.anomaly-sev { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.anomaly-label { font-size: 12px; font-weight: 600; color: var(--text-primary); }
.anomaly-body { font-size: 12.5px; color: var(--text-secondary); white-space: pre-wrap; line-height: 1.5; }

/* Hypothesis */
.card-hypothesis { background: var(--bg-surface); border: 1px solid rgba(229, 160, 32, 0.2); border-radius: 8px; padding: 14px 16px; max-width: 75%; }
.hypo-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.hypo-tag { font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--amber); font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.hypo-conf { font-size: 11px; color: var(--text-muted); }
.hypo-bar { height: 3px; background: var(--bg-raised); border-radius: 2px; margin-bottom: 10px; overflow: hidden; }
.hypo-fill { height: 100%; background: var(--amber); border-radius: 2px; transition: width 0.5s ease; }
.hypo-text { font-size: 13px; color: var(--text-primary); white-space: pre-wrap; line-height: 1.5; }
.hypo-evidence { margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border); font-size: 11.5px; color: var(--text-secondary); display: flex; gap: 6px; }
.ev-label { font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; font-size: 10px; flex-shrink: 0; }

/* Root Cause */
.card-root-cause { background: rgba(240, 74, 74, 0.06); border: 1px solid rgba(240, 74, 74, 0.25); border-left: 3px solid var(--red); border-radius: 0 6px 6px 0; padding: 14px 16px; max-width: 75%; }
.rc-head { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--red); margin-bottom: 8px; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.rc-body { font-size: 13px; color: var(--text-primary); white-space: pre-wrap; line-height: 1.5; margin-bottom: 6px; }
.rc-conf { font-size: 11px; color: var(--text-muted); }

/* RAG */
.card-rag { background: rgba(46, 204, 113, 0.05); border: 1px solid rgba(46, 204, 113, 0.15); border-radius: 6px; padding: 10px 14px; max-width: 75%; }
.rag-head { display: flex; align-items: center; gap: 6px; font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--green); margin-bottom: 6px; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.rag-body { font-size: 12px; color: var(--text-secondary); white-space: pre-wrap; line-height: 1.45; max-height: 200px; overflow-y: auto; }

/* Reasoning */
.loading-zone { margin-top: 16px; }
.reasoning-box { margin-bottom: 12px; }
.reasoning-toggle { display: flex; align-items: center; gap: 6px; background: none; border: none; color: var(--text-muted); font-size: 11px; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; letter-spacing: 0.04em; text-transform: uppercase; cursor: pointer; padding: 6px 0; transition: color 0.2s; }
.reasoning-toggle:hover { color: var(--cyan); }
.reasoning-content { background: var(--bg-deep); border: 1px solid var(--border); border-left: 2px solid var(--cyan); border-radius: 0 4px 4px 0; padding: 12px 16px; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; font-size: 11px; color: var(--text-muted); white-space: pre-wrap; max-height: 260px; overflow-y: auto; line-height: 1.55; }

/* Remedy */
.card-remedy { background: rgba(59, 158, 255, 0.04); border: 1px solid rgba(59, 158, 255, 0.15); border-radius: 6px; padding: 12px 14px; max-width: 78%; }
.rp-head { display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--blue); margin-bottom: 8px; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.rp-strategy { font-size: 12.5px; color: var(--text-secondary); white-space: pre-wrap; line-height: 1.5; margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }
.rp-cmd { display: flex; align-items: center; gap: 8px; padding: 5px 0; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; font-size: 11.5px; }
.rp-cmd code { color: var(--text-primary); background: var(--bg-deep); padding: 3px 8px; border-radius: 3px; font-size: 11px; }

/* Risk Badges */
.rp-risk { font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; font-size: 9.5px; font-weight: 700; letter-spacing: 0.06em; padding: 2px 7px; border-radius: 3px; flex-shrink: 0; }
.risk-low { background: rgba(46, 204, 113, 0.12); color: var(--green); border: 1px solid rgba(46, 204, 113, 0.2); }
.risk-med { background: rgba(229, 160, 32, 0.12); color: var(--amber); border: 1px solid rgba(229, 160, 32, 0.2); }
.risk-high { background: rgba(240, 74, 74, 0.12); color: var(--red); border: 1px solid rgba(240, 74, 74, 0.25); }
.risk-critical { background: rgba(240, 74, 74, 0.16); color: var(--red); border: 1px solid rgba(240, 74, 74, 0.4); box-shadow: 0 0 8px rgba(240, 74, 74, 0.15); }

/* Approval */
.card-approval { background: rgba(240, 74, 74, 0.04); border: 2px solid rgba(240, 74, 74, 0.35); border-radius: 8px; padding: 16px; max-width: 78%; }
.ap-head { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; color: var(--red); margin-bottom: 6px; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; }
.ap-risk { margin-left: auto; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; font-size: 10px; font-weight: 700; letter-spacing: 0.06em; padding: 2px 8px; border-radius: 3px; }
.ap-body { margin-bottom: 12px; }
.ap-reason { font-size: 12.5px; color: var(--text-secondary); margin: 0 0 10px 0; line-height: 1.5; }
.ap-cmds { display: flex; flex-direction: column; gap: 6px; }
.ap-cmd-line { display: flex; align-items: center; gap: 8px; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; font-size: 11.5px; }
.ap-cmd-line code { color: var(--text-primary); background: var(--bg-deep); padding: 3px 8px; border-radius: 3px; font-size: 11px; }
.ap-actions { display: flex; gap: 10px; padding-top: 12px; border-top: 1px solid rgba(240, 74, 74, 0.15); }
.btn-approve, .btn-reject { display: flex; align-items: center; gap: 6px; padding: 8px 20px; border-radius: 6px; font-size: 12.5px; font-weight: 600; letter-spacing: 0.03em; cursor: pointer; transition: all 0.2s; font-family: inherit; }
.btn-approve { background: var(--green); color: #071a0f; border: none; }
.btn-approve:hover { background: #27ae60; box-shadow: 0 0 12px rgba(46, 204, 113, 0.3); }
.btn-reject { background: transparent; color: var(--red); border: 1px solid rgba(240, 74, 74, 0.35); }
.btn-reject:hover { background: rgba(240, 74, 74, 0.1); border-color: var(--red); }
.btn-icon { font-size: 11px; font-weight: 700; }
.ap-resolved { padding-top: 12px; border-top: 1px solid var(--border); }
.resolved-text { font-size: 11.5px; color: var(--text-muted); font-style: italic; }

/* Verification */
.card-verify { display: flex; align-items: center; gap: 10px; padding: 8px 14px; background: var(--bg-surface); border-radius: 5px; max-width: 70%; font-size: 12px; }
.v-icon { width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; flex-shrink: 0; }
.v-pass { background: rgba(46, 204, 113, 0.15); color: var(--green); }
.v-fail { background: rgba(240, 74, 74, 0.15); color: var(--red); }
.v-pending { background: rgba(107, 122, 141, 0.1); color: var(--text-muted); animation: pulse-dot 1.4s infinite; }
.v-label { font-weight: 500; color: var(--text-primary); text-transform: capitalize; }
.v-detail { color: var(--text-muted); font-size: 11px; margin-left: auto; }

/* Retry */
.card-retry { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: rgba(229, 160, 32, 0.06); border: 1px solid rgba(229, 160, 32, 0.2); border-radius: 6px; max-width: 70%; font-size: 12px; color: var(--amber); }
.retry-icon { font-size: 16px; animation: spin 2s linear infinite; flex-shrink: 0; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.retry-label { font-weight: 600; font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; letter-spacing: 0.04em; color: var(--amber); }
.retry-reason { color: var(--text-muted); font-size: 11px; margin-left: auto; }

/* Thinking */
.thinking-row { display: flex; gap: 5px; padding: 8px 16px; }
.thinking-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text-muted); animation: think 1.4s infinite both; }
.thinking-dot:nth-child(2) { animation-delay: 0.2s; }
.thinking-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes think { 0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); } 30% { opacity: 1; transform: scale(1); } }
</style>
