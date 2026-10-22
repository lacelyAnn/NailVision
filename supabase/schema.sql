-- NailVision schema. Paste into Supabase > SQL Editor and run once.
-- Two roles: 'client' (makes designs, books a salon) and 'technician' (belongs to a company, reviews bookings).
-- Login uses our own credentials table, not Supabase Auth: sign_in/sign_up return a session token,
-- the app sends it as the x-session header, and app_uid() turns it back into the user id for RLS.

create extension if not exists pgcrypto with schema extensions; -- crypt() for password hashes

create table public.companies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address text
);

create table public.credentials (
  id uuid primary key default gen_random_uuid(),
  username text not null unique check (username ~ '^[a-z0-9._-]{3,32}$'),
  password_hash text not null -- bcrypt, never the plain password
);

create table public.sessions (
  token text primary key default gen_random_uuid()::text,
  user_id uuid not null references public.credentials on delete cascade,
  created_at timestamptz not null default now()
);

create table public.profiles (
  id uuid primary key references public.credentials on delete cascade,
  role text not null check (role in ('client', 'technician')),
  full_name text not null default '',
  company_id uuid references public.companies,
  check (role = 'client' or company_id is not null) -- a technician always works somewhere
);

create table public.bookings (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  client_id uuid not null references public.profiles on delete cascade,
  company_id uuid not null references public.companies,
  style text not null,
  kind text not null,
  palette_hex text[] not null,
  -- shortcut: image kept inline as base64 jpeg, move to Supabase Storage if rows get heavy
  zoom text not null,
  client_rating int not null default 0,
  client_note text not null default '',
  status text not null default 'pending' check (status in ('pending', 'accepted', 'changes', 'done')),
  tech_rating int not null default 0 check (tech_rating between 0 and 5),
  tech_note text not null default '',
  technician_id uuid references public.profiles
);

-- the caller's user id from the x-session header, null when missing, unknown or older than 30 days
create function public.app_uid() returns uuid language sql stable security definer set search_path = public
  as $$
    select user_id from sessions
    where token = nullif(current_setting('request.headers', true), '')::json->>'x-session'
      and created_at > now() - interval '30 days'
  $$;
alter table public.bookings alter column client_id set default public.app_uid();

-- a technician types their salon at sign-up; it becomes a new company that clients can book
create function public.sign_up(
  username text, password text, role text, full_name text,
  company_name text default null, company_address text default null
)
returns text language plpgsql security definer set search_path = public, extensions as $$
declare uid uuid; tok text; cid uuid; uname text := lower(trim(username));
begin
  if uname !~ '^[a-z0-9._-]{3,32}$' then
    raise exception 'Username must be 3-32 letters, numbers, dots, dashes or underscores';
  end if;
  if length(password) < 6 then raise exception 'Password must be at least 6 characters'; end if;
  if role = 'technician' then
    if coalesce(trim(company_name), '') = '' then raise exception 'Enter your salon name'; end if;
    insert into companies (name, address)
      values (trim(company_name), nullif(trim(company_address), ''))
      returning id into cid;
  end if;
  insert into credentials (username, password_hash)
    values (uname, crypt(password, gen_salt('bf')))
    returning id into uid;
  insert into profiles (id, role, full_name, company_id)
    values (uid, role, full_name, cid);
  insert into sessions (user_id) values (uid) returning token into tok;
  return tok;
exception
  when unique_violation then raise exception 'That username is taken';
end $$;

create function public.sign_in(username text, password text)
returns text language plpgsql security definer set search_path = public, extensions as $$
declare uid uuid; tok text;
begin
  select id into uid from credentials c
    where c.username = lower(trim(sign_in.username)) and c.password_hash = crypt(password, c.password_hash);
  if uid is null then raise exception 'Wrong username or password'; end if;
  insert into sessions (user_id) values (uid) returning token into tok;
  return tok;
end $$;

create function public.sign_out() returns void language sql security definer set search_path = public
  as $$ delete from sessions where token = nullif(current_setting('request.headers', true), '')::json->>'x-session' $$;

create function public.me() returns setof public.profiles language sql stable security definer set search_path = public
  as $$ select * from profiles where id = app_uid() $$;

-- security definer helpers: let policies read the caller's profile without recursing into its RLS
create function public.my_role() returns text language sql stable security definer set search_path = public
  as $$ select role from profiles where id = app_uid() $$;
create function public.my_company() returns uuid language sql stable security definer set search_path = public
  as $$ select company_id from profiles where id = app_uid() $$;

alter table public.companies enable row level security;
alter table public.credentials enable row level security;
alter table public.sessions enable row level security;
alter table public.profiles enable row level security;
alter table public.bookings enable row level security;

-- passwords and tokens are reachable only through the functions above
revoke all on public.credentials, public.sessions from anon, authenticated;

create policy "companies are public" on public.companies for select using (true);

create policy "read own profile" on public.profiles for select using (id = app_uid());
create policy "technicians read their clients" on public.profiles for select using (
  exists (select 1 from bookings b where b.client_id = profiles.id and b.company_id = my_company())
);

create policy "clients book" on public.bookings for insert
  with check (client_id = app_uid() and my_role() = 'client');
create policy "clients see own bookings" on public.bookings for select using (client_id = app_uid());
create policy "clients cancel pending" on public.bookings for delete
  using (client_id = app_uid() and status = 'pending');
create policy "technicians see company bookings" on public.bookings for select
  using (my_role() = 'technician' and company_id = my_company());
create policy "technicians review" on public.bookings for update
  using (my_role() = 'technician' and company_id = my_company())
  with check (technician_id = app_uid());

-- technicians may only change the review columns, never the design or the client
-- (every request now runs as anon, since Supabase Auth is not used)
revoke update on public.bookings from authenticated, anon;
grant update (status, tech_rating, tech_note, technician_id) on public.bookings to anon;
