'use client';

import { FormEvent, useMemo, useState } from 'react';
import BodyAvatar3D, { BodyMeasurements, TryOnGarmentBinding } from './BodyAvatar3D';

const DEFAULT_API_URL = process.env.NEXT_PUBLIC_AI_STYLIST_API_URL ?? 'http://127.0.0.1:8000';
const STYLE_OPTIONS = [
  ['minimal', 'Tối giản'], ['classic', 'Cổ điển'], ['smart_casual', 'Smart casual'], ['business', 'Chuyên nghiệp'],
  ['quiet_luxury', 'Quiet luxury'], ['preppy', 'Preppy'], ['romantic', 'Lãng mạn'], ['bohemian', 'Bohemian'],
  ['streetwear', 'Đường phố'], ['edgy', 'Cá tính'], ['athleisure', 'Athleisure'], ['utility', 'Utility'],
  ['modest', 'Kín đáo'], ['resort', 'Resort'], ['creative', 'Sáng tạo'], ['vintage', 'Vintage'],
] as const;
const INTENT_OPTIONS = [
  ['comfort', 'Thoải mái'], ['all_day', 'Mặc cả ngày'], ['movement', 'Di chuyển nhiều'], ['weather_protection', 'Che nắng/mưa/lạnh'],
  ['professional_presence', 'Chỉn chu chuyên nghiệp'], ['photo_ready', 'Lên hình đẹp'], ['low_maintenance', 'Dễ chăm sóc'],
  ['packable', 'Dễ mang theo'], ['coverage', 'Ưu tiên coverage'], ['celebration', 'Dịp kỷ niệm'], ['confidence', 'Tăng tự tin'],
] as const;
const OCCASIONS = ['daily', 'work', 'meeting', 'interview', 'presentation', 'date', 'weekend', 'travel', 'outdoor', 'gym', 'cocktail', 'celebration', 'wedding_guest', 'event', 'formal'];

type BodyProfile = { profile_id: string; status: string; contract: { measurements: Record<string, number | string> } };
type WardrobeAsset = { asset_id: string; revision_id: string; name: string; category: string; status: string; canonical_garment_id?: string | null };
type Session = { session_id: string; status: string; body_profile_id: string; context: Record<string, unknown>; wardrobe_snapshot: WardrobeAsset[]; active_decision_run_id?: string | null; selected_outfit_id?: string | null };
type Candidate = { outfit_id: string; garment_ids: string[]; total_score: number; confidence: number; evidence: Array<{ rule_id: string; message: string; score_delta: number }>; tradeoffs: string[]; needs_user_confirmation: string[]; style_archetypes?: string[]; style_story?: string; functional_highlights?: string[] };
type Decision = { decision_run_id: string; status: string; decision: { candidates: Candidate[]; abstained: boolean; abstention_reason?: string | null; score_breakdown?: Record<string, number>; rejected_candidates?: Array<{ candidate_key: string; reason_code: string; message: string }> } };
type TryOn = { try_on_run_id: string; status: string; selected_outfit_id: string; render_mode: 'canonical_proxy' | 'rigged_template' | 'approved_reconstructed_asset'; requested_render_mode: string; quality_status: string; asset_bindings: TryOnGarmentBinding[]; limitations: string[] };

type ViewPreset = 'front' | 'side' | 'back' | 'free';

const initialMeasurements = { height_cm: 170, weight_kg: 60, shoulder_cm: 42, bust_cm: 88, waist_cm: 72, hip_cm: 94, inseam_cm: 78, shoulder_slope: 'straight', chest_profile: 'full', leg_alignment: 'straight' };
const newIntent = (prefix: string) => `${prefix}-${crypto.randomUUID()}`;
const correlation = () => `corr-${crypto.randomUUID().replaceAll('-', '').slice(0, 20)}`;
const toggle = (current: string[], item: string) => current.includes(item) ? current.filter((value) => value !== item) : [...current, item];

