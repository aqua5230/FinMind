"use client";

import React, { useState, useEffect, useCallback } from 'react';
import {
  API_URL as API_BASE,
  fetchPairScan,
  fetchScan,
  fetchRevenueScan,
  resolveStockId,
  type PairScanResponse,
  type PairScanResult,
  type ScanResult,
  type RevenueScanResult,
} from "@/lib/api";

const MACRO_INDICES = [
  { id: 'IDX.TAIEX',   name: '加權指數', price: '35,417.83', change: '+556.67', percent: '+1.60%', vol: '8295 億', trend: [35000, 35100, 35050, 35200, 35350, 35417] },
  { id: 'IDX.TPEX',    name: '櫃買指數', price: '425.30',    change: '+4.15',   percent: '+0.98%', vol: '1250 億', trend: [420, 422, 421, 423, 424, 425] },
  { id: 'FUT.TX00',    name: '台指期近', price: '35,420.00', change: '+643.00', percent: '+1.85%', vol: '12 萬口', trend: [34800, 34900, 35100, 35300, 35420] },
  { id: 'CUR.USDTWD',  name: '美元/台幣', price: '31.850',   change: '-0.150',  percent: '-0.47%', vol: '12 億',   trend: [32.0, 31.95, 31.9, 31.87, 31.85], isDown: true },
];

const SYSTEM_LOGS = [
  { time: '18:23:45', level: '資訊', msg: '加權指數創歷史新高 35417.83 收盤。台積電觸及 2000.00。' },
  { time: '15:08:12', level: '數據', msg: '三大法人淨買超：+378.9 億台幣。外資淨買：+288.0 億台幣。' },
  { time: '13:33:15', level: '警報', msg: '選擇權市場偵測到波動率飆升。VIX 指數 +5.2%。' },
  { time: '09:57:21', level: '執行', msg: '標的 2489.TW 觸及漲停價 42.75。委託簿出現買盤失衡。' },
  { time: '09:45:00', level: '總經', msg: '台幣升值 0.15 來到 31.850。偵測到龐大熱錢資金匯入。' },
  { time: '09:00:01', level: '資訊', msg: '台股開盤。加權指數突破 35000 點關鍵整數壓力位。' },
];

const LOG_COLORS: Record<string, { text: string; bg: string }> = {
  '資訊': { text: 'text-blue-400',   bg: 'bg-blue-900/20' },
  '數據': { text: 'text-emerald-400', bg: 'bg-emerald-900/20' },
  '警報': { text: 'text-amber-400',  bg: 'bg-amber-900/20' },
  '執行': { text: 'text-purple-400', bg: 'bg-purple-900/20' },
  '總經': { text: 'text-rose-400',   bg: 'bg-rose-900/20' },
};

type WatchItem  = { stock_id: string; stock_name: string };
type ActiveTab  = 'scan' | 'watch1' | 'watch2' | 'pair';
type SignalStats = { total: number; resolved: number; pending: number; wins: number; win_rate_pct: number };
type IconProps   = { size?: number; className?: string; strokeWidth?: number };

