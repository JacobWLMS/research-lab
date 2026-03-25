import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import './style.css'

// Initialize theme before mount (composable applies data-theme on import)
import './composables/useTheme'
import './composables/useZoom'

const app = createApp(App)
app.use(router)
app.mount('#app')
