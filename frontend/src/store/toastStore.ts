import { create } from 'zustand'

export type ToastKind = 'success' | 'error' | 'info'
export interface Toast {
  id: number
  kind: ToastKind
  message: string
  // Optional inline action (e.g. "Go to Leads") shown as a button in the toast
  actionLabel?: string
  onAction?: () => void
}

interface ToastState {
  toasts: Toast[]
  push: (t: Omit<Toast, 'id'>) => void
  dismiss: (id: number) => void
}

let _id = 0

export const useToast = create<ToastState>((set) => ({
  toasts: [],
  push: (t) => {
    const id = ++_id
    set((s) => ({ toasts: [...s.toasts, { ...t, id }] }))
    // Auto-dismiss after 6s (actions give enough time to click)
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) }))
    }, 6000)
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })),
}))

// Convenience helpers
export const toast = {
  success: (message: string, action?: { label: string; onClick: () => void }) =>
    useToast.getState().push({ kind: 'success', message, actionLabel: action?.label, onAction: action?.onClick }),
  error: (message: string) => useToast.getState().push({ kind: 'error', message }),
  info: (message: string, action?: { label: string; onClick: () => void }) =>
    useToast.getState().push({ kind: 'info', message, actionLabel: action?.label, onAction: action?.onClick }),
}
