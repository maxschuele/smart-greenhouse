<script lang="ts">
  import ConnectionBadge from '$lib/components/ConnectionBadge.svelte'
  import NodeCard from '$lib/components/NodeCard.svelte'
  import PlanningPanel from '$lib/components/PlanningPanel.svelte'
  import * as Tabs from '$lib/components/ui/tabs'
  import { connect } from '$lib/socket'
  import { now, series, topics } from '$lib/stores'
  import { Sprout } from '@lucide/svelte'
  import { onMount } from 'svelte'

  onMount(() => {
    connect()
    const tick = setInterval(() => now.set(Date.now()), 1000)
    return () => clearInterval(tick)
  })

  const sortedTopics = $derived(Object.keys($topics).sort())
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

      <Tabs.Content value="nodes" class="mt-6">
        {#if sortedTopics.length === 0}
          <div
            class="rounded-lg border border-dashed py-16 text-center text-sm text-muted-foreground"
          >
            No messages yet. Waiting for nodes to publish...
          </div>
        {:else}
          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {#each sortedTopics as topic (topic)}
              <NodeCard {topic} state={$topics[topic]} points={$series[topic] ?? []} />
            {/each}
          </div>
        {/if}
      </Tabs.Content>

      <Tabs.Content value="planning" class="mt-6">
        <PlanningPanel />
      </Tabs.Content>
    </Tabs.Root>
  </main>
</div>