export default function SessionWorkspace() {
  const [apiUrl, setApiUrl] = useState(DEFAULT_API_URL);
  const [token, setToken] = useState('');
  const [demoActorId, setDemoActorId] = useState('');
  const [profiles, setProfiles] = useState<BodyProfile[]>([]);
  const [assets, setAssets] = useState<WardrobeAsset[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeProfileId, setActiveProfileId] = useState('');
  const [selectedAssetIds, setSelectedAssetIds] = useState<string[]>([]);
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [tryOn, setTryOn] = useState<TryOn | null>(null);
  const [measurements, setMeasurements] = useState(initialMeasurements);
  const [occasion, setOccasion] = useState('work');
  const [styles, setStyles] = useState<string[]>(['business', 'classic']);
  const [intents, setIntents] = useState<string[]>(['professional_presence', 'confidence']);
  const [weather, setWeather] = useState('unknown');
  const [mobility, setMobility] = useState('normal');
  const [modesty, setModesty] = useState('standard');
  const [formality, setFormality] = useState('business');
  const [styleIntensity, setStyleIntensity] = useState('balanced');
  const [availability, setAvailability] = useState('owned_only');
  const [optionalSlots, setOptionalSlots] = useState<string[]>(['outerwear', 'footwear', 'accessory']);
  const [budget, setBudget] = useState('');
  const [colorGoals, setColorGoals] = useState('');
  const [feedbackReason, setFeedbackReason] = useState('visual_mismatch');
  const [feedbackNote, setFeedbackNote] = useState('');
  const [viewPreset, setViewPreset] = useState<ViewPreset>('front');
  const [message, setMessage] = useState('Chọn nhu cầu, style và item trong kho đồ; sau đó tạo snapshot server-side.');
  const [busy, setBusy] = useState(false);

  const isDemo = !token.trim();
  const readSuffix = isDemo && demoActorId ? `?actor_id=${encodeURIComponent(demoActorId)}` : '';
  const bodyMeasurements: BodyMeasurements = useMemo(() => {
    const source = profiles.find((profile) => profile.profile_id === activeSession?.body_profile_id)?.contract.measurements;
    const value = source ?? measurements;
    return {
      height: Number(value.height_cm ?? measurements.height_cm), weight: Number(value.weight_kg ?? measurements.weight_kg), shoulder: Number(value.shoulder_cm ?? measurements.shoulder_cm), bust: Number(value.bust_cm ?? measurements.bust_cm), waist: Number(value.waist_cm ?? measurements.waist_cm), hip: Number(value.hip_cm ?? measurements.hip_cm), inseam: Number(value.inseam_cm ?? measurements.inseam_cm),
      shoulder_slope: (value.shoulder_slope as 'straight' | 'sloped') ?? 'straight', chest_profile: (value.chest_profile as 'full' | 'flat') ?? 'full', leg_alignment: (value.leg_alignment as 'straight' | 'bowed') ?? 'straight',
    };
  }, [activeSession?.body_profile_id, measurements, profiles]);

  const request = async <T,>(path: string, init: RequestInit = {}, intent?: string): Promise<T> => {
    const headers = new Headers(init.headers);
    if (token.trim()) headers.set('Authorization', `Bearer ${token.trim()}`);
    if (intent) { headers.set('Idempotency-Key', intent); headers.set('X-Correlation-ID', correlation()); headers.set('Content-Type', 'application/json'); }
    const response = await fetch(`${apiUrl}${path}`, { ...init, headers });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail ?? `HTTP ${response.status}`);
    return payload as T;
  };

  const commandPayload = (payload: Record<string, unknown>) => isDemo ? { ...payload, actor_id: Number(demoActorId) } : payload;

  const loadWorkspace = async () => {
    if (isDemo && (!demoActorId || Number(demoActorId) <= 0)) { setMessage('Demo mode cần actor ID dương; production cần JWT.'); return; }
    setBusy(true);
    try {
      const [profilePage, assetPage, sessionPage] = await Promise.all([
        request<{ items: BodyProfile[] }>(`/workflow/body-profiles${readSuffix}`), request<{ items: WardrobeAsset[] }>(`/workflow/wardrobe-assets${readSuffix}`), request<{ items: Session[] }>(`/workflow/styling-sessions${readSuffix}`),
      ]);
      setProfiles(profilePage.items); setAssets(assetPage.items); setSessions(sessionPage.items);
      const profile = profilePage.items.find((item) => item.status === 'active') ?? profilePage.items[0];
      if (profile) setActiveProfileId(profile.profile_id);
      setMessage(`Đã tải ${profilePage.items.length} body revision, ${assetPage.items.length} asset và ${sessionPage.items.length} session.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Không tải được Session Workspace.'); }
    finally { setBusy(false); }
  };

  const createAndConfirmProfile = async () => {
    setBusy(true);
    try {
      const profile = await request<BodyProfile>('/workflow/body-profiles', { method: 'POST', body: JSON.stringify(commandPayload({ measurements })) }, newIntent('body-create'));
      const confirmed = await request<BodyProfile>(`/workflow/body-profiles/${profile.profile_id}/confirm`, { method: 'POST', body: JSON.stringify(commandPayload({ confirmation_note: 'User verified measurement inputs in Session Workspace.' })) }, newIntent('body-confirm'));
      setProfiles((current) => [confirmed, ...current.filter((item) => item.profile_id !== confirmed.profile_id)]); setActiveProfileId(confirmed.profile_id); setMessage('Body profile đã được confirm và active.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Không thể tạo body profile.'); }
    finally { setBusy(false); }
  };

  const createSession = async () => {
    if (!activeProfileId) { setMessage('Chọn hoặc tạo body profile active trước.'); return; }
    if (availability === 'owned_only' && selectedAssetIds.length === 0) { setMessage('Owned-only cần chọn ít nhất các item active trong kho đồ.'); return; }
    setBusy(true);
    try {
      const context = {
        occasion, preferred_styles: styles, intent_tags: intents, season: 'all_season', fit_preference: 'regular', required_slots: ['base_top', 'bottom'], optional_slots: optionalSlots,
        weather, mobility_need: mobility, modesty_preference: modesty, formality_target: formality, style_intensity: styleIntensity,
        budget_max: budget ? Number(budget) : null, color_goals: colorGoals.split(',').map((value) => value.trim()).filter(Boolean), availability_policy: availability,
      };
      const session = await request<Session>('/workflow/styling-sessions', { method: 'POST', body: JSON.stringify(commandPayload({ body_profile_id: activeProfileId, context, wardrobe_asset_ids: selectedAssetIds })) }, newIntent('session-create'));
      setSessions((current) => [session, ...current]); setActiveSession(session); setDecision(null); setTryOn(null); setMessage('StylingSession immutable snapshot đã được tạo từ nhu cầu và kho đồ hiện tại.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Không thể tạo session.'); }
    finally { setBusy(false); }
  };

  const runDecision = async () => {
    if (!activeSession) return;
    setBusy(true);
    try {
      const result = await request<Decision>(`/workflow/styling-sessions/${activeSession.session_id}/outfit-decisions`, { method: 'POST', body: JSON.stringify(commandPayload({ top_k: 3 })) }, newIntent('decision-run'));
      setDecision(result); setTryOn(null); setMessage(result.decision.abstained ? (result.decision.abstention_reason ?? 'Decision abstained.') : 'Đã tạo các hướng phối đồ khác nhau, có evidence và trade-off. Chọn Preview để xem trên hình nhân.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Không chạy được outfit decision.'); }
    finally { setBusy(false); }
  };

  const selectCandidate = async (outfitId: string) => {
    if (!activeSession) return;
    setBusy(true);
    try {
      const session = await request<Session>(`/workflow/styling-sessions/${activeSession.session_id}/select-outfit`, { method: 'POST', body: JSON.stringify(commandPayload({ outfit_id: outfitId })) }, newIntent('outfit-select'));
      setActiveSession(session); setSessions((current) => current.map((item) => item.session_id === session.session_id ? session : item)); setMessage('Candidate đã được xác nhận và lưu vào session. Bạn có thể yêu cầu try-on chính thức.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Không thể chọn candidate.'); }
    finally { setBusy(false); }
  };

  const previewCandidate = async (candidate: Candidate, renderMode: 'canonical_proxy' | 'rigged_template' | 'approved_reconstructed_asset' = 'canonical_proxy') => {
    if (!activeSession) return;
    setBusy(true);
    try {
      const result = await request<TryOn>(`/workflow/styling-sessions/${activeSession.session_id}/try-on`, { method: 'POST', body: JSON.stringify(commandPayload({ render_mode: renderMode, preview_outfit_id: candidate.outfit_id })) }, newIntent('tryon-preview'));
      setTryOn(result); setMessage(`Đang preview ${candidate.outfit_id}. Đây chưa phải thao tác chọn outfit; actual render mode là ${result.render_mode}.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Không preview được candidate.'); }
    finally { setBusy(false); }
  };

  const requestFinalTryOn = async (renderMode: 'canonical_proxy' | 'rigged_template' | 'approved_reconstructed_asset') => {
    if (!activeSession?.selected_outfit_id) { setMessage('Hãy xác nhận một candidate trước khi tạo try-on chính thức.'); return; }
    setBusy(true);
    try {
      const result = await request<TryOn>(`/workflow/styling-sessions/${activeSession.session_id}/try-on`, { method: 'POST', body: JSON.stringify(commandPayload({ render_mode: renderMode })) }, newIntent('tryon-request'));
      setTryOn(result); setMessage(result.status === 'ready' ? 'Approved asset evidence cho phép render đã yêu cầu.' : 'Server dùng proxy fallback; đọc limitations trước khi diễn giải kết quả.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Không tạo được try-on run.'); }
    finally { setBusy(false); }
  };

  const submitFeedback = async (event: FormEvent) => {
    event.preventDefault();
    if (!activeSession || !decision) return;
    setBusy(true);
    try {
      await request(`/workflow/styling-sessions/${activeSession.session_id}/feedback`, { method: 'POST', body: JSON.stringify(commandPayload({ decision_run_id: decision.decision_run_id, try_on_run_id: tryOn?.try_on_run_id ?? null, target_outfit_id: tryOn?.selected_outfit_id ?? activeSession.selected_outfit_id ?? null, sentiment: 'dislike', reason_codes: [feedbackReason], issue_type: feedbackReason === 'visual_mismatch' ? 'visual_render' : 'other', note: feedbackNote || null, confidence: 3 })) }, newIntent('feedback-submit'));
      setFeedbackNote(''); setMessage('Feedback đã được lưu với provenance; issue có thể tạo ReviewTask triage.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Không gửi được feedback.'); }
    finally { setBusy(false); }
  };

  return <main className="mx-auto max-w-7xl space-y-6 p-5 md:p-8">
    <header className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm"><p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-600">Style intelligence workspace</p><h1 className="mt-2 text-3xl font-black text-slate-950">Phối đồ theo kho đồ, nhu cầu và góc nhìn 3D</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Engine dùng metadata và evidence trong immutable session snapshot. Preview giúp so sánh candidate, còn xác nhận outfit là command riêng có audit. Proxy không phải fitting 3D thật.</p></header>

    <section className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-950 p-4 text-white md:grid-cols-[1fr_1fr_auto]"><label className="text-xs font-bold">API URL<input value={apiUrl} onChange={(event) => setApiUrl(event.target.value)} className="mt-1 w-full rounded-lg bg-white/10 px-3 py-2 text-sm outline-none" /></label><label className="text-xs font-bold">JWT production hoặc để trống cho demo<input value={token} onChange={(event) => setToken(event.target.value)} type="password" placeholder="Bearer token (memory only)" className="mt-1 w-full rounded-lg bg-white/10 px-3 py-2 text-sm outline-none" /></label>{isDemo && <label className="text-xs font-bold">Demo actor ID<input value={demoActorId} onChange={(event) => setDemoActorId(event.target.value)} inputMode="numeric" className="mt-1 w-full rounded-lg bg-white/10 px-3 py-2 text-sm outline-none" /></label>}<button onClick={loadWorkspace} disabled={busy} className="self-end rounded-lg bg-indigo-500 px-4 py-2 text-sm font-bold hover:bg-indigo-400 disabled:opacity-50">Tải workspace</button></section>
    <p className="rounded-xl border border-indigo-100 bg-indigo-50 px-4 py-3 text-sm text-indigo-950">{message}</p>

    <div className="grid gap-6 xl:grid-cols-[1fr_1fr]"><section className="space-y-5 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm"><div><h2 className="text-lg font-black">1. Body và nhu cầu sử dụng</h2><p className="text-sm text-slate-500">Chọn style, mục đích và mức độ chỉn chu trước khi tạo snapshot.</p></div><div className="grid grid-cols-2 gap-2">{Object.entries(measurements).filter(([key]) => !['shoulder_slope', 'chest_profile', 'leg_alignment'].includes(key)).map(([key, value]) => <label key={key} className="text-xs font-semibold text-slate-600">{key.replace('_cm', '')}<input type="number" value={value as number} onChange={(event) => setMeasurements((current) => ({ ...current, [key]: Number(event.target.value) }))} className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2" /></label>)}</div><button onClick={createAndConfirmProfile} disabled={busy} className="w-full rounded-xl bg-slate-900 px-4 py-3 text-sm font-bold text-white disabled:opacity-50">Tạo và confirm body profile</button><select value={activeProfileId} onChange={(event) => setActiveProfileId(event.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"><option value="">Chọn active body profile</option>{profiles.map((profile) => <option key={profile.profile_id} value={profile.profile_id}>{profile.profile_id} · {profile.status}</option>)}</select><div className="grid gap-2 sm:grid-cols-2"><label className="text-xs font-semibold">Nhu cầu / occasion<select value={occasion} onChange={(event) => setOccasion(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2">{OCCASIONS.map((item) => <option key={item} value={item}>{item}</option>)}</select></label><label className="text-xs font-semibold">Formality<select value={formality} onChange={(event) => setFormality(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2"><option value="casual">Casual</option><option value="smart_casual">Smart casual</option><option value="business">Business</option><option value="formal">Formal</option><option value="ceremonial">Ceremonial</option></select></label><label className="text-xs font-semibold">Style intensity<select value={styleIntensity} onChange={(event) => setStyleIntensity(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2"><option value="subtle">Subtle</option><option value="balanced">Balanced</option><option value="statement">Statement</option></select></label><label className="text-xs font-semibold">Availability<select value={availability} onChange={(event) => setAvailability(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2"><option value="owned_only">Chỉ kho đồ của tôi</option><option value="owned_preferred">Ưu tiên kho đồ của tôi</option><option value="allow_catalog">Khám phá catalog</option></select></label><label className="text-xs font-semibold">Weather<select value={weather} onChange={(event) => setWeather(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2"><option value="unknown">Unknown</option><option value="hot">Hot</option><option value="mild">Mild</option><option value="cold">Cold</option><option value="rainy">Rainy</option><option value="humid">Humid</option></select></label><label className="text-xs font-semibold">Mobility<select value={mobility} onChange={(event) => setMobility(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2"><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></label><label className="text-xs font-semibold">Modesty<select value={modesty} onChange={(event) => setModesty(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2"><option value="standard">Standard</option><option value="covered">Covered</option><option value="conservative">Conservative</option></select></label><label className="text-xs font-semibold">Budget<input value={budget} onChange={(event) => setBudget(event.target.value)} inputMode="decimal" placeholder="Optional" className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2" /></label></div><label className="block text-xs font-semibold">Color goals<input value={colorGoals} onChange={(event) => setColorGoals(event.target.value)} placeholder="navy, neutral" className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2" /></label><div><p className="text-xs font-bold text-slate-700">Định hướng style</p><div className="mt-2 flex flex-wrap gap-2">{STYLE_OPTIONS.map(([value, label]) => <button type="button" key={value} onClick={() => setStyles((current) => toggle(current, value))} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${styles.includes(value) ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600'}`}>{label}</button>)}</div></div><div><p className="text-xs font-bold text-slate-700">Mục tiêu chức năng</p><div className="mt-2 flex flex-wrap gap-2">{INTENT_OPTIONS.map(([value, label]) => <button type="button" key={value} onClick={() => setIntents((current) => toggle(current, value))} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${intents.includes(value) ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-600'}`}>{label}</button>)}</div></div></section>

    <section className="space-y-5 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm"><div><h2 className="text-lg font-black">2. Kho đồ và snapshot</h2><p className="text-sm text-slate-500">Chọn asset active. Snapshot không thay đổi khi revision wardrobe về sau được cập nhật.</p></div><div className="max-h-72 space-y-2 overflow-auto rounded-xl bg-slate-50 p-3">{assets.length === 0 && <p className="text-sm text-slate-500">Chưa có asset active. Import/approve item từ workflow trước.</p>}{assets.map((asset) => <label key={asset.asset_id} className="flex items-center justify-between gap-3 rounded-lg bg-white p-3 text-sm shadow-sm"><span><b>{asset.name}</b><span className="ml-2 text-xs text-slate-500">{asset.category} · {asset.status}</span></span><input type="checkbox" disabled={asset.status !== 'active'} checked={selectedAssetIds.includes(asset.asset_id)} onChange={() => setSelectedAssetIds((current) => current.includes(asset.asset_id) ? current.filter((id) => id !== asset.asset_id) : [...current, asset.asset_id])} /></label>)}</div><div><p className="text-xs font-bold text-slate-700">Optional layers để tạo biến thể</p><div className="mt-2 flex flex-wrap gap-2">{[['outerwear', 'Outerwear'], ['footwear', 'Footwear'], ['belt', 'Belt'], ['accessory', 'Accessory']].map(([value, label]) => <button type="button" key={value} onClick={() => setOptionalSlots((current) => toggle(current, value))} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${optionalSlots.includes(value) ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600'}`}>{label}</button>)}</div></div><button onClick={createSession} disabled={busy} className="w-full rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white disabled:opacity-50">Tạo StylingSession snapshot</button><div className="border-t border-slate-100 pt-4"><h3 className="text-sm font-black">Resume session</h3><div className="mt-2 space-y-2">{sessions.map((session) => <button key={session.session_id} onClick={() => { setActiveSession(session); setDecision(null); setTryOn(null); }} className={`w-full rounded-lg border p-3 text-left text-sm ${activeSession?.session_id === session.session_id ? 'border-indigo-500 bg-indigo-50' : 'border-slate-200'}`}><b>{session.session_id}</b><span className="ml-2 text-xs text-slate-500">{session.status}</span></button>)}</div></div></section></div>

    {activeSession && <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]"><div className="space-y-5 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wider text-indigo-600">Active case</p><h2 className="text-lg font-black">{activeSession.session_id}</h2></div><button onClick={runDecision} disabled={busy} className="rounded-xl bg-slate-950 px-4 py-3 text-sm font-bold text-white disabled:opacity-50">Tạo 3 hướng phối đồ</button></div>{decision && <div className="space-y-4"><div className="rounded-xl bg-slate-50 p-4 text-sm"><b>Score breakdown</b><div className="mt-2 flex flex-wrap gap-2">{Object.entries(decision.decision.score_breakdown ?? {}).map(([rule, value]) => <span key={rule} className="rounded-full bg-white px-2 py-1 text-xs shadow-sm">{rule}: {value}</span>)}</div></div>{decision.decision.abstained ? <p className="rounded-xl bg-amber-50 p-4 text-sm text-amber-950">Abstained: {decision.decision.abstention_reason}</p> : decision.decision.candidates.map((candidate, index) => <article key={candidate.outfit_id} className={`rounded-2xl border p-4 ${tryOn?.selected_outfit_id === candidate.outfit_id ? 'border-indigo-500 bg-indigo-50/40' : 'border-slate-200'}`}><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold text-indigo-600">LOOK {index + 1} · {(candidate.style_archetypes ?? []).join(' / ') || 'balanced'}</p><h3 className="font-black">{candidate.outfit_id}</h3><p className="text-sm text-slate-500">Score {candidate.total_score} · Confidence {candidate.confidence}</p></div><div className="flex gap-2"><button onClick={() => previewCandidate(candidate)} disabled={busy} className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-bold text-white">Preview 3D</button><button onClick={() => selectCandidate(candidate.outfit_id)} disabled={busy} className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-bold text-white">Chọn</button></div></div>{candidate.style_story && <p className="mt-3 text-sm leading-6 text-slate-700">{candidate.style_story}</p>}{(candidate.functional_highlights ?? []).length > 0 && <div className="mt-3 flex flex-wrap gap-1">{candidate.functional_highlights?.map((item) => <span key={item} className="rounded-full bg-emerald-100 px-2 py-1 text-xs text-emerald-900">{item}</span>)}</div>}<ul className="mt-3 space-y-1 text-sm text-slate-700">{candidate.evidence.slice(0, 6).map((evidence, evidenceIndex) => <li key={`${candidate.outfit_id}-${evidence.rule_id}-${evidenceIndex}`}>• {evidence.message} ({evidence.score_delta >= 0 ? '+' : ''}{evidence.score_delta})</li>)}</ul>{candidate.tradeoffs.length > 0 && <p className="mt-3 text-xs text-amber-700">Trade-off: {candidate.tradeoffs.join(' · ')}</p>}{candidate.needs_user_confirmation.length > 0 && <p className="mt-2 text-xs text-slate-500">Cần xác nhận: {candidate.needs_user_confirmation.join(' · ')}</p>}</article>)}</div>}</div>

    <div className="space-y-4 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm"><div><h2 className="text-lg font-black">3. So sánh 3D đa góc</h2><p className="text-sm text-slate-500">Preview chỉ dùng candidate trong decision snapshot. Xoay tự do không thay đổi result server-side.</p></div><div className="grid grid-cols-4 gap-2">{([['front', 'Trước'], ['side', 'Bên'], ['back', 'Sau'], ['free', 'Tự do']] as const).map(([preset, label]) => <button key={preset} onClick={() => setViewPreset(preset)} className={`rounded-lg px-2 py-2 text-xs font-bold ${viewPreset === preset ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-700'}`}>{label}</button>)}</div><BodyAvatar3D measurements={bodyMeasurements} autoRotate={viewPreset === 'free'} viewPreset={viewPreset} garmentBindings={tryOn?.asset_bindings ?? []} /><div className="grid grid-cols-3 gap-2"><button onClick={() => requestFinalTryOn('canonical_proxy')} disabled={!activeSession.selected_outfit_id || busy} className="rounded-lg bg-slate-900 px-2 py-2 text-xs font-bold text-white disabled:opacity-50">Proxy đã chọn</button><button onClick={() => requestFinalTryOn('rigged_template')} disabled={!activeSession.selected_outfit_id || busy} className="rounded-lg bg-slate-900 px-2 py-2 text-xs font-bold text-white disabled:opacity-50">Rigged đã chọn</button><button onClick={() => requestFinalTryOn('approved_reconstructed_asset')} disabled={!activeSession.selected_outfit_id || busy} className="rounded-lg bg-slate-900 px-2 py-2 text-xs font-bold text-white disabled:opacity-50">Mesh đã duyệt</button></div>{tryOn && <div className={`rounded-xl p-4 text-sm ${tryOn.quality_status === 'approved' ? 'bg-emerald-50 text-emerald-950' : 'bg-amber-50 text-amber-950'}`}><b>{tryOn.status} · actual {tryOn.render_mode}</b><p className="mt-1">Preview/selected outfit: {tryOn.selected_outfit_id}. Requested: {tryOn.requested_render_mode}; quality: {tryOn.quality_status}</p><ul className="mt-2 space-y-1">{tryOn.limitations.map((limitation) => <li key={limitation}>• {limitation}</li>)}</ul>{tryOn.asset_bindings.some((binding) => binding.structural_profile) && <details className="mt-3 rounded-lg border border-current/20 bg-white/40 p-3"><summary className="cursor-pointer text-xs font-black">Structural cue hiển thị trên proxy</summary><div className="mt-2 space-y-2 text-xs">{tryOn.asset_bindings.filter((binding) => binding.structural_profile).map((binding) => <div key={binding.asset_id ?? binding.import_id ?? binding.category}><b>{binding.category}</b>: {Object.entries(binding.structural_profile ?? {}).filter(([key, value]) => !['schema_version', 'source_views', 'evidence', 'limitations'].includes(key) && typeof value === 'string' && value !== 'unknown').map(([key, value]) => `${key.replaceAll('_', ' ')}=${value}`).join(' · ') || 'No visible cue confirmed'}<p className="mt-1 opacity-80">2D cue minh họa proxy; không phải số đo, sewing pattern, mesh reconstruction hay fit guarantee.</p></div>)}</div></details>}</div>}
<form onSubmit={submitFeedback} className="space-y-2 border-t border-slate-100 pt-4"><h3 className="text-sm font-black">Structured feedback</h3><select value={feedbackReason} onChange={(event) => setFeedbackReason(event.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"><option value="visual_mismatch">Visual render mismatch</option><option value="fit_concern">Fit concern</option><option value="occasion_mismatch">Occasion mismatch</option><option value="asset_mismatch">Asset mismatch</option></select><textarea value={feedbackNote} onChange={(event) => setFeedbackNote(event.target.value)} placeholder="Optional evidence note" className="min-h-20 w-full rounded-lg border border-slate-200 p-3 text-sm" /><button disabled={!decision || busy} className="w-full rounded-lg bg-slate-950 px-3 py-2 text-sm font-bold text-white disabled:opacity-50">Lưu feedback có provenance</button></form></div></section>}
  </main>;
}
