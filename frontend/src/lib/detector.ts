import * as ort from 'onnxruntime-web'
import modelUrl from '@/model/nail_seg.onnx?url'

// wasm runtime comes from the CDN (pinned to the installed version) so Vite doesn't bundle 14 MB
ort.env.wasm.wasmPaths = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.30.0/dist/'

const SIZE = 640 // model input
const PROTO = 160 // mask prototype grid
const NC = 32 // mask coefficients (output0 = 4 box + 1 class + 32 coeffs)

export interface Nail {
  number: number
  conf: number
  box: Box // x0,y0,x1,y1 in original image pixels
  mask: HTMLCanvasElement // PROTO×PROTO RGBA, letterbox space
}

export interface Detection {
  nails: Nail[]
  ms: number
  // letterbox transform: original = (letterbox - pad) / r
  r: number
  padX: number
  padY: number
}

let session: Promise<ort.InferenceSession> | null = null
const getSession = () =>
  (session ??= ort.InferenceSession.create(modelUrl, { executionProviders: ['wasm'] }))

type Box = [number, number, number, number]
const at = (a: ArrayLike<number>, i: number) => a[i] as number

const iou = (a: Box, b: Box) => {
  const w = Math.min(a[2], b[2]) - Math.max(a[0], b[0])
  const h = Math.min(a[3], b[3]) - Math.max(a[1], b[1])
  if (w <= 0 || h <= 0) return 0
  const i = w * h
  return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i)
}

export async function detectNails(
  img: HTMLImageElement,
  conf = 0.35,
  iouThr = 0.5,
): Promise<Detection> {
  const t0 = performance.now()
  const W = img.naturalWidth
  const H = img.naturalHeight
  const r = Math.min(SIZE / W, SIZE / H)
  const padX = (SIZE - W * r) / 2
  const padY = (SIZE - H * r) / 2

  // letterbox → CHW float32 RGB 0..1
  const c = document.createElement('canvas')
  c.width = c.height = SIZE
  const ctx = c.getContext('2d', { willReadFrequently: true })!
  ctx.fillStyle = 'rgb(114,114,114)'
  ctx.fillRect(0, 0, SIZE, SIZE)
  ctx.drawImage(img, padX, padY, W * r, H * r)
  const px = ctx.getImageData(0, 0, SIZE, SIZE).data
  const chw = new Float32Array(3 * SIZE * SIZE)
  const plane = SIZE * SIZE
  for (let i = 0; i < plane; i++) {
    chw[i] = at(px, i * 4) / 255
    chw[plane + i] = at(px, i * 4 + 1) / 255
    chw[2 * plane + i] = at(px, i * 4 + 2) / 255
  }

  const s = await getSession()
  const out = await s.run({ images: new ort.Tensor('float32', chw, [1, 3, SIZE, SIZE]) })
  const o = out.output0!.data as Float32Array // [37, 8400]
  const proto = out.output1!.data as Float32Array // [32, 160, 160]
  const N = out.output0!.dims[2] as number

  // candidates above conf, then greedy NMS
  const cands: { box: Box; score: number; idx: number }[] = []
  for (let i = 0; i < N; i++) {
    const score = at(o, 4 * N + i)
    if (score < conf) continue
    const cx = at(o, i),
      cy = at(o, N + i),
      w = at(o, 2 * N + i),
      h = at(o, 3 * N + i)
    cands.push({ box: [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], score, idx: i })
  }
  cands.sort((a, b) => b.score - a.score)
  const kept: typeof cands = []
  for (const c2 of cands) if (kept.every((k) => iou(k.box, c2.box) < iouThr)) kept.push(c2)

  const nails: Nail[] = kept.map((k) => {
    // mask = sigmoid(coeffs · proto), cropped to the box
    const m = document.createElement('canvas')
    m.width = m.height = PROTO
    const mctx = m.getContext('2d')!
    const id = mctx.createImageData(PROTO, PROTO)
    const k4 = SIZE / PROTO
    const [bx0, by0, bx1, by1] = k.box
    for (let y = 0; y < PROTO; y++) {
      for (let x = 0; x < PROTO; x++) {
        const lx = x * k4,
          ly = y * k4
        if (lx < bx0 || lx > bx1 || ly < by0 || ly > by1) continue
        let v = 0
        for (let j = 0; j < NC; j++)
          v += at(o, (5 + j) * N + k.idx) * at(proto, j * PROTO * PROTO + y * PROTO + x)
        if (1 / (1 + Math.exp(-v)) > 0.5) {
          const p = (y * PROTO + x) * 4
          id.data[p] = 255
          id.data[p + 1] = 0
          id.data[p + 2] = 180
          id.data[p + 3] = 140
        }
      }
    }
    mctx.putImageData(id, 0, 0)
    const cl = (v: number, m: number) => Math.max(0, Math.min(m, v))
    const [a, b, c3, d] = k.box
    return {
      number: 0,
      conf: k.score,
      mask: m,
      box: [
        cl((a - padX) / r, W),
        cl((b - padY) / r, H),
        cl((c3 - padX) / r, W),
        cl((d - padY) / r, H),
      ] as Box,
    }
  })
  nails.sort((a, b) => a.box[0] + a.box[2] - (b.box[0] + b.box[2])) // left → right
  nails.forEach((n, i) => (n.number = i + 1))
  return { nails, ms: performance.now() - t0, r, padX, padY }
}

