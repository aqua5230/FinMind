"use client";

import React, { useState, useEffect, useCallback } from 'react';
import {
  setChartInitialActiveIndicators,
  type IndicatorKey,
} from "@/components/chart/CandlestickChart";
import { KLinePanel } from "@/components/chart/KLinePanel";
import { StockInfoBar } from "@/components/layout/StockInfoBar";
import { fetchLatestPrice, fetchScan, resolveStockId, type ScanResult } from "@/lib/api";
import type { LatestPrice, StockState } from "@/lib/types";

const MACRO_INDICES = [
  { id: 'IDX.TAIEX', name: '加權指數', price: '35417.83', change: '+556.67', percent: '+1.60%', vol: '8295億' },
  { id: 'IDX.TPEX', name: '櫃買指數', price: '425.30', change: '+4.15', percent: '+0.98%', vol: '1250億' },
  { id: 'FUT.TX00', name: '台指期近', price: '35420.00', change: '+643.00', percent: '+1.85%', vol: '12萬口' },
  { id: 'CUR.USDTWD', name: '美元/台幣', price: '31.850', change: '-0.150', percent: '-0.47%', vol: '12億' },
];

const SYSTEM_LOGS = [
  { time: '18:23:45.001', level: '資訊', msg: '加權指數創歷史新高 35417.83 收盤。台積電觸及 2000.00。' },
  { time: '15:08:12.443', level: '數據', msg: '三大法人淨買超：+378.9 億台幣。外資淨買：+288.0 億台幣。' },
  { time: '13:33:15.999', level: '警報', msg: '選擇權市場偵測到波動率飆升。VIX 指數 +5.2%。' },
  { time: '09:57:21.104', level: '執行', msg: '標的 2489.TW 觸及漲停價 42.75。委託簿出現買盤失衡。' },
  { time: '09:45:00.000', level: '總經', msg: '台幣升值 0.15 來到 31.850。偵測到龐大熱錢資金匯入。' },
  { time: '09:00:01.050', level: '資訊', msg: '台股開盤。加權指數突破 35000 點關鍵整數壓力位。' },
];

const C_UP = 'text-[#00FF66]';
const C_DOWN = 'text-[#FF003C]';
const C_SYS = 'text-[#00E5FF]';
const C_BORDER = 'border-[#222222]';

type WatchItem = { stock_id: string; stock_name: string };
type ActiveTab = 'scan' | 'watch1' | 'watch2';

type IconProps = {
  size?: number;
  className?: string;
  strokeWidth?: number;
};

function Icon({
  size = 16,
  className,
  strokeWidth = 2,
  children,
}: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

function Search(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="m16 16 4 4" />
    </Icon>
  );
}

function Activity(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M3 12h4l3-8 4 16 3-8h4" />
    </Icon>
  );
}

function Terminal(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m4 7 5 5-5 5" />
      <path d="M12 19h8" />
    </Icon>
  );
}

function Database(props: IconProps) {
  return (
    <Icon {...props}>
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
      <path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
    </Icon>
  );
}

function formatDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function loadWatchlist(key: string): WatchItem[] {
  if (typeof window === 'undefined') return [];
  try {
    return JSON.parse(localStorage.getItem(key) ?? '[]') as WatchItem[];
  } catch {
    return [];
  }
}

function saveWatchlist(key: string, list: WatchItem[]) {
  localStorage.setItem(key, JSON.stringify(list));
}

const SCAN_INDICATORS: IndicatorKey[] = ["BOLL", "MACD", "RSI"];
const WL1_KEY = 'watchlist_1';
const WL2_KEY = 'watchlist_2';

