<script lang="ts">
  import { getThresholds, updateThresholds, type PlanningThresholds } from '$lib/api'
  import { Button } from '$lib/components/ui/button'
  import * as Card from '$lib/components/ui/card'
  import { CircleCheck, LoaderCircle, SlidersHorizontal } from '@lucide/svelte'
  import { onMount } from 'svelte'

  interface Field {
    key: keyof PlanningThresholds
    label: string
    unit: string
    scale?: number // display = stored * scale (cloud cover: 0-1 -> %)
  }

  const groups: { title: string; fields: Field[] }[] = [
    {
      title: 'Irrigation',
      fields: [
        { key: 'moisture_dry_pct', label: 'soil dry below', unit: '%' },
        { key: 'moisture_dry_pct_hot', label: 'dry below (hot forecast)', unit: '%' },
      ],
    },
    {
      title: 'Ventilation',
      fields: [
        { key: 'temp_high_c', label: 'temperature above', unit: '°C' },
        { key: 'humidity_high_pct', label: 'humidity above', unit: '%' },
        { key: 'co2_high_ppm', label: 'CO2 above', unit: 'ppm' },
      ],
    },
    {
      title: 'Weather',
      fields: [
        { key: 'cloud_cover_threshold', label: 'light when clouds above', unit: '%', scale: 100 },
        { key: 'hot_forecast_c', label: 'hot mode above', unit: '°C' },
      ],
    },
    {
      title: 'Water tank',
      fields: [
        { key: 'tank_low_pct', label: 'refill alert below', unit: '%' },
        { key: 'tank_empty_cm', label: 'empty at distance', unit: 'cm' },
        { key: 'tank_full_cm', label: 'full at distance', unit: 'cm' },
      ],
    },
  ]

  // Loaded thresholds (for diffing) and the editable text fields.
  let loaded = $state<PlanningThresholds | null>(null)
  let inputs = $state<Record<string, string>>({})
  let busy = $state(false)
  let error = $state<string | null>(null)
  let saved = $state(false)

  onMount(async () => {
    try {
      applyThresholds(await getThresholds())
    } catch {
      error = 'failed to load thresholds'
    }
  })

  function applyThresholds(th: PlanningThresholds) {
    loaded = th
    for (const g of groups) {
      for (const f of g.fields) {
        const v = th[f.key] * (f.scale ?? 1)
        inputs[f.key] = String(Math.round(v * 100) / 100)
      }
    }
  }

  const dirty = $derived.by(() => {
    if (loaded === null) return false
    return groups.some((g) =>
      g.fields.some((f) => Number(inputs[f.key]) !== loaded![f.key] * (f.scale ?? 1)),
    )
  })

  async function apply() {
    if (loaded === null) return
    const update: Partial<PlanningThresholds> = {}
    for (const g of groups) {
      for (const f of g.fields) {
        const n = Number(inputs[f.key])
        if (!Number.isFinite(n)) {
          error = `invalid value for ${f.label}`
          return
        }
        const stored = n / (f.scale ?? 1)
        if (stored !== loaded[f.key]) update[f.key] = stored
      }
    }
    if (Object.keys(update).length === 0) return
    busy = true
    error = null
    saved = false
    try {
      applyThresholds(await updateThresholds(update))
      saved = true
      setTimeout(() => (saved = false), 3000)
    } catch {
      error = 'update failed'
    } finally {
      busy = false
    }
  }

  const inputClass =
    'h-8 w-full rounded-md border border-input bg-transparent px-2 text-sm tabular-nums ' +
    'outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50'
</script>

<Card.Root class="md:col-span-2">
  <Card.Header>
    <div class="flex items-center gap-2">
      <SlidersHorizontal class="size-4 text-muted-foreground" />
      <Card.Title class="text-base">Automation config</Card.Title>
    </div>
    <Card.Description>
      Thresholds that turn raw readings into planner facts. Changes apply on the next planning
      cycle and reset to defaults on hub restart.
    </Card.Description>
  </Card.Header>
  <Card.Content class="space-y-4">
    {#if loaded === null}
      <p class="text-sm text-muted-foreground">{error ?? 'Loading thresholds...'}</p>
    {:else}
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {#each groups as group (group.title)}
          <div class="space-y-2">
            <p class="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              {group.title}
            </p>
            {#each group.fields as field (field.key)}
              <label class="block space-y-1">
                <span class="text-xs text-muted-foreground">{field.label}</span>
                <div class="flex items-center gap-1.5">
                  <input class={inputClass} bind:value={inputs[field.key]} />
                  <span class="w-7 shrink-0 text-xs text-muted-foreground">{field.unit}</span>
                </div>
              </label>
            {/each}
          </div>
        {/each}
      </div>

      <div class="flex items-center gap-2">
        <Button size="sm" variant="outline" disabled={busy || !dirty} onclick={apply}>
          Apply
        </Button>
        {#if busy}
          <LoaderCircle class="size-3.5 animate-spin text-muted-foreground" />
        {:else if saved}
          <span class="flex items-center gap-1 text-xs text-emerald-500">
            <CircleCheck class="size-3.5" /> saved
          </span>
        {/if}
        {#if error}
          <span class="text-xs text-destructive">{error}</span>
        {/if}
      </div>
    {/if}
  </Card.Content>
</Card.Root>
