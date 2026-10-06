import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { HomePage } from './HomePage'

afterEach(() => vi.unstubAllGlobals())

function stubFetch(response: Promise<Response>) {
  vi.stubGlobal('fetch', vi.fn(() => response))
}

describe('HomePage', () => {
  it('後端正常時顯示「正常」', async () => {
    stubFetch(Promise.resolve(Response.json({ status: 'ok', database: 'ok' })))
    render(<HomePage />)
    expect(await screen.findByText('後端連線：正常')).toBeInTheDocument()
  })

  it('後端無法連線時顯示錯誤', async () => {
    stubFetch(Promise.reject(new TypeError('Failed to fetch')))
    render(<HomePage />)
    expect(await screen.findByText('後端連線：無法連線')).toBeInTheDocument()
  })
})
