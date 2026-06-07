import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { initSettings, saveSettings } from '@/lib/settings'
import { getAppSettings } from '@/lib/api'

initSettings()
getAppSettings().then((data) => {
  if (!data) return
  saveSettings({
    autoSaveInterval: data.auto_save_interval,
    maxSaveSlots: data.max_save_slots,
    exportFormat: data.export_format,
    autoExport: data.auto_export,
  }, { skipEngineSync: true })
}).catch(() => {})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
