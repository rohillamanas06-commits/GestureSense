import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState, useCallback } from "react";
import {
  Camera, Upload, Loader2, Square,
  Activity, Github, Image as ImageIcon, Trash2, RefreshCw,
} from "lucide-react";

export const Route = createFileRoute("/")({ component: Index });

type DetectResult = { detected: boolean; sign: string | null; confidence: number; processing_ms?: number };
type LogEntry = { id: number; sign: string; confidence: number; ts: string; source: "live" | "upload" };
type HealthStatus = { status: string; model_ready: boolean; dataset: string; samples_trained: number; classes: number; csv_present: boolean; cache_present: boolean; using_synthetic?: boolean; warning?: string };

const DEFAULT_API = "http://localhost:8000";

function useApi() {
  const [api, setApi] = useState(DEFAULT_API);
  useEffect(() => { const v = localStorage.getItem("gs_api"); if (v) setApi(v); }, []);
  return [api, (v: string) => { setApi(v); localStorage.setItem("gs_api", v); }] as const;
}

function useHealth(api: string, refreshKey: number) {
  const [s, setS] = useState<"loading" | "online" | "offline">("loading");
  const [health, setHealth] = useState<HealthStatus | null>(null);
  useEffect(() => {
    let alive = true;
    setS("loading");
    fetch(`${api}/health`).then(r => r.json())
      .then(d => {
        if (alive) {
          setHealth(d);
          setS(d.model_ready ? "online" : "loading");
        }
      })
      .catch(() => alive && setS("offline"));
    return () => { alive = false; };
  }, [api, refreshKey]);
  return [s, health] as const;
}

// ─── HEADER ──────────────────────────────────────────────────────────────────
function Header({ api, setApi, status, health, onRefresh }: {
  api: string; setApi: (v: string) => void;
  status: "loading" | "online" | "offline"; health: HealthStatus | null; onRefresh: () => void;
}) {
  const dot = status === "online" ? "bg-cyan" : status === "offline" ? "bg-destructive" : "bg-amber";
  const label = status === "online" ? "ONLINE" : status === "offline" ? "OFFLINE" : "BOOTING";

  return (
    <header className="border-b border-border bg-background/90 backdrop-blur sticky top-0 z-30">
      <div className="max-w-[1400px] mx-auto px-6 h-16 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="size-9 border border-cyan-soft bg-cyan-soft flex items-center justify-center text-cyan text-xs">
            <span className="font-bold">[ ]</span>
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold tracking-wider">
              <span className="text-cyan">GESTURE</span><span>SENSE</span>
            </div>
            <div className="text-[10px] text-muted-foreground tracking-[0.18em] uppercase mt-0.5">
              Sign Language Detection Console
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <a
            href="https://github.com/rohillamanas06-commits/GestureSense"
            target="_blank"
            rel="noreferrer"
            className="pill hover:text-cyan transition-colors"
            title="Open GitHub repository"
          >
            <Github className="size-3" />
          </a>
          <span className="pill">
            <span className={`size-1.5 rounded-full ${dot} ${status === "loading" ? "blink" : ""}`} />
            <span className={status === "offline" ? "text-destructive" : status === "online" ? "text-cyan" : "text-amber"}>
              {label}
            </span>
          </span>
          <button onClick={onRefresh} className="pill hover:text-cyan transition-colors" title="Refresh status">
            <RefreshCw className="size-3" />
          </button>
        </div>
      </div>
    </header>
  );
}

