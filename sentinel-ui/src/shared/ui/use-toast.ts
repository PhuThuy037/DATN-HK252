import { create } from "zustand";

type ToastVariant = "default" | "destructive" | "success";

export type ToastItem = {
  id: string;
  title: string;
  description?: string;
  variant?: ToastVariant;
};

type ToastInput = Omit<ToastItem, "id">;

type ToastState = {
  toasts: ToastItem[];
  push: (input: ToastInput) => string;
  dismiss: (id: string) => void;
};

const TOAST_DURATION_MS = 3500;

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: (input) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    set((state) => ({
      toasts: [...state.toasts, { ...input, id }],
    }));

    window.setTimeout(() => {
      get().dismiss(id);
    }, TOAST_DURATION_MS);

    return id;
  },
  dismiss: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((toast) => toast.id !== id),
    })),
}));

export function useToast() {
  const push = useToastStore((state) => state.push);
  const dismiss = useToastStore((state) => state.dismiss);
  return {
    toast: push,
    dismiss,
  };
}

export function toast(input: ToastInput) {
  return useToastStore.getState().push(input);
}
