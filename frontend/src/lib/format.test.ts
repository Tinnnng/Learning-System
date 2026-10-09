import { describe, expect, it } from 'vitest'
import { clock, fileSize, isoDay, parseUtc, percent, plainText, relativeDay, shortName, usd } from './format'

describe('format', () => {
  it('shortName 去掉「(包括…)」說明', () => {
    expect(shortName('法學知識與英文(包括中華民國憲法、法學緒論、英文)')).toBe('法學知識與英文')
    expect(shortName('115 年普考　法學知識與英文(包括憲法)（模擬考）')).toBe('115 年普考　法學知識與英文（模擬考）')
    expect(shortName('國文(作文與測驗)')).toBe('國文(作文與測驗)')
  })

  it('plainText 把題目轉成好讀的摘要', () => {
    expect(plainText('一個8 進制的數值$(535)_8$，其結果為：')).toBe('一個8 進制的數值(535)8，其結果為：')
    expect(plainText('$F=Z(X \\oplus Y)$')).toBe('F=Z(X ⊕ Y)')
    expect(plainText('輸出為何？\n```java\nint c = 2;\n```')).toBe('輸出為何？ 〔程式碼〕')
    expect(plainText('The painting {{blank}} a tree.')).toBe('The painting ＿＿ a tree.')
  })

  it('parseUtc 把沒有時區的時間當成 UTC', () => {
    expect(parseUtc('2026-10-06T01:00:00').toISOString()).toBe('2026-10-06T01:00:00.000Z')
  })

  it('relativeDay 以台灣時間判斷', () => {
    const now = new Date('2026-10-06T01:00:00Z') // 台灣 09:00
    expect(relativeDay('2026-10-06T15:00:00', now)).toBe('今天') // UTC 15:00＝台灣 10/6 23:00
    expect(relativeDay('2026-10-06T16:30:00', now)).toBe('明天') // UTC 16:30＝台灣 10/7 00:30
  })

  it('percent、usd、fileSize', () => {
    expect(percent(0.756)).toBe('76%')
    expect(percent(0.5, 1)).toBe('50.0%')
    expect(usd(0.24)).toBe('$0.24')
    expect(usd(0.0042)).toBe('$0.004')
    expect(usd(0)).toBe('$0.00')
    expect(fileSize(2.5 * 1024 * 1024)).toBe('2.5 MB')
    expect(fileSize(100)).toBe('1 KB')
  })

  it('isoDay 以台灣時間分天', () => {
    expect(isoDay(new Date('2026-10-06T16:30:00Z'))).toBe('2026-10-07')
  })

  it('clock', () => {
    expect(clock(59)).toBe('0:59')
    expect(clock(3600 + 65)).toBe('1:01:05')
  })
})
