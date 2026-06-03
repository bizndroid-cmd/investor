import { useEffect, useState, useCallback } from "react";
import { X } from "lucide-react";

export interface ToastMessage {
  id: string;
  title: string;
  description?: string;
  variant?: "default" | "success" | "error";
}

let toastListeners: Array<(toast: ToastMessage) => void> = [];

export function showToast(toast: Omit<ToastMessage, "id">) {
  const message: ToastMessage = { ...toast, id: crypto.randomUUID() };
  toastListeners.forEach((listener) => listener(message));
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((toast: ToastMessage) => {
    setToasts((prev) => [...prev, toast]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== toast.id));
    }, 5000);
  }, []);

  useEffect(() => {
    toastListeners.push(addToast);
    return () => {
      toastListeners = toastListeners.filter((l) => l !== addToast);
    };
  }, [addToast]);

  const dismiss = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const variantClasses: Record<string, string> = {
    default: "border-border",
    success: "border-green-500 bg-green-50",
    error: "border-red-500 bg-red-50",
  };

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm"
      aria-live="polite"
      aria-label="Notifications"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`rounded-lg border bg-card p-3 shadow-lg animate-in slide-in-from-bottom-2 ${
            variantClasses[toast.variant || "default"]
          }`}
          role="alert"
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-sm font-medium">{toast.title}</p>
              {toast.description && (
                <p className="text-xs text-muted-foreground mt-0.5">{toast.description}</p>
              )}
            </div>
            <button
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss notification"
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
