'use client';

import { FormEvent, useCallback, useMemo, useState } from 'react';

type DeadLetterEvent = {
  event_id: string;
  aggregate_type: string;
  aggregate_id: string;
  event_type: string;
  correlation_id: string;
  status: 'dead_letter' | 'retry' | 'pending' | 'processing' | 'published';
  attempt_count: number;
  last_error?: string | null;
  created_at: string;
  reviewed_at?: string | null;
  review_note?: string | null;
  reviewer_actor_id?: number | null;
  payload: Record<string, unknown>;
};

type QueueResponse = { items: DeadLetterEvent[]; total: number };

const defaultApiUrl = 'http://127.0.0.1:8000';

function commandHeaders(token: string, action: string, eventId: string) {
  const suffix = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
    'Idempotency-Key': `admin-${action}-${eventId}-${suffix}`.slice(0, 128),
    'X-Correlation-ID': `corr-admin-${action}-${suffix}`.slice(0, 128),
  };
}

export default function AdminReviewDashboard() {
  const [apiUrl, setApiUrl] = useState(defaultApiUrl);
  const [token, setToken] = useState('');
  const [queue, setQueue] = useState<QueueResponse>({ items: [], total: 0 });
  const [selected, setSelected] = useState<DeadLetterEvent | null>(null);
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(false);
  const [acting, setActing] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedReviewed = Boolean(selected?.reviewed_at);
  const queueLabel = useMemo(() => `${queue.total} dead-letter event${queue.total === 1 ? '' : 's'}`, [queue.total]);

  const refresh = useCallback(async () => {
    if (!token.trim()) {
      setError('Cần JWT có role admin để tải Review Queue. Token chỉ giữ trong bộ nhớ trang này.');
      return;
    }
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(`${apiUrl.replace(/\/$/, '')}/admin/outbox/dead-letters`, {
        headers: { Authorization: `Bearer ${token.trim()}` },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Không thể tải Review Queue.');
      setQueue(data);
      setSelected((current) => data.items.find((item: DeadLetterEvent) => item.event_id === current?.event_id) || null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Không thể tải Review Queue.');
    } finally {
      setLoading(false);
    }
  }, [apiUrl, token]);

  const submitAction = async (event: FormEvent, action: 'review' | 'replay') => {
    event.preventDefault();
    if (!selected) return;
    if (note.trim().length < 5) {
      setError('Ghi chú review/replay cần ít nhất 5 ký tự để tạo bằng chứng audit.');
      return;
    }
    setActing(true);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(`${apiUrl.replace(/\/$/, '')}/admin/outbox/dead-letters/${selected.event_id}/${action}`, {
        method: 'POST',
        headers: commandHeaders(token.trim(), action, selected.event_id),
        body: JSON.stringify({ review_note: note.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `Không thể ${action} event.`);
      setNotice(action === 'review'
        ? 'Review đã được ghi audit. Replay chỉ khả dụng sau khi review thành công.'
        : 'Replay đã được xếp lại trạng thái retry. Relay nền sẽ publish khi event đến hạn.');
      setNote('');
      await refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Lệnh Admin thất bại.');
    } finally {
      setActing(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100 sm:px-8">
      <section className="mx-auto max-w-7xl">
        <header className="mb-8 flex flex-col gap-3 border-b border-slate-800 pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-400">Operations Console</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight">Outbox Review Queue</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">Admin-only queue for reviewing durable dead-letter events. Review and replay actions create immutable audit evidence; a replay does not mark an event published.</p>
          </div>
          <a href="/" className="text-sm font-medium text-cyan-300 hover:text-cyan-200">← Back to Stylist</a>
        </header>

        <section className="mb-6 grid gap-4 rounded-2xl border border-slate-800 bg-slate-900/80 p-5 lg:grid-cols-[1fr_1.5fr_auto]">
          <label className="text-sm font-medium text-slate-300">Backend URL
            <input value={apiUrl} onChange={(event) => setApiUrl(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none ring-cyan-500 focus:ring-2" />
          </label>
          <label className="text-sm font-medium text-slate-300">Admin JWT
            <input value={token} onChange={(event) => setToken(event.target.value)} type="password" autoComplete="off" placeholder="Bearer token value (not stored)" className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none ring-cyan-500 focus:ring-2" />
          </label>
          <button onClick={refresh} disabled={loading || !token.trim()} className="self-end rounded-lg bg-cyan-400 px-5 py-2.5 text-sm font-bold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-50">{loading ? 'Refreshing…' : 'Refresh queue'}</button>
        </section>

        {error && <p role="alert" className="mb-5 rounded-lg border border-rose-800 bg-rose-950/60 px-4 py-3 text-sm text-rose-200">{error}</p>}
        {notice && <p className="mb-5 rounded-lg border border-emerald-800 bg-emerald-950/60 px-4 py-3 text-sm text-emerald-200">{notice}</p>}

        <div className="grid gap-6 xl:grid-cols-[1.25fr_.75fr]">
          <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/80">
            <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4"><h2 className="font-semibold">{queueLabel}</h2><span className="text-xs text-slate-500">Only status = dead_letter</span></div>
            <div className="max-h-[620px] overflow-auto">
              {queue.items.length === 0 ? <div className="p-8 text-center text-sm text-slate-500">No dead-letter events are currently visible.</div> : queue.items.map((item) => (
                <button key={item.event_id} onClick={() => { setSelected(item); setNote(item.review_note || ''); }} className={`w-full border-b border-slate-800 px-5 py-4 text-left transition hover:bg-slate-800/70 ${selected?.event_id === item.event_id ? 'bg-cyan-950/40' : ''}`}>
                  <div className="flex gap-3"><span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-rose-400" /><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><p className="truncate font-mono text-xs text-cyan-300">{item.event_id}</p><span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-300">attempt {item.attempt_count}</span></div><p className="mt-1 text-sm font-medium">{item.event_type}</p><p className="mt-1 line-clamp-2 text-xs text-slate-400">{item.last_error || 'No failure text recorded.'}</p><p className="mt-2 text-xs text-slate-500">{item.reviewed_at ? `Reviewed by actor ${item.reviewer_actor_id}` : 'Awaiting review'} · {new Date(item.created_at).toLocaleString()}</p></div></div>
                </button>
              ))}
            </div>
          </section>

          <aside className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5">
            {!selected ? <div className="py-16 text-center text-sm text-slate-500">Select a dead-letter event to inspect its durable payload and decide on review.</div> : <>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-400">Selected event</p>
              <h2 className="mt-2 break-all font-mono text-sm text-slate-100">{selected.event_id}</h2>
              <dl className="mt-5 grid grid-cols-2 gap-3 text-xs"><div><dt className="text-slate-500">Aggregate</dt><dd className="mt-1 break-all text-slate-200">{selected.aggregate_type}</dd></div><div><dt className="text-slate-500">Correlation</dt><dd className="mt-1 break-all text-slate-200">{selected.correlation_id}</dd></div></dl>
              <div className="mt-5"><p className="text-xs text-slate-500">Payload snapshot</p><pre className="mt-2 max-h-44 overflow-auto rounded-lg bg-slate-950 p-3 text-xs leading-5 text-slate-300">{JSON.stringify(selected.payload, null, 2)}</pre></div>
              <form className="mt-5" onSubmit={(event) => submitAction(event, selectedReviewed ? 'replay' : 'review')}>
                <label className="text-sm font-medium text-slate-300">{selectedReviewed ? 'Replay authorization note' : 'Review note'}
                  <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={4} placeholder="State why payload, downstream dependency, and replay safety were checked." className="mt-2 w-full resize-y rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none ring-cyan-500 focus:ring-2" />
                </label>
                <button type="submit" disabled={acting} className={`mt-3 w-full rounded-lg px-4 py-2.5 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-50 ${selectedReviewed ? 'bg-amber-400 text-slate-950 hover:bg-amber-300' : 'bg-emerald-400 text-slate-950 hover:bg-emerald-300'}`}>{acting ? 'Saving…' : selectedReviewed ? 'Approve controlled replay' : 'Record review'}</button>
              </form>
              <p className="mt-4 text-xs leading-5 text-slate-500">Replay changes durable status to <code>retry</code>. The background relay, not this dashboard, publishes when eligible. An audit event records every review and replay request.</p>
            </>}
          </aside>
        </div>
      </section>
    </main>
  );
}