export function drawDetections(
  canvas: HTMLCanvasElement,
  img: HTMLImageElement,
  d: Detection,
  selected: number[],
) {
  const W = img.naturalWidth,
    H = img.naturalHeight
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')!
  ctx.drawImage(img, 0, 0)
  const th = Math.max(2, Math.round(Math.min(W, H) / 250))
  for (const n of d.nails) {
    ctx.drawImage(n.mask, -d.padX / d.r, -d.padY / d.r, SIZE / d.r, SIZE / d.r)
  }
  ctx.font = `bold ${th * 8}px sans-serif`
  ctx.textAlign = 'center'
  for (const n of d.nails) {
    const [x0, y0, x1] = n.box
    const sel = selected.includes(n.number)
    ctx.lineWidth = th
    ctx.strokeStyle = sel ? '#22d3ee' : '#ff00b4'
    ctx.strokeRect(x0, y0, x1 - x0, n.box[3] - y0)
    ctx.lineWidth = th * 3
    ctx.strokeStyle = '#000'
    ctx.strokeText(String(n.number), (x0 + x1) / 2, Math.max(th * 8, y0 - th * 2))
    ctx.fillStyle = '#fff'
    ctx.fillText(String(n.number), (x0 + x1) / 2, Math.max(th * 8, y0 - th * 2))
  }
}

/** Full-resolution binary PNG mask of one nail (white = nail), for the SD service. */
// uploads are capped at the size the server works at: smaller transfer, and full-size photos overflow its memory
const MAX_SIDE = 2048
const uploadScale = (img: HTMLImageElement) =>
  Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight))

export function photoBlob(img: HTMLImageElement): Promise<Blob> {
  const s = uploadScale(img)
  const c = document.createElement('canvas')
  c.width = Math.round(img.naturalWidth * s)
  c.height = Math.round(img.naturalHeight * s)
  c.getContext('2d')!.drawImage(img, 0, 0, c.width, c.height)
  return new Promise((res, rej) =>
    c.toBlob((b) => (b ? res(b) : rej(new Error('photo export failed'))), 'image/jpeg', 0.92),
  )
}

export function nailMaskBlob(img: HTMLImageElement, d: Detection, n: Nail): Promise<Blob> {
  const s = uploadScale(img)
  const W = Math.round(img.naturalWidth * s),
    H = Math.round(img.naturalHeight * s)
  const c = document.createElement('canvas')
  c.width = W
  c.height = H
  const ctx = c.getContext('2d', { willReadFrequently: true })!
  ctx.imageSmoothingQuality = 'high'
  ctx.scale(s, s) // same placement as the photo, just smaller
  ctx.drawImage(n.mask, -d.padX / d.r, -d.padY / d.r, SIZE / d.r, SIZE / d.r)
  const id = ctx.getImageData(0, 0, W, H)
  for (let i = 0; i < W * H; i++) {
    const on = at(id.data, i * 4 + 3) > 70 ? 255 : 0
    id.data[i * 4] = id.data[i * 4 + 1] = id.data[i * 4 + 2] = on
    id.data[i * 4 + 3] = 255
  }
  ctx.putImageData(id, 0, 0)
  return new Promise((res, rej) =>
    c.toBlob((b) => (b ? res(b) : rej(new Error('mask export failed'))), 'image/png'),
  )
}
