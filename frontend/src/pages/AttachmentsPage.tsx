import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { Paperclip, RefreshCw, CheckCircle2, Clock, AlertTriangle, FileSpreadsheet } from "lucide-react";

interface AttachmentItem {
  id: string;
  file_name: string;
  file_size: number | null;
  mime_type: string | null;
  status: string;
  records_imported: number | null;
  error_message: string | null;
  received_at: string | null;
  processed_at: string | null;
}

export function AttachmentsPage() {
  const queryClient = useQueryClient();
  const { data: attachments, isLoading } = useQuery({
    queryKey: ["attachments"],
    queryFn: () => apiFetch<AttachmentItem[]>("/telegram/attachments"),
  });

  const syncMutation = useMutation({
    mutationFn: () => apiFetch<any>("/telegram/sync", { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["attachments"] }),
  });

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Paperclip className="h-6 w-6 text-blue-500" />
            Attachments
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Documents sent via Telegram. Send any broker report to your bot — it appears here.
          </p>
        </div>
        <button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
          className="btn-primary text-xs"
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${syncMutation.isPending ? "animate-spin" : ""}`} />
          Pull from Telegram
        </button>
      </div>

      {/* Instructions */}
      <div className="bento-card border-dashed border-primary/20 bg-primary/5">
        <p className="text-xs text-muted-foreground leading-relaxed">
          <strong>How it works:</strong> Send XLSX or CSV files to your Telegram bot.
          Click "Pull from Telegram" to fetch them here.
          Then use them in Earnings or other pages by selecting from this list.
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[1,2,3].map(i => <div key={i} className="bento-card h-16 skeleton-shimmer" />)}
        </div>
      ) : !attachments || attachments.length === 0 ? (
        <div className="bento-card text-center py-12">
          <FileSpreadsheet className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground">No documents yet</p>
          <p className="text-xs text-muted-foreground/70 mt-1">Send a file to your Telegram bot, then pull here</p>
        </div>
      ) : (
        <div className="space-y-2">
          {attachments.map((a) => (
            <AttachmentRow key={a.id} attachment={a} />
          ))}
        </div>
      )}
    </div>
  );
}

function AttachmentRow({ attachment: a }: { attachment: AttachmentItem }) {
  const statusConfig = {
    pending: { icon: Clock, color: "text-amber-500", bg: "bg-amber-500/10", label: "Pending" },
    processed: { icon: CheckCircle2, color: "text-emerald-500", bg: "bg-emerald-500/10", label: "Processed" },
    failed: { icon: AlertTriangle, color: "text-red-500", bg: "bg-red-500/10", label: "Failed" },
  }[a.status] || { icon: Clock, color: "text-muted-foreground", bg: "bg-muted", label: a.status };

  const Icon = statusConfig.icon;

  return (
    <div className="bento-card flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className={`h-9 w-9 rounded-lg ${statusConfig.bg} flex items-center justify-center`}>
          <FileSpreadsheet className={`h-4 w-4 ${statusConfig.color}`} />
        </div>
        <div>
          <p className="text-sm font-medium">{a.file_name}</p>
          <div className="flex items-center gap-2 text-[10px] text-muted-foreground mt-0.5">
            {a.file_size && <span>{(a.file_size / 1024).toFixed(0)} KB</span>}
            {a.received_at && <span>· {new Date(a.received_at).toLocaleDateString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>}
            {a.records_imported && <span>· {a.records_imported} trades imported</span>}
          </div>
          {a.error_message && <p className="text-[10px] text-red-500 mt-0.5">{a.error_message}</p>}
        </div>
      </div>
      <div className="flex items-center gap-1.5">
        <Icon className={`h-3.5 w-3.5 ${statusConfig.color}`} />
        <span className={`text-[10px] font-medium ${statusConfig.color}`}>{statusConfig.label}</span>
      </div>
    </div>
  );
}
