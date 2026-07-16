import { MAX_POINTS, numeric, type Point, type Reading, connection, series, topics } from './stores'

let ws: WebSocket | null = null
let backoff = 500

interface Snapshot {
  type: 'snapshot'
  data: Record<string, { payload: string; ts: number }> // ts: epoch seconds
}
interface Message {
  type: 'message'
  topic: string
  payload: string
  ts: number // epoch seconds
}

function pushPoint(m: Record<string, Point[]>, key: string, t: number, v: number): void {
  const pts: Point[] = [...(m[key] ?? []), { t, v }]
  if (pts.length > MAX_POINTS) pts.splice(0, pts.length - MAX_POINTS)
  m[key] = pts
}

function record(topic: string, payload: string, ts: number): void {
  topics.update((m) => ({ ...m, [topic]: { payload, ts } }))

  const telemetry = topic.match(/^nodes\/([^/]+)\/telemetry$/)
  if (telemetry) {
    // Chart each numeric reading under "<nodeId>/<sensorId>".
    let readings: Reading[]
    try {
      readings = JSON.parse(payload).readings ?? []
    } catch {
      return
    }
    series.update((m) => {
      const next = { ...m }
      for (const r of readings) {
        if (typeof r.number === 'number') pushPoint(next, `${telemetry[1]}/${r.sensor_id}`, ts, r.number)
      }
      return next
    })
    return
  }

  // Plain-text topics (demo/#) chart their payload when purely numeric.
  const v = numeric(payload)
  if (v === null) return
  series.update((m) => {
    const next = { ...m }
    pushPoint(next, topic, ts, v)
    return next
  })
}

/**
 * Open the hub WebSocket and stream messages into the stores. Reconnects with
 * exponential backoff so a hub restart heals without a page reload. The URL is
 * relative, so it works behind the Vite dev proxy and when served by the hub.
 */
export function connect(): void {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  connection.set('connecting')
  ws = new WebSocket(`${proto}://${location.host}/ws`)

  ws.onopen = () => {
    connection.set('open')
    backoff = 500
  }

  ws.onmessage = (ev) => {
    const msg: Snapshot | Message = JSON.parse(ev.data)
    if (msg.type === 'snapshot') {
      for (const [topic, { payload, ts }] of Object.entries(msg.data)) record(topic, payload, ts * 1000)
    } else if (msg.type === 'message') {
      record(msg.topic, msg.payload, msg.ts * 1000)
    }
  }

  ws.onclose = () => {
    connection.set('closed')
    setTimeout(connect, backoff)
    backoff = Math.min(backoff * 2, 10_000)
  }

  ws.onerror = () => ws?.close()
}
