'use client';

import { useMemo, useState } from 'react';

const DEFAULT_API_URL = process.env.NEXT_PUBLIC_AI_STYLIST_API_URL ?? 'http://127.0.0.1:8000';

type SemanticEvidence = { dimension: string; values: string[]; confidence: number; rationale: string };
type StructuralEvidence = { feature: string; value: string; confidence: number; visible_views: string[]; rationale: string };
type SemanticDraft = {
  status?: string; provider?: string; model_id?: string | null; model_revision?: string | null;
  candidate_metadata?: Record<string, unknown> | null; structural_profile?: Record<string, unknown> | null; evidence?: SemanticEvidence[]; limitations?: string[];
};
type Task = {
  task_id: string; review_type: string; status: string; priority: string; owner_id: number;
  subject_type: string; subject_id: string; subject_revision_id?: string | null; assignee_actor_id?: number | null;
  evidence_snapshot: Record<string, unknown>; checklist_version: string; reason_codes: string[]; reviewer_note?: string | null;
  created_at?: string; claimed_at?: string | null; completed_at?: string | null;
};
type AuditEvent = { event_id: string; event_type: string; actor_id?: number | null; correlation_id: string; payload: Record<string, unknown>; created_at: string };
type Proposal = {
  proposal_id: string; dimension: string; subject_key: string; status: string; support_count: number;
  average_confidence: Record<string, number>; proposal_payload: Record<string, unknown>; source_review_task_ids: string[];
  generated_at: string; reviewed_at?: string | null; reviewer_actor_id?: number | null; review_note?: string | null;
};

const intent = (prefix: string) => `${prefix}-${crypto.randomUUID()}`;
const correlation = () => `corr-${crypto.randomUUID().replaceAll('-', '').slice(0, 20)}`;
const asRecord = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
const asList = <T,>(value: unknown): T[] => Array.isArray(value) ? value as T[] : [];

function findSemanticDraft(snapshot: Record<string, unknown>): SemanticDraft | null {
  const manifest = asRecord(snapshot.manifest);
  const analysis = asRecord(snapshot.analysis ?? manifest.analysis);
  const tagging = asRecord(analysis.semantic_tagging ?? snapshot.semantic_tagging);
  return Object.keys(tagging).length ? tagging as SemanticDraft : null;
}

function confidenceTone(value: number) {
  if (value >= 0.8) return 'bg-emerald-100 text-emerald-900';
  if (value >= 0.55) return 'bg-amber-100 text-amber-900';
  return 'bg-rose-100 text-rose-900';
}

