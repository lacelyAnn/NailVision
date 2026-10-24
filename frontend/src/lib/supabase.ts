import { createClient } from '@supabase/supabase-js'

export const SESSION_KEY = 'nailvision-session'

// anon key is public by design; Row Level Security in supabase/schema.sql guards the data.
// Every request carries our own session token, which the policies read through app_uid().
export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
  {
    global: {
      fetch: (url, init) => {
        const headers = new Headers(init?.headers)
        const token = localStorage.getItem(SESSION_KEY)
        if (token) headers.set('x-session', token)
        return fetch(url, { ...init, headers })
      },
    },
  },
)

export interface Company {
  id: string
  name: string
  address: string | null
}
export interface Profile {
  id: string
  role: 'client' | 'technician'
  full_name: string
  company_id: string | null
}
export interface Booking {
  id: string
  created_at: string
  client_id: string
  company_id: string
  style: string
  kind: string
  palette_hex: string[]
  zoom: string
  client_rating: number
  client_note: string
  status: 'pending' | 'accepted' | 'changes' | 'done'
  tech_rating: number
  tech_note: string
  companies?: { name: string }
  profiles?: { full_name: string } | null
}
