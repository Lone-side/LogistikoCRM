/**
 * AccountantDashboard — Mission Control variant
 *
 * Visual identity:
 *   - Deep navy + cyan/amber/green/red mission-control palette
 *   - Monospace numerals, tabular-nums everywhere
 *   - Multi-panel layout: KPI strip, heatmap, treemap, cashflow,
 *     gantt, donut, dense table, live event stream, sparkline grid
 *   - Subtle scanlines + pulse indicators for "live" feel
 *
 * Self-contained: scoped `acd-*` classes via inline <style>, no external deps.
 * Drop into a route. Static data — replace with hooks when wiring real data.
 */

import { useEffect, useMemo, useState } from 'react';

// ─── Sub-components ─────────────────────────────────────────────────────────

function Sparkline({
  points,
  color = 'currentColor',
  fill = true,
  width = 100,
  height = 30,
}: {
  points: number[];
  color?: string;
  fill?: boolean;
  width?: number;
  height?: number;
}) {
  const line = useMemo(() => {
    if (!points.length) return '';
    const step = width / (points.length - 1);
    return points.map((y, i) => `${i * step},${y}`).join(' ');
  }, [points, width]);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"
         style={{ color, display: 'block' }} aria-hidden="true">
      {fill && (
        <polyline points={`${line} ${width},${height} 0,${height}`}
                  fill="currentColor" opacity={0.1} stroke="none" />
      )}
      <polyline points={line} fill="none" stroke="currentColor" strokeWidth={1.4} />
    </svg>
  );
}

function ComplianceRing({ pct }: { pct: number }) {
  return (
    <div className="acd-ring" aria-label={`${pct}% compliance`}>
      <svg viewBox="0 0 36 36" style={{ transform: 'rotate(-90deg)' }}>
        <circle cx="18" cy="18" r="15.5" fill="none" stroke="var(--line)" strokeWidth={3} />
        <circle cx="18" cy="18" r="15.5" fill="none" stroke="var(--green)" strokeWidth={3}
                strokeDasharray={`${pct * 0.973} 100`} strokeLinecap="round" />
      </svg>
      <span className="acd-pct">{pct}%</span>
    </div>
  );
}

function Heatmap() {
  const clients = [
    'ΠΕΤΡΑΚΗ ΑΕ','MARINE LTD','ΓΕΩΡΓΑΝΤΑΣ','VENTUS TECH','ΔΕΛΦΙΝΙΑ',
    'ΟΛΥΜΠΟΣ','ΚΑΛΑΪΤΖΑΚΗΣ','SOLARIS','ΑΓΓΕΛΟΥ','FERRO',
    'NOVA AE','BLUE LINE','ΘΕΟΔΩΡΟΥ','HELIOS LTD',
  ];
  const colors = ['transparent', '#0EA5C0', '#22D3EE', '#FBBF24', '#F87171'];
  const data = useMemo(
    () => clients.map((_, ri) =>
      Array.from({ length: 12 }, (_, ci) => {
        const x = (ri * 7 + ci * 3) % 11;
        return x < 5 ? 0 : x < 8 ? 1 : x < 9 ? 2 : x < 10 ? 3 : 4;
      })
    ),
    []
  );
  return (
    <>
      <div className="acd-heatmap">
        <div className="acd-hm-labels">
          {clients.map(n => <div key={n}>{n}</div>)}
        </div>
        <div className="acd-hm-grid">
          {data.map((row, ri) =>
            row.map((v, ci) => (
              <div key={`${ri}-${ci}`} className="acd-cell"
                   style={{ ['--cell' as never]: colors[v] }}
                   title={`${clients[ri]} · W${22 + ci} · ${v} υποχρ.`} />
            ))
          )}
        </div>
      </div>
      <div className="acd-hm-axis">
        <div className="acd-pad">W →</div>
        <div className="acd-weeks">
          {Array.from({ length: 12 }, (_, i) => <span key={i}>W{22 + i}</span>)}
        </div>
      </div>
    </>
  );
}

function Treemap() {
  const tiles = [
    { l: 0,  t: 0,  w: 48, h: 42, bg: '#22D3EE', n: 'ΑΦΟΙ ΠΕΤΡΑΚΗ ΑΕ',  v: '€84.500' },
    { l: 48, t: 0,  w: 30, h: 42, bg: '#34D399', n: 'MARINE LOGISTICS', v: '€52.300' },
    { l: 78, t: 0,  w: 22, h: 25, bg: '#A78BFA', n: 'ΓΕΩΡΓΑΝΤΑΣ',       v: '€31.200' },
    { l: 78, t: 25, w: 22, h: 17, bg: '#FBBF24', n: 'ΔΕΛΦΙΝΙΑ',          v: '€18.400' },
    { l: 0,  t: 42, w: 34, h: 32, bg: '#F472B6', n: 'VENTUS TECH',       v: '€38.700' },
    { l: 34, t: 42, w: 26, h: 32, bg: '#22D3EE', op: 0.75, n: 'ΟΛΥΜΠΟΣ ΑΕΒΕ', v: '€24.100' },
    { l: 60, t: 42, w: 23, h: 18, bg: '#34D399', op: 0.7,  n: 'ΚΑΛΑΪΤΖΑΚΗΣ',  v: '€14.800' },
    { l: 60, t: 60, w: 23, h: 14, bg: '#A78BFA', op: 0.7,  n: 'SOLARIS',      v: '€9.450' },
    { l: 83, t: 42, w: 17, h: 18, bg: '#FBBF24', op: 0.65, n: 'ΑΓΓΕΛΟΥ',      v: '€7.200' },
    { l: 83, t: 60, w: 17, h: 14, bg: '#F472B6', op: 0.65, n: 'FERRO',        v: '€5.900' },
    { l: 0,  t: 74, w: 60, h: 26, bg: '#1E2A41', n: '+ 174 ΛΟΙΠΟΙ', v: '€55.630 / 16.3%', mute: true },
    { l: 60, t: 74, w: 40, h: 26, bg: '#0F1626', n: 'UNALLOCATED',   v: '—', mute: true },
  ];
  return (
    <div className="acd-treemap" aria-label="Treemap πελατών κατά όγκο ΦΠΑ">
      {tiles.map((t, i) => (
        <div key={i} className={`acd-tile${t.mute ? ' acd-tile-mute' : ''}`}
             style={{
               left: `${t.l}%`, top: `${t.t}%`, width: `${t.w}%`, height: `${t.h}%`,
               background: t.bg, opacity: t.op,
             }}>
          <span className="acd-t-name">{t.n}</span>
          <span className="acd-t-val">{t.v}</span>
        </div>
      ))}
    </div>
  );
}

