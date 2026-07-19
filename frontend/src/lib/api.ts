import { writable } from 'svelte/store'

/** Send an actuator command through the hub REST API. */
export async function sendCommand(
  nodeId: string,
  actuatorId: string,
  value: boolean | number | string,
): Promise<void> {
  const res = await fetch(`/api/nodes/${encodeURIComponent(nodeId)}/command`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ actuator_id: actuatorId, value }),
  })
  if (!res.ok) throw new Error(`command failed: ${res.status}`)
}

/** Planner thresholds, mirrored from the hub's Thresholds dataclass. */
export interface PlanningThresholds {
  moisture_dry_pct: number
  moisture_dry_pct_hot: number
  temp_high_c: number
  humidity_high_pct: number
  co2_high_ppm: number
  tank_low_pct: number
  cloud_cover_threshold: number
  hot_forecast_c: number
  tank_empty_cm: number
  tank_full_cm: number
}

/**
 * Last known thresholds, shared across components. getThresholds and
 * updateThresholds refresh it, so e.g. the node cards' tank-percentage
 * recomputes immediately when the Automation config panel saves.
 */
export const thresholds = writable<PlanningThresholds | null>(null)

export async function getThresholds(): Promise<PlanningThresholds> {
  const res = await fetch('/api/planning')
  if (!res.ok) throw new Error(`planning state failed: ${res.status}`)
  const th: PlanningThresholds = (await res.json()).thresholds
  thresholds.set(th)
  return th
}

export async function updateThresholds(
  update: Partial<PlanningThresholds>,
): Promise<PlanningThresholds> {
  const res = await fetch('/api/planning/thresholds', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  })
  if (!res.ok) throw new Error(`thresholds update failed: ${res.status}`)
  const th: PlanningThresholds = await res.json()
  thresholds.set(th)
  return th
}

/** Weather source configuration, mirrored from the hub's WeatherConfig. */
export interface WeatherConfig {
  mode: 'auto' | 'manual'
  lat: number | null
  lon: number | null
  cloud_cover: number // manual-mode values
  temp_forecast_c: number
  is_day: boolean
}

export async function getWeatherConfig(): Promise<WeatherConfig> {
  const res = await fetch('/api/weather')
  if (!res.ok) throw new Error(`weather config failed: ${res.status}`)
  return res.json()
}

export async function updateWeatherConfig(
  update: Partial<WeatherConfig>,
): Promise<WeatherConfig> {
  const res = await fetch('/api/weather', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  })
  if (!res.ok) throw new Error(`weather update failed: ${res.status}`)
  return res.json()
}