export default function ReviewerQueueDashboard() {
  const [apiUrl, setApiUrl] = useState(DEFAULT_API_URL);
  const [token, setToken] = useState('');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [status, setStatus] = useState('open');
  const [reviewType, setReviewType] = useState('garment_metadata');
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [audits, setAudits] = useState<AuditEvent[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [message, setMessage] = useState('Nhập reviewer JWT, tải queue và kiểm tra semantic evidence trước khi quyết định. Token chỉ tồn tại trong memory.');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [activePanel, setActivePanel] = useState<'tasks' | 'learning'>('tasks');

  const call = async <T,>(path: string, init: RequestInit = {}, idempotencyKey?: string): Promise<T> => {
    if (!token.trim()) throw new Error('Nhập reviewer JWT trước khi thực hiện thao tác.');
    const headers = new Headers(init.headers);
    headers.set('Authorization', `Bearer ${token.trim()}`);
    if (idempotencyKey) {
      headers.set('Idempotency-Key', idempotencyKey);
      headers.set('X-Correlation-ID', correlation());
      headers.set('Content-Type', 'application/json');
    }
    const response = await fetch(`${apiUrl}${path}`, { ...init, headers });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail ?? `HTTP ${response.status}`);
    return body as T;
  };

  const load = async () => {
    try {
      const params = new URLSearchParams({ status });
      if (reviewType) params.set('review_type', reviewType);
      const [page, proposalPage] = await Promise.all([
        call<{ items: Task[] }>(`/review-tasks?${params.toString()}`),
        call<{ items: Proposal[] }>('/taxonomy-learning/proposals?status=proposed'),
      ]);
      setTasks(page.items);
      setProposals(proposalPage.items);
      setSelectedTask(null); setAudits([]); setSelectedProposal(null);
      setMessage(`Đã tải ${page.items.length} review task và ${proposalPage.items.length} taxonomy proposal đang chờ governance.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Không tải được reviewer dashboard.'); }
  };

  const selectTask = async (task: Task) => {
    setSelectedTask(task); setSelectedProposal(null); setAudits([]);
    try {
      const [detail, events] = await Promise.all([
        call<Task>(`/review-tasks/${task.task_id}`),
        call<AuditEvent[]>(`/review-tasks/${task.task_id}/audit-events`),
      ]);
      setSelectedTask(detail); setAudits(events);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Không tải được task detail.'); }
  };

  const submitTaskAction = async (operation: 'claim' | 'approve' | 'reject' | 'rework' | 'release') => {
    if (!selectedTask) return;
    const note = notes[selectedTask.task_id]?.trim() ?? '';
    if (operation !== 'claim' && note.length < 5) { setMessage('Ghi reviewer note tối thiểu 5 ký tự trước khi quyết định hoặc release.'); return; }
    setBusyId(selectedTask.task_id);
    try {
      let updated: Task;
      if (operation === 'claim') updated = await call<Task>(`/review-tasks/${selectedTask.task_id}/claim`, { method: 'POST', body: JSON.stringify({}) }, intent('review-claim'));
      else if (operation === 'release') updated = await call<Task>(`/review-tasks/${selectedTask.task_id}/release`, { method: 'POST', body: JSON.stringify({ release_note: note }) }, intent('review-release'));
      else updated = await call<Task>(`/review-tasks/${selectedTask.task_id}/submit-decision`, { method: 'POST', body: JSON.stringify({ decision: operation, reason_codes: ['semantic_evidence_reviewed'], reviewer_note: note }) }, intent('review-decision'));
      setSelectedTask(updated);
      setTasks((current) => current.map((item) => item.task_id === updated.task_id ? updated : item));
      await selectTask(updated);
      setMessage(`${operation} đã được lưu qua idempotent command và audit trail.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Thao tác reviewer thất bại.'); }
    finally { setBusyId(null); }
  };

  const decideProposal = async (decision: 'approve_for_evaluation' | 'reject') => {
    if (!selectedProposal) return;
    const note = notes[selectedProposal.proposal_id]?.trim() ?? '';
    if (note.length < 10) { setMessage('Taxonomy proposal cần governance note ít nhất 10 ký tự.'); return; }
    setBusyId(selectedProposal.proposal_id);
    try {
      const updated = await call<Proposal>(`/taxonomy-learning/proposals/${selectedProposal.proposal_id}/decision`, { method: 'POST', body: JSON.stringify({ decision, review_note: note }) }, intent('taxonomy-proposal'));
      setSelectedProposal(updated);
      setProposals((current) => current.map((item) => item.proposal_id === updated.proposal_id ? updated : item));
      setMessage(`${decision} đã được lưu. Catalog/ranker vẫn không thay đổi; cần đánh giá holdout và release riêng.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Không thể quyết định taxonomy proposal.'); }
    finally { setBusyId(null); }
  };

  const semanticDraft = useMemo(() => selectedTask ? findSemanticDraft(selectedTask.evidence_snapshot) : null, [selectedTask]);
  const metadata = asRecord(semanticDraft?.candidate_metadata);
  const evidence = asList<SemanticEvidence>(semanticDraft?.evidence);
  const structural = asRecord(semanticDraft?.structural_profile);
  const structuralEvidence = asList<StructuralEvidence>(structural.evidence);
  const structuralFields = Object.entries(structural).filter(([key, value]) => !['schema_version', 'source_views', 'evidence', 'limitations'].includes(key) && typeof value === 'string' && value !== 'unknown');

  return <main className="mx-auto max-w-7xl space-y-6 p-5 md:p-8">
    <header className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm"><p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-600">Reviewer control plane</p><h1 className="mt-2 text-3xl font-black text-slate-950">Duyệt semantic tag có evidence và taxonomy learning có kiểm soát</h1><p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">Prediction từ ảnh chỉ là draft. Approve kích hoạt metadata revision cho workflow; taxonomy learning chỉ tạo proposal dựa trên lịch sử review và không tự thay đổi catalog, rule weight hoặc model.</p></header>

    <section className="grid gap-3 rounded-2xl bg-slate-950 p-4 text-white lg:grid-cols-[1fr_1fr_180px_180px_auto]"><label className="text-xs font-bold">API URL<input value={apiUrl} onChange={(event) => setApiUrl(event.target.value)} className="mt-1 w-full rounded-lg bg-white/10 px-3 py-2 text-sm outline-none" /></label><label className="text-xs font-bold">Reviewer/Admin JWT<input value={token} onChange={(event) => setToken(event.target.value)} type="password" placeholder="Memory only" className="mt-1 w-full rounded-lg bg-white/10 px-3 py-2 text-sm outline-none" /></label><label className="text-xs font-bold">Task status<select value={status} onChange={(event) => setStatus(event.target.value)} className="mt-1 w-full rounded-lg bg-white/10 px-3 py-2 text-sm"><option value="open">Open</option><option value="claimed">Claimed</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="rework_required">Rework</option></select></label><label className="text-xs font-bold">Review type<select value={reviewType} onChange={(event) => setReviewType(event.target.value)} className="mt-1 w-full rounded-lg bg-white/10 px-3 py-2 text-sm"><option value="garment_metadata">Garment metadata</option><option value="garment_mesh_quality">Mesh quality</option><option value="decision_quality">Decision quality</option><option value="user_feedback_triage">Feedback triage</option><option value="">All types</option></select></label><button onClick={load} className="self-end rounded-lg bg-indigo-500 px-4 py-2 text-sm font-bold hover:bg-indigo-400">Tải dashboard</button></section>
    <p className="rounded-xl border border-indigo-100 bg-indigo-50 px-4 py-3 text-sm text-indigo-950">{message}</p>

    <div className="flex gap-2"><button onClick={() => setActivePanel('tasks')} className={`rounded-lg px-4 py-2 text-sm font-bold ${activePanel === 'tasks' ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-700'}`}>Semantic review queue</button><button onClick={() => setActivePanel('learning')} className={`rounded-lg px-4 py-2 text-sm font-bold ${activePanel === 'learning' ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-700'}`}>Taxonomy proposals</button></div>

    {activePanel === 'tasks' && <section className="grid gap-5 xl:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.5fr)]"><aside className="max-h-[72vh] space-y-3 overflow-auto rounded-[2rem] border border-slate-200 bg-white p-4 shadow-sm">{tasks.length === 0 && <p className="p-6 text-center text-sm text-slate-500">Không có task trong filter hiện tại.</p>}{tasks.map((task) => { const draft = findSemanticDraft(task.evidence_snapshot); return <button key={task.task_id} onClick={() => selectTask(task)} className={`w-full rounded-xl border p-4 text-left ${selectedTask?.task_id === task.task_id ? 'border-indigo-500 bg-indigo-50' : 'border-slate-200 hover:border-indigo-200'}`}><div className="flex items-center justify-between gap-2"><span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-bold text-slate-700">{task.review_type}</span><span className="text-xs font-bold text-indigo-700">{task.status}</span></div><p className="mt-3 font-black text-slate-950">{task.subject_id}</p><p className="mt-1 text-xs text-slate-500">{task.subject_revision_id ?? 'No revision'} · priority {task.priority}</p>{draft && <p className="mt-2 text-xs text-indigo-700">{draft.provider ?? 'unknown provider'} · {draft.status ?? 'unknown status'} · {(asRecord(draft.candidate_metadata).styles as string[] ?? []).join(', ') || 'no style tag'}</p>}</button>;})}</aside>

    <article className="min-h-[560px] rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">{!selectedTask ? <div className="flex h-full min-h-96 items-center justify-center text-center text-sm text-slate-500">Chọn một task để xem metadata, evidence, limitations và audit trail.</div> : <div className="space-y-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wider text-indigo-600">{selectedTask.review_type} · {selectedTask.status}</p><h2 className="mt-1 text-xl font-black text-slate-950">{selectedTask.task_id}</h2><p className="mt-1 text-sm text-slate-500">Subject {selectedTask.subject_type} · {selectedTask.subject_id} · checklist {selectedTask.checklist_version}</p></div><div className="flex flex-wrap gap-2">{selectedTask.status === 'open' && <button disabled={busyId === selectedTask.task_id} onClick={() => submitTaskAction('claim')} className="rounded-lg bg-slate-950 px-3 py-2 text-xs font-bold text-white">Claim task</button>}{selectedTask.status === 'claimed' && <button disabled={busyId === selectedTask.task_id} onClick={() => submitTaskAction('release')} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold">Release</button>}</div></div>

    {semanticDraft ? <><section className="rounded-2xl border border-indigo-100 bg-indigo-50 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-xs font-bold uppercase tracking-wider text-indigo-600">Vision draft provenance</p><p className="mt-1 font-black text-indigo-950">{semanticDraft.provider ?? 'unknown'} · {semanticDraft.model_id ?? 'unrecorded model'} · {semanticDraft.model_revision ?? 'unrecorded revision'}</p></div><span className="rounded-full bg-white px-3 py-1 text-xs font-black text-indigo-700">{semanticDraft.status ?? 'unknown'}</span></div><p className="mt-3 text-xs leading-5 text-indigo-900">Provider/model information supports review provenance; it does not establish physical fit, hidden construction, fabric composition or actual 3D reconstruction.</p></section>
    <section className="grid gap-3 md:grid-cols-2"><div className="rounded-2xl border border-slate-200 p-4"><h3 className="text-sm font-black">Draft garment metadata</h3><dl className="mt-3 space-y-2 text-sm"><div><dt className="text-xs font-bold text-slate-500">Name / category</dt><dd>{String(metadata.name ?? 'Unknown')} · {String(metadata.category ?? 'Unknown')}</dd></div><div><dt className="text-xs font-bold text-slate-500">Style</dt><dd>{asList<string>(metadata.styles).join(', ') || 'No tag'}</dd></div><div><dt className="text-xs font-bold text-slate-500">Occasion / intent</dt><dd>{asList<string>(metadata.occasions).join(', ') || 'No occasion'} · {asList<string>(metadata.intent_support).join(', ') || 'No intent'}</dd></div><div><dt className="text-xs font-bold text-slate-500">Formality / color / silhouette</dt><dd>{String(metadata.formality_level ?? 'Unknown')} · {String(metadata.color_family ?? 'Unknown')} · {String(metadata.silhouette ?? 'Unknown')}</dd></div></dl></div><div className="rounded-2xl border border-slate-200 p-4"><h3 className="text-sm font-black">Review checklist</h3><ul className="mt-3 space-y-2 text-sm text-slate-700"><li>• Xác nhận category và visible cue có khớp ảnh.</li><li>• Kiểm tra style/occasion có evidence, không chỉ nghe hợp lý.</li><li>• Không approve vật liệu ẩn, size hoặc physical fit từ một ảnh.</li><li>• Reject/rework khi tag làm sai hard constraint hoặc provenance thiếu.</li></ul></div></section>
    <section className="rounded-2xl border border-cyan-200 bg-cyan-50/40 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><div><h3 className="text-sm font-black text-cyan-950">Visible garment structural profile</h3><p className="mt-1 text-xs text-cyan-900">Cues 2D dùng để minh họa proxy/review. Không phải sewing pattern, số đo, back panel hoặc mesh/fitting 3D.</p></div><span className="rounded-full bg-white px-2 py-1 text-xs font-bold text-cyan-800">views: {asList<string>(structural.source_views).join(', ') || 'unknown'}</span></div>{structuralFields.length === 0 ? <p className="mt-3 text-sm text-cyan-900">Chưa có structural cue đủ evidence; giữ proxy category-only.</p> : <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{structuralFields.map(([key, value]) => <div key={key} className="rounded-xl bg-white p-3"><p className="text-xs font-bold uppercase tracking-wide text-slate-500">{key.replaceAll('_', ' ')}</p><p className="mt-1 text-sm font-black text-slate-950">{String(value)}</p></div>)}</div>}<div className="mt-3 grid gap-2 md:grid-cols-2">{structuralEvidence.map((item) => <div key={`struct-${item.feature}`} className="rounded-xl border border-cyan-100 bg-white p-3"><div className="flex items-center justify-between gap-2"><b className="text-sm">{item.feature}</b><span className={`rounded-full px-2 py-1 text-xs font-bold ${confidenceTone(item.confidence)}`}>{Math.round(item.confidence * 100)}%</span></div><p className="mt-1 text-xs text-slate-600">{item.value} · visible: {item.visible_views.join(', ')}</p><p className="mt-2 text-xs leading-5 text-slate-700">{item.rationale || 'No rationale recorded.'}</p></div>)}</div>{asList<string>(structural.limitations).length > 0 && <ul className="mt-3 space-y-1 text-xs text-cyan-950">{asList<string>(structural.limitations).map((item) => <li key={item}>• {item}</li>)}</ul>}</section>
    <section className="rounded-2xl border border-slate-200 p-4"><h3 className="text-sm font-black">Evidence confidence theo dimension</h3><div className="mt-3 grid gap-2 md:grid-cols-2">{evidence.length === 0 && <p className="text-sm text-slate-500">Không có structured evidence trong snapshot.</p>}{evidence.map((item) => <div key={item.dimension} className="rounded-xl bg-slate-50 p-3"><div className="flex items-center justify-between gap-2"><b className="text-sm">{item.dimension}</b><span className={`rounded-full px-2 py-1 text-xs font-bold ${confidenceTone(item.confidence)}`}>{Math.round(item.confidence * 100)}%</span></div><p className="mt-1 text-xs text-slate-600">{item.values.join(', ')}</p><p className="mt-2 text-xs leading-5 text-slate-700">{item.rationale || 'No rationale recorded.'}</p></div>)}</div></section>
    <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4"><h3 className="text-sm font-black text-amber-950">Limitations phải giữ lại sau approval</h3><ul className="mt-2 space-y-1 text-xs leading-5 text-amber-900">{asList<string>(semanticDraft.limitations).map((item) => <li key={item}>• {item}</li>)}</ul></section></> : <details className="rounded-2xl bg-slate-50 p-4"><summary className="cursor-pointer text-sm font-bold">Task không có semantic tag structure; xem raw evidence snapshot</summary><pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap text-xs text-slate-700">{JSON.stringify(selectedTask.evidence_snapshot, null, 2)}</pre></details>}

    {selectedTask.status === 'claimed' && <section className="rounded-2xl border border-slate-200 p-4"><h3 className="text-sm font-black">Reviewer decision</h3><textarea value={notes[selectedTask.task_id] ?? ''} onChange={(event) => setNotes((current) => ({ ...current, [selectedTask.task_id]: event.target.value }))} placeholder="Evidence-based reviewer note; tối thiểu 5 ký tự" className="mt-3 min-h-24 w-full rounded-xl border border-slate-200 p-3 text-sm" /><div className="mt-3 grid gap-2 sm:grid-cols-3"><button disabled={busyId === selectedTask.task_id} onClick={() => submitTaskAction('approve')} className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white">Approve metadata</button><button disabled={busyId === selectedTask.task_id} onClick={() => submitTaskAction('reject')} className="rounded-lg bg-rose-600 px-3 py-2 text-xs font-bold text-white">Reject</button><button disabled={busyId === selectedTask.task_id} onClick={() => submitTaskAction('rework')} className="rounded-lg bg-amber-400 px-3 py-2 text-xs font-bold text-slate-950">Request rework</button></div></section>}

    <details className="rounded-2xl bg-slate-50 p-4"><summary className="cursor-pointer text-sm font-bold">Audit trail ({audits.length})</summary><div className="mt-3 space-y-2">{audits.map((event) => <div key={event.event_id} className="rounded-xl bg-white p-3 text-xs shadow-sm"><p className="font-bold text-slate-900">{event.event_type} · actor {event.actor_id ?? 'system'}</p><p className="mt-1 text-slate-500">{event.created_at} · {event.correlation_id}</p><pre className="mt-2 overflow-auto whitespace-pre-wrap text-slate-700">{JSON.stringify(event.payload, null, 2)}</pre></div>)}</div></details></div>}</article></section>}

    {activePanel === 'learning' && <section className="grid gap-5 xl:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.5fr)]"><aside className="max-h-[72vh] space-y-3 overflow-auto rounded-[2rem] border border-slate-200 bg-white p-4 shadow-sm">{proposals.length === 0 && <p className="p-6 text-center text-sm text-slate-500">Không có proposal đang chờ governance.</p>}{proposals.map((proposal) => <button key={proposal.proposal_id} onClick={() => { setSelectedProposal(proposal); setSelectedTask(null); }} className={`w-full rounded-xl border p-4 text-left ${selectedProposal?.proposal_id === proposal.proposal_id ? 'border-indigo-500 bg-indigo-50' : 'border-slate-200 hover:border-indigo-200'}`}><div className="flex justify-between gap-2"><span className="text-xs font-bold text-indigo-700">{proposal.dimension}</span><span className="text-xs font-bold text-slate-600">support {proposal.support_count}</span></div><p className="mt-2 font-black text-slate-950">{proposal.subject_key}</p><p className="mt-1 text-xs text-slate-500">{proposal.source_review_task_ids.length} review source(s)</p></button>)}</aside><article className="min-h-[420px] rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">{!selectedProposal ? <div className="flex h-full min-h-80 items-center justify-center text-center text-sm text-slate-500">Chọn proposal để xem support, provenance và release preconditions.</div> : <div className="space-y-5"><div><p className="text-xs font-bold uppercase tracking-wider text-indigo-600">Learning proposal · {selectedProposal.status}</p><h2 className="mt-1 text-xl font-black">{selectedProposal.subject_key}</h2><p className="mt-1 text-sm text-slate-500">{selectedProposal.dimension} · support {selectedProposal.support_count}</p></div><section className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"><b>Safety boundary.</b> Đây là prior candidate sinh tự động từ review đã approve. Nó không sửa `canonical_garments`, không đổi weight ranker, không kích hoạt VLM training và không ảnh hưởng người dùng cho đến khi qua holdout evaluation và một release governance riêng.</section><section className="grid gap-3 md:grid-cols-2"><div className="rounded-2xl bg-slate-50 p-4"><h3 className="text-sm font-black">Average source confidence</h3><pre className="mt-2 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(selectedProposal.average_confidence, null, 2)}</pre></div><div className="rounded-2xl bg-slate-50 p-4"><h3 className="text-sm font-black">Source review tasks</h3><p className="mt-2 text-xs leading-5">{selectedProposal.source_review_task_ids.join(', ')}</p></div></section><details className="rounded-2xl border border-slate-200 p-4"><summary className="cursor-pointer text-sm font-bold">Proposal payload and release preconditions</summary><pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap text-xs text-slate-700">{JSON.stringify(selectedProposal.proposal_payload, null, 2)}</pre></details>{selectedProposal.status === 'proposed' && <section className="rounded-2xl border border-slate-200 p-4"><h3 className="text-sm font-black">Admin governance decision</h3><textarea value={notes[selectedProposal.proposal_id] ?? ''} onChange={(event) => setNotes((current) => ({ ...current, [selectedProposal.proposal_id]: event.target.value }))} placeholder="Governance note (minimum 10 characters)" className="mt-3 min-h-24 w-full rounded-xl border border-slate-200 p-3 text-sm" /><div className="mt-3 grid gap-2 sm:grid-cols-2"><button disabled={busyId === selectedProposal.proposal_id || selectedProposal.support_count < 3} onClick={() => decideProposal('approve_for_evaluation')} className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-50">Approve for offline evaluation</button><button disabled={busyId === selectedProposal.proposal_id} onClick={() => decideProposal('reject')} className="rounded-lg bg-rose-600 px-3 py-2 text-xs font-bold text-white">Reject proposal</button></div>{selectedProposal.support_count < 3 && <p className="mt-2 text-xs text-amber-700">Cần ít nhất 3 nguồn review độc lập trước khi có thể approve cho evaluation.</p>}</section>}</div>}</article></section>}
  </main>;
}
