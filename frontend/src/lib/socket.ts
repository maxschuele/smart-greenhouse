import { connection, MAX_POINTS, numeric, type Point, series, topics } from './stores'

let ws: WebSocket | null = null
let backoff = 500

interface Snapshot {
  type: 'snapshot'
  data: Record<string, string>
}
interface Message {
  type: 'message'
  topic: string
  payload: string
}

function record(topic: string, payload: string, ts: number): void {
  topics.update((m) => ({ ...m, [topic]: { payload, ts } }))

  const v = numeric(payload)
  if (v === null) return
  series.update((m) => {
    const pts: Point[] = [...(m[topic] ?? []), { t: ts, v }]
    if (pts.length > MAX_POINTS) pts.splice(0, pts.length - MAX_POINTS)
    return { ...m, [topic]: pts }
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
    const ts = Date.now()
    if (msg.type === 'snapshot') {
      for (const [topic, payload] of Object.entries(msg.data)) record(topic, payload, ts)
    } else if (msg.type === 'message') {
      record(msg.topic, msg.payload, ts)
    }
  }

  ws.onclose = () => {
    connection.set('closed')
    setTimeout(connect, backoff)
    backoff = Math.min(backoff * 2, 10_000)
  }

  ws.onerror = () => ws?.close()
}
