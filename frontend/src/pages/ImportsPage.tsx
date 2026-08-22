import { useState, useRef, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Upload, FileSpreadsheet, Loader2, CheckCircle2, X, AlertTriangle, Send } from "lucide-react";

type ParseStatus = "idle" | "uploading" | "parsing" | "review" | "confirming" | "done" | "error";

interface ParseResult {
  status: string;
  doc_type: string;
  columns: string[];
  rows: Record<string, any>[];
  metadata: Record<string, any>;
  parse_log: string[];
  broker: string;
  currency: string;
  message?: string;
}

const BROKER_OPTIONS = [
  { id: "groww", label: "Groww" },
  { id: "zerodha", label: "Zerodha" },
  { id: "fidelity", label: "Fidelity" },
  { id: "robinhood", label: "Robinhood" },
  { id: "other", label: "Other" },
];

export function ImportsPage() {
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const logRef = useRef<HTMLDivElement>(null);

  const [status, setStatus] = useState<ParseStatus>("idle");
  const [broker, setBroker] = useState("groww");
  const [currency, setCurrency] = useState("INR");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [editedRows, setEditedRows] = useState<Record<string, any>[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Auto-scroll logs
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setStatus("idle");
      setError(null);
      setParseResult(null);
    }
  };

  const handleParse = async () => {
    if (!selectedFile) return;
    setStatus("uploading");
    setLogs(["Preparing upload..."]);
    setError(null);

    // Simulate upload progress
    await delay(300);
    setLogs((l) => [...l, `Uploading ${selectedFile.name} (${(selectedFile.size / 1024).toFixed(0)} KB)...`]);
    await delay(500);
    setLogs((l) => [...l, "Upload complete"]);
    setStatus("parsing");
    setLogs((l) => [...l, "Starting AI document analysis..."]);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("broker", broker);
      formData.append("currency", currency);
      formData.append("doc_type", "auto");

      const token = localStorage.getItem("access_token");
      const baseUrl = import.meta.env.VITE_API_URL || "/api";

      const response = await fetch(`${baseUrl}/imports/parse`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.status}`);
      }

      const result: ParseResult = await response.json();

      // Animate log messages
      if (result.parse_log) {
        for (const msg of result.parse_log) {
          setLogs((l) => [...l, msg]);
          await delay(200 + Math.random() * 300);
        }
      }

      if (result.status === "error") {
        setError(result.message || "Parsing failed");
        setStatus("error");
        return;
      }

      setParseResult(result);
      setEditedRows(result.rows || []);
      setStatus("review");
      setLogs((l) => [...l, "Ready for review — verify data below"]);
    } catch (e: any) {
      setError(e.message || "Parse failed");
      setStatus("error");
      setLogs((l) => [...l, `✗ Error: ${e.message}`]);
    }
  };

  const handleConfirm = async () => {
    if (!parseResult) return;
    setStatus("confirming");
    setLogs((l) => [...l, "Importing data into RuDo..."]);

    try {
      const token = localStorage.getItem("access_token");
      const baseUrl = import.meta.env.VITE_API_URL || "/api";

      const response = await fetch(`${baseUrl}/imports/confirm`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          doc_type: parseResult.doc_type,
          broker: parseResult.broker,
          currency: parseResult.currency,
          rows: editedRows,
        }),
      });

      const result = await response.json();
      setLogs((l) => [...l, `✓ Imported ${result.imported} records`]);
      setStatus("done");

      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["earnings"] });
      queryClient.invalidateQueries({ queryKey: ["wealth-summary"] });
    } catch (e: any) {
      setError(e.message);
      setStatus("error");
    }
  };

  const handleReset = () => {
    setStatus("idle");
    setSelectedFile(null);
    setParseResult(null);
    setEditedRows([]);
    setLogs([]);
    setError(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Upload className="h-6 w-6 text-blue-500" />
          Offline Import
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Upload broker statements (CSV, XLSX, PDF) — AI extracts your portfolio data automatically
        </p>
        <div className="mt-3 p-3 rounded-xl bg-blue-500/5 border border-blue-500/10 text-xs text-muted-foreground space-y-1">
          <p><strong className="text-foreground">Two files recommended:</strong></p>
          <p>1. <strong>Holdings Statement</strong> — current stocks, quantity, prices (populates Portfolio page)</p>
          <p>2. <strong>Order History</strong> — buy/sell dates and prices (populates Earnings + dividend calculations)</p>
          <p className="text-[10px] mt-1">Upload them one at a time. The system auto-detects which type each file is.</p>
        </div>
      </div>

      {/* Upload Section */}
      {(status === "idle" || status === "done") && (
        <div className="bento-card">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div>
              <label className="text-[10px] text-muted-foreground uppercase block mb-1">Broker</label>
              <select value={broker} onChange={(e) => setBroker(e.target.value)} className="input-field">
                {BROKER_OPTIONS.map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground uppercase block mb-1">Currency</label>
              <select value={currency} onChange={(e) => setCurrency(e.target.value)} className="input-field">
                <option value="INR">₹ INR (Indian Rupee)</option>
                <option value="USD">$ USD (US Dollar)</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground uppercase block mb-1">Document</label>
              <div className="flex gap-2">
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv,.xlsx,.xls,.pdf"
                  onChange={handleFileSelect}
                  className="input-field text-xs file:mr-2 file:py-1 file:px-3 file:rounded-lg file:border-0 file:bg-primary/10 file:text-primary file:text-xs file:font-medium"
                />
              </div>
            </div>
          </div>

          {selectedFile && (
            <div className="flex items-center justify-between p-3 rounded-xl bg-primary/5 border border-primary/20">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="h-4 w-4 text-primary" />
                <span className="text-xs font-medium">{selectedFile.name}</span>
                <span className="text-[9px] text-muted-foreground">({(selectedFile.size / 1024).toFixed(0)} KB)</span>
              </div>
              <button onClick={handleParse} className="btn-primary text-xs">
                <Send className="h-3.5 w-3.5 mr-1.5" />
                Parse with AI
              </button>
            </div>
          )}

          {status === "done" && (
            <div className="mt-4 flex items-center gap-2 text-emerald-500">
              <CheckCircle2 className="h-4 w-4" />
              <span className="text-xs font-medium">Import successful! Upload another document to continue.</span>
            </div>
          )}
        </div>
      )}

      {/* Processing Animation */}
      {(status === "uploading" || status === "parsing" || status === "confirming") && (
        <div className="bento-card">
          <div className="flex items-center gap-2 mb-4">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            <span className="text-sm font-bold">
              {status === "uploading" ? "Uploading..." : status === "confirming" ? "Importing..." : "AI Parsing..."}
            </span>
          </div>
          <div
            ref={logRef}
            className="bg-muted/30 rounded-xl p-4 font-mono text-[11px] max-h-48 overflow-y-auto space-y-1"
          >
            {logs.map((log, i) => (
              <div key={i} className={`flex items-start gap-2 animate-fade-in ${log.startsWith("✓") ? "text-emerald-500" : log.startsWith("✗") ? "text-red-500" : "text-muted-foreground"}`}>
                <span className="text-[9px] text-muted-foreground/50 shrink-0">{String(i + 1).padStart(2, "0")}</span>
                <span>{log}</span>
              </div>
            ))}
            {status !== "confirming" && (
              <div className="flex items-center gap-2 text-primary animate-pulse">
                <span className="text-[9px]">▸</span>
                <span>Processing...</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Error */}
      {status === "error" && (
        <div className="bento-card border-destructive/20">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="h-4 w-4 text-destructive" />
            <span className="text-sm font-bold text-destructive">Parse Failed</span>
          </div>
          <p className="text-xs text-muted-foreground">{error}</p>
          <button onClick={handleReset} className="btn-ghost text-xs mt-3">Try Again</button>
        </div>
      )}

      {/* Review Table */}
      {status === "review" && parseResult && (
        <div className="bento-card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold">Review Extracted Data</h3>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                {editedRows.length} records • {parseResult.doc_type} • {parseResult.broker} • {parseResult.currency}
              </p>
            </div>
            <div className="flex gap-2">
              <button onClick={handleReset} className="btn-ghost text-xs">
                <X className="h-3 w-3 mr-1" /> Cancel
              </button>
              <button onClick={handleConfirm} className="btn-primary text-xs">
                <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />
                Confirm Import ({editedRows.length})
              </button>
            </div>
          </div>

          {/* Metadata */}
          {parseResult.metadata && Object.keys(parseResult.metadata).some((k) => parseResult.metadata[k]) && (
            <div className="flex flex-wrap gap-3 mb-4 text-[10px]">
              {parseResult.metadata.account_name && (
                <span className="badge badge-info">Account: {parseResult.metadata.account_name}</span>
              )}
              {parseResult.metadata.statement_date && (
                <span className="badge badge-info">Date: {parseResult.metadata.statement_date}</span>
              )}
              {parseResult.metadata.total_value && (
                <span className="badge badge-success">Value: {parseResult.currency === "INR" ? "₹" : "$"}{parseResult.metadata.total_value.toLocaleString()}</span>
              )}
            </div>
          )}

          {/* Editable Table */}
          <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-card">
                <tr className="border-b">
                  {parseResult.columns.slice(0, 8).map((col) => (
                    <th key={col} className="text-left py-2 px-2 font-medium text-muted-foreground whitespace-nowrap">
                      {col.replace(/_/g, " ")}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {editedRows.map((row, i) => (
                  <tr key={i} className="border-b border-border/50 hover:bg-secondary/20">
                    {parseResult.columns.slice(0, 8).map((col) => (
                      <td key={col} className="py-1.5 px-2">
                        <input
                          type="text"
                          value={row[col] ?? ""}
                          onChange={(e) => {
                            const updated = [...editedRows];
                            updated[i] = { ...updated[i], [col]: e.target.value };
                            setEditedRows(updated);
                          }}
                          className="w-full bg-transparent border-0 text-xs py-0.5 px-1 rounded focus:bg-secondary/50 focus:ring-1 focus:ring-primary/30"
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
