<script lang="ts">
  import { sendCommand } from '$lib/api'
  import { Switch } from '$lib/components/ui/switch'
  import type { ActuatorCap } from '$lib/stores'
  import { LoaderCircle } from '@lucide/svelte'

  let {
    nodeId,
    actuator,
    state,
  }: { nodeId: string; actuator: ActuatorCap; state: boolean | undefined } = $props()

  // Optimistic toggle: show the desired state as pending until the node's
  // next telemetry confirms it (or a timeout gives up and reverts to truth).
  let desired = $state<boolean | null>(null)
  let failed = $state(false)
  let timeout: ReturnType<typeof setTimeout> | null = null
  const pending = $derived(desired !== null)
  const shown = $derived(desired ?? state ?? false)

  $effect(() => {
    if (desired !== null && state === desired) {
      desired = null
      if (timeout) clearTimeout(timeout)
    }
  })

  async function toggle() {
    if (pending || state === undefined) return
    failed = false
    desired = !state
    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(() => (desired = null), 10_000)
    try {
      await sendCommand(nodeId, actuator.actuator_id, desired)
    } catch {
      failed = true
      desired = null
      if (timeout) clearTimeout(timeout)
    }
  }
</script>

<div class="flex items-center justify-between gap-2">
  <div class="flex items-center gap-2">
    <span class="text-sm font-medium">{actuator.actuator_id}</span>
    {#if actuator.kind}
      <span class="text-xs text-muted-foreground">{actuator.kind}</span>
    {/if}
    {#if failed}
      <span class="text-xs text-destructive">failed</span>
    {/if}
  </div>
  <div class="flex items-center gap-2">
    {#if pending}
      <LoaderCircle class="size-3.5 animate-spin text-muted-foreground" />
    {/if}
    <Switch
      checked={shown}
      disabled={pending || state === undefined}
      onCheckedChange={toggle}
      aria-label={`toggle ${actuator.actuator_id}`}
    />
  </div>
</div>
