import { createClient } from '@supabase/supabase-js';

// A production build must never silently send photos to a localhost development service.
export const cloudEnabled = Boolean(import.meta.env.VITE_REST_API_URL) || import.meta.env.PROD;
const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;
// This is the public publishable/anon key. Never use a service-role key here.
export const supabase = cloudEnabled && url && key ? createClient(url, key) : null;
export async function accessToken() {
  if (!supabase) throw new Error('Cloud sign-in is not configured yet.');
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session) throw new Error('Sign in to create or open a cloud preview.');
  return data.session.access_token;
}