function CashflowChart() {
  // monthly out / in bars for 12 months; baseline at y=90
  const out = [20, 30, 35, 50, 40, 55, 45, 60, 48, 52, 42, 70];
  const inn = [14, 22, 26, 32, 28, 34, 30, 38, 32, 36, 28, 44];
  const balY = [84, 78, 76, 72, 76, 68, 74, 64, 72, 68, 74, 58];

  return (
    <svg viewBox="0 0 360 180" preserveAspectRatio="none"
         style={{ width: '100%', height: 180, display: 'block' }} aria-hidden="true">
      <g stroke="var(--line-soft)" strokeWidth={0.5}>
        {[40, 80, 120, 160].map(y => <line key={y} x1={0} y1={y} x2={360} y2={y} />)}
      </g>
      <g>
        {out.map((h, i) => (
          <rect key={`o${i}`} x={6 + i * 30} y={90 - h} width={20} height={h}
                fill="var(--green)" opacity={i === 11 ? 1 : 0.85} />
        ))}
        {inn.map((h, i) => (
          <rect key={`i${i}`} x={6 + i * 30} y={90} width={20} height={h}
                fill="var(--red)" opacity={i === 11 ? 1 : 0.85} />
        ))}
      </g>
      <line x1={0} y1={90} x2={360} y2={90} stroke="var(--ink-mute)" strokeWidth={0.8} />
      <polyline fill="none" stroke="var(--cyan)" strokeWidth={1.8} strokeLinejoin="round"
        points={balY.map((y, i) => `${16 + i * 30},${y}`).join(' ')} />
      <circle cx={346} cy={58} r={2.5} fill="var(--cyan)" />
      <g fontFamily="var(--font-mono)" fontSize={7} fill="var(--ink-mute)">
        <text x={6} y={176}>06</text><text x={66} y={176}>08</text>
        <text x={126} y={176}>10</text><text x={186} y={176}>12</text>
        <text x={246} y={176}>02</text><text x={306} y={176}>04</text>
        <text x={336} y={176} fill="var(--cyan)">05*</text>
      </g>
    </svg>
  );
}

