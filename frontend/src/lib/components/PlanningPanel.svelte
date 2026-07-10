<script lang="ts">
  import { Badge } from '$lib/components/ui/badge'
  import * as Card from '$lib/components/ui/card'
  import { Separator } from '$lib/components/ui/separator'
  import { now, topics } from '$lib/stores'
  import { Brain, CircleCheck, CircleDashed, Hand, ListTree, TriangleAlert } from '@lucide/svelte'

  // Shape published by the hub's planning service on planning/plan.
  interface PlanStep {
    action: string
    args?: string[]
  }
  interface PlanState {
    status: 'startup' | 'idle' | 'planned' | 'unsolvable' | 'error' | string
    steps?: PlanStep[]
    cost?: number | null
    detail?: string | null
  }

  const plan = $derived.by((): PlanState | null => {
    const state = $topics['planning/plan']
    if (!state) return null
    try {
      return JSON.parse(state.payload) as PlanState
    } catch {
      return null
    }
  })
  const planTs = $derived($topics['planning/plan']?.ts ?? null)
  const ago = $derived(planTs === null ? null : Math.max(0, Math.round(($now - planTs) / 1000)))
  const steps = $derived(plan?.steps ?? [])
  const needsHuman = $derived(steps.some((s) => s.action === 'refill-tank'))

  const badge = $derived.by(() => {
    switch (plan?.status) {
      case 'planned':
        return { label: `${steps.length} step${steps.length === 1 ? '' : 's'}`, variant: 'secondary' as const }
      case 'idle':
        return { label: 'idle', variant: 'outline' as const }
      case 'unsolvable':
        return { label: 'unsolvable', variant: 'destructive' as const }
      case 'error':
        return { label: 'planner error', variant: 'destructive' as const }
      default:
        return { label: 'none', variant: 'outline' as const }
    }
  })

  function formatStep(step: PlanStep): string {
    return `(${[step.action, ...(step.args ?? [])].join(' ')})`
  }

  const model = $derived<[string, string][]>([
    ['Domain', 'greenhouse (PDDL)'],
    ['Problem generator', 'auto, from sensor snapshot'],
    ['Planner', 'Fast Downward — A* + LM-Cut'],
    ['Last solved', ago === null ? 'never' : `${ago}s ago`],
  ])
</script>

<div class="grid gap-4 md:grid-cols-2">
  <Card.Root>
    <Card.Header>
      <div class="flex items-center gap-2">
        <ListTree class="size-4 text-muted-foreground" />
        <Card.Title class="text-base">Current plan</Card.Title>
        <Badge variant={badge.variant} class="ml-auto">{badge.label}</Badge>
      </div>
      <Card.Description>The latest plan (being) executed.</Card.Description>
    </Card.Header>
    <Card.Content class="space-y-4">
      {#if needsHuman}
        <div
          class="flex items-center gap-2 rounded-md border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-sm text-amber-600"
        >
          <Hand class="size-4 shrink-0" />
          Human action required: refill the water tank.
        </div>
      {/if}

      {#if plan?.status === 'planned' && steps.length > 0}
        <ol class="space-y-1">
          {#each steps as step, i (i)}
            <li class="flex items-center gap-2 font-mono text-sm">
              <span class="w-5 text-right text-xs text-muted-foreground">{i + 1}.</span>
              {formatStep(step)}
              {#if step.action === 'refill-tank'}
                <Hand class="size-3.5 text-amber-500" />
              {/if}
            </li>
          {/each}
        </ol>
        {#if plan.cost != null}
          <p class="text-xs text-muted-foreground">total cost (energy proxy): {plan.cost}</p>
        {/if}
      {:else if plan?.status === 'idle'}
        <div
          class="flex flex-col items-center justify-center gap-2 py-10 text-center text-muted-foreground"
        >
          <CircleCheck class="size-8 text-emerald-500 opacity-70" />
          <p class="text-sm">All care conditions satisfied.</p>
          <p class="text-xs">Nothing to plan for this cycle.</p>
        </div>
      {:else if plan?.status === 'error' || plan?.status === 'unsolvable'}
        <div
          class="flex flex-col items-center justify-center gap-2 py-10 text-center text-muted-foreground"
        >
          <TriangleAlert class="size-8 text-destructive opacity-70" />
          <p class="text-sm">{plan.status === 'error' ? 'Planner failed.' : 'Problem is unsolvable.'}</p>
          {#if plan.detail}
            <p class="max-w-full break-words px-4 font-mono text-xs">{plan.detail}</p>
          {/if}
        </div>
      {:else}
        <div
          class="flex flex-col items-center justify-center gap-2 py-10 text-center text-muted-foreground"
        >
          <CircleDashed class="size-8 opacity-50" />
          <p class="text-sm">No plan yet.</p>
          <p class="text-xs">The planning service publishes its first result shortly after startup.</p>
        </div>
      {/if}
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