// ─── TITLE BAR ───────────────────────────────────────────────────────────────
function TitleBar({ signCount }: { signCount: number }) {
  return (
    <div className="max-w-[1400px] mx-auto px-6 pt-8 pb-6 flex items-end justify-between flex-wrap gap-4">
      <div>
        <h1 className="text-2xl md:text-3xl font-semibold tracking-[0.05em] uppercase">
          Gesture Recognition Console
        </h1>
        <p className="text-xs md:text-sm text-muted-foreground mt-2 max-w-2xl leading-relaxed">
          MediaPipe hand landmark extraction · Random Forest classifier · Real-time inference
          over {signCount || 8} word-level signs. Operate via live camera or single-frame upload.
        </p>
      </div>
      <div className="flex gap-2">
        <span className="pill"><span className="text-muted-foreground">BUILD</span> <span className="text-cyan">2.1.0</span></span>
        <span className="pill"><span className="text-muted-foreground">SIGNS</span> <span className="text-cyan">{signCount || 8}</span></span>
        <span className="pill"><span className="text-muted-foreground">ENGINE</span> <span className="text-cyan">MP + RF</span></span>
      </div>
    </div>
  );
}

// ─── ALERT BAR ───────────────────────────────────────────────────────────────
function AlertBar({ status, health }: { status: "loading" | "online" | "offline"; health: HealthStatus | null }) {
  if (status === "offline") {
    return (
      <div className="max-w-[1400px] mx-auto px-6 mb-6">
        <div className="flex items-center justify-between gap-4 border border-destructive/40 bg-destructive/10 px-4 py-2.5 text-xs uppercase tracking-[0.1em]">
          <span className="text-destructive">
            ▲ Backend unreachable.
          </span>
        </div>
      </div>
    );
  }
  if (health?.using_synthetic) {
    return (
      <div className="max-w-[1400px] mx-auto px-6 mb-6">
        <div className="flex items-center justify-between gap-4 border border-amber/40 bg-amber/10 px-4 py-2.5 text-xs uppercase tracking-[0.1em]">
          <span className="text-amber">
            ⚠ SYNTHETIC DATA MODE — Predictions may not be accurate. Ensure CSV is in the app folder for real gestures.
          </span>
        </div>
      </div>
    );
  }
  return null;
}

