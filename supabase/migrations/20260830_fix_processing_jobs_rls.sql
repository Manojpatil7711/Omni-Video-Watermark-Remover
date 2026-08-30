-- Secure server-side job creation: keep RLS enabled and permit only the
-- service_role to insert/update processing jobs. The browser must never
-- receive the service-role key.
alter table public.media_processing_jobs enable row level security;

drop policy if exists "service role can insert processing jobs" on public.media_processing_jobs;
create policy "service role can insert processing jobs"
on public.media_processing_jobs
for insert
to service_role
with check (true);

drop policy if exists "service role can update processing jobs" on public.media_processing_jobs;
create policy "service role can update processing jobs"
on public.media_processing_jobs
for update
to service_role
using (true)
with check (true);
