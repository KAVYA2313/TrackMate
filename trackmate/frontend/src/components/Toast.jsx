import { useEffect } from "react";

export default function Toast({ toast, onClose }) {
  useEffect(() => {
    if (!toast) return;

    const timer = setTimeout(() => {
      onClose();
    }, toast.duration || 2800);

    return () => clearTimeout(timer);
  }, [toast, onClose]);

  if (!toast) return null;

  return (
    <div className={`tm-toast tm-toast-${toast.type || "success"}`}>
      <div className="tm-toast-icon">
        {toast.type === "error" ? "!" : toast.type === "warning" ? "!" : "✓"}
      </div>

      <div className="tm-toast-content">
        <strong>{toast.title || "Success"}</strong>
        <p>{toast.message}</p>
      </div>

      <button className="tm-toast-close" onClick={onClose}>
        ×
      </button>
    </div>
  );
}