// ─── LIVE PANEL ──────────────────────────────────────────────────────────────
function LivePanel({ api, onLog }: { api: string; onLog: (e: Omit<LogEntry, "id" | "ts">) => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const intervalRef = useRef<number | null>(null);
  const inFlightRef = useRef(false);
  const lastSignRef = useRef<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [result, setResult] = useState<DetectResult | null>(null);
  const [latency, setLatency] = useState(0);
  const [interval, setIntervalMs] = useState(400);
  const [error, setError] = useState<string | null>(null);

  const stop = useCallback(() => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    wsRef.current?.close(); wsRef.current = null;
    inFlightRef.current = false;
    lastSignRef.current = null;
    setResult(null);
    setLatency(0);
    const s = videoRef.current?.srcObject as MediaStream | null;
    s?.getTracks().forEach(t => t.stop());
    if (videoRef.current) videoRef.current.srcObject = null;
    setStreaming(false);
  }, []);

  const sendFrame = useCallback((ws: WebSocket) => {
    if (inFlightRef.current) return;
    if (!videoRef.current || !canvasRef.current || ws.readyState !== WebSocket.OPEN) return;
    if (videoRef.current.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;

    const c = canvasRef.current;
    const width = Math.max(videoRef.current.videoWidth || 0, 640);
    const height = Math.max(videoRef.current.videoHeight || 0, 480);
    c.width = width;
    c.height = height;

    const ctx = c.getContext("2d");
    if (!ctx) return;

    inFlightRef.current = true;
    ctx.drawImage(videoRef.current, 0, 0, c.width, c.height);
    ws.send(JSON.stringify({ frame: c.toDataURL("image/jpeg", 0.92) }));
  }, []);

  const start = async () => {
    setError(null);
    setResult(null);
    setLatency(0);
    lastSignRef.current = null;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      if (!videoRef.current) return;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setStreaming(true);

      const ws = new WebSocket(api.replace(/^http/, "ws") + "/ws/stream");
      wsRef.current = ws;
      ws.onmessage = ev => {
        try {
          const d = JSON.parse(ev.data);
          inFlightRef.current = false;
          if (d.error) return;
          setResult(d);
          setLatency(d.processing_ms ?? 0);
          if (d.detected && d.sign && d.sign !== lastSignRef.current) {
            lastSignRef.current = d.sign;
            onLog({ sign: d.sign, confidence: d.confidence, source: "live" });
          }
          if (!d.detected) lastSignRef.current = null;
        } catch {}
      };
      ws.onerror = () => {
        inFlightRef.current = false;
        setError("WebSocket error.");
      };
      ws.onclose = () => {
        inFlightRef.current = false;
      };
      ws.onopen = () => {
        intervalRef.current = window.setInterval(() => {
          sendFrame(ws);
        }, interval);
        sendFrame(ws);
      };
    } catch (e: any) {
      setError(e?.message ?? "Camera permission denied.");
      stop();
    }
  };

  useEffect(() => () => stop(), [stop]);

  // Restart interval if changed while streaming
  useEffect(() => {
    if (!streaming || !wsRef.current) return;
    if (intervalRef.current) clearInterval(intervalRef.current);
    const ws = wsRef.current;
    intervalRef.current = window.setInterval(() => {
      sendFrame(ws);
    }, interval);
  }, [interval, sendFrame, streaming]);

  return (
    <div className="panel flex flex-col">
      <div className="panel-header">
        <span className="flex items-center gap-2"><Camera className="size-3.5" /> Live Detection</span>
        <span className="flex items-center gap-3 normal-case tracking-normal">
          <span className="text-[10px] text-muted-foreground tracking-widest">LATENCY: <span className="text-cyan">{latency.toFixed(0)}MS</span></span>
          <select
            value={interval}
            onChange={e => setIntervalMs(Number(e.target.value))}
            className="bg-input border border-border text-[10px] px-1.5 py-0.5 text-cyan tracking-widest outline-none"
          >
            {[200, 300, 400, 600, 1000].map(v => <option key={v} value={v}>{v}MS</option>)}
          </select>
        </span>
      </div>

      <div className="relative aspect-[4/3] bg-background grid-bg corner-brackets overflow-hidden">
        <span className="br" />
        <video ref={videoRef} className="w-full h-full object-cover" muted playsInline />
        {streaming && <div className="scanline" />}
        {!streaming && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-muted-foreground">
            <Camera className="size-8 opacity-50" />
            <div className="text-xs uppercase tracking-[0.18em]">Camera Inactive</div>
            <div className="text-[10px] text-center max-w-[240px] leading-relaxed normal-case tracking-normal">
              Start the camera to begin live gesture recognition. Frames are sampled every {interval}ms.
            </div>
          </div>
        )}
        {streaming && result?.detected && result.sign && (
          <div className="absolute top-3 left-3 px-2 py-1 bg-background/80 border border-cyan-soft text-cyan text-xs tracking-widest">
            ► {result.sign.toUpperCase()} · {result.confidence.toFixed(0)}%
          </div>
        )}
        <canvas ref={canvasRef} className="hidden" />
      </div>

      <div className="p-3 border-t border-border flex items-center gap-2">
        {!streaming ? (
          <button onClick={start} className="flex-1 flex items-center justify-center gap-2 bg-cyan-soft border border-cyan-soft text-cyan text-xs uppercase tracking-[0.18em] py-2 hover:bg-cyan hover:text-primary-foreground transition-colors">
            <Camera className="size-3.5" /> Initialize Stream
          </button>
        ) : (
          <button onClick={stop} className="flex-1 flex items-center justify-center gap-2 border border-destructive/50 text-destructive text-xs uppercase tracking-[0.18em] py-2 hover:bg-destructive/10 transition-colors">
            <Square className="size-3.5" /> Halt Stream
          </button>
        )}
      </div>
      {error && <div className="px-3 pb-3 text-[10px] text-destructive uppercase tracking-widest">{error}</div>}
    </div>
  );
}

