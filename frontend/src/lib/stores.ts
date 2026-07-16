import { derived, writable } from 'svelte/store'

export type Connection = 'connecting' | 'open' | 'closed'

export interface TopicState {
  payload: string
  ts: number // epoch ms, server-side receive time
}

export interface Point {
  t: number
  v: number
}

// Shapes produced by the hub's MessageToDict(preserving_proto_field_name=True)
// of NodeAdvert/Telemetry. Empty repeated fields are omitted entirely, and
// uint64 timestamp_ms arrives as a string; rely on the server ts instead.
export interface SensorCap {
  sensor_id: string
  kind?: string
  unit?: string
}

export interface ActuatorCap {
  actuator_id: string
  kind?: string
}

export interface Advert {
  node_id: string
  hw?: string
  fw_version?: string
  sensors?: SensorCap[]
  actuators?: ActuatorCap[]
}

export interface Reading {
  sensor_id: string
  number?: number
  boolean?: boolean
  text?: string
}

export interface NodeState {
  id: string
  advert: Advert | null
  readings: Record<string, Reading> // latest reading per sensor_id
  lastSeen: number // epoch ms, max(advert ts, telemetry ts)
}

/** Latest payload + server receive time per topic. */
export const topics = writable<Record<string, TopicState>>({})

/** Bounded numeric history per series key (topic, or nodeId/sensorId). */
export const series = writable<Record<string, Point[]>>({})

/** WebSocket connection state. */
export const connection = writable<Connection>('closed')

/** Ticks once per second so "updated Ns ago" labels stay live. */
export const now = writable<number>(Date.now())

export const MAX_POINTS = 60

/**
 * A node is online while its last advert/telemetry is younger than this
 * (nodes advertise every 30 s and publish telemetry every 5 s). Compares
 * server timestamps against the client clock, so a skewed hub clock shows
 * every node offline.
 */
export const ONLINE_THRESHOLD_MS = 30_000

/** Node registry derived from nodes/<id>/advert + nodes/<id>/telemetry topics. */
export const nodes = derived(topics, ($topics) => {
  const out: Record<string, NodeState> = {}
  for (const [topic, state] of Object.entries($topics)) {
    const m = topic.match(/^nodes\/([^/]+)\/(advert|telemetry)$/)
    if (!m) continue
    const id = m[1]
    const node = (out[id] ??= { id, advert: null, readings: {}, lastSeen: 0 })
    let parsed: unknown
    try {
      parsed = JSON.parse(state.payload)
    } catch {
      continue
    }
    if (m[2] === 'advert') {
      node.advert = parsed as Advert
    } else {
      for (const r of (parsed as { readings?: Reading[] }).readings ?? []) {
        node.readings[r.sensor_id] = r
      }
    }
    node.lastSeen = Math.max(node.lastSeen, state.ts)
  }
  return out
})

/** Parse a payload as a number, or return null if it is not purely numeric. */
export function numeric(payload: string): number | null {
  const s = payload.trim()
  if (s === '') return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}
