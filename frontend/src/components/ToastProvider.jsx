import { createContext, useCallback, useContext, useState } from 'react';
import { CheckCircle2, CircleAlert, X } from 'lucide-react';

const ToastContext = createContext(() => {});

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }) {
  const [toast, setToast] = useState(null);
  const showToast = useCallback((message, type = 'success') => {
    setToast({ message, type, key: Date.now() + Math.random() });
    window.setTimeout(() => setToast((current) => current?.message === message ? null : current), 4500);
  }, []);
  return (
    <ToastContext.Provider value={showToast}>
      {children}
      {toast && (
        <div className={`toast toast-${toast.type}`} role="status" key={toast.key}>
          {toast.type === 'error' ? <CircleAlert size={18} /> : <CheckCircle2 size={18} />}
          <span>{toast.message}</span>
          <button className="icon-button toast-close" aria-label="Dismiss message" onClick={() => setToast(null)}><X size={16} /></button>
        </div>
      )}
    </ToastContext.Provider>
  );
}