// ─── UPLOAD PANEL ────────────────────────────────────────────────────────────
function UploadPanel({ api, onLog }: { api: string; onLog: (e: Omit<LogEntry, "id" | "ts">) => void }) {
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<DetectResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const upload = async (file: File) => {
    setMsg(null); setResult(null); setPreview(URL.createObjectURL(file)); setLoading(true);
    try {
      const fd = new FormData(); fd.append("file", file);
      const r = await fetch(`${api}/detect/upload`, { method: "POST", body: fd });
      const data = await r.json();
      if (data.success && data.result) {
        setResult(data.result);
        if (data.result.detected && data.result.sign) {
          onLog({ sign: data.result.sign, confidence: data.result.confidence, source: "upload" });
        }
      } else {
        setResult({ detected: false, sign: null, confidence: 0 });
        setMsg(data.message ?? "No hand detected.");
      }
    } catch (e: any) { setMsg(e?.message ?? "Request failed."); }
    finally { setLoading(false); }
  };

  const status = loading ? "ANALYZING" : result?.detected ? "DETECTED" : result ? "NO MATCH" : "AWAITING IMAGE";
  const statusColor = loading ? "text-amber" : result?.detected ? "text-cyan" : "text-muted-foreground";

  return (
    <div className="panel flex flex-col">
      <div className="panel-header">
        <span className="flex items-center gap-2"><ImageIcon className="size-3.5" /> Image Upload</span>
        <span className="text-[10px] text-muted-foreground tracking-widest normal-case">SINGLE FRAME</span>
      </div>

      <div className="p-3 flex-1 flex flex-col gap-3">
        <div className="relative flex-1 min-h-[280px] max-h-[400px] border border-dashed border-border bg-background/40 grid-bg corner-brackets overflow-hidden">
          <span className="br" />
          {preview ? (
            <img src={preview} alt="upload" className="w-full h-full object-contain" />
          ) : (
            <button
              onClick={() => inputRef.current?.click()}
              className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-muted-foreground hover:text-cyan transition-colors"
            >
              <Upload className="size-8" />
              <div className="text-xs uppercase tracking-[0.18em]">Drop Image or Click to Browse</div>
              <div className="text-[10px] normal-case tracking-normal">JPG · PNG · WEBP · max 10 MB</div>
            </button>
          )}
          {loading && (
            <div className="absolute inset-0 bg-background/70 flex items-center justify-center">
              <Loader2 className="size-6 animate-spin text-cyan" />
            </div>
          )}
          <input
            ref={inputRef} type="file" accept="image/*" className="hidden"
            onChange={e => e.target.files?.[0] && upload(e.target.files[0])}
          />
        </div>

        {/* Status row */}
        <div className="border border-border bg-background/40">
          <div className="flex items-center justify-between px-3 py-2 border-b border-border">
            <span className="flex items-center gap-2 text-[10px] tracking-widest uppercase">
              <span className={`size-1.5 rounded-full ${result?.detected ? "bg-cyan" : loading ? "bg-amber blink" : "bg-muted-foreground"}`} />
              <span className={statusColor}>{status}</span>
              {result?.detected && result.sign && <span className="text-foreground">› {result.sign}</span>}
            </span>
            <button
              onClick={() => { setPreview(null); setResult(null); setMsg(null); }}
              className="text-muted-foreground hover:text-destructive text-[10px]"
              title="Clear"
            >−</button>
          </div>
          <div className="px-3 py-2.5">
            <div className="flex items-center justify-between text-[10px] tracking-widest uppercase mb-1.5">
              <span className="text-muted-foreground">Confidence</span>
              <span className="text-cyan">{(result?.confidence ?? 0).toFixed(1)}%</span>
            </div>
            <div className="h-1 bg-input overflow-hidden">
              <div className="h-full bg-cyan transition-all duration-500" style={{ width: `${Math.min(100, result?.confidence ?? 0)}%` }} />
            </div>
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => inputRef.current?.click()}
            className="flex-1 flex items-center justify-center gap-2 bg-cyan-soft border border-cyan-soft text-cyan text-xs uppercase tracking-[0.18em] py-2 hover:bg-cyan hover:text-primary-foreground transition-colors"
          >
            <Upload className="size-3.5" /> Choose Image
          </button>
          {preview && (
            <button
              onClick={() => { setPreview(null); setResult(null); setMsg(null); }}
              className="flex-1 flex items-center justify-center gap-2 border border-destructive/50 text-destructive text-xs uppercase tracking-[0.18em] py-2 hover:bg-destructive/10 transition-colors"
              title="Remove image"
            >
              ✕ Remove
            </button>
          )}
        </div>
        {msg && <div className="text-[10px] text-muted-foreground uppercase tracking-widest">{msg}</div>}
      </div>
    </div>
  );
}

