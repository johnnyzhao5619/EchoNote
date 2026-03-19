import { ref, watch, onMounted } from 'vue'

const THEME_STORAGE_KEY = 'echonote-theme'

export function useTheme() {
  const isDark = ref(false)

  const applyTheme = (dark: boolean) => {
    if (typeof document !== 'undefined') {
      if (dark) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    }
  }

  const toggleTheme = () => {
    isDark.value = !isDark.value
    localStorage.setItem(THEME_STORAGE_KEY, isDark.value ? 'dark' : 'light')
  }

  onMounted(() => {
    const savedTheme = localStorage.getItem(THEME_STORAGE_KEY)
    if (savedTheme) {
      isDark.value = savedTheme === 'dark'
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      isDark.value = true
    }
    applyTheme(isDark.value)
  })

  watch(isDark, (newValue) => {
    applyTheme(newValue)
  })

  return {
    isDark,
    toggleTheme
  }
}
