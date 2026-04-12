"use client";

import React, { useState, useEffect, useCallback } from 'react';
import {
  setChartInitialActiveIndicators,
  type IndicatorKey,
} from "@/components/chart/CandlestickChart";
import { KLinePanel } from "@/components/chart/KLinePanel";
import { StockInfoBar } from "@/components/layout/StockInfoBar";
import { ScanPanel } from "@/components/ui/ScanPanel";
import { fetchLatestPrice, fetchScan, resolveStockId, type ScanResult } from "@/lib/api";
import type { LatestPrice, StockState } from "@/lib/types";

const MACRO_INDICES = [
  { id: 'IDX.TAIEX', name: '加權指數', price: '35417.83', change: '+556.67', percent: '+1.60%', vol: '8295億' },
  { id: 'IDX.TPEX', name: '櫃買指數', price: '425.30', change: '+4.15', percent: '+0.98%', vol: '1250億' },
  { id: 'FUT.TX00', name: '台指期近', price: '35420.00', change: '+643.00', percent: '+1.85%', vol: '12萬口' },
  { id: 'CUR.USDTWD', name: '美元/台幣', price: '31.850', change: '-0.150', percent: '-0.47%', vol: '12億' },
];

const QUANT_WATCHLIST = [
  { sym: '2330.TW', name: '台積電', px: '2000.00', chg: '+45.00', pct: '+2.30%', signal: '強力買進' },
  { sym: '2489.TW', name: '瑞軒', px: '42.75', chg: '+3.85', pct: '+9.89%', signal: '亮燈漲停' },
  { sym: '3231.TW', name: '緯創', px: '125.00', chg: '+11.00', pct: '+9.65%', signal: '動能強勢' },
  { sym: '2317.TW', name: '鴻海', px: '245.50', chg: '-1.50', pct: '-0.61%', signal: '區間盤整' },
  { sym: '2603.TW', name: '長榮', px: '185.00', chg: '+8.50', pct: '+4.82%', signal: '持續建倉' },
  { sym: '1519.TW', name: '華城', px: '850.00', chg: '-35.00', pct: '-3.95%', signal: '超買過熱' },
  { sym: '2454.TW', name: '聯發科', px: '1520.00', chg: '+35.00', pct: '+2.36%', signal: '建議買進' },
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

function Crosshair(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="7" />
      <path d="M12 3v4" />
      <path d="M12 17v4" />
      <path d="M3 12h4" />
      <path d="M17 12h4" />
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

const SCAN_INDICATORS: IndicatorKey[] = ["BOLL", "MACD", "RSI"];

export default function Home() {
  const [cmdInput, setCmdInput] = useState('');
  const [time, setTime] = useState('');
  const [stock, setStock] = useState<StockState | null>(null);
  const [latestPrice, setLatestPrice] = useState<LatestPrice | null>(null);
  const [error, setError] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [isScanPanelOpen, setIsScanPanelOpen] = useState(false);
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [chartSessionKey, setChartSessionKey] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      const d = new Date();
      setTime(`2026-04-10 ${d.toLocaleTimeString('en-US', { hour12: false })}.${d.getMilliseconds().toString().padStart(3, '0')} 台北時間`);
    }, 113);
    return () => clearInterval(timer);
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
    setIsScanning(true);
    setIsScanPanelOpen(true);
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
  }, []);

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

  return (
    <div className="h-screen w-full bg-[#000000] text-[#CCCCCC] font-mono flex flex-col selection:bg-[#00E5FF] selection:text-black overflow-hidden">

      {/* 頂部狀態列 */}
      <header className={`flex justify-between items-center px-4 h-[40px] shrink-0 border-b ${C_BORDER} bg-[#050505]`}>
        <div className="flex items-center space-x-4">
          <div className="w-[18px] h-[18px] bg-[#00E5FF] flex items-center justify-center text-black">
            <Terminal size={12} strokeWidth={3} />
          </div>
          <span className={`text-[15px] font-bold tracking-widest ${C_SYS}`}>量化終端_v2.6</span>
          <span className="text-[#555] text-[13px]">|</span>
          <span className="text-[14px] text-[#888] flex items-center">
            <Activity size={10} className="mr-1.5 text-[#00FF66] animate-pulse" />
            系統連線正常
          </span>
        </div>
        <div className="text-[14px] text-[#888] tracking-widest">{time}</div>
      </header>

      {/* 搜尋列 */}
      <div className={`flex items-center px-4 h-[48px] shrink-0 border-b ${C_BORDER} bg-[#050505]`}>
        <div className="bg-[#00E5FF]/10 border border-[#00E5FF]/30 px-2 py-0.5 rounded-sm mr-3 flex items-center shrink-0 whitespace-nowrap">
          <Search size={12} className={`mr-1.5 ${C_SYS}`} />
          <span className={`text-[14px] font-bold ${C_SYS} tracking-widest`}>搜尋</span>
        </div>
        <input
          type="text"
          value={cmdInput}
          onChange={(e) => setCmdInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch(cmdInput)}
          placeholder="搜尋股票代號..."
          className="bg-transparent border-none outline-none text-[17px] text-[#00E5FF] w-full min-w-0 flex-1 placeholder-[#444] tracking-widest"
          autoFocus
        />
        <button
          type="button"
          onClick={() => handleSearch(cmdInput)}
          className="text-[13px] text-[#666] bg-[#000000] px-2.5 py-1 border border-[#333] rounded-sm flex items-center shrink-0 whitespace-nowrap ml-3 hover:border-[#555] hover:text-[#999] cursor-pointer"
        >
          <span className="text-[#00E5FF] mr-1.5">↵</span> 確認
        </button>
        <button
          type="button"
          onClick={handleScan}
          disabled={isScanning}
          className="text-[13px] text-[#00FF66] bg-[#000000] px-2.5 py-1 border border-[#00FF66]/40 rounded-sm flex items-center shrink-0 whitespace-nowrap ml-2 hover:bg-[#00FF66]/10 disabled:opacity-50 disabled:cursor-wait cursor-pointer"
        >
          {isScanning ? '掃描中...' : '掃描'}
        </button>
      </div>

      {/* 掃描結果列 */}
      {isScanPanelOpen && (
        <ScanPanel
          isLoading={isScanning}
          results={scanResults}
          onSelect={handleSelectScanResult}
        />
      )}

      {/* 錯誤訊息 */}
      {error && (
        <div className={`px-4 py-1.5 text-[14px] text-[#FF003C] border-b ${C_BORDER} bg-[#050505]`}>{error}</div>
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
                    <span className="text-[13px] text-[#666] tracking-widest">{idx.name}</span>
                    <span className="text-[13px] text-[#444]">量:{idx.vol}</span>
                  </div>
                  <div className="text-[28px] text-white font-light tracking-tight mb-2">{idx.price}</div>
                  <div className={`flex items-center justify-between text-[15px] font-bold ${isUp ? C_UP : C_DOWN}`}>
                    <span>{idx.change}</span>
                    <span>{idx.percent}</span>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex-1 flex flex-col overflow-hidden bg-[#020202]">
            <div className={`px-4 py-2 border-b ${C_BORDER} flex justify-between items-center shrink-0 bg-[#080808]`}>
              <span className="text-[13px] text-[#666] tracking-widest flex items-center">
                <Database size={12} className="mr-2" /> 即時事件日誌
              </span>
              <span className={`text-[13px] ${C_SYS} animate-pulse`}>[接收中]</span>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {SYSTEM_LOGS.map((log, i) => (
                <div key={i} className="flex space-x-3 text-[14px] leading-tight hover:bg-[#111] p-1 -mx-1">
                  <span className="text-[#555] shrink-0">[{log.time}]</span>
                  <span className={`shrink-0 w-8 ${log.level === '警報' ? 'text-[#FF003C]' : log.level === '執行' ? 'text-[#00FF66]' : log.level === '總經' ? 'text-[#FFCC00]' : 'text-[#00E5FF]'}`}>
                    {log.level}
                  </span>
                  <span className="text-[#AAA] break-words">{log.msg}</span>
                </div>
              ))}
              <div className="flex space-x-3 text-[14px] leading-tight mt-2">
                <span className="text-[#555] shrink-0">[{time.split(' ')[1] ?? '00:00:00.000'}]</span>
                <span className="w-2 h-3 bg-[#00E5FF] animate-pulse" />
              </div>
            </div>
          </div>
        </div>

        {/* 右側：K 線圖 or 監控列表 */}
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
            <>
              <div className={`px-4 py-2 border-b ${C_BORDER} flex justify-between items-center shrink-0 bg-[#080808]`}>
                <span className="text-[13px] text-[#666] tracking-widest flex items-center">
                  <Crosshair size={12} className="mr-2" /> 活躍標的監控
                </span>
                <span className="text-[13px] text-[#444]">列數: 07</span>
              </div>
              <div className="flex-1 overflow-auto">
                <table className="w-full text-left border-collapse">
                  <thead className={`sticky top-0 bg-[#000000] border-b ${C_BORDER} z-10`}>
                    <tr className="text-[14px] text-[#666] tracking-widest">
                      <th className="py-2 px-4 font-normal w-[15%]">代號</th>
                      <th className="py-2 px-4 font-normal w-[20%]">名稱</th>
                      <th className="py-2 px-4 font-normal text-right w-[15%]">最新價</th>
                      <th className="py-2 px-4 font-normal text-right w-[15%]">漲跌點</th>
                      <th className="py-2 px-4 font-normal text-right w-[15%]">漲跌幅</th>
                      <th className="py-2 px-4 font-normal text-center w-[20%]">AI 訊號</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#111111]">
                    {QUANT_WATCHLIST.map((s, i) => {
                      const isUp = s.chg.startsWith('+');
                      return (
                        <tr
                          key={i}
                          className="hover:bg-[#0A0A0A] cursor-crosshair group transition-colors"
                          onClick={() => handleSearch(s.sym.replace('.TW', ''))}
                        >
                          <td className={`py-3 px-4 text-[15px] ${C_SYS} group-hover:underline`}>{s.sym}</td>
                          <td className="py-3 px-4 text-[15px] text-[#DDD]">{s.name}</td>
                          <td className={`py-3 px-4 text-[16px] font-bold text-right ${isUp ? C_UP : C_DOWN}`}>{s.px}</td>
                          <td className={`py-3 px-4 text-[15px] text-right ${isUp ? C_UP : C_DOWN}`}>{s.chg}</td>
                          <td className={`py-3 px-4 text-[15px] text-right ${isUp ? C_UP : C_DOWN}`}>{s.pct}</td>
                          <td className="py-3 px-4 text-center">
                            <span className={`inline-block px-2 py-0.5 text-[13px] border ${
                              s.signal === '強力買進' || s.signal === '亮燈漲停' ? 'border-[#00FF66] text-[#00FF66]' :
                              s.signal === '超買過熱' ? 'border-[#FF003C] text-[#FF003C]' :
                              s.signal === '動能強勢' ? 'border-[#FFCC00] text-[#FFCC00]' :
                              'border-[#555] text-[#888]'
                            }`}>
                              {s.signal}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className={`px-4 py-2 border-t ${C_BORDER} flex justify-between items-center shrink-0 bg-[#050505]`}>
                <span className="text-[13px] text-[#444]">市場寬度: <span className={C_UP}>上漲:68%</span> / <span className={C_DOWN}>下跌:32%</span></span>
                <span className="text-[13px] text-[#444]">系統延遲: 12ms</span>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