// ─── DETECTION LOG ───────────────────────────────────────────────────────────
function LogPanel({ entries, onClear }: { entries: LogEntry[]; onClear: () => void }) {
  return (
    <div className="panel flex flex-col">
      <div className="panel-header">
        <span className="flex items-center gap-2"><Activity className="size-3.5" /> Detection Log</span>
        <span className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground tracking-widest">{entries.length} ENTRIES</span>
          <button onClick={onClear} className="text-muted-foreground hover:text-destructive" title="Clear log">
            <Trash2 className="size-3" />
          </button>
        </span>
      </div>
      <div className="flex-1 min-h-[220px] max-h-[320px] overflow-y-auto">
        {entries.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center py-12 text-muted-foreground">
            <div className="text-[11px] tracking-[0.18em] uppercase">Log Empty</div>
            <div className="text-[10px] mt-2 text-center px-6">
              Detected signs from live and upload modes will appear here.
            </div>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {entries.map(e => (
              <li key={e.id} className="px-3 py-2 flex items-center gap-3 text-xs hover:bg-cyan-soft transition-colors">
                <span className="text-[10px] text-muted-foreground tabular-nums w-14">{e.ts}</span>
                <span className={`size-1.5 rounded-full ${e.source === "live" ? "bg-cyan" : "bg-amber"}`} />
                <span className="flex-1 text-foreground">{e.sign}</span>
                <span className="text-cyan tabular-nums">{e.confidence.toFixed(1)}%</span>
                <span className="text-[9px] text-muted-foreground uppercase tracking-widest w-12 text-right">{e.source}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}



// ─── INDEX ───────────────────────────────────────────────────────────────────
function Index() {
  const [api, setApi] = useApi();
  const [refreshKey, setRefreshKey] = useState(0);
  const [status, health] = useHealth(api, refreshKey);
  const [log, setLog] = useState<LogEntry[]>([]);

  const addLog = (e: Omit<LogEntry, "id" | "ts">) => {
    setLog(prev => [{
      ...e,
      id: Date.now() + Math.random(),
      ts: new Date().toLocaleTimeString("en-GB", { hour12: false }).slice(0, 8),
    }, ...prev].slice(0, 50));
  };

  return (
    <div className="min-h-screen">
      <Header api={api} setApi={setApi} status={status} health={health} onRefresh={() => setRefreshKey(k => k + 1)} />
      <AlertBar status={status} health={health} />

      <main className="max-w-[1400px] mx-auto px-6 pb-10">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <LivePanel api={api} onLog={addLog} />
          <UploadPanel api={api} onLog={addLog} />
        </div>
        <div className="mt-4">
          <LogPanel entries={log} onClear={() => setLog([])} />
        </div>
      </main>

      <footer className="max-w-[1400px] mx-auto px-6 py-6 mt-6 border-t border-border flex items-center justify-between text-[10px] uppercase tracking-[0.18em] text-muted-foreground flex-wrap gap-4">
        <span>► GestureSense Console</span>
        <div className="flex gap-4">
          <a href="/about" className="hover:text-cyan transition-colors">About</a>
          <a href="/privacy" className="hover:text-cyan transition-colors">Privacy</a>
          <a href="/terms" className="hover:text-cyan transition-colors">Terms</a>
          <a href="/cookie" className="hover:text-cyan transition-colors">Cookie</a>
          <a href="/license" className="hover:text-cyan transition-colors">License</a>
          <a href="/faq" className="hover:text-cyan transition-colors">FAQ</a>
        </div>
      </footer>
    </div>
  );
}
