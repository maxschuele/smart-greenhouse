<script lang="ts">
  import { getWeatherConfig, updateWeatherConfig, type WeatherConfig } from '$lib/api'
  import { Badge } from '$lib/components/ui/badge'
  import { Button } from '$lib/components/ui/button'
  import * as Card from '$lib/components/ui/card'
  import { Separator } from '$lib/components/ui/separator'
  import { Switch } from '$lib/components/ui/switch'
  import { now, topics } from '$lib/stores'
  import { CloudSun, LoaderCircle, Moon, Sun } from '@lucide/svelte'
  import { onMount } from 'svelte'

  // Payload published by hub/weather.py on virtual/weather.
  interface WeatherReading {
    cloud_cover?: number
    temp_forecast_c?: number
    is_day?: boolean
    source?: string
  }

  const reading = $derived.by((): WeatherReading | null => {
    const state = $topics['virtual/weather']
    if (!state) return null
    try {
      return JSON.parse(state.payload) as WeatherReading
    } catch {
      return null
    }
  })
  const ts = $derived($topics['virtual/weather']?.ts ?? null)
  const ago = $derived(ts === null ? null : Math.max(0, Math.round(($now - ts) / 1000)))

  // Config form: loaded once from the hub, edited locally, saved via PUT.
  let config = $state<WeatherConfig | null>(null)
  let lat = $state('')
  let lon = $state('')
  let cloudPct = $state('')
  let tempC = $state('')
  let busy = $state(false)
  let error = $state<string | null>(null)

  onMount(async () => {
    try {
      applyConfig(await getWeatherConfig())
    } catch {
      error = 'failed to load weather config'
    }
  })

  function applyConfig(c: WeatherConfig) {
    config = c
    lat = c.lat === null ? '' : String(c.lat)
    lon = c.lon === null ? '' : String(c.lon)
    cloudPct = String(Math.round(c.cloud_cover * 100))
    tempC = String(c.temp_forecast_c)
  }

  async function put(update: Partial<WeatherConfig>) {
    busy = true
    error = null
    try {
      applyConfig(await updateWeatherConfig(update))
    } catch {
      error = 'update failed'
    } finally {
      busy = false
    }
  }

  function apply() {
    if (!config) return
    if (config.mode === 'auto') {
      const la = lat.trim() === '' ? null : Number(lat)
      const lo = lon.trim() === '' ? null : Number(lon)
      if ((la !== null && !Number.isFinite(la)) || (lo !== null && !Number.isFinite(lo))) {
        error = 'invalid coordinates'
        return
      }
      put({ lat: la, lon: lo })
    } else {
      const cloud = Number(cloudPct)
      const temp = Number(tempC)
      if (!Number.isFinite(cloud) || cloud < 0 || cloud > 100 || !Number.isFinite(temp)) {
        error = 'invalid values'
        return
      }
      put({ cloud_cover: cloud / 100, temp_forecast_c: temp })
    }
  }

  const values = $derived<[string, string][]>([
    [
      'cloud cover',
      reading?.cloud_cover === undefined ? '—' : `${Math.round(reading.cloud_cover * 100)} %`,
    ],
    [
      'forecast max',
      reading?.temp_forecast_c === undefined ? '—' : `${reading.temp_forecast_c.toFixed(1)} °C`,
    ],
    ['daylight', reading?.is_day === undefined ? '—' : reading.is_day ? 'day' : 'night'],
  ])

  const inputClass =
    'h-8 w-full rounded-md border border-input bg-transparent px-2 text-sm tabular-nums ' +
    'outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50'
</script>

<Card.Root>
  <Card.Header>
    <div class="flex items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <CloudSun class="size-4 text-muted-foreground" />
        <Card.Title class="text-base font-medium">weather</Card.Title>
      </div>
      <Badge variant="secondary" class="text-sky-500">virtual</Badge>
    </div>
    <Card.Description class="font-mono text-xs">
      {reading?.source === 'manual' ? 'manual override' : 'open-meteo forecast'}
      → virtual/weather
    </Card.Description>
  </Card.Header>
  <Card.Content class="space-y-4">
    <div class="space-y-3">
      {#each values as [label, value] (label)}
        <div class="flex items-baseline justify-between gap-2">
          <span class="text-sm text-muted-foreground">{label}</span>
          <span class="text-xl font-semibold tabular-nums">{value}</span>
        </div>
      {/each}
    </div>

    <Separator />

    {#if config === null}
      <p class="text-sm text-muted-foreground">{error ?? 'Loading configuration...'}</p>
    {:else}
      <div class="space-y-3">
        <div class="flex items-center gap-1">
          <Button
            size="xs"
            variant={config.mode === 'auto' ? 'secondary' : 'ghost'}
            disabled={busy}
            onclick={() => put({ mode: 'auto' })}
          >
            Open-Meteo
          </Button>
          <Button
            size="xs"
            variant={config.mode === 'manual' ? 'secondary' : 'ghost'}
            disabled={busy}
            onclick={() => put({ mode: 'manual' })}
          >
            Manual
          </Button>
          {#if busy}
            <LoaderCircle class="size-3.5 animate-spin text-muted-foreground" />
          {/if}
          {#if error}
            <span class="text-xs text-destructive">{error}</span>
          {/if}
        </div>

        {#if config.mode === 'auto'}
          <div class="flex items-end gap-2">
            <label class="flex-1 space-y-1">
              <span class="text-xs text-muted-foreground">latitude</span>
              <input class={inputClass} bind:value={lat} placeholder="48.78" />
            </label>
            <label class="flex-1 space-y-1">
              <span class="text-xs text-muted-foreground">longitude</span>
              <input class={inputClass} bind:value={lon} placeholder="9.18" />
            </label>
            <Button size="sm" variant="outline" disabled={busy} onclick={apply}>Apply</Button>
          </div>
          {#if config.lat === null || config.lon === null}
            <p class="text-xs text-amber-600">
              No coordinates set — nothing is published until you apply some.
            </p>
          {/if}
        {:else}
          <div class="flex items-end gap-2">
            <label class="flex-1 space-y-1">
              <span class="text-xs text-muted-foreground">cloud cover %</span>
              <input class={inputClass} bind:value={cloudPct} placeholder="80" />
            </label>
            <label class="flex-1 space-y-1">
              <span class="text-xs text-muted-foreground">forecast °C</span>
              <input class={inputClass} bind:value={tempC} placeholder="33" />
            </label>
            <Button size="sm" variant="outline" disabled={busy} onclick={apply}>Apply</Button>
          </div>
          <div class="flex items-center justify-between gap-2">
            <span class="flex items-center gap-1.5 text-sm font-medium">
              {#if config.is_day}<Sun class="size-3.5 text-amber-500" />{:else}<Moon
                  class="size-3.5 text-indigo-400"
                />{/if}
              daylight
            </span>
            <Switch
              checked={config.is_day}
              disabled={busy}
              onCheckedChange={(v: boolean) => put({ is_day: v })}
              aria-label="toggle daylight"
            />
          </div>
        {/if}
      </div>
    {/if}

    <p class="text-xs text-muted-foreground">
      {ago === null ? 'nothing published yet' : `updated ${ago}s ago`}
    </p>
  </Card.Content>
</Card.Root>
