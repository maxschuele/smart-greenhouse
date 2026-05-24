<script lang="ts">
  import { Badge } from '$lib/components/ui/badge'
  import * as Card from '$lib/components/ui/card'
  import { Separator } from '$lib/components/ui/separator'
  import { Brain, CircleDashed, ListTree } from '@lucide/svelte'

  const model: [string, string][] = [
    ['Domain', 'TODO'],
    ['Problem generator', 'TODO'],
    ['Planner', 'TODO'],
    ['Last solved', 'never'],
  ]
</script>

<div class="grid gap-4 md:grid-cols-2">
  <Card.Root>
    <Card.Header>
      <div class="flex items-center gap-2">
        <ListTree class="size-4 text-muted-foreground" />
        <Card.Title class="text-base">Current plan</Card.Title>
        <Badge variant="outline" class="ml-auto">none</Badge>
      </div>
      <Card.Description>The latest plan being executed.</Card.Description>
    </Card.Header>
    <Card.Content>
      <div
        class="flex flex-col items-center justify-center gap-2 py-10 text-center text-muted-foreground"
      >
        <CircleDashed class="size-8 opacity-50" />
        <p class="text-sm">Planner not yet implemented.</p>
        <p class="text-xs">Plan steps appear here once the AI planner is wired up.</p>
      </div>
    </Card.Content>
  </Card.Root>

  <Card.Root>
    <Card.Header>
      <div class="flex items-center gap-2">
        <Brain class="size-4 text-muted-foreground" />
        <Card.Title class="text-base">Planning model</Card.Title>
      </div>
      <Card.Description>Domain, problem instance, and planner in use.</Card.Description>
    </Card.Header>
    <Card.Content class="text-sm">
      {#each model as [key, value], i (key)}
        {#if i > 0}<Separator class="my-3" />{/if}
        <div class="flex items-center justify-between">
          <span class="text-muted-foreground">{key}</span>
          <span class="font-mono">{value}</span>
        </div>
      {/each}
    </Card.Content>
  </Card.Root>
</div>
