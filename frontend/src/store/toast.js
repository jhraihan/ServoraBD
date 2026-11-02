import { create } from "zustand";

const MAX_TOASTS = 3;
let nextId = 1;

export const useToastStore = create((set) => ({
  toasts: [],
  push: ({ message, tone = "good" }) => {
    const id = nextId++;
    set((state) => ({ toasts: [...state.toasts, { id, message, tone }].slice(-MAX_TOASTS) }));
    return id;
  },
  dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));

export function toast(message, tone = "good") {
  return useToastStore.getState().push({ message, tone });
}
