<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'

marked.setOptions({
  breaks: true,
  gfm: true,
  highlight(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return hljs.highlightAuto(code).value
  },
})

const props = defineProps({ content: { type: String, default: '' } })

const html = computed(() => {
  try {
    return marked.parse(props.content || '')
  } catch {
    return props.content
  }
})
</script>

<template>
  <div class="markdown-body" v-html="html"></div>
</template>

<style>
.markdown-body {
  font-size: 13px;
  line-height: 1.65;
  color: #dce2ea;
  word-break: break-word;
}
.markdown-body h1,.markdown-body h2,.markdown-body h3 {
  color: #dce2ea;
  margin: 12px 0 6px;
  font-weight: 600;
}
.markdown-body h2 { font-size: 15px; border-bottom: 1px solid #1e2a38; padding-bottom: 4px; }
.markdown-body h3 { font-size: 13.5px; }
.markdown-body p { margin: 4px 0 8px; }
.markdown-body ul,.markdown-body ol { padding-left: 20px; margin: 4px 0; }
.markdown-body li { margin: 2px 0; }
.markdown-body code {
  background: #0b0f15;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Cascadia Code','Fira Code','JetBrains Mono',monospace;
  font-size: 11.5px;
  color: #00d4aa;
}
.markdown-body pre {
  background: #0b0f15;
  border: 1px solid #1e2a38;
  border-radius: 5px;
  padding: 12px;
  overflow-x: auto;
  margin: 8px 0;
}
.markdown-body pre code {
  background: none;
  padding: 0;
  color: #dce2ea;
  font-size: 11px;
}
.markdown-body table {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
  font-size: 12px;
}
.markdown-body th,.markdown-body td {
  border: 1px solid #1e2a38;
  padding: 6px 10px;
  text-align: left;
}
.markdown-body th {
  background: #1a2230;
  font-weight: 600;
  color: #7c8b9e;
}
.markdown-body blockquote {
  border-left: 2px solid #3b9eff;
  padding-left: 12px;
  margin: 8px 0;
  color: #7c8b9e;
}
.markdown-body a { color: #3b9eff; }
.markdown-body strong { color: #dce2ea; }
.markdown-body hr { border: none; border-top: 1px solid #1e2a38; margin: 12px 0; }
</style>
