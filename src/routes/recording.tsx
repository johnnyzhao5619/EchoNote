import { useState, useCallback, useEffect } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { RecordingPanel, type RecordingPanelConfig } from '@/components/recording/RecordingPanel'
import { RecordingMain } from '@/components/recording/RecordingMain'
import { useShellStore } from '@/store/shell'
import type { RealtimeConfig } from '@/lib/bindings'

export const Route = createFileRoute('/recording')({
  component: RecordingPage,
})

function buildConfig(panel: RecordingPanelConfig): RealtimeConfig {
  return {
    device_id: panel.deviceId || null,
    language: panel.language === 'auto' ? null : panel.language || null,
    // RecordingMode from bindings: "record_only" | "transcribe_only" | { transcribe_and_translate: { target_language } }
    mode: panel.mode === 'transcribe_and_translate'
      ? { transcribe_and_translate: { target_language: panel.targetLang } }
      : panel.mode,   // 'record_only' | 'transcribe_only' pass through directly
    vad_threshold: panel.vadThreshold,
  }
}

function RecordingPage() {
  const setSecondPanelContent = useShellStore((s) => s.setSecondPanelContent)
  const [config, setConfig] = useState<RealtimeConfig | undefined>(undefined)

  const handleConfigChange = useCallback((panelConfig: RecordingPanelConfig) => {
    setConfig(buildConfig(panelConfig))
  }, [])

  // Inject RecordingPanel into the Shell's SecondPanel slot
  useEffect(() => {
    setSecondPanelContent(<RecordingPanel onConfigChange={handleConfigChange} />)
    return () => setSecondPanelContent(null)
  }, [setSecondPanelContent, handleConfigChange])

  return (
    <div className="flex flex-col h-full">
      <RecordingMain config={config} />
    </div>
  )
}
