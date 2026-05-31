import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN.js'
import enUS from './en-US.js'

const LOCALE_KEY = 'aiops-locale'

function getSavedLocale() {
  return localStorage.getItem(LOCALE_KEY) || 'zh-CN'
}

export function setLocale(locale) {
  localStorage.setItem(LOCALE_KEY, locale)
}

export function getLocale() {
  return getSavedLocale()
}

const i18n = createI18n({
  legacy: false,
  locale: getSavedLocale(),
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
})

export default i18n
