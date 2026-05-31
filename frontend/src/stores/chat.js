import { defineStore } from 'pinia'
import api from '../api'

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [],
    sessionId: null,
    loading: false,
    activeAgent: null,
    agentReasoning: '',
    showReasoning: false,
    totalTokens: 0,

    // Phase 3: Self-Healing + Approval
    approvalRequired: false,
    approvalData: null,
    approvalResolved: false,
    remedyCommands: [],
    verificationChecks: [],
    retryAttempts: 0,
    maxRetryAttempts: 3,
    graphPaused: false,

    // Stop generation
    _abortController: null,

    // Selected machine for multi-machine ops
    selectedMachine: null,
  }),

  actions: {
    addMessage(message) {
      this.messages.push({ ...message, timestamp: new Date().toISOString() })
    },

    clearMessages() {
      this.messages = []
      this.sessionId = null
      this.activeAgent = null
      this.agentReasoning = ''
      this.showReasoning = false
      this.approvalRequired = false
      this.approvalData = null
      this.approvalResolved = false
      this.remedyCommands = []
      this.verificationChecks = []
      this.retryAttempts = 0
      this.graphPaused = false
      this.totalTokens = 0
    },

    stopGeneration() {
      if (this._abortController) {
        this._abortController.abort()
        this._abortController = null
      }
      this.loading = false
      this.activeAgent = null
      this.graphPaused = false
    },

    async restoreSession(sessionId) {
      this.clearMessages()
      this.sessionId = sessionId
      this.loading = true
      try {
        const { data } = await api.get(`/audit/sessions/${sessionId}`)
        if (!data || !data.messages) {
          this.addMessage({ role: 'system', type: 'error', content: 'Session not found or has no messages' })
          this.loading = false
          return
        }
        // Replay messages into the chat panel in order
        for (const m of data.messages) {
          const content = typeof m.content === 'object' ? m.content : { text: m.content }
          const msg = {
            role: m.role,
            type: m.message_type,
            content: content.text || (typeof m.content === 'string' ? m.content : JSON.stringify(m.content)),
            agent: m.agent_name,
            timestamp: m.created_at,
          }
          // Map special types
          if (m.message_type === 'anomaly_detected') {
            msg.type = 'anomaly'
            msg.severity = content.severity || 'info'
            msg.content = content.summary || msg.content
          } else if (m.message_type === 'hypothesis') {
            msg.type = 'hypothesis'
            msg.confidence = content.confidence || 0
            msg.evidence = content.evidence || ''
            msg.content = content.hypothesis || msg.content
          } else if (m.message_type === 'root_cause') {
            msg.type = 'root_cause'
            msg.confidence = content.confidence || 0
            msg.content = content.cause || msg.content
          } else if (m.message_type === 'agent_response') {
            msg.type = 'agent_response'
          } else if (m.message_type === 'user_input') {
            msg.type = 'user_input'
          } else if (m.message_type === 'tool_call') {
            msg.type = 'tool_call'
            msg.content = content.tool || m.agent_name || ''
            msg.args = content.args || {}
          } else if (m.message_type === 'tool_result') {
            msg.type = 'tool_result'
            msg.content = content.result || content.output || msg.content
          } else if (m.message_type === 'approval_required') {
            msg.type = 'approval_required'
          } else if (m.message_type === 'remedy_plan') {
            msg.type = 'remedy_plan'
            msg.commands = content.commands || []
          }
          this.messages.push(msg)
        }
      } catch (e) {
        this.addMessage({ role: 'system', type: 'error', content: `Failed to load session: ${e.message || e}` })
      } finally {
        this.loading = false
      }
    },

    async sendMessage(content) {
      this.addMessage({ role: 'user', type: 'user_input', content })
      this.loading = true
      this.activeAgent = null
      this.agentReasoning = ''
      this.showReasoning = false
      this.approvalRequired = false
      this.approvalData = null
      this.approvalResolved = false
      this.remedyCommands = []
      this.verificationChecks = []
      this.retryAttempts = 0
      this.graphPaused = false

      await this._streamFromUrl('/api/chat/stream', {
        method: 'POST',
        body: JSON.stringify({
          message: content,
          session_id: this.sessionId,
          machine_id: this.selectedMachine?.id || undefined,
        }),
      })
    },

    async sendApproval(sessionId, approved, reason = '') {
      this.approvalResolved = true
      await this._streamFromUrl('/api/chat/resume', {
        method: 'POST',
        body: JSON.stringify({ session_id: sessionId, approved, reason }),
      })
      this.approvalRequired = false
      this.approvalData = null
      this.graphPaused = false
    },

    async _streamFromUrl(url, fetchOptions) {
      const token = localStorage.getItem('access_token')
      this._abortController = new AbortController()
      const signal = this._abortController.signal

      try {
        const response = await fetch(url, {
          ...fetchOptions,
          signal,
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
            ...(fetchOptions.headers || {}),
          },
        })

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''
          let currentEvent = ''
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                this.handleSSEEvent(currentEvent, data)
              } catch { /* skip */ }
              currentEvent = ''
            }
          }
        }
      } catch (error) {
        if (error.name === 'AbortError') {
          this.addMessage({ role: 'system', type: 'agent_response', content: 'Generation stopped.' })
        } else {
          this.addMessage({ role: 'system', type: 'error', content: `Connection error: ${error.message}` })
        }
      } finally {
        this._abortController = null
        if (!this.graphPaused) this.loading = false
      }
    },

    handleSSEEvent(event, data) {
      switch (event) {
        case 'agent_active':
          this.activeAgent = data.agent
          this.agentReasoning = ''
          this.showReasoning = false
          if (data.session_id) this.sessionId = data.session_id
          break
        case 'agent_reasoning':
          if (data.content) this.agentReasoning += data.content
          break
        case 'anomaly_detected':
          this.addMessage({ role: 'agent', type: 'anomaly', content: data.summary, severity: data.severity })
          break
        case 'hypothesis':
          this.addMessage({ role: 'agent', type: 'hypothesis', content: data.hypothesis, confidence: data.confidence, evidence: data.evidence })
          break
        case 'root_cause':
          this.addMessage({ role: 'agent', type: 'root_cause', content: data.cause, confidence: data.confidence })
          break
        case 'rag_context':
          this.addMessage({ role: 'agent', type: 'rag_context', content: data.content })
          break
        case 'agent_thought':
          this.addMessage({ role: 'agent', type: 'agent_thought', content: data.content, agent: data.agent })
          if (data.session_id) this.sessionId = data.session_id
          break
        case 'tool_call':
          this.addMessage({ role: 'agent', type: 'tool_call', content: data.tool, args: data.args })
          break
        case 'tool_result':
          this.addMessage({ role: 'agent', type: 'tool_result', content: data.result, tool: data.tool })
          break
        // Phase 3
        case 'remedy_plan':
          this.remedyCommands = (data.commands || []).map(c => ({ ...c, status: 'pending' }))
          this.addMessage({ role: 'agent', type: 'remedy_plan', content: data.strategy, commands: data.commands })
          break
        case 'approval_required':
          this.approvalRequired = true; this.approvalData = data; this.graphPaused = true
          if (data.session_id) this.sessionId = data.session_id
          this.addMessage({ role: 'agent', type: 'approval_required', content: data, session_id: data.session_id })
          break
        case 'approval_result':
          this.approvalResolved = true; this.loading = true
          break
        case 'remedy_executing':
          {
            const cmd = this.remedyCommands.find(c => c.command === data.command)
            if (cmd) cmd.status = 'running'
            this.addMessage({ role: 'agent', type: 'tool_call', content: data.command, args: { risk_level: data.risk_level, attempt: data.attempt } })
          }
          break
        case 'remedy_result':
          {
            const cmdR = this.remedyCommands.find(c => c.command === data.command)
            if (cmdR) cmdR.status = data.success ? 'done' : 'failed'
            this.addMessage({ role: 'agent', type: 'tool_result', content: data.output, tool: data.command, success: data.success })
          }
          break
        case 'verification_status':
          this.verificationChecks.push(data)
          this.addMessage({ role: 'agent', type: 'verification', content: data })
          break
        case 'retry_attempt':
          this.retryAttempts = data.attempt
          this.addMessage({ role: 'agent', type: 'retry', content: data })
          break
        case 'graph_paused':
          this.graphPaused = true; this.loading = false
          break
        case 'agent_response':
          this.addMessage({ role: 'agent', type: 'agent_response', content: data.content, agent: data.agent })
          break
        case 'error':
          this.addMessage({ role: 'system', type: 'error', content: data.message })
          break
        case 'done':
          if (data.session_id) this.sessionId = data.session_id
          if (data.total_tokens) this.totalTokens = data.total_tokens
          break
      }
    },
  },
})