function GanttChart() {
  const rows = [
    { name: 'ΠΕΤΡΑΚΗ ΑΕ', bars: [{ l: 0,  w: 6,  cls: 'urgent', t: 'ΦΠΑ' }] },
    { name: 'ΓΕΩΡΓΑΝΤΑΣ', bars: [{ l: 3,  w: 8,  cls: 'urgent', t: 'ΠΑΡΑΚΡ' }] },
    { name: 'ΔΕΛΦΙΝΙΑ',   bars: [{ l: 8,  w: 14, cls: 'warn',   t: 'ΕΦΚΑ' }] },
    { name: 'ΚΑΛΑΪΤΖΑΚΗΣ',bars: [{ l: 12, w: 18, cls: 'draft',  t: 'ΦΠΑ M5' }] },
    { name: 'MARINE LTD', bars: [{ l: 18, w: 10, cls: 'ok',     t: 'INTRA' }] },
    { name: 'VENTUS',     bars: [
      { l: 32, w: 14, cls: 'info', t: 'Ε3' },
      { l: 52, w: 10, cls: 'warn', t: 'ΦΠΑ' },
    ] },
    { name: 'ΟΛΥΜΠΟΣ',    bars: [{ l: 45, w: 20, cls: 'info', t: 'ΕΝΦΙΑ' }] },
    { name: 'SOLARIS',    bars: [{ l: 60, w: 16, cls: 'info', t: 'Ε1' }] },
  ];
  return (
    <div className="acd-gantt">
      <div className="acd-g-rows">
        {rows.map(r => <div key={r.name} className="acd-g-label">{r.name}</div>)}
      </div>
      <div className="acd-g-track">
        {rows.map((r, ri) => (
          <div key={r.name} className="acd-g-row">
            {ri === 0 && <div className="acd-g-today" style={{ left: '0%' }} />}
            {r.bars.map((b, bi) => (
              <div key={bi} className={`acd-g-bar acd-${b.cls}`}
                   style={{ left: `${b.l}%`, width: `${b.w}%` }}>
                {b.t}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function StatusDonut() {
  // 47 total: 12 today(red) / 18 soon(amber) / 12 ready(green) / 5 draft(cyan)
  const segs = [
    { v: 25.5, color: 'var(--red)',   off: 0 },
    { v: 38.3, color: 'var(--amber)', off: -25.5 },
    { v: 25.5, color: 'var(--green)', off: -63.8 },
    { v: 10.7, color: 'var(--cyan)',  off: -89.3 },
  ];
  return (
    <div className="acd-donut-wrap">
      <svg className="acd-donut" viewBox="0 0 36 36" aria-hidden="true">
        <circle cx="18" cy="18" r="15.91549" fill="none" stroke="var(--panel-2)" strokeWidth={4.5} />
        {segs.map((s, i) => (
          <circle key={i} cx="18" cy="18" r="15.91549" fill="none"
                  stroke={s.color} strokeWidth={4.5}
                  strokeDasharray={`${s.v} 100`} strokeDashoffset={s.off}
                  transform="rotate(-90 18 18)" />
        ))}
        <text x="18" y="19" textAnchor="middle" fontFamily="var(--font-mono)"
              fontSize={6.5} fontWeight={700} fill="var(--ink)">47</text>
        <text x="18" y="24" textAnchor="middle" fontFamily="var(--font-mono)"
              fontSize={2.5} fill="var(--ink-mute)" letterSpacing="0.25">TOTAL</text>
      </svg>
      <div className="acd-donut-legend">
        <div className="acd-li"><span className="acd-sw" style={{ background: 'var(--red)' }} />
          <span>TODAY <small>≤ 1d</small></span><b>12</b></div>
        <div className="acd-li"><span className="acd-sw" style={{ background: 'var(--amber)' }} />
          <span>SOON <small>2–5d</small></span><b>18</b></div>
        <div className="acd-li"><span className="acd-sw" style={{ background: 'var(--green)' }} />
          <span>READY <small>filed/done</small></span><b>12</b></div>
        <div className="acd-li"><span className="acd-sw" style={{ background: 'var(--cyan)' }} />
          <span>DRAFT <small>in prep</small></span><b>5</b></div>
      </div>
    </div>
  );
}

interface ClientRow {
  rank: string; name: string; afm: string;
  out: string; in: string; bal: string; balPct: number; balPos: boolean;
  trend: number[]; trendColor: string;
  status: 'URG' | 'WARN' | 'OK' | 'DRAFT';
}

const CLIENTS: ClientRow[] = [
  { rank: '01', name: 'ΑΦΟΙ ΠΕΤΡΑΚΗ ΑΕ',     afm: '099876543', out: '84.500', in: '52.100', bal: '+32.400', balPct: 92, balPos: true,
    trend: [12,10,11,7,8,5,3], trendColor: 'var(--green)', status: 'URG' },
  { rank: '02', name: 'MARINE LOGISTICS LTD',afm: '800998877', out: '52.300', in: '38.700', bal: '+13.600', balPct: 60, balPos: true,
    trend: [8,9,7,10,8,6,7],   trendColor: 'var(--green)', status: 'OK' },
  { rank: '03', name: 'ΓΕΩΡΓΑΝΤΑΣ ΙΚΕ',      afm: '800123456', out: '31.200', in: '22.800', bal: '+8.400',  balPct: 48, balPos: true,
    trend: [10,9,11,8,10,7,8], trendColor: 'var(--cyan)',  status: 'URG' },
  { rank: '04', name: 'VENTUS TECH ΜΟΝ. ΙΚΕ',afm: '801234567', out: '38.700', in: '31.200', bal: '+7.500',  balPct: 42, balPos: true,
    trend: [14,12,11,9,7,6,4], trendColor: 'var(--green)', status: 'WARN' },
  { rank: '05', name: 'ΔΕΛΦΙΝΙΑ ΕΠΕ',         afm: '094567890', out: '18.400', in: '21.500', bal: '−3.100',  balPct: 20, balPos: false,
    trend: [4,6,5,8,9,11,12],  trendColor: 'var(--red)',   status: 'WARN' },
  { rank: '06', name: 'ΟΛΥΜΠΟΣ ΑΕΒΕ',         afm: '094445566', out: '24.100', in: '19.800', bal: '+4.300',  balPct: 28, balPos: true,
    trend: [8,7,9,8,10,9,8],   trendColor: 'var(--cyan)',  status: 'OK' },
  { rank: '07', name: 'ΚΑΛΑΪΤΖΑΚΗΣ Γ.',      afm: '045678123', out: '14.800', in: '11.200', bal: '+3.600',  balPct: 24, balPos: true,
    trend: [12,11,9,10,7,8,6], trendColor: 'var(--green)', status: 'DRAFT' },
  { rank: '08', name: 'SOLARIS A.E.',          afm: '800556677', out: '9.450',  in: '7.800',  bal: '+1.650',  balPct: 18, balPos: true,
    trend: [9,10,8,9,8,7,8],   trendColor: 'var(--cyan)',  status: 'OK' },
  { rank: '09', name: 'ΑΓΓΕΛΟΥ ΔΟΜΗ',         afm: '800888999', out: '7.200',  in: '8.100',  bal: '−900',    balPct: 8,  balPos: false,
    trend: [5,7,6,9,8,11,12],  trendColor: 'var(--red)',   status: 'URG' },
  { rank: '10', name: 'FERRO ΕΠΕ',             afm: '094332211', out: '5.900',  in: '4.700',  bal: '+1.200',  balPct: 14, balPos: true,
    trend: [11,10,8,9,7,6,5],  trendColor: 'var(--green)', status: 'OK' },
];

const STATUS_COLOR: Record<ClientRow['status'], string> = {
  URG:   'var(--red)',
  WARN:  'var(--amber)',
  OK:    'var(--green)',
  DRAFT: 'var(--cyan)',
};

function TopClientsTable() {
  return (
    <table className="acd-tdense">
      <thead>
        <tr>
          <th>#</th>
          <th>Πελάτης</th>
          <th className="acd-right">Εκροές</th>
          <th className="acd-right">Εισροές</th>
          <th className="acd-right">Υπόλοιπο</th>
          <th>Trend</th>
          <th className="acd-right">Status</th>
        </tr>
      </thead>
      <tbody>
        {CLIENTS.map(c => (
          <tr key={c.afm}>
            <td className="acd-mute">{c.rank}</td>
            <td>{c.name}<div className="acd-afm">{c.afm}</div></td>
            <td className="acd-right acd-pos">{c.out}</td>
            <td className="acd-right acd-neg">{c.in}</td>
            <td className="acd-right acd-bar-cell" style={!c.balPos ? { color: 'var(--red)' } : undefined}>
              {c.bal}
              <div className="acd-bar">
                <i style={{ width: `${c.balPct}%`, background: c.balPos ? 'var(--green)' : 'var(--red)' }} />
              </div>
            </td>
            <td style={{ width: 70 }}>
              <Sparkline points={c.trend} color={c.trendColor} fill={false} width={60} height={16} />
            </td>
            <td className="acd-right" style={{ color: STATUS_COLOR[c.status] }}>●{c.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ─── Live event stream ──────────────────────────────────────────────────────

interface StreamEvent { time: string; glyph: string; tone: ''|'g'|'a'|'r'; body: React.ReactNode }

const INITIAL_STREAM: StreamEvent[] = [
  { time: '14:42:11', glyph: '✓', tone: 'g', body: <><b>SUBMIT</b> · ΦΠΑ Q1 / ΠΕΤΡΑΚΗ ΑΕ · ack <b>MARK 4029101</b></> },
  { time: '14:38:02', glyph: '↻', tone: '',  body: <><b>SYNC</b> · myDATA / 23 clients · 412 records · 2.3s</> },
  { time: '14:31:45', glyph: '+', tone: 'g', body: <><b>CREATE</b> · client / VENTUS TECH ΙΚΕ · ΑΦΜ 801234567</> },
  { time: '14:22:18', glyph: '!', tone: 'a', body: <><b>WARN</b> · myDATA stale / ΑΓΓΕΛΟΥ &gt; 24h</> },
  { time: '14:15:09', glyph: '📎', tone: '', body: <><b>DOC</b> · συμβόλαιο εργασίας / ΔΕΛΦΙΝΙΑ ΕΠΕ · 412KB</> },
  { time: '14:08:34', glyph: '✓', tone: 'g', body: <><b>BATCH</b> · 8× obligation completed / Α.Κωνσταντινίδης</> },
  { time: '13:58:21', glyph: '✕', tone: 'r', body: <><b>FAIL</b> · AADE auth 401 / SOLARIS · retry in 30s</> },
  { time: '13:51:07', glyph: '→', tone: '',  body: <><b>EMAIL</b> · reminder ΦΠΑ Μαΐου · 47 recipients</> },
  { time: '13:42:55', glyph: '✓', tone: 'g', body: <><b>SUBMIT</b> · Παρακρ. φόροι / MARINE LTD · MARK 4029044</> },
  { time: '13:30:00', glyph: '⏱', tone: '',  body: <><b>CRON</b> · daily backup · 1.8GB compressed · ok</> },
];

const ROTATING_EVENTS: Omit<StreamEvent, 'time'>[] = [
  { glyph: '✕', tone: 'r', body: <><b>TIMEOUT</b> · AADE /vatinfo · ΘΕΟΔΩΡΟΥ · retry q</> },
  { glyph: '✓', tone: 'g', body: <><b>SUBMIT</b> · ΕΦΚΑ April / NOVA AE · ack ok</> },
  { glyph: '↻', tone: '',  body: <><b>SYNC</b> · myDATA / 5 clients · 84 records</> },
  { glyph: '!', tone: 'a', body: <><b>WARN</b> · disk &gt; 80% on db-1</> },
];

function EventStream() {
  const [events, setEvents] = useState<StreamEvent[]>(INITIAL_STREAM);

  useEffect(() => {
    let i = 0;
    const id = setInterval(() => {
      const e = ROTATING_EVENTS[i % ROTATING_EVENTS.length]; i++;
      const d = new Date();
      const pad = (n: number) => String(n).padStart(2, '0');
      const time = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
      setEvents(prev => [{ ...e, time }, ...prev].slice(0, 14));
    }, 6000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="acd-stream">
      {events.map((e, i) => (
        <div key={i} className="acd-stream-row">
          <time>{e.time}</time>
          <span className={`acd-glyph ${e.tone ? 'acd-g-' + e.tone : ''}`}>{e.glyph}</span>
          <span>{e.body}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Spark grid ─────────────────────────────────────────────────────────────

interface SparkItem { n: string; v: string; d: string; up: boolean; c: string }
const SPARK_ITEMS: SparkItem[] = [
  { n: 'ΠΕΤΡΑΚΗ',     v: '84.5K', d: '+12%', up: true,  c: 'var(--green)' },
  { n: 'MARINE',      v: '52.3K', d: '+8%',  up: true,  c: 'var(--green)' },
  { n: 'ΓΕΩΡΓΑΝΤΑΣ',  v: '31.2K', d: '+3%',  up: true,  c: 'var(--cyan)' },
  { n: 'VENTUS',      v: '38.7K', d: '+22%', up: true,  c: 'var(--green)' },
  { n: 'ΔΕΛΦΙΝΙΑ',    v: '18.4K', d: '-7%',  up: false, c: 'var(--red)' },
  { n: 'ΟΛΥΜΠΟΣ',     v: '24.1K', d: '+1%',  up: true,  c: 'var(--cyan)' },
  { n: 'ΚΑΛΑΪΤΖΑΚΗΣ', v: '14.8K', d: '+5%',  up: true,  c: 'var(--green)' },
  { n: 'SOLARIS',     v: '9.45K', d: '+2%',  up: true,  c: 'var(--cyan)' },
  { n: 'ΑΓΓΕΛΟΥ',     v: '7.2K',  d: '-4%',  up: false, c: 'var(--red)' },
  { n: 'FERRO',       v: '5.9K',  d: '+3%',  up: true,  c: 'var(--green)' },
  { n: 'NOVA',        v: '4.8K',  d: '+11%', up: true,  c: 'var(--green)' },
  { n: 'BLUE LINE',   v: '4.1K',  d: '-2%',  up: false, c: 'var(--red)' },
  { n: 'ΘΕΟΔΩΡΟΥ',    v: '3.7K',  d: '0%',   up: true,  c: 'var(--ink-mute)' },
  { n: 'HELIOS',      v: '3.2K',  d: '+9%',  up: true,  c: 'var(--green)' },
  { n: 'BETA STORE',  v: '2.9K',  d: '+1%',  up: true,  c: 'var(--cyan)' },
  { n: 'PHOENIX',     v: '2.4K',  d: '-1%',  up: false, c: 'var(--red)' },
];

function SparkGrid() {
  function path(seed: number): number[] {
    const pts: number[] = []; let y = 14;
    for (let i = 0; i < 12; i++) {
      y += ((seed * (i + 1)) % 7) - 3;
      y = Math.max(2, Math.min(20, y));
      pts.push(y);
    }
    return pts;
  }
  return (
    <div className="acd-sparkgrid">
      {SPARK_ITEMS.map((it, i) => (
        <div key={it.n} className="acd-sparkcell">
          <div className="acd-sc-name">{it.n}</div>
          <div className="acd-sc-val">{it.v}</div>
          <div className={`acd-sc-delta acd-sc-${it.up ? 'up' : 'dn'}`}>
            {it.up ? '▲' : '▼'} {it.d}
          </div>
          <Sparkline points={path(i + 3)} color={it.c} fill={false} width={60} height={22} />
        </div>
      ))}
    </div>
  );
}

// ─── Live clock ─────────────────────────────────────────────────────────────

function useClock(): string {
  const [t, setT] = useState(() => {
    const d = new Date();
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  });
  useEffect(() => {
    const id = setInterval(() => {
      const d = new Date();
      const pad = (n: number) => String(n).padStart(2, '0');
      setT(`${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`);
    }, 1000);
    return () => clearInterval(id);
  }, []);
  return t;
}

// ─── Main component ────────────────────────────────────────────────────────

export default function AccountantDashboard() {
  const clock = useClock();

  return (
    <div className="acd-root">
      <style>{ACD_STYLES}</style>

      <main className="acd-shell">

        {/* TOP BAR */}
        <header className="acd-topbar" role="banner">
          <span className="acd-brand">
            <span className="acd-dot" aria-hidden="true" />
            LogistikoCRM<small>OPS·v3.4.1</small>
          </span>
          <div className="acd-sep" />
          <div className="acd-meta">
            <span>PERIOD <b>2026·05</b></span>
            <span>USERS <b>4</b> ONLINE</span>
            <span>SYNC <span className="acd-ok">●</span> 184/184</span>
            <span>QUEUE <span className="acd-warn">●</span> 7</span>
          </div>
          <div className="acd-spacer" />
          <div className="acd-meta">
            <span>UTC+03 · <time>{clock}</time></span>
          </div>
          <span className="acd-live">LIVE</span>
        </header>

        {/* KPI STRIP */}
        <section className="acd-kpi-strip" aria-label="KPIs">

          <article className="acd-kpi" data-accent="cyan">
            <div className="acd-kpi-label">CLIENTS·ACTIVE <span className="acd-tag">+3</span></div>
            <div className="acd-kpi-value">184</div>
            <div className="acd-kpi-delta acd-up">▲ +1.6% / 30d</div>
            <Sparkline points={[22,21,18,19,17,15,16,12,13,10,11,8,9,7]} color="var(--cyan)" />
          </article>

          <article className="acd-kpi" data-accent="green">
            <div className="acd-kpi-label">VAT·OUT MTD</div>
            <div className="acd-kpi-value">342.180<span className="acd-u">€</span></div>
            <div className="acd-kpi-delta acd-up">▲ +12.4% MoM</div>
            <Sparkline points={[24,20,22,15,17,10,12,6,8,4,5]} color="var(--green)" />
          </article>

          <article className="acd-kpi" data-accent="red">
            <div className="acd-kpi-label">VAT·IN MTD</div>
            <div className="acd-kpi-value">214.520<span className="acd-u">€</span></div>
            <div className="acd-kpi-delta acd-dn">▼ −3.1% MoM</div>
            <Sparkline points={[8,12,10,15,14,18,16,21,19,23,21]} color="var(--red)" />
          </article>

          <article className="acd-kpi" data-accent="amber">
            <div className="acd-kpi-label">CREDIT·BAL <span className="acd-tag">23</span></div>
            <div className="acd-kpi-value">127.660<span className="acd-u">€</span></div>
            <div className="acd-kpi-delta">→ stable</div>
            <Sparkline points={[14,15,13,16,14,15,13,16,14,15,13]} color="var(--amber)" fill={false} />
          </article>

          <article className="acd-kpi" data-accent="violet">
            <div className="acd-kpi-label">COMPLIANCE</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '0.5rem' }}>
              <ComplianceRing pct={92} />
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6875rem', color: 'var(--ink-mute)', lineHeight: 1.4 }}>
                169 / 184<br />
                <span style={{ color: 'var(--amber)' }}>15</span> at risk<br />
                <span style={{ color: 'var(--red)' }}>3</span> overdue
              </div>
            </div>
          </article>

        </section>

        {/* HEATMAP + TREEMAP */}
        <section className="acd-row acd-r-1">
          <article className="acd-panel">
            <header>
              <h2>obligations · client × week</h2>
              <div className="acd-legend">
                <span><i style={{ background: '#1A2538' }} />0</span>
                <span><i style={{ background: '#0EA5C0' }} />1</span>
                <span><i style={{ background: '#22D3EE' }} />2</span>
                <span><i style={{ background: '#FBBF24' }} />3</span>
                <span><i style={{ background: '#F87171' }} />≥4</span>
              </div>
            </header>
            <div className="acd-panel-body acd-flush"><Heatmap /></div>
          </article>

          <article className="acd-panel">
            <header>
              <h2>portfolio · ΦΠΑ volume</h2>
              <div className="acd-legend"><span>top 12 / 184</span></div>
            </header>
            <div className="acd-panel-body acd-flush"><Treemap /></div>
          </article>
        </section>

        {/* CASHFLOW + GANTT + DONUT */}
        <section className="acd-row acd-r-2">
          <article className="acd-panel">
            <header>
              <h2>vat · cashflow 12m</h2>
              <div className="acd-legend">
                <span style={{ color: 'var(--green)' }}><i style={{ background: 'var(--green)' }} />OUT</span>
                <span style={{ color: 'var(--red)' }}><i style={{ background: 'var(--red)' }} />IN</span>
                <span style={{ color: 'var(--cyan)' }}><i style={{ background: 'var(--cyan)' }} />BAL</span>
              </div>
            </header>
            <div className="acd-cashflow"><CashflowChart /></div>
          </article>

          <article className="acd-panel">
            <header>
              <h2>deadlines · next 30d</h2>
              <div className="acd-legend">
                <span style={{ color: 'var(--red)' }}><i style={{ background: 'var(--red)' }} />URG</span>
                <span style={{ color: 'var(--amber)' }}><i style={{ background: 'var(--amber)' }} />WARN</span>
                <span style={{ color: 'var(--green)' }}><i style={{ background: 'var(--green)' }} />OK</span>
                <span style={{ color: 'var(--cyan)' }}><i style={{ background: 'var(--cyan)' }} />INFO</span>
              </div>
            </header>
            <div className="acd-panel-body acd-flush"><GanttChart /></div>
          </article>

          <article className="acd-panel">
            <header>
              <h2>status · M+30</h2>
              <div className="acd-legend"><span>47 total</span></div>
            </header>
            <StatusDonut />
          </article>
        </section>

        {/* TOP CLIENTS + STREAM */}
        <section className="acd-row acd-r-3">
          <article className="acd-panel">
            <header>
              <h2>top clients · vat balance M</h2>
              <div className="acd-legend"><span>showing 10 / 184</span></div>
            </header>
            <div className="acd-panel-body acd-flush"><TopClientsTable /></div>
          </article>

          <article className="acd-panel">
            <header>
              <h2>event stream · live</h2>
              <span className="acd-live">REC</span>
            </header>
            <EventStream />
          </article>
        </section>

        {/* SPARK GRID */}
        <section className="acd-panel">
          <header>
            <h2>vat trend · top 16 clients · 12 months</h2>
            <div className="acd-legend"><span>shift+click to pin</span></div>
          </header>
          <SparkGrid />
        </section>

      </main>
    </div>
  );
}

// ─── Scoped styles ──────────────────────────────────────────────────────────
const ACD_STYLES = `
.acd-root {
  --bg:#0A0F1C; --bg-2:#0F1626;
  --panel:#131C2E; --panel-2:#182236; --panel-3:#1E2A41;
  --line:#25334D; --line-soft:#1A2538;
  --ink:#E8ECF5; --ink-2:#B8C2D6; --ink-mute:#6F7B95; --ink-dim:#475167;
  --cyan:#22D3EE; --cyan-d:#0EA5C0;
  --green:#34D399; --green-d:#16A36A;
  --amber:#FBBF24; --amber-d:#D89A12;
  --red:#F87171; --red-d:#DC4444;
  --violet:#A78BFA; --pink:#F472B6;
  --font-sans:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI","Helvetica Neue",Arial,sans-serif;
  --font-mono:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace;
  --t-fast:120ms ease; --t:200ms cubic-bezier(.2,.7,.2,1);
  color-scheme: dark;
  font-family: var(--font-sans); font-size:13px; line-height:1.5;
  color: var(--ink); background: var(--bg);
  background-image:
    radial-gradient(800px 600px at 10% -10%, rgba(34,211,238,.06), transparent 60%),
    radial-gradient(700px 500px at 110% 110%, rgba(167,139,250,.05), transparent 60%);
  min-height: 100vh;
  position: relative;
}
.acd-root::before {
  content:""; position: fixed; inset: 0; pointer-events: none; z-index: 100;
  background: repeating-linear-gradient(0deg, transparent 0, transparent 2px, rgba(255,255,255,0.012) 2px, rgba(255,255,255,0.012) 3px);
}
.acd-root, .acd-root * { box-sizing: border-box; }
.acd-root h1, .acd-root h2, .acd-root h3, .acd-root h4 { margin:0; font-weight: 500; }
.acd-root :focus-visible { outline: 2px solid var(--cyan); outline-offset: 2px; }

@keyframes acd-pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(.9)} }
@media (prefers-reduced-motion: reduce) {
  .acd-root *, .acd-root *::before, .acd-root *::after { animation-duration:.01ms !important; transition-duration:.01ms !important; }
}

.acd-shell { max-width: 1600px; margin: 0 auto; padding: 1rem; }

.acd-topbar { display:flex; align-items:center; gap:1.5rem; padding:.75rem 1rem; border:1px solid var(--line);
  background: linear-gradient(180deg, var(--panel) 0%, var(--bg-2) 100%); border-radius: 4px; margin-bottom: 1rem; flex-wrap: wrap; }
.acd-brand { display:inline-flex; align-items:baseline; gap:.5rem; font-weight:700; font-size:.875rem; letter-spacing:-.01em; }
.acd-dot { width:8px; height:8px; border-radius:50%; background:var(--green); box-shadow:0 0 8px var(--green), 0 0 0 4px rgba(52,211,153,.15); animation: acd-pulse 1.8s ease-in-out infinite; }
.acd-brand small { font-family:var(--font-mono); font-size:.6875rem; color:var(--ink-mute); text-transform:uppercase; letter-spacing:.1em; margin-left: .3em; }
.acd-sep { width:1px; height:20px; background:var(--line); }
.acd-meta { display:inline-flex; gap:1.25rem; font-family:var(--font-mono); font-size:.6875rem; color:var(--ink-mute); text-transform:uppercase; letter-spacing:.08em; flex-wrap: wrap; }
.acd-meta b { color: var(--cyan); font-weight: 500; }
.acd-meta .acd-ok   { color: var(--green); }
.acd-meta .acd-warn { color: var(--amber); }
.acd-spacer { margin-left:auto; }
.acd-live { display:inline-flex; align-items:center; gap:.4rem; font-family:var(--font-mono); font-size:.6875rem; color:var(--green); text-transform:uppercase; letter-spacing:.12em; padding:.3rem .6rem; border:1px solid var(--green-d); background: rgba(52,211,153,.06); border-radius: 4px; }
.acd-live::before { content:""; width:6px; height:6px; border-radius:50%; background:var(--green); animation: acd-pulse 1.4s infinite; }

.acd-kpi-strip { display:grid; grid-template-columns: repeat(5, minmax(0,1fr)); border:1px solid var(--line); background:var(--panel); margin-bottom:1rem; }
@media (max-width: 1080px) { .acd-kpi-strip { grid-template-columns: repeat(2,1fr); } }
.acd-kpi { padding:1.1rem 1.25rem; border-right:1px solid var(--line); position:relative; overflow:hidden; }
.acd-kpi:last-child { border-right: 0; }
.acd-kpi::after { content:""; position:absolute; left:0; right:0; bottom:0; height:2px; background:var(--acc, var(--cyan)); transform:scaleX(0); transform-origin:left; transition: transform var(--t); }
.acd-kpi:hover::after { transform: scaleX(1); }
.acd-kpi[data-accent="cyan"]   { --acc: var(--cyan); }
.acd-kpi[data-accent="green"]  { --acc: var(--green); }
.acd-kpi[data-accent="red"]    { --acc: var(--red); }
.acd-kpi[data-accent="amber"]  { --acc: var(--amber); }
.acd-kpi[data-accent="violet"] { --acc: var(--violet); }
.acd-kpi-label { font-family:var(--font-mono); font-size:.6875rem; color:var(--ink-mute); text-transform:uppercase; letter-spacing:.1em; display:flex; align-items:center; justify-content:space-between; }
.acd-tag { padding:.1rem .4rem; border:1px solid currentColor; border-radius:2px; font-size:.6125rem; font-weight:600; }
.acd-kpi-value { font-family:var(--font-mono); font-variant-numeric: tabular-nums; font-size:1.875rem; line-height:1.1; margin-top:.5rem; letter-spacing:-.02em; color:var(--ink); }
.acd-u { color:var(--ink-mute); font-size:.5em; margin-left:.25em; }
.acd-kpi-delta { font-family:var(--font-mono); font-size:.75rem; margin-top:.4rem; color:var(--ink-2); display:inline-flex; align-items:center; gap:.3rem; }
.acd-kpi-delta.acd-up { color:var(--green); }
.acd-kpi-delta.acd-dn { color:var(--red); }
.acd-kpi svg { width:100%; height:30px; margin-top:.5rem; display:block; }

.acd-ring { width:56px; height:56px; display:inline-grid; place-items:center; position:relative; }
.acd-ring svg { width:100%; height:100%; }
.acd-pct { position:absolute; font-family:var(--font-mono); font-size:.875rem; font-weight:600; color:var(--green); }

.acd-row { display:grid; gap:1rem; margin-bottom:1rem; }
.acd-r-1 { grid-template-columns: minmax(0,1.7fr) minmax(0,1fr); }
.acd-r-2 { grid-template-columns: repeat(3, minmax(0,1fr)); }
.acd-r-3 { grid-template-columns: minmax(0,1.4fr) minmax(0,1fr); }
@media (max-width: 1080px) {
  .acd-r-1, .acd-r-2, .acd-r-3 { grid-template-columns: 1fr; }
}

.acd-panel { background:var(--panel); border:1px solid var(--line); border-radius:4px; display:flex; flex-direction:column; overflow:hidden; }
.acd-panel header { display:flex; align-items:center; justify-content:space-between; padding:.75rem 1rem; border-bottom:1px solid var(--line); background: linear-gradient(180deg, var(--panel-2) 0%, var(--panel) 100%); flex-wrap: wrap; gap:.5rem; }
.acd-panel header h2 { font-family:var(--font-mono); font-size:.75rem; font-weight:600; text-transform:uppercase; letter-spacing:.12em; color:var(--ink-2); }
.acd-panel header h2::before { content:"// "; color:var(--cyan); font-weight:400; }
.acd-legend { display:inline-flex; gap:.75rem; font-family:var(--font-mono); font-size:.6875rem; color:var(--ink-mute); flex-wrap: wrap; }
.acd-legend i { width:10px; height:10px; display:inline-block; margin-right:.3rem; vertical-align:middle; }
.acd-panel-body { padding:1rem; flex:1; }
.acd-panel-body.acd-flush { padding: 0; }

.acd-heatmap { display:grid; grid-template-columns: 140px 1fr; font-family:var(--font-mono); font-size:.6875rem; }
.acd-hm-labels { display:grid; grid-auto-rows:22px; border-right:1px solid var(--line); }
.acd-hm-labels div { display:flex; align-items:center; padding:0 .6rem; color:var(--ink-2); border-bottom:1px solid var(--line-soft); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.acd-hm-grid { display:grid; grid-template-columns: repeat(12,1fr); grid-auto-rows:22px; position:relative; }
.acd-cell { border-right:1px solid var(--line-soft); border-bottom:1px solid var(--line-soft); position:relative; transition: transform var(--t-fast); }
.acd-cell:hover { transform: scale(1.4); z-index:5; outline:1px solid var(--cyan); }
.acd-cell::after { content:""; position:absolute; inset:2px; background:var(--cell, transparent); border-radius:1px; }
.acd-hm-axis { display:grid; grid-template-columns: 140px 1fr; font-family:var(--font-mono); font-size:.625rem; color:var(--ink-mute); border-top:1px solid var(--line); }
.acd-pad { padding:.3rem .6rem; border-right:1px solid var(--line); }
.acd-weeks { display:grid; grid-template-columns: repeat(12,1fr); }
.acd-weeks span { padding:.3rem 0; text-align:center; }

.acd-treemap { position:relative; width:100%; aspect-ratio: 1 / 1.05; background:var(--panel-2); font-family:var(--font-mono); }
.acd-tile { position:absolute; border:1px solid var(--bg); display:flex; flex-direction:column; justify-content:space-between; padding:.4rem .5rem; overflow:hidden; transition: filter var(--t-fast); cursor:pointer; }
.acd-tile:hover { filter: brightness(1.2); }
.acd-t-name { font-size:.6875rem; font-weight:600; color:var(--bg); text-transform:uppercase; letter-spacing:.04em; text-shadow:0 1px 0 rgba(0,0,0,.15); line-height:1.1; overflow:hidden; }
.acd-t-val  { font-size:.75rem; color:var(--bg); opacity:.9; font-weight:500; }
.acd-tile.acd-tile-mute .acd-t-name { color: var(--ink); text-shadow: none; }
.acd-tile.acd-tile-mute .acd-t-val  { color: var(--ink-mute); }

.acd-cashflow { padding:1rem; }

.acd-gantt { display:grid; grid-template-columns: 110px 1fr; font-family:var(--font-mono); font-size:.6875rem; }
.acd-g-rows { display:grid; grid-auto-rows:24px; }
.acd-g-label { padding:.2rem .6rem; color:var(--ink-2); border-bottom:1px solid var(--line-soft); border-right:1px solid var(--line); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; display:flex; align-items:center; }
.acd-g-track { display:grid; grid-auto-rows:24px; position:relative; }
.acd-g-row { border-bottom:1px solid var(--line-soft); position:relative; }
.acd-g-row::before { content:""; position:absolute; inset:0; background-image: repeating-linear-gradient(90deg, transparent 0, transparent calc(100%/30 - 1px), var(--line-soft) calc(100%/30 - 1px), var(--line-soft) calc(100%/30)); opacity:.6; }
.acd-g-bar { position:absolute; top:4px; bottom:4px; border-radius:2px; display:flex; align-items:center; padding:0 .4rem; font-size:.625rem; color:var(--bg); font-weight:600; letter-spacing:.02em; overflow:hidden; }
.acd-g-bar.acd-urgent { background:var(--red); }
.acd-g-bar.acd-warn   { background:var(--amber); }
.acd-g-bar.acd-ok     { background:var(--green); }
.acd-g-bar.acd-info   { background:var(--cyan); }
.acd-g-bar.acd-draft  { background:var(--ink-dim); color:var(--ink-2); }
.acd-g-today { position:absolute; top:0; bottom:0; width:1px; background:var(--cyan); box-shadow:0 0 8px var(--cyan); }
.acd-g-today::before { content:"TODAY"; position:absolute; top:-16px; left:-22px; font-family:var(--font-mono); font-size:.5625rem; color:var(--cyan); letter-spacing:.1em; }

.acd-donut-wrap { display:grid; grid-template-columns: auto 1fr; gap:1.25rem; align-items:center; padding:1rem; }
.acd-donut { width:140px; height:140px; }
.acd-donut-legend { display:grid; gap:.5rem; }
.acd-li { display:grid; grid-template-columns: 14px 1fr auto; align-items:center; gap:.6rem; font-family:var(--font-mono); font-size:.75rem; }
.acd-sw { width:12px; height:12px; border-radius:2px; }
.acd-li b { color:var(--ink); font-weight:600; }
.acd-li small { color:var(--ink-mute); font-size:.6875rem; margin-left: .25rem; }

.acd-tdense { width:100%; border-collapse: collapse; font-family:var(--font-mono); font-size:.75rem; }
.acd-tdense thead th { text-align:left; font-size:.625rem; text-transform:uppercase; letter-spacing:.12em; color:var(--ink-mute); font-weight:600; padding:.5rem .75rem; border-bottom:1px solid var(--line); background:var(--panel-2); }
.acd-tdense tbody td { padding:.55rem .75rem; border-bottom:1px solid var(--line-soft); vertical-align:middle; }
.acd-tdense tbody tr:hover { background: var(--panel-2); }
.acd-bar-cell { position:relative; padding-right: 60px; }
.acd-bar-cell .acd-bar { position:absolute; right:.75rem; top:50%; transform:translateY(-50%); width:50px; height:6px; background:var(--line); border-radius:1px; overflow:hidden; }
.acd-bar-cell .acd-bar i { position:absolute; left:0; top:0; bottom:0; }
.acd-right { text-align:right; }
.acd-pos  { color: var(--green); }
.acd-neg  { color: var(--red); }
.acd-mute { color: var(--ink-mute); }
.acd-afm  { font-size:.625rem; color:var(--ink-mute); }

.acd-stream { font-family:var(--font-mono); font-size:.75rem; max-height: 320px; overflow:hidden; position:relative; }
.acd-stream::after { content:""; position:absolute; left:0; right:0; bottom:0; height:40px; background: linear-gradient(180deg, transparent, var(--panel)); pointer-events:none; }
.acd-stream-row { display:grid; grid-template-columns: 70px 12px 1fr; gap:.5rem; padding:.45rem 1rem; border-bottom:1px solid var(--line-soft); color:var(--ink-2); align-items: baseline; }
.acd-stream-row time { color:var(--ink-mute); font-size:.6875rem; }
.acd-glyph { color:var(--cyan); font-weight:600; }
.acd-glyph.acd-g-g { color:var(--green); }
.acd-glyph.acd-g-a { color:var(--amber); }
.acd-glyph.acd-g-r { color:var(--red); }
.acd-stream-row b { color:var(--ink); font-weight:600; }

.acd-sparkgrid { display:grid; grid-template-columns: repeat(8, minmax(0,1fr)); border-top:1px solid var(--line); }
@media (max-width:1080px) { .acd-sparkgrid { grid-template-columns: repeat(4,1fr); } }
@media (max-width:600px)  { .acd-sparkgrid { grid-template-columns: repeat(2,1fr); } }
.acd-sparkcell { padding:.75rem; border-right:1px solid var(--line); border-bottom:1px solid var(--line); }
.acd-sc-name { font-family:var(--font-mono); font-size:.6875rem; color:var(--ink-2); font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.acd-sc-val  { font-family:var(--font-mono); font-size:.875rem; margin-top:.15rem; font-variant-numeric: tabular-nums; }
.acd-sc-delta { font-family:var(--font-mono); font-size:.625rem; color:var(--ink-mute); }
.acd-sc-delta.acd-sc-up { color:var(--green); }
.acd-sc-delta.acd-sc-dn { color:var(--red); }
.acd-sparkcell svg { width:100%; height:22px; margin-top:.25rem; display:block; }
`;
