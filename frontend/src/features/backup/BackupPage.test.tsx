import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '@/lib/api'
import { BackupPage } from './BackupPage'

const snapshot = (name: string, created_at: string) => ({ name, created_at, kind: 'auto' as const, size_bytes: 1024 })
const status = {
  snapshots: [snapshot('learning-20261017-120000-auto.zip', '2026-10-17T04:00:00'), snapshot('learning-20261016-120000-auto.zip', '2026-10-16T04:00:00')],
  folder: 'C:/data/backups',
  auto_hours: 24,
  keep: 7,
}

// jsdom 沒有實作 <dialog> 的 showModal／close；照瀏覽器行為補上：Esc 先發 cancel，沒被擋才關閉並發 close
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function () {
    if (!this.hasAttribute('open')) return
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
})

function pressEscape(dialog: HTMLDialogElement) {
  const cancel = new Event('cancel', { cancelable: true })
  dialog.dispatchEvent(cancel)
  if (!cancel.defaultPrevented) dialog.close()
}

const openDialogs = () => Array.from(document.querySelectorAll('dialog')).filter((dialog) => dialog.open)

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <BackupPage />
    </QueryClientProvider>,
  )
}

afterEach(() => vi.restoreAllMocks())

describe('BackupPage', () => {
  it('keeps the restore dialog open on Escape while restoring, so a failure is visible and it can be reopened', async () => {
    vi.spyOn(api, 'get').mockResolvedValue(status)
    let fail: (error: unknown) => void = () => {}
    vi.spyOn(api, 'post').mockImplementation(() => new Promise((_, reject) => (fail = reject)))
    renderPage()

    fireEvent.click((await screen.findAllByRole('button', { name: /^還原 / }))[0])
    fireEvent.click(screen.getByRole('button', { name: '覆蓋目前的資料' }))
    await screen.findByRole('button', { name: '還原中…' })

    const [dialog] = openDialogs()
    act(() => pressEscape(dialog))
    expect(dialog.open).toBe(true)

    await act(async () => fail(new ApiError(500, '還原失敗了')))
    expect(await within(dialog).findByText('還原失敗了')).toBeTruthy()

    // 失敗後可以關掉，再打開另一份
    act(() => pressEscape(dialog))
    expect(openDialogs()).toHaveLength(0)
    fireEvent.click(screen.getAllByRole('button', { name: /^還原 / })[1])
    expect(openDialogs()).toHaveLength(1)
  })

  it('clears the previous error when opening the dialog for another snapshot', async () => {
    vi.spyOn(api, 'get').mockResolvedValue(status)
    vi.spyOn(api, 'post').mockRejectedValue(new ApiError(400, '這不是有效的 zip 備份檔'))
    vi.spyOn(api, 'delete').mockRejectedValue(new ApiError(404, '找不到這份備份'))
    renderPage()

    fireEvent.click((await screen.findAllByRole('button', { name: /^還原 / }))[0])
    fireEvent.click(screen.getByRole('button', { name: '覆蓋目前的資料' }))
    await screen.findByText('這不是有效的 zip 備份檔')
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    fireEvent.click(screen.getAllByRole('button', { name: /^還原 / })[1])
    expect(screen.queryByText('這不是有效的 zip 備份檔')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    fireEvent.click(screen.getAllByRole('button', { name: /^刪除 / })[0])
    fireEvent.click(screen.getByRole('button', { name: '刪除' }))
    await screen.findByText('找不到這份備份')
    fireEvent.click(screen.getAllByRole('button', { name: '取消' }).at(-1)!)
    fireEvent.click(screen.getAllByRole('button', { name: /^刪除 / })[1])
    await waitFor(() => expect(screen.queryByText('找不到這份備份')).toBeNull())
  })
})
