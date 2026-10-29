const API = import.meta.env.VITE_SD_URL ?? 'https://nailvision-bx7e.onrender.com'
const TOKEN = import.meta.env.VITE_SD_TOKEN as string | undefined // not secret: ships in the bundle
const headers: HeadersInit = TOKEN ? { 'X-API-Token': TOKEN } : {}

export interface Design {
  slot: number
  kind: 'palette' | 'random'
  label: string
  style: string
  palette_hex: string[]
  delta_e: number
  on_palette: number
  seconds: number
  full_jpeg_b64: string
  zoom_jpeg_b64: string
}
export interface Job {
  status: 'queued' | 'running' | 'done' | 'failed'
  designs: Design[]
  progress: number // 0-100, of the design being painted
  error: string | null
}

export async function startJob(
  photo: Blob,
  masks: Blob[],
  colors: string[],
  steps: number,
): Promise<string> {
  const f = new FormData()
  f.append('photo', photo, 'photo.jpg')
  masks.forEach((m, i) => f.append('masks', m, `mask${i}.png`))
  f.append('colors', colors.join(','))
  f.append('steps', String(steps))
  const r = await fetch(`${API}/jobs`, { method: 'POST', body: f, headers })
  if (!r.ok) throw new Error(`SD service: ${r.status} ${await r.text()}`)
  return (await r.json()).job_id
}

export async function getJob(id: string): Promise<Job> {
  const r = await fetch(`${API}/jobs/${id}`, { headers })
  if (!r.ok) throw new Error(`SD service: ${r.status}`)
  return r.json()
}

export interface Health {
  mode: 'cloudflare' | 'cuda' | 'mps' | 'cpu' | 'mock'
  device?: string // older servers do not send it
}

export async function checkService(): Promise<Health | null> {
  try {
    const r = await fetch(`${API}/health`, { signal: AbortSignal.timeout(2500) })
    return r.ok ? await r.json() : null
  } catch {
    return null
  }
}
