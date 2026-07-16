<script lang="ts">
  import ActuatorToggle from '$lib/components/ActuatorToggle.svelte'
  import SensorChart from '$lib/components/SensorChart.svelte'
  import { Badge } from '$lib/components/ui/badge'
  import * as Card from '$lib/components/ui/card'
  import { Separator } from '$lib/components/ui/separator'
  import { now, ONLINE_THRESHOLD_MS, type NodeState, type Point, type Reading } from '$lib/stores'

  let { node, series }: { node: NodeState; series: Record<string, Point[]> } = $props()

  const online = $derived($now - node.lastSeen < ONLINE_THRESHOLD_MS)
  const ago = $derived(Math.max(0, Math.round(($now - node.lastSeen) / 1000)))
  const sensors = $derived(node.advert?.sensors ?? [])
  const actuators = $derived(node.advert?.actuators ?? [])

  function format(r: Reading | undefined): string {
    if (r === undefined) return '—'
    if (typeof r.number === 'number') {
      return Number.isInteger(r.number) ? String(r.number) : r.number.toFixed(1)
    }
    if (typeof r.boolean === 'boolean') return r.boolean ? 'on' : 'off'
    return r.text ?? '—'
  }
</script>

<Card.Root>
  <Card.Header>
    <div class="flex items-center justify-between gap-2">
      <Card.Title class="text-base font-medium">{node.id}</Card.Title>
      <Badge
        variant={online ? 'secondary' : 'destructive'}
        class={online ? 'text-emerald-500' : ''}
      >
        {online ? 'online' : 'offline'}
      </Badge>
    </div>
    <Card.Description class="flex gap-2 font-mono text-xs">
      {#if node.advert?.hw}<span>{node.advert.hw}</span>{/if}
      {#if node.advert?.fw_version}<span>fw {node.advert.fw_version}</span>{/if}
    </Card.Description>
  </Card.Header>
  <Card.Content class="space-y-4">
    {#if sensors.length === 0}
      <p class="text-sm text-muted-foreground">No advertised sensors.</p>
    {:else}
      <div class="space-y-3">
        {#each sensors as sensor (sensor.sensor_id)}
          {@const pts = series[`${node.id}/${sensor.sensor_id}`] ?? []}
          <div>
            <div class="flex items-baseline justify-between gap-2">
              <span class="text-sm text-muted-foreground">{sensor.sensor_id}</span>
              <span class="text-xl font-semibold tabular-nums">
                {format(node.readings[sensor.sensor_id])}
                {#if sensor.unit}<span class="ml-0.5 text-xs font-normal text-muted-foreground"
                    >{sensor.unit}</span
                  >{/if}
              </span>
            </div>
            {#if pts.length > 1}
              <SensorChart points={pts} />
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    {#if actuators.length > 0}
      <Separator />
      <div class="space-y-2">
        {#each actuators as actuator (actuator.actuator_id)}
          <ActuatorToggle
            nodeId={node.id}
            {actuator}
            reported={node.readings[actuator.actuator_id]?.boolean}
          />
        {/each}
      </div>
    {/if}

    <p class="text-xs text-muted-foreground">updated {ago}s ago</p>
  </Card.Content>
</Card.Root>
