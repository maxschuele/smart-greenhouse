<script lang="ts">
  import { Badge } from '$lib/components/ui/badge'
  import * as Card from '$lib/components/ui/card'
  import { now, numeric, type Point, type TopicState } from '$lib/stores'
  import SensorChart from './SensorChart.svelte'

  let {
    topic,
    state,
    points = [],
  }: { topic: string; state: TopicState; points?: Point[] } = $props()

  const segments = $derived(topic.split('/'))
  const group = $derived(segments.length > 1 ? segments[0] : 'topic')
  const label = $derived(segments[segments.length - 1])
  const isNumber = $derived(numeric(state.payload) !== null)
  const ago = $derived(Math.max(0, Math.round(($now - state.ts) / 1000)))
</script>

<Card.Root>
  <Card.Header>
    <div class="flex items-center justify-between gap-2">
      <Card.Title class="text-base font-medium">{label}</Card.Title>
      <Badge variant="secondary" class="font-mono text-xs">{group}</Badge>
    </div>
    <Card.Description class="truncate font-mono text-xs">{topic}</Card.Description>
  </Card.Header>
  <Card.Content class="space-y-3">
    <div class="truncate text-3xl font-semibold tabular-nums" title={state.payload}>
      {state.payload}
    </div>
    {#if isNumber && points.length > 1}
      <SensorChart {points} />
    {/if}
    <p class="text-xs text-muted-foreground">updated {ago}s ago</p>
  </Card.Content>
</Card.Root>
