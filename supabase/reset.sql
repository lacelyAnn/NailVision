-- NailVision teardown. Drops every table, policy and function from schema.sql, with all their data.
-- Paste into Supabase > SQL Editor and run. Cannot be undone. Run schema.sql again to set it back up.
begin;
drop table if exists public.bookings, public.profiles, public.sessions, public.credentials, public.companies cascade; -- policies go with the tables
drop function if exists public.app_uid(), public.sign_up(text, text, text, text, text, text),
  public.sign_up(text, text, text, text, uuid), /* older version */ public.sign_in(text, text),
  public.sign_out(), public.me(), public.my_role(), public.my_company();
commit;