export default function Home() {
  const [cmdInput, setCmdInput] = useState('');
  const [time, setTime] = useState('');
  const [stock, setStock] = useState<StockState | null>(null);
  const [latestPrice, setLatestPrice] = useState<LatestPrice | null>(null);
  const [error, setError] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [chartSessionKey, setChartSessionKey] = useState(0);
  const [activeTab, setActiveTab] = useState<ActiveTab>('scan');

  const [watch1, setWatch1] = useState<WatchItem[]>([]);
  const [watch2, setWatch2] = useState<WatchItem[]>([]);
  const [wlInput1, setWlInput1] = useState('');
  const [wlInput2, setWlInput2] = useState('');
  const [wlError1, setWlError1] = useState('');
  const [wlError2, setWlError2] = useState('');

  useEffect(() => {
    setWatch1(loadWatchlist(WL1_KEY));
    setWatch2(loadWatchlist(WL2_KEY));
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      const d = new Date();
      setTime(`2026-04-10 ${d.toLocaleTimeString('en-US', { hour12: false })}.${d.getMilliseconds().toString().padStart(3, '0')} 台北時間`);
    }, 113);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const preloadScan = async () => {
      try {
        const scan = await fetchScan();
        setScanResults(scan.results);
      } catch {
        // Ignore preload failures; clicking scan will retry normally.
      }
    };
    preloadScan();
  }, []);

  const loadStock = useCallback(async (
    stockId: string,
    stockName: string,
    activeIndicators: IndicatorKey[] = [],
    signalDate?: string,
  ) => {
    const lp = await fetchLatestPrice(stockId);
    setChartInitialActiveIndicators(activeIndicators);
    setLatestPrice(lp);
    setStock({ stockId, stockName, startDate: '2000-01-01', endDate: formatDate(new Date()), signalDate });
    setChartSessionKey(c => c + 1);
  }, []);

  const handleSearch = useCallback(async (value: string) => {
    const v = value.trim() || cmdInput.trim();
    if (!v) { setError('請輸入股票代號'); return; }
    try {
      const { stockId, stockName } = await resolveStockId(v);
      await loadStock(stockId, stockName);
      setCmdInput('');
      setError('');
    } catch (err) {
      setLatestPrice(null);
      setError(err instanceof Error ? err.message : '查詢失敗，請稍後再試');
    }
  }, [cmdInput, loadStock]);

  const handleScan = useCallback(async () => {
    if (scanResults.length > 0) return;
    setIsScanning(true);
    setError('');
    try {
      const scan = await fetchScan();
      setScanResults(scan.results);
    } catch (err) {
      setScanResults([]);
      setError(err instanceof Error ? err.message : '掃描失敗，請稍後再試');
    } finally {
      setIsScanning(false);
    }
  }, [scanResults.length]);

  const handleSelectScanResult = useCallback(async (result: ScanResult) => {
    try {
      await loadStock(result.stock_id, result.stock_name, SCAN_INDICATORS, result.signal_date);
      setCmdInput(result.stock_id);
      setError('');
    } catch (err) {
      setLatestPrice(null);
      setError(err instanceof Error ? err.message : '查詢失敗，請稍後再試');
    }
  }, [loadStock]);

  const handleAddWatch = useCallback(async (which: 1 | 2) => {
    const input = which === 1 ? wlInput1.trim() : wlInput2.trim();
    const setInput = which === 1 ? setWlInput1 : setWlInput2;
    const setErr = which === 1 ? setWlError1 : setWlError2;
    const list = which === 1 ? watch1 : watch2;
    const setList = which === 1 ? setWatch1 : setWatch2;
    const key = which === 1 ? WL1_KEY : WL2_KEY;
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
    const list = which === 1 ? watch1 : watch2;
    const setList = which === 1 ? setWatch1 : setWatch2;
    const key = which === 1 ? WL1_KEY : WL2_KEY;
    const next = list.filter(w => w.stock_id !== stockId);
    setList(next);
    saveWatchlist(key, next);
  }, [watch1, watch2]);

  const tabClass = (tab: ActiveTab) =>
    `px-4 py-2 text-[15px] tracking-widest cursor-pointer border-b-2 transition-colors ${
      activeTab === tab
        ? `${C_SYS} border-[#00E5FF]`
        : 'text-[#555] border-transparent hover:text-[#888]'
    }`;

  const renderWatchlist = (which: 1 | 2) => {
    const list = which === 1 ? watch1 : watch2;
    const input = which === 1 ? wlInput1 : wlInput2;
    const setInput = which === 1 ? setWlInput1 : setWlInput2;
    const err = which === 1 ? wlError1 : wlError2;
    return (
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-auto">
          {list.length === 0 ? (
            <div className="px-4 py-8 text-[#555] text-[15px] text-center">清單為空，請新增標的</div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead className={`sticky top-0 bg-[#000000] border-b ${C_BORDER} z-10`}>
                <tr className="text-[16px] text-[#666] tracking-widest">
                  <th className="py-2 px-4 font-normal w-[35%]">代號</th>
                  <th className="py-2 px-4 font-normal">名稱</th>
                  <th className="py-2 px-4 font-normal w-[10%]" />
                </tr>
              </thead>
              <tbody className="divide-y divide-[#111111]">
                {list.map((w) => (
                  <tr
                    key={w.stock_id}
                    className="hover:bg-[#0A0A0A] cursor-crosshair group transition-colors"
                    onClick={() => handleSearch(w.stock_id.replace('.TW', ''))}
                  >
                    <td className={`py-3 px-4 text-[17px] ${C_SYS} group-hover:underline`}>{w.stock_id}</td>
                    <td className="py-3 px-4 text-[17px] text-[#DDD]">{w.stock_name}</td>
                    <td className="py-3 px-4 text-right">
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); handleRemoveWatch(which, w.stock_id); }}
                        className="text-[#555] hover:text-[#FF003C] text-[17px] leading-none px-1 cursor-pointer"
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div className={`border-t ${C_BORDER} px-4 py-2 flex items-center gap-2 shrink-0 bg-[#050505]`}>
          <input
            type="text"
            value={input}
            onChange={(e) => { setInput(e.target.value); (which === 1 ? setWlError1 : setWlError2)(''); }}
            onKeyDown={(e) => e.key === 'Enter' && handleAddWatch(which)}
            placeholder="輸入代號…"
            className="flex-1 bg-transparent border border-[#333] focus:border-[#00E5FF] outline-none rounded-sm px-2 py-1 text-[15px] text-[#00E5FF] placeholder-[#444]"
          />
          <button
            type="button"
            onClick={() => handleAddWatch(which)}
            className="text-[15px] text-[#00FF66] border border-[#00FF66]/40 px-2.5 py-1 rounded-sm hover:bg-[#00FF66]/10 cursor-pointer shrink-0 whitespace-nowrap"
          >
            新增
          </button>
          {err && <span className="text-[#FF003C] text-[13px] shrink-0">{err}</span>}
        </div>
      </div>
    );
  };

  return (
    <div className="h-screen w-full bg-[#000000] text-[#CCCCCC] font-mono flex flex-col selection:bg-[#00E5FF] selection:text-black overflow-hidden">

      {/* 頂部狀態列 */}
      <header className={`flex justify-between items-center px-4 h-[40px] shrink-0 border-b ${C_BORDER} bg-[#050505]`}>
        <div className="flex items-center space-x-4">
          <div className="w-[18px] h-[18px] bg-[#00E5FF] flex items-center justify-center text-black">
            <Terminal size={12} strokeWidth={3} />
          </div>
          <span className={`text-[17px] font-bold tracking-widest ${C_SYS}`}>量化終端_v2.6</span>
          <span className="text-[#555] text-[15px]">|</span>
          <span className="text-[16px] text-[#888] flex items-center">
            <Activity size={10} className="mr-1.5 text-[#00FF66] animate-pulse" />
            系統連線正常
          </span>
        </div>
        <div className="text-[16px] text-[#888] tracking-widest">{time}</div>
      </header>

      {/* 搜尋列 */}
      <div className={`flex items-center px-4 h-[48px] shrink-0 border-b ${C_BORDER} bg-[#050505]`}>
        <div className="bg-[#00E5FF]/10 border border-[#00E5FF]/30 px-2 py-0.5 rounded-sm mr-3 flex items-center shrink-0 whitespace-nowrap">
          <Search size={12} className={`mr-1.5 ${C_SYS}`} />
          <span className={`text-[16px] font-bold ${C_SYS} tracking-widest`}>搜尋</span>
        </div>
        <input
          type="text"
          value={cmdInput}
          onChange={(e) => setCmdInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch(cmdInput)}
          placeholder="搜尋股票代號..."
          className="bg-transparent border-none outline-none text-[19px] text-[#00E5FF] w-full min-w-0 flex-1 placeholder-[#444] tracking-widest"
          autoFocus
        />
        <button
          type="button"
          onClick={() => handleSearch(cmdInput)}
          className="text-[15px] text-[#666] bg-[#000000] px-2.5 py-1 border border-[#333] rounded-sm flex items-center shrink-0 whitespace-nowrap ml-3 hover:border-[#555] hover:text-[#999] cursor-pointer"
        >
          <span className="text-[#00E5FF] mr-1.5">↵</span> 確認
        </button>
        <button
          type="button"
          onClick={handleScan}
          disabled={isScanning}
          className="text-[15px] text-[#00FF66] bg-[#000000] px-2.5 py-1 border border-[#00FF66]/40 rounded-sm flex items-center shrink-0 whitespace-nowrap ml-2 hover:bg-[#00FF66]/10 disabled:opacity-50 disabled:cursor-wait cursor-pointer"
        >
          {isScanning ? '掃描中...' : '掃描'}
        </button>
      </div>

      {/* 錯誤訊息 */}
      {error && (
        <div className={`px-4 py-1.5 text-[16px] text-[#FF003C] border-b ${C_BORDER} bg-[#050505]`}>{error}</div>
      )}

      {/* 主體 */}
      <main className="flex-1 flex overflow-hidden">

        {/* 左側：大盤指數 + 事件日誌 */}
        <div className={`w-[45%] flex flex-col border-r ${C_BORDER}`}>
          <div className={`grid grid-cols-2 grid-rows-2 border-b ${C_BORDER} shrink-0`}>
            {MACRO_INDICES.map((idx, i) => {
              const isUp = idx.change.startsWith('+');
              return (
                <div key={idx.id} className={`p-4 flex flex-col ${i % 2 === 0 ? `border-r ${C_BORDER}` : ''} ${i < 2 ? `border-b ${C_BORDER}` : ''} hover:bg-[#0A0A0A] cursor-crosshair`}>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-[15px] text-[#666] tracking-widest">{idx.name}</span>
                    <span className="text-[15px] text-[#444]">量:{idx.vol}</span>
                  </div>
                  <div className="text-[32px] text-white font-light tracking-tight mb-2">{idx.price}</div>
                  <div className={`flex items-center justify-between text-[17px] font-bold ${isUp ? C_UP : C_DOWN}`}>
                    <span>{idx.change}</span>
                    <span>{idx.percent}</span>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex-1 flex flex-col overflow-hidden bg-[#020202]">
            <div className={`px-4 py-2 border-b ${C_BORDER} flex justify-between items-center shrink-0 bg-[#080808]`}>
              <span className="text-[15px] text-[#666] tracking-widest flex items-center">
                <Database size={12} className="mr-2" /> 即時事件日誌
              </span>
              <span className={`text-[15px] ${C_SYS} animate-pulse`}>[接收中]</span>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {SYSTEM_LOGS.map((log, i) => (
                <div key={i} className="flex space-x-3 text-[16px] leading-tight hover:bg-[#111] p-1 -mx-1">
                  <span className="text-[#555] shrink-0">[{log.time}]</span>
                  <span className={`shrink-0 w-8 ${log.level === '警報' ? 'text-[#FF003C]' : log.level === '執行' ? 'text-[#00FF66]' : log.level === '總經' ? 'text-[#FFCC00]' : 'text-[#00E5FF]'}`}>
                    {log.level}
                  </span>
                  <span className="text-[#AAA] break-words">{log.msg}</span>
                </div>
              ))}
              <div className="flex space-x-3 text-[16px] leading-tight mt-2">
                <span className="text-[#555] shrink-0">[{time.split(' ')[1] ?? '00:00:00.000'}]</span>
                <span className="w-2 h-3 bg-[#00E5FF] animate-pulse" />
              </div>
            </div>
          </div>
        </div>

        {/* 右側：K 線圖 or 三 Tab 面板 */}
        <div className="w-[55%] flex flex-col bg-black">
          {stock ? (
            <>
              <StockInfoBar
                stockId={stock.stockId}
                stockName={stock.stockName}
                startDate={stock.startDate}
                endDate={stock.endDate}
                latestPrice={latestPrice}
              />
              <div className="flex-1 overflow-hidden">
                <KLinePanel
                  key={`${stock.stockId}-${chartSessionKey}`}
                  stockId={stock.stockId}
                  startDate={stock.startDate}
                  endDate={stock.endDate}
                  signalDate={stock.signalDate}
                />
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Tab bar */}
              <div className={`flex items-end border-b ${C_BORDER} bg-[#080808] shrink-0 px-2`}>
                <button type="button" className={tabClass('scan')} onClick={() => setActiveTab('scan')}>掃描</button>
                <button type="button" className={tabClass('watch1')} onClick={() => setActiveTab('watch1')}>自選清單</button>
                <button type="button" className={tabClass('watch2')} onClick={() => setActiveTab('watch2')}>自選清單二</button>
                {activeTab === 'scan' && (
                  <span className="ml-auto text-[13px] text-[#555] tracking-wider pb-2 pr-2">RSI &lt; 30 ｜ 跌幅 ≥ 20%</span>
                )}
              </div>

              {/* 掃描 tab */}
              {activeTab === 'scan' && (
                <div className="flex-1 flex flex-col overflow-hidden">
                  {isScanning ? (
                    <div className="flex-1 flex items-center justify-center text-[#555] text-[15px]">掃描中…</div>
                  ) : scanResults.length === 0 ? (
                    <div className="flex-1 flex items-center justify-center text-[#555] text-[15px]">今日無訊號</div>
                  ) : (
                    <div className="flex-1 overflow-auto">
                      <table className="w-full text-left border-collapse">
                        <thead className={`sticky top-0 bg-[#000000] border-b ${C_BORDER} z-10`}>
                          <tr className="text-[16px] text-[#666] tracking-widest">
                            <th className="py-2 px-4 font-normal w-[20%]">代號</th>
                            <th className="py-2 px-4 font-normal w-[20%]">名稱</th>
                            <th className="py-2 px-4 font-normal w-[20%]">訊號日期</th>
                            <th className="py-2 px-4 font-normal text-right w-[15%]">天前</th>
                            <th className="py-2 px-4 font-normal text-center w-[25%]">訊號</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#111111]">
                          {scanResults.map((s) => (
                            <tr
                              key={`${s.stock_id}-${s.signal_date}`}
                              className="hover:bg-[#0A0A0A] cursor-crosshair group transition-colors"
                              onClick={() => handleSelectScanResult(s)}
                            >
                              <td className={`py-3 px-4 text-[17px] ${C_SYS} group-hover:underline`}>{s.stock_id}</td>
                              <td className="py-3 px-4 text-[17px] text-[#DDD]">{s.stock_name}</td>
                              <td className="py-3 px-4 text-[16px] text-[#888]">{s.signal_date}</td>
                              <td className="py-3 px-4 text-[16px] text-right text-[#666]">{s.days_ago}</td>
                              <td className="py-3 px-4 text-center">
                                <span className="inline-block px-2 py-0.5 text-[15px] border border-[#00FF66] text-[#00FF66]">
                                  強力買進
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  <div className={`px-4 py-2 border-t ${C_BORDER} flex justify-between items-center shrink-0 bg-[#050505]`}>
                    <span className="text-[15px] text-[#444]">共 {scanResults.length} 筆訊號</span>
                  </div>
                </div>
              )}

              {/* 自選清單 tabs */}
              {activeTab === 'watch1' && renderWatchlist(1)}
              {activeTab === 'watch2' && renderWatchlist(2)}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