function Icon({ size = 16, className, strokeWidth = 2, children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"
      className={className} aria-hidden="true" focusable="false">
      {children}
    </svg>
  );
}
function SearchIcon(p: IconProps)      { return <Icon {...p}><circle cx="11" cy="11" r="7" /><path d="m16 16 4 4" /></Icon>; }
function ActivityIcon(p: IconProps)    { return <Icon {...p}><path d="M3 12h4l3-8 4 16 3-8h4" /></Icon>; }
function ZapIcon(p: IconProps)         { return <Icon {...p}><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" /></Icon>; }
function ClockIcon(p: IconProps)       { return <Icon {...p}><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></Icon>; }
function ShieldCheckIcon(p: IconProps) { return <Icon {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path d="m9 12 2 2 4-4" /></Icon>; }
function GlobeIcon(p: IconProps)       { return <Icon {...p}><circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" /></Icon>; }
function MonitorIcon(p: IconProps)     { return <Icon {...p}><rect x="2" y="3" width="20" height="14" rx="2" /><path d="M8 21h8M12 17v4" /></Icon>; }

function openStock(stockId: string, stockName: string, opts?: { signal?: string; indicators?: string }) {
  const params = new URLSearchParams({ id: stockId, name: stockName });
  if (opts?.signal)     params.set('signal', opts.signal);
  if (opts?.indicators) params.set('indicators', opts.indicators);
  window.open(`/stock?${params.toString()}`, '_blank');
}

function loadWatchlist(key: string): WatchItem[] {
  if (typeof window === 'undefined') return [];
  try { return JSON.parse(localStorage.getItem(key) ?? '[]') as WatchItem[]; }
  catch { return []; }
}
function saveWatchlist(key: string, list: WatchItem[]) {
  localStorage.setItem(key, JSON.stringify(list));
}

const WL1_KEY = 'watchlist_1';
const WL2_KEY = 'watchlist_2';

export default function Home() {
  const [cmdInput,            setCmdInput]            = useState('');
  const [time,                setTime]                = useState('');
  const [error,               setError]               = useState('');
  const [isScanning,          setIsScanning]          = useState(false);
  const [scanResults,         setScanResults]         = useState<ScanResult[]>([]);
  const [revenueScanResults,  setRevenueScanResults]  = useState<RevenueScanResult[]>([]);
  const [revenueScanMarket,   setRevenueScanMarket]   = useState<string>('unknown');
  const [revenueScanAt,       setRevenueScanAt]       = useState<string>('');
  const [pairResults,         setPairResults]         = useState<PairScanResult[]>([]);
  const [isPairScanning,      setIsPairScanning]      = useState(false);
  const [pairComputedAt,      setPairComputedAt]      = useState<string>('');
  const [signalStats,         setSignalStats]         = useState<SignalStats | null>(null);
  const [activeTab,           setActiveTab]           = useState<ActiveTab>('scan');
  const [watch1,              setWatch1]              = useState<WatchItem[]>([]);
  const [watch2,              setWatch2]              = useState<WatchItem[]>([]);
  const [wlInput1,            setWlInput1]            = useState('');
  const [wlInput2,            setWlInput2]            = useState('');
  const [wlError1,            setWlError1]            = useState('');
  const [wlError2,            setWlError2]            = useState('');

  useEffect(() => {
    setWatch1(loadWatchlist(WL1_KEY));
    setWatch2(loadWatchlist(WL2_KEY));
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toLocaleTimeString('zh-TW', { hour12: false }));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => { fetchScan().then(s => setScanResults(s.results)).catch(() => {}); }, []);

  useEffect(() => {
    fetchRevenueScan()
      .then(r => { setRevenueScanResults(r.results); setRevenueScanMarket(r.market_filter); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/api/signals/stats`)
      .then(res => res.ok ? res.json() as Promise<SignalStats> : null)
      .then(stats => setSignalStats(stats))
      .catch(() => {});
  }, []);

  const handleSearch = useCallback(async (value: string) => {
    const v = value.trim() || cmdInput.trim();
    if (!v) { setError('請輸入股票代號'); return; }
    try {
      const { stockId, stockName } = await resolveStockId(v);
      openStock(stockId, stockName);
      setCmdInput('');
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '查詢失敗，請稍後再試');
    }
  }, [cmdInput]);

  const handleScan = useCallback(async () => {
    setIsScanning(true);
    setError('');
    try {
      const scan = await fetchRevenueScan();
      setRevenueScanResults(scan.results);
      setRevenueScanMarket(scan.market_filter);
      setRevenueScanAt(scan.scanned_at);
    } catch (err) {
      setRevenueScanResults([]);
      setError(err instanceof Error ? err.message : '掃描失敗，請稍後再試');
    } finally {
      setIsScanning(false);
    }
  }, []);

  const handlePairScan = useCallback(async () => {
    setIsPairScanning(true);
    try {
      const r: PairScanResponse = await fetchPairScan();
      setPairResults(r.pairs);
      setPairComputedAt(r.computed_at);
    } catch {
      setPairResults([]);
    } finally {
      setIsPairScanning(false);
    }
  }, []);

  const handleAddWatch = useCallback(async (which: 1 | 2) => {
    const input   = (which === 1 ? wlInput1 : wlInput2).trim();
    const setInput = which === 1 ? setWlInput1 : setWlInput2;
    const setErr   = which === 1 ? setWlError1 : setWlError2;
    const list     = which === 1 ? watch1 : watch2;
    const setList  = which === 1 ? setWatch1 : setWatch2;
    const key      = which === 1 ? WL1_KEY : WL2_KEY;
    if (!input) return;
    try {
      const { stockId, stockName } = await resolveStockId(input);
      if (list.some(w => w.stock_id === stockId)) { setErr('已在清單中'); return; }
      const next = [...list, { stock_id: stockId, stock_name: stockName }];
      setList(next);
      saveWatchlist(key, next);
      setInput('');
      setErr('');
    } catch {
      setErr('找不到此股票');
    }
  }, [watch1, watch2, wlInput1, wlInput2]);

  const handleRemoveWatch = useCallback((which: 1 | 2, stockId: string) => {
    const list    = which === 1 ? watch1 : watch2;
    const setList = which === 1 ? setWatch1 : setWatch2;
    const key     = which === 1 ? WL1_KEY : WL2_KEY;
    const next    = list.filter(w => w.stock_id !== stockId);
    setList(next);
    saveWatchlist(key, next);
  }, [watch1, watch2]);

  const renderWatchlist = (which: 1 | 2) => {
    const list     = which === 1 ? watch1 : watch2;
    const input    = which === 1 ? wlInput1 : wlInput2;
    const setInput = which === 1 ? setWlInput1 : setWlInput2;
    const err      = which === 1 ? wlError1 : wlError2;
    return (
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-auto">
          {list.length === 0 ? (
            <div className="px-4 py-10 text-slate-500 text-sm text-center">清單為空，請新增標的</div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead className="sticky top-0 bg-[#151921] border-b border-white/5 z-10">
                <tr className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                  <th className="py-3 px-5 font-normal">代號</th>
                  <th className="py-3 px-2 font-normal">名稱</th>
                  <th className="py-3 px-5 font-normal w-10" />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.03]">
                {list.map(w => (
                  <tr key={w.stock_id}
                    className="hover:bg-blue-600/5 cursor-pointer group transition-colors"
                    onClick={() => openStock(w.stock_id, w.stock_name)}
                  >
                    <td className="py-3.5 px-5 text-sm font-mono font-bold text-blue-400 group-hover:underline">{w.stock_id}</td>
                    <td className="py-3.5 px-2 text-sm text-slate-200 group-hover:text-white">{w.stock_name}</td>
                    <td className="py-3.5 px-5 text-right">
                      <button type="button"
                        onClick={e => { e.stopPropagation(); handleRemoveWatch(which, w.stock_id); }}
                        className="text-slate-600 hover:text-rose-500 text-base leading-none px-1 cursor-pointer transition-colors"
                      >×</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div className="border-t border-white/5 px-4 py-2 flex items-center gap-2 shrink-0 bg-[#1a1f29]/30">
          <input
            type="text"
            value={input}
            onChange={e => { setInput(e.target.value); (which === 1 ? setWlError1 : setWlError2)(''); }}
            onKeyDown={e => e.key === 'Enter' && handleAddWatch(which)}
            placeholder="輸入代號…"
            className="flex-1 bg-transparent border border-white/10 focus:border-blue-500 outline-none rounded-lg px-3 py-1.5 text-sm text-blue-400 placeholder-slate-600 transition-colors"
          />
          <button type="button" onClick={() => handleAddWatch(which)}
            className="text-sm text-emerald-400 border border-emerald-500/30 px-3 py-1.5 rounded-lg hover:bg-emerald-500/10 cursor-pointer shrink-0 whitespace-nowrap transition-colors"
          >新增</button>
          {err && <span className="text-rose-500 text-xs shrink-0">{err}</span>}
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen md:h-screen bg-[#0a0c10] text-slate-200 font-sans selection:bg-blue-500/30 flex flex-col md:overflow-hidden">

      {/* ── Header ── */}
      <header className="h-14 border-b border-white/5 bg-[#0f1117]/80 backdrop-blur-md flex items-center justify-between px-3 md:px-6 shrink-0 z-50">
        <div className="flex items-center gap-2 md:gap-6">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-indigo-700 rounded-lg flex items-center justify-center shadow-lg shadow-blue-900/20">
              <ActivityIcon size={18} className="text-white" />
            </div>
            <span className="font-bold tracking-tight text-white text-base md:text-lg">
              PRO QUANT <span className="text-blue-500 text-xs md:text-sm font-medium">v3.0</span>
            </span>
          </div>
          <div className="hidden sm:flex items-center gap-2 bg-white/5 border border-white/10 px-3 py-1.5 rounded-full text-xs text-emerald-400">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            系統連線正常
          </div>
          {/* Mobile: compact status dot */}
          <div className="flex sm:hidden items-center gap-1 text-xs text-emerald-400">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          </div>
        </div>

        {/* Desktop search */}
        <div className="hidden md:block flex-1 max-w-xl px-10">
          <div className="relative group">
            <SearchIcon size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-blue-400 transition-colors" />
            <input
              type="text"
              value={cmdInput}
              onChange={e => setCmdInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch(cmdInput)}
              placeholder="搜尋代號、名稱 (Enter 確認)"
              className="w-full bg-white/5 border border-white/10 rounded-lg py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all placeholder:text-slate-600"
              autoFocus
            />
          </div>
        </div>

        <div className="flex items-center gap-2 md:gap-4">
          {/* Mobile: inline search */}
          <div className="flex md:hidden relative group">
            <SearchIcon size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-blue-400 transition-colors" />
            <input
              type="text"
              value={cmdInput}
              onChange={e => setCmdInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch(cmdInput)}
              placeholder="搜尋代號"
              className="w-[110px] bg-white/5 border border-white/10 rounded-lg py-1.5 pl-8 pr-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500/50 focus:border-blue-500 transition-all placeholder:text-slate-600 focus:w-[140px]"
            />
          </div>
          <div className="hidden md:flex flex-col items-end">
            <div className="text-xs text-slate-500 flex items-center gap-1.5">
              <ClockIcon size={12} /> 台北時間 (GMT+8)
            </div>
            <div className="text-sm font-mono font-medium text-white">{time}</div>
          </div>
          <div className="flex md:hidden text-xs font-mono text-slate-400">{time}</div>
        </div>
      </header>

      {/* ── Error banner ── */}
      {error && (
        <div className="px-6 py-2 text-sm text-rose-400 bg-rose-500/10 border-b border-rose-500/20 shrink-0">{error}</div>
      )}

      {/* ── Main ── */}
      <main className="flex-1 flex flex-col md:flex-row p-3 md:p-4 gap-3 md:gap-4 pb-12 md:overflow-hidden max-w-[1600px] w-full mx-auto">

        {/* Left: Market cards + Logs */}
        <div className="flex flex-col gap-3 md:gap-4 md:flex-1 min-w-0 md:overflow-hidden">

          {/* 2×2 Market cards */}
          <div className="grid grid-cols-2 gap-2 md:gap-4 shrink-0">
            {MACRO_INDICES.map(card => {
              const isDown = card.isDown ?? false;
              const max = Math.max(...card.trend);
              const min = Math.min(...card.trend);
              return (
                <div key={card.id} className="bg-[#151921] border border-white/5 rounded-xl p-3 md:p-5 hover:border-white/10 transition-all group cursor-pointer">
                  <div className="flex justify-between items-start mb-2 md:mb-4">
                    <div>
                      <h3 className="text-slate-400 text-xs md:text-sm font-medium mb-1">{card.name}</h3>
                      <div className="text-lg md:text-2xl font-bold tracking-tight text-white font-mono">{card.price}</div>
                    </div>
                    <div className={`text-right ${isDown ? 'text-rose-500' : 'text-emerald-400'}`}>
                      <div className="text-sm font-bold">{card.change}</div>
                      <div className="text-xs font-medium opacity-80">{card.percent}</div>
                    </div>
                  </div>
                  <div className="flex items-end justify-between gap-4">
                    <div className="flex-1 h-12 flex items-end gap-1 px-1">
                      {card.trend.map((val, i) => {
                        const h = max === min ? 50 : ((val - min) / (max - min)) * 100;
                        return (
                          <div key={i}
                            className={`flex-1 rounded-t-sm transition-all duration-500 ${isDown ? 'bg-rose-500/30 group-hover:bg-rose-500/50' : 'bg-emerald-500/30 group-hover:bg-emerald-500/50'}`}
                            style={{ height: `${h}%` }}
                          />
                        );
                      })}
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">Volume</div>
                      <div className="text-xs text-slate-300 font-mono">{card.vol}</div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Event logs */}
          <div className="bg-[#151921] border border-white/5 rounded-xl h-[260px] md:flex-1 flex flex-col overflow-hidden">
            <div className="px-5 py-3.5 border-b border-white/5 flex justify-between items-center shrink-0">
              <h3 className="flex items-center gap-2 text-sm font-bold text-white">
                <MonitorIcon size={16} className="text-blue-500" />
                即時事件日誌
                <span className="ml-2 px-1.5 py-0.5 bg-blue-500/10 text-blue-400 text-[10px] rounded uppercase tracking-widest">Live</span>
              </h3>
              <div className="text-[10px] text-slate-500 font-medium animate-pulse">接收中...</div>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {SYSTEM_LOGS.map((log, i) => {
                const c = LOG_COLORS[log.level] ?? { text: 'text-slate-400', bg: 'bg-slate-900/20' };
                return (
                  <div key={i} className="flex items-start gap-3 p-3 rounded-lg hover:bg-white/5 transition-colors cursor-pointer group">
                    <div className="text-[11px] font-mono text-slate-500 mt-0.5 whitespace-nowrap">{log.time}</div>
                    <div className={`text-[10px] font-bold px-2 py-0.5 rounded ${c.bg} ${c.text} border border-current/10 min-w-[44px] text-center shrink-0`}>
                      {log.level}
                    </div>
                    <div className="text-sm text-slate-300 leading-relaxed group-hover:text-white transition-colors">{log.msg}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right: Tab panel */}
        <div className="w-full md:w-[450px] shrink-0 bg-[#151921] border border-white/5 rounded-xl flex flex-col overflow-hidden min-h-[480px] md:min-h-0">

          {/* Tab bar */}
          <div className="p-1.5 border-b border-white/5 bg-[#1a1f29]/50 shrink-0">
            <div className="flex gap-1">
              {(['scan', 'watch1', 'watch2', 'pair'] as ActiveTab[]).map((tab, i) => (
                <button key={tab} type="button"
                  onClick={() => setActiveTab(tab)}
                  className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                    activeTab === tab
                      ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20'
                      : 'text-slate-500 hover:bg-white/5 hover:text-slate-300'
                  }`}
                >
                  {['策略掃描', '自選清單', '自選清單二', '雙刀掃描'][i]}
                </button>
              ))}
            </div>
          </div>

          {/* ── Scan tab ── */}
          {activeTab === 'scan' && (
            <div className="flex-1 flex flex-col overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-2 border-b border-white/5 bg-white/[0.02] shrink-0">
                <button
                  type="button"
                  onClick={handleScan}
                  disabled={isScanning}
                  className="px-3 py-1.5 text-xs bg-cyan-900 hover:bg-cyan-800 text-cyan-300 rounded-lg disabled:opacity-50 disabled:cursor-wait transition-colors cursor-pointer"
                >
                  {isScanning ? '掃描中…' : '刷新'}
                </button>
                {revenueScanAt && (
                  <span className="text-xs text-slate-500">
                    更新：{new Date(revenueScanAt).toLocaleTimeString('zh-TW')}
                  </span>
                )}
                <span className="text-xs text-slate-500 ml-auto">共 {revenueScanResults.length} 支</span>
              </div>

              {signalStats !== null && signalStats.resolved > 0 && (
                <div className="px-4 py-2 border-b border-white/5 text-xs text-slate-400 shrink-0 tracking-wider">
                  策略追蹤：{signalStats.resolved} 筆已結算，勝率{' '}
                  <span className="text-blue-400">{signalStats.win_rate_pct}%</span>
                  <span className="text-slate-600 ml-2">({signalStats.pending} 筆追蹤中)</span>
                </div>
              )}

              {revenueScanMarket === 'block' && (
                <div className="px-4 py-2 bg-rose-500/10 border-b border-rose-500/20 text-rose-400 text-xs tracking-wider shrink-0">
                  ⚠ 大盤低於 200MA，月營收策略暫停
                </div>
              )}

              <div className="flex-1 overflow-auto">
                {isScanning ? (
                  <div className="flex items-center justify-center text-slate-500 text-sm py-16">掃描中…</div>
                ) : revenueScanResults.length === 0 ? (
                  <div className="flex items-center justify-center text-slate-500 text-sm py-16">本月無月營收動能訊號</div>
                ) : (
                  <table className="w-full text-left border-collapse">
                    <thead className="sticky top-0 bg-[#151921] z-10">
                      <tr className="text-[10px] font-bold text-slate-500 uppercase tracking-widest border-b border-white/5">
                        <th className="px-5 py-3">代號/名稱</th>
                        <th className="px-2 py-3">月份</th>
                        <th className="px-2 py-3 text-right">YoY</th>
                        <th className="px-5 py-3 text-right">排名</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.03]">
                      {revenueScanResults.map(r => {
                        const yoyPct = (r.revenue_yoy * 100).toFixed(1);
                        const isUp   = r.revenue_yoy >= 0;
                        return (
                          <tr key={r.stock_id}
                            className="hover:bg-blue-600/5 transition-colors group cursor-pointer"
                            onClick={() => openStock(r.stock_id, r.stock_name)}
                          >
                            <td className="px-5 py-3.5">
                              <div className="flex items-center gap-3">
                                <div className="text-xs font-mono font-bold text-blue-400 group-hover:underline">{r.stock_id}</div>
                                <div className="text-sm font-medium text-slate-200 group-hover:text-white">{r.stock_name}</div>
                              </div>
                            </td>
                            <td className="px-2 py-3.5 text-xs text-slate-500 font-mono">
                              {r.revenue_ym.slice(0, 4)}/{r.revenue_ym.slice(4)}
                            </td>
                            <td className={`px-2 py-3.5 text-right font-mono font-bold text-sm ${isUp ? 'text-emerald-400' : 'text-rose-500'}`}>
                              {isUp ? '+' : ''}{yoyPct}%
                            </td>
                            <td className="px-5 py-3.5 text-right text-xs font-bold text-slate-600 group-hover:text-slate-400">#{r.rank}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>

            </div>
          )}

          {activeTab === 'watch1' && renderWatchlist(1)}
          {activeTab === 'watch2' && renderWatchlist(2)}
          {activeTab === 'pair' && (
            <div className="flex-1 flex flex-col overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-2 border-b border-white/5 bg-white/[0.02] shrink-0">
                <button
                  type="button"
                  onClick={handlePairScan}
                  disabled={isPairScanning}
                  className="px-3 py-1.5 text-xs bg-cyan-900 hover:bg-cyan-800 text-cyan-300 rounded-lg disabled:opacity-50 disabled:cursor-wait transition-colors cursor-pointer"
                >
                  {isPairScanning ? '計算中…' : '刷新'}
                </button>
                {pairComputedAt && (
                  <span className="text-xs text-slate-500">
                    更新：{new Date(pairComputedAt).toLocaleTimeString('zh-TW')}
                  </span>
                )}
                <span className="text-xs text-slate-500 ml-auto">共 {pairResults.length} 對</span>
              </div>

              {pairResults.length === 0 ? (
                <div className="flex items-center justify-center text-slate-500 text-sm py-16">
                  {isPairScanning ? '計算中…' : '點擊刷新載入配對'}
                </div>
              ) : (
                <div className="overflow-y-auto flex-1">
                  <table className="w-full text-left border-collapse">
                    <thead className="sticky top-0 bg-[#151921] z-10">
                      <tr className="text-[10px] font-bold text-slate-500 uppercase tracking-widest border-b border-white/5">
                        <th className="px-2 py-3">A 股</th>
                        <th className="px-2 py-3">B 股</th>
                        <th className="px-2 py-3 text-right">相關</th>
                        <th className="px-2 py-3 text-right">偏差</th>
                        <th className="px-2 py-3">建議</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.03]">
                      {pairResults.map((p, idx) => {
                        const absdev = Math.abs(p.deviation);
                        const devColor = absdev >= 2 ? 'text-red-400' : absdev >= 1.5 ? 'text-orange-400' : 'text-slate-300';
                        return (
                          <tr
                            key={`${p.stock_a}-${p.stock_b}-${idx}`}
                            className="hover:bg-blue-600/5 cursor-pointer transition-colors group text-xs"
                            onClick={() => openStock(p.stock_a, p.stock_a)}
                          >
                            <td className="px-2 py-3">
                              <span className="text-cyan-300 font-mono font-bold group-hover:underline">{p.stock_a}</span>
                              <span className={`ml-1 text-xs ${p.a_return_5d >= 0 ? 'text-emerald-400' : 'text-rose-500'}`}>
                                {p.a_return_5d >= 0 ? '+' : ''}{p.a_return_5d.toFixed(1)}%
                              </span>
                            </td>
                            <td className="px-2 py-3">
                              <span className="text-cyan-300 font-mono font-bold">{p.stock_b}</span>
                              <span className={`ml-1 text-xs ${p.b_return_5d >= 0 ? 'text-emerald-400' : 'text-rose-500'}`}>
                                {p.b_return_5d >= 0 ? '+' : ''}{p.b_return_5d.toFixed(1)}%
                              </span>
                            </td>
                            <td className="px-2 py-3 text-right text-slate-400 font-mono">{p.correlation.toFixed(2)}</td>
                            <td className={`px-2 py-3 text-right font-mono font-bold ${devColor}`}>
                              {p.deviation > 0 ? '+' : ''}{p.deviation.toFixed(1)}σ
                            </td>
                            <td className="px-2 py-3 text-slate-400 whitespace-nowrap">{p.suggestion}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      {/* ── Footer status bar ── */}
      <footer className="fixed bottom-0 left-0 right-0 h-8 bg-blue-600 flex items-center px-4 justify-between text-[11px] text-white font-medium z-50">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <ShieldCheckIcon size={12} /> 加密連線
          </div>
          <div className="w-px h-3 bg-white/20" />
          <div>API 延遲: <span className="font-mono">14ms</span></div>
        </div>
        <div className="flex items-center gap-4">
          <div className="uppercase tracking-widest opacity-80">Market Status: Open</div>
          <div className="bg-white/10 px-2 py-0.5 rounded flex items-center gap-1">
            <GlobeIcon size={10} /> TWSE
          </div>
        </div>
      </footer>
    </div>
  );
}
