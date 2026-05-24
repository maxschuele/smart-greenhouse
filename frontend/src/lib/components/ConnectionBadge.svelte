<script lang="ts">
  import { Badge } from '$lib/components/ui/badge'
  import { connection } from '$lib/stores'
  import { LoaderCircle, Wifi, WifiOff } from '@lucide/svelte'
</script>

{#if $connection === 'open'}
  <Badge variant="outline" class="gap-1.5 border-emerald-500/40 text-emerald-500">
    <Wifi class="size-3.5" /> Live
  </Badge>
{:else if $connection === 'connecting'}
  <Badge variant="outline" class="gap-1.5 text-muted-foreground">
    <LoaderCircle class="size-3.5 animate-spin" /> Connecting
  </Badge>
{:else}
  <Badge variant="outline" class="gap-1.5 border-destructive/40 text-destructive">
    <WifiOff class="size-3.5" /> Offline
  </Badge>
{/if}
