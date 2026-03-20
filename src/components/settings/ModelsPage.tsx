// src/components/settings/ModelsPage.tsx
//
// Settings sub-page for model management.
// Shows Whisper and LLM groups with download, cancel, delete, set-active actions.

import { useEffect } from 'react'
import { useModelsStore } from '../../store/models'
import { useT } from '../../hooks/useT'
import { Button } from '../ui/button'
import { Progress } from '../ui/progress'
import { Badge } from '../ui/badge'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '../ui/alert-dialog'
import type { ModelVariant } from '../../lib/bindings'

export function ModelsPage() {
  const t = useT()
  const {
    variants,
    downloads,
    loadVariants,
    startDownload,
    cancelDownload,
    deleteModel,
    setActive,
  } = useModelsStore()

  useEffect(() => {
    loadVariants()
  }, [])

  const whisperVariants = variants.filter((v) => v.model_type === 'whisper')
  const llmVariants = variants.filter((v) => v.model_type === 'llm')

  return (
    <div className="p-6 space-y-8 max-w-2xl">
      <h1 className="text-xl font-semibold text-text-primary">
        {t('models.page_title')}
      </h1>

      <ModelGroup
        title={t('models.group_whisper')}
        variants={whisperVariants}
        downloads={downloads}
        t={t}
        onDownload={startDownload}
        onCancel={cancelDownload}
        onDelete={deleteModel}
        onSetActive={setActive}
      />

      <ModelGroup
        title={t('models.group_llm')}
        variants={llmVariants}
        downloads={downloads}
        t={t}
        onDownload={startDownload}
        onCancel={cancelDownload}
        onDelete={deleteModel}
        onSetActive={setActive}
      />
    </div>
  )
}

// ── ModelGroup ────────────────────────────────────────────────

interface ModelGroupProps {
  title: string
  variants: ModelVariant[]
  downloads: Record<
    string,
    {
      downloadedBytes: number
      totalBytes: number | null
      speedBps: number
      etaSecs: number | null
    }
  >
  t: (key: string, vars?: Record<string, string>) => string
  onDownload: (id: string) => void
  onCancel: (id: string) => void
  onDelete: (id: string) => Promise<void>
  onSetActive: (id: string) => Promise<void>
}

function ModelGroup({
  title,
  variants,
  downloads,
  t,
  onDownload,
  onCancel,
  onDelete,
  onSetActive,
}: ModelGroupProps) {
  if (variants.length === 0) return null

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium text-text-secondary uppercase tracking-wide">
        {title}
      </h2>
      <div className="space-y-2">
        {variants.map((v) => (
          <ModelRow
            key={v.variant_id}
            variant={v}
            dlState={downloads[v.variant_id]}
            t={t}
            onDownload={onDownload}
            onCancel={onCancel}
            onDelete={onDelete}
            onSetActive={onSetActive}
          />
        ))}
      </div>
    </section>
  )
}

// ── ModelRow ──────────────────────────────────────────────────

interface ModelRowProps {
  variant: ModelVariant
  dlState?: {
    downloadedBytes: number
    totalBytes: number | null
    speedBps: number
    etaSecs: number | null
  }
  t: (key: string, vars?: Record<string, string>) => string
  onDownload: (id: string) => void
  onCancel: (id: string) => void
  onDelete: (id: string) => Promise<void>
  onSetActive: (id: string) => Promise<void>
}

function ModelRow({
  variant: v,
  dlState,
  t,
  onDownload,
  onCancel,
  onDelete,
  onSetActive,
}: ModelRowProps) {
  const isDownloading = !!dlState
  const pct =
    dlState?.totalBytes
      ? Math.round((dlState.downloadedBytes / dlState.totalBytes) * 100)
      : 0

  return (
    <div className="border border-border rounded-lg p-4 space-y-3">
      {/* Title row */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-text-primary">{v.name}</span>
            {v.is_active && (
              <Badge
                variant="outline"
                className="text-xs text-accent border-accent"
              >
                {t('models.status_active')}
              </Badge>
            )}
          </div>
          <p className="text-xs text-text-muted mt-0.5">{v.description}</p>
          <p className="text-xs text-text-muted">{v.size_display}</p>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 shrink-0">
          {!v.is_downloaded && !isDownloading && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onDownload(v.variant_id)}
            >
              {t('models.action_download')}
            </Button>
          )}

          {isDownloading && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onCancel(v.variant_id)}
            >
              {t('models.action_cancel')}
            </Button>
          )}

          {v.is_downloaded && !v.is_active && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onSetActive(v.variant_id)}
            >
              {t('models.action_set_active')}
            </Button>
          )}

          {v.is_downloaded && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-status-error hover:text-status-error"
                >
                  {t('models.action_delete')}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>{t('models.action_delete')}</AlertDialogTitle>
                  <AlertDialogDescription>
                    {t('models.delete_confirm')}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                  <AlertDialogAction
                    className="bg-status-error text-white hover:bg-status-error/90"
                    onClick={() => onDelete(v.variant_id)}
                  >
                    {t('models.action_delete')}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
        </div>
      </div>

      {/* Progress bar (shown while downloading) */}
      {isDownloading && dlState && (
        <div className="space-y-1">
          <Progress value={pct} className="h-1.5" />
          <div className="flex justify-between text-xs text-text-muted">
            <span>
              {formatBytes(dlState.downloadedBytes)}
              {dlState.totalBytes != null
                ? ` / ${formatBytes(dlState.totalBytes)}`
                : ''}{' '}
              ·{' '}
              {t('models.download_speed', {
                speed: formatSpeed(dlState.speedBps),
              })}
            </span>
            {dlState.etaSecs != null && (
              <span>
                {t('models.download_eta', { eta: formatEta(dlState.etaSecs) })}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Formatters ────────────────────────────────────────────────

function formatBytes(b: number): string {
  if (b >= 1_073_741_824) return `${(b / 1_073_741_824).toFixed(1)} GB`
  if (b >= 1_048_576) return `${(b / 1_048_576).toFixed(0)} MB`
  if (b >= 1_024) return `${(b / 1_024).toFixed(0)} KB`
  return `${b} B`
}

function formatSpeed(bps: number): string {
  if (bps >= 1_048_576) return `${(bps / 1_048_576).toFixed(1)} MB`
  if (bps >= 1_024) return `${(bps / 1_024).toFixed(0)} KB`
  return `${bps} B`
}

function formatEta(secs: number): string {
  if (secs >= 3600)
    return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`
  if (secs >= 60) return `${Math.floor(secs / 60)}m ${secs % 60}s`
  return `${secs}s`
}
