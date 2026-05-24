<script lang="ts">
  import type { Point } from '$lib/stores'
  import {
    CategoryScale,
    Chart,
    Filler,
    LinearScale,
    LineElement,
    PointElement,
    Tooltip,
  } from 'chart.js'
  import { Line } from 'svelte-chartjs'

  Chart.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Filler)

  let { points, color = '#10b981' }: { points: Point[]; color?: string } = $props()

  const data = $derived({
    labels: points.map((p) => new Date(p.t).toLocaleTimeString()),
    datasets: [
      {
        data: points.map((p) => p.v),
        borderColor: color,
        backgroundColor: `${color}22`,
        borderWidth: 2,
        fill: true,
        tension: 0.3,
        pointRadius: 0,
      },
    ],
  })

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false as const,
    plugins: { legend: { display: false } },
    scales: {
      x: { display: false },
      y: { ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.06)' } },
    },
  }
</script>

<div class="h-28">
  <Line {data} {options} />
</div>
