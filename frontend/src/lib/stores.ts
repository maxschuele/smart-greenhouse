import { writable } from 'svelte/store'

export type Connection = 'connecting' | 'open' | 'closed'

export interface TopicState {
  payload: string
  ts: number // epoch ms, client receive time
}

export interface Point {
  t: number
  v: number
}

/** Latest payload + receive time per topic. */
export const topics = writable<Record<string, TopicState>>({})

/** Bounded history of numeric payloads per topic, for charting. */
export const series = writable<Record<string, Point[]>>({})

/** WebSocket connection state. */
export const connection = writable<Connection>('closed')

/** Ticks once per second so "updated Ns ago" labels stay live. */
export const now = writable<number>(Date.now())

export const MAX_POINTS = 60

/** Parse a payload as a number, or return null if it is not purely numeric. */
export function numeric(payload: string): number | null {
  const s = payload.trim()
  if (s === '') return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}
