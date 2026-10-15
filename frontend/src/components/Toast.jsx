import { useEffect } from "react";

export default function Toast({ toast, onClear }) {
  useEffect(() => {
    if (toast) {
      const t = setTimeout(onClear, 3000);
      return () => clearTimeout(t);
    }
  }, [toast, onClear]);

  if (!toast) return null;
  return <div className={`toast ${toast.type}`}>{toast.message}</div>;
}
