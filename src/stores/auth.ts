import { ref } from 'vue'
import { defineStore } from 'pinia'
import { supabase, SESSION_KEY, type Profile } from '@/lib/supabase'

export const useAuth = defineStore('auth', () => {
  const profile = ref<Profile | null>(null)
  const busy = ref(false) // drives the top progress bar during sign-in and sign-out
  let loaded: Promise<void> | null = null

  async function load() {
    profile.value = localStorage.getItem(SESSION_KEY)
      ? (await supabase.rpc('me').maybeSingle<Profile>()).data
      : null
    if (!profile.value) localStorage.removeItem(SESSION_KEY) // expired or deleted session
  }
  // router guard awaits this; first call reads the stored session, later calls reuse it
  const ready = () => (loaded ??= load())

  async function start(call: PromiseLike<{ data: string | null; error: Error | null }>) {
    const { data, error } = await call
    if (error) throw error
    localStorage.setItem(SESSION_KEY, data!)
    await load()
  }
  const signIn = (username: string, password: string) =>
    start(supabase.rpc('sign_in', { username, password }))
  const signUp = (
    username: string,
    password: string,
    meta: {
      role: Profile['role']
      full_name: string
      company_name?: string
      company_address?: string
    },
  ) => start(supabase.rpc('sign_up', { username, password, ...meta }))
  async function signOut() {
    await supabase.rpc('sign_out')
    localStorage.removeItem(SESSION_KEY)
    profile.value = null
  }

  return { profile, busy, ready, signIn, signUp, signOut }
})
