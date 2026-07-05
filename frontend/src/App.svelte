<script lang="ts">
  import ConnectionBadge from '$lib/components/ConnectionBadge.svelte'
  import NodeCard from '$lib/components/NodeCard.svelte'
  import NodePanel from '$lib/components/NodePanel.svelte'
  import PlanningPanel from '$lib/components/PlanningPanel.svelte'
  import * as Tabs from '$lib/components/ui/tabs'
  import { connect } from '$lib/socket'
  import { nodes, now, series, topics } from '$lib/stores'
  import { Sprout } from '@lucide/svelte'
  import { onMount } from 'svelte'

  onMount(() => {
    connect()
    const tick = setInterval(() => now.set(Date.now()), 1000)
    return () => clearInterval(tick)
  })

  const sortedNodes = $derived(Object.keys($nodes).sort())
  const rawTopics = $derived(
    Object.keys($topics)
      .filter((t) => !t.startsWith('nodes/'))
      .sort(),
  )
</script>

<div class="min-h-svh">
  <header class="border-b">
    <div class="mx-auto flex max-w-6xl items-center gap-3 px-6 py-4">
      <Sprout class="size-6 text-emerald-500" />
      <h1 class="text-lg font-semibold">Smart Greenhouse Hub</h1>
      <div class="ml-auto"><ConnectionBadge /></div>
    </div>
  </header>

  <main class="mx-auto max-w-6xl px-6 py-6">
    <Tabs.Root value="nodes">
      <Tabs.List>
        <Tabs.Trigger value="nodes">Nodes</Tabs.Trigger>
        <Tabs.Trigger value="planning">AI Planning</Tabs.Trigger>
      </Tabs.List>

      <Tabs.Content value="nodes" class="mt-6 space-y-6">
        {#if sortedNodes.length === 0}
          <div
            class="rounded-lg border border-dashed py-16 text-center text-sm text-muted-foreground"
          >
            No nodes discovered yet. Waiting for adverts...
          </div>
        {:else}
          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {#each sortedNodes as id (id)}
              <NodePanel node={$nodes[id]} series={$series} />
            {/each}
          </div>
        {/if}

        {#if rawTopics.length > 0}
          <details>
            <summary class="cursor-pointer text-sm text-muted-foreground">
              Raw topics ({rawTopics.length})
            </summary>
            <div class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {#each rawTopics as topic (topic)}
                <NodeCard {topic} state={$topics[topic]} points={$series[topic] ?? []} />
              {/each}
            </div>
          </details>
        {/if}
      </Tabs.Content>

      <Tabs.Content value="planning" class="mt-6">
        <PlanningPanel />
      </Tabs.Content>
    </Tabs.Root>
  </main>
</div>
