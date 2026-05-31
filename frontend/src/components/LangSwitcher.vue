<script setup>
import { useI18n } from 'vue-i18n'
import { setLocale } from '../i18n/index.js'

const { locale } = useI18n()

function toggle() {
  const next = locale.value === 'zh-CN' ? 'en-US' : 'zh-CN'
  locale.value = next
  setLocale(next)
}
</script>

<template>
  <button class="lang-switch" @click="toggle" :title="locale === 'zh-CN' ? 'Switch to English' : '切换中文'">
    <span class="lang-icon">{{ locale === 'zh-CN' ? '中' : 'EN' }}</span>
  </button>
</template>

<style scoped>
.lang-switch {
  background: none;
  border: 1px solid #2a3a4e;
  color: #7c8b9e;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.lang-switch:hover {
  border-color: #3b9eff;
  color: #3b9eff;
  background: rgba(59, 158, 255, 0.06);
}
.lang-icon {
  line-height: 1;
}
</style>
