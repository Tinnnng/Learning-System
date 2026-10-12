/**
 * 白噪音：用 Web Audio 即時合成，不用下載音檔。全站共用一個播放器（換頁不會停）。
 * - 雨聲：粉紅噪音去掉低頻，像窗外的細雨
 * - 海浪：棕噪音，音量用很慢的波起伏
 * - 風扇：棕噪音只留低頻的嗡嗡聲
 * - 白噪音：最平的沙沙聲
 * 瀏覽器規定要使用者按過按鈕才能出聲，所以只在 play() 時建立 AudioContext。
 */

import { useSyncExternalStore } from 'react'

export type NoiseKind = 'rain' | 'waves' | 'fan' | 'white'

export const NOISE_LABELS: Record<NoiseKind, string> = { rain: '雨聲', waves: '海浪', fan: '風扇', white: '白噪音' }

interface NoiseState {
  playing: NoiseKind | null
  volume: number
}

const listeners = new Set<() => void>()
let state: NoiseState = { playing: null, volume: readVolume() }
let context: AudioContext | null = null
let stopCurrent: (() => void) | null = null
let master: GainNode | null = null

function readVolume(): number {
  try {
    const value = Number(localStorage.getItem('ls-noise-volume'))
    return value > 0 && value <= 1 ? value : 0.5
  } catch {
    return 0.5
  }
}

function set(next: Partial<NoiseState>) {
  state = { ...state, ...next }
  for (const listener of listeners) listener()
}

function noiseBuffer(ctx: AudioContext, kind: 'white' | 'pink' | 'brown'): AudioBuffer {
  const length = ctx.sampleRate * 4
  const buffer = ctx.createBuffer(2, length, ctx.sampleRate)
  for (let channel = 0; channel < 2; channel += 1) {
    const data = buffer.getChannelData(channel)
    let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0, last = 0
    for (let i = 0; i < length; i += 1) {
      const white = Math.random() * 2 - 1
      if (kind === 'white') {
        data[i] = white * 0.5
      } else if (kind === 'pink') {
        // Paul Kellet 的粉紅噪音濾波
        b0 = 0.99886 * b0 + white * 0.0555179
        b1 = 0.99332 * b1 + white * 0.0750759
        b2 = 0.969 * b2 + white * 0.153852
        b3 = 0.8665 * b3 + white * 0.3104856
        b4 = 0.55 * b4 + white * 0.5329522
        b5 = -0.7616 * b5 - white * 0.016898
        data[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.11
        b6 = white * 0.115926
      } else {
        last = (last + 0.02 * white) / 1.02
        data[i] = last * 3.5
      }
    }
  }
  return buffer
}

function build(ctx: AudioContext, kind: NoiseKind, output: AudioNode): () => void {
  const source = ctx.createBufferSource()
  source.buffer = noiseBuffer(ctx, kind === 'rain' ? 'pink' : kind === 'white' ? 'white' : 'brown')
  source.loop = true
  const nodes: AudioNode[] = []
  let node: AudioNode = source

  const filter = (type: BiquadFilterType, frequency: number) => {
    const biquad = ctx.createBiquadFilter()
    biquad.type = type
    biquad.frequency.value = frequency
    node.connect(biquad)
    node = biquad
    nodes.push(biquad)
  }
  if (kind === 'rain') {
    filter('highpass', 500)
    filter('lowpass', 6000)
  } else if (kind === 'fan') {
    filter('lowpass', 380)
  } else if (kind === 'white') {
    filter('lowpass', 9000)
  }

  const gain = ctx.createGain()
  gain.gain.value = kind === 'white' ? 0.35 : 0.8
  node.connect(gain)
  gain.connect(output)

  let lfo: OscillatorNode | null = null
  if (kind === 'waves') {
    // 一波大約 8 秒：音量在 0.25～0.95 之間慢慢起伏
    lfo = ctx.createOscillator()
    lfo.frequency.value = 0.12
    const depth = ctx.createGain()
    depth.gain.value = 0.35
    gain.gain.value = 0.6
    lfo.connect(depth).connect(gain.gain)
    lfo.start()
  }
  source.start()
  return () => {
    source.stop()
    lfo?.stop()
    source.disconnect()
    gain.disconnect()
    for (const item of nodes) item.disconnect()
  }
}

export const noise = {
  async play(kind: NoiseKind) {
    if (!context) {
      context = new AudioContext()
      master = context.createGain()
      master.connect(context.destination)
    }
    await context.resume()
    stopCurrent?.()
    master!.gain.value = state.volume
    stopCurrent = build(context, kind, master!)
    set({ playing: kind })
  },
  stop() {
    stopCurrent?.()
    stopCurrent = null
    void context?.suspend()
    set({ playing: null })
  },
  setVolume(volume: number) {
    if (master) master.gain.value = volume
    try {
      localStorage.setItem('ls-noise-volume', String(volume))
    } catch {
      // 記不住音量沒關係
    }
    set({ volume })
  },
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useNoise(): NoiseState {
  return useSyncExternalStore(subscribe, () => state)
}
