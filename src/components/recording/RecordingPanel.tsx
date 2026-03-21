import { useEffect, useState } from 'react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { useRecordingStore } from '@/store/recording'
import { commands } from '@/lib/bindings'

const LANGUAGES = [
  { value: 'auto', label: 'Auto Detect' },
  { value: 'zh',   label: '中文' },
  { value: 'en',   label: 'English' },
  { value: 'fr',   label: 'Français' },
  { value: 'ja',   label: '日本語' },
]

interface RecordingPanelProps {
  onConfigChange?: (config: {
    deviceId: string
    language: string
    mode: 'record_only' | 'transcribe_only' | 'transcribe_and_translate'
    targetLang: string
    vadThreshold: number
    autoProcess: boolean
  }) => void
}

export function RecordingPanel({ onConfigChange }: RecordingPanelProps) {
  const { devices, devicesLoading, loadDevices } = useRecordingStore()

  const [deviceId, setDeviceId] = useState<string>('')
  const [language, setLanguage] = useState<string>('auto')
  const [mode, setMode] = useState<'record_only' | 'transcribe_only' | 'transcribe_and_translate'>('transcribe_only')
  const [targetLang, setTargetLang] = useState<string>('en')
  const [vadThreshold, setVadThreshold] = useState<number>(0.008)
  const [autoProcess, setAutoProcess] = useState<boolean>(false)

  // Load defaults from AppConfig on mount
  useEffect(() => {
    commands.getConfig().then((r) => {
      if (r.status === 'ok' && r.data) {
        const cfg = r.data
        // 将保存的阈值 clamp 到合理范围：iPhone 麦克风 RMS 通常 0.003–0.04，
        // 阈值超过 0.05 基本会过滤掉所有语音
        // iPhone Continuity Camera 麦克风 RMS 通常 0.001–0.030，阈值超过 0.020 会过滤所有语音
        if (cfg.vad_threshold != null) setVadThreshold(Math.min(cfg.vad_threshold, 0.015))
        if (cfg.default_language) setLanguage(cfg.default_language)
        if (cfg.auto_llm_on_stop != null) setAutoProcess(cfg.auto_llm_on_stop)
      }
    })
    loadDevices()
  }, [loadDevices])

  useEffect(() => {
    const defaultDevice = devices.find((d) => d.is_default)
    if (defaultDevice && !deviceId) setDeviceId(defaultDevice.id)
  }, [devices, deviceId])

  useEffect(() => {
    onConfigChange?.({ deviceId, language, mode, targetLang, vadThreshold, autoProcess })
  }, [deviceId, language, mode, targetLang, vadThreshold, autoProcess, onConfigChange])

  return (
    <div className="flex flex-col gap-4 p-4 overflow-y-auto h-full">
      <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
        Input
      </h2>

      {/* 设备选择 */}
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs text-text-muted">Microphone</Label>
        <Select value={deviceId} onValueChange={setDeviceId} disabled={devicesLoading}>
          <SelectTrigger className="h-8 text-xs">
            <SelectValue placeholder={devicesLoading ? 'Loading...' : 'Select device'} />
          </SelectTrigger>
          <SelectContent>
            {devices.map((d) => (
              <SelectItem key={d.id} value={d.id} className="text-xs">
                {d.name}{d.is_default ? ' (Default)' : ''}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* 语言选择 */}
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs text-text-muted">Language</Label>
        <Select value={language} onValueChange={setLanguage}>
          <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            {LANGUAGES.map((l) => (
              <SelectItem key={l.value} value={l.value} className="text-xs">{l.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* 录音模式 */}
      <div className="flex flex-col gap-2">
        <Label className="text-xs text-text-muted">Mode</Label>
        <RadioGroup value={mode} onValueChange={(v) => setMode(v as typeof mode)} className="gap-1.5">
          <div className="flex items-center gap-2">
            <RadioGroupItem value="record_only" id="mode-record" />
            <Label htmlFor="mode-record" className="text-xs cursor-pointer font-normal">Record Only</Label>
          </div>
          <div className="flex items-center gap-2">
            <RadioGroupItem value="transcribe_only" id="mode-transcribe" />
            <Label htmlFor="mode-transcribe" className="text-xs cursor-pointer font-normal">Transcribe</Label>
          </div>
          <div className="flex items-center gap-2">
            <RadioGroupItem value="transcribe_and_translate" id="mode-translate" />
            <Label htmlFor="mode-translate" className="text-xs cursor-pointer font-normal">Transcribe + Translate</Label>
          </div>
        </RadioGroup>
      </div>

      {/* 目标语言（仅 TranscribeAndTranslate 模式显示） */}
      {mode === 'transcribe_and_translate' && (
        <div className="flex flex-col gap-1.5">
          <Label className="text-xs text-text-muted">Target Language</Label>
          <Select value={targetLang} onValueChange={setTargetLang}>
            <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {LANGUAGES.filter((l) => l.value !== 'auto').map((l) => (
                <SelectItem key={l.value} value={l.value} className="text-xs">{l.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* VAD 灵敏度滑块 */}
      <div className="flex flex-col gap-2">
        <div className="flex justify-between items-center">
          <Label className="text-xs text-text-muted">VAD Threshold</Label>
          <span className={`text-xs font-mono ${vadThreshold > 0.025 ? 'text-yellow-500' : 'text-text-muted'}`}>
            {vadThreshold.toFixed(3)}
          </span>
        </div>
        <Slider
          min={0.001} max={0.1} step={0.001}
          value={[vadThreshold]}
          onValueChange={([v]) => setVadThreshold(v)}
          className="w-full"
        />
        <p className="text-xs text-text-muted leading-tight">
          推荐值 0.005–0.015。iPhone 麦克风 RMS 通常仅 0.005–0.025，阈值过高会过滤所有语音。
        </p>
      </div>

      {/* 自动处理开关 */}
      <div className="flex items-center justify-between">
        <Label className="text-xs text-text-muted">Auto Process After Stop</Label>
        <Switch
          checked={autoProcess}
          onCheckedChange={setAutoProcess}
          className="scale-75"
        />
      </div>
    </div>
  )
}

export type { RecordingPanelProps }
export type RecordingPanelConfig = {
  deviceId: string
  language: string
  mode: 'record_only' | 'transcribe_only' | 'transcribe_and_translate'
  targetLang: string
  vadThreshold: number
  autoProcess: boolean
}
