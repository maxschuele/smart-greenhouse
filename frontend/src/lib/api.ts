/** Send an actuator command through the hub REST API. */
export async function sendCommand(
  nodeId: string,
  actuatorId: string,
  value: boolean | number | string,
): Promise<void> {
  const res = await fetch(`/api/nodes/${encodeURIComponent(nodeId)}/command`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ actuator_id: actuatorId, value }),
  })
  if (!res.ok) throw new Error(`command failed: ${res.status}`)
}
