// src/components/models/ModelRequiredDialog.tsx
//
// Shown when models:required event fires (first launch without models).
// Blocks interaction until all required models are downloaded.

import { useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '../ui/dialog'
import { Button } from '../ui/button'
import { Progress } from '../ui/progress'
import { useModelsStore } from '../../store/models'
import { useT } from '../../hooks/useT'

export function ModelRequiredDialog() {
  const t = useT()
  const {
    variants,
    downloads,
    requiredMissing,
    isRequiredDialogOpen,
    dismissRequiredDialog,
    startDownload,
    loadVariants,
  } = useModelsStore()

  // Load variants when dialog opens
  useEffect(() => {
    if (isRequiredDialogOpen) loadVariants()
  }, [isRequiredDialogOpen])

  // Auto-close when all required models are downloaded
  useEffect(() => {
    if (!isRequiredDialogOpen) return
    if (requiredMissing.length === 0) return
    const allDone = requiredMissing.every((id) =>
      variants.find((v) => v.variant_id === id)?.is_downloaded
    )
    if (allDone) dismissRequiredDialog()
  }, [variants, requiredMissing, isRequiredDialogOpen])

  const missingVariants = variants.filter((v) => requiredMissing.includes(v.variant_id))

  return (
    <Dialog open={isRequiredDialogOpen} onOpenChange={(open) => { if (!open) dismissRequiredDialog(); }}>
      <DialogContent
        className="max-w-lg"
        onPointerDownOutside={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>{t('models.required_title')}</DialogTitle>
          <DialogDescription>{t('models.required_desc')}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 mt-4">
          {missingVariants.map((v) => {
            const dl = downloads[v.variant_id]
            const isDownloading = !!dl
            const pct =
              dl && dl.totalBytes
                ? Math.round((dl.downloadedBytes / dl.totalBytes) * 100)
                : 0

            return (
              <div
                key={v.variant_id}
                className="border border-border rounded-md p-3 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-text-primary">{v.name}</p>
                    <p className="text-xs text-text-muted">
                      {v.description} · {v.size_display}
                    </p>
                  </div>
                  {!isDownloading && !v.is_downloaded && (
                    <Button size="sm" onClick={() => startDownload(v.variant_id)}>
                      {t('models.action_download')}
                    </Button>
                  )}
                  {v.is_downloaded && (
                    <span className="text-xs text-status-success">
                      {t('models.status_downloaded')}
                    </span>
                  )}
                </div>

                {isDownloading && (
                  <div className="space-y-1">
                    <Progress value={pct} className="h-1.5" />
                    <div className="flex justify-between text-xs text-text-muted">
                      <span>
                        {t('models.download_speed', {
                          speed: formatSpeed(dl.speedBps),
                        })}
                      </span>
                      {dl.etaSecs != null && (
                        <span>
                          {t('models.download_eta', {
                            eta: formatEta(dl.etaSecs),
                          })}
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )
          })}

          {missingVariants.length === 0 && isRequiredDialogOpen && (
            <p className="text-sm text-text-muted text-center py-4">
              {t('common.loading')}
            </p>
          )}
        </div>

        <div className="flex justify-end mt-4">
          <Button variant="ghost" size="sm" onClick={dismissRequiredDialog}>
            {t('common.later')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
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
