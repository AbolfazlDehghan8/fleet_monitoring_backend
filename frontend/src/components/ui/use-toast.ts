import * as React from 'react';

export interface ToastItem {
  id: string;
  title?: string;
  description?: string;
  variant?: 'default' | 'destructive' | 'success';
}

type ToastInput = Omit<ToastItem, 'id'>;

let listeners: Array<(toasts: ToastItem[]) => void> = [];
let memoryState: ToastItem[] = [];

function emit() {
  listeners.forEach((listener) => listener(memoryState));
}

export function toast(input: ToastInput) {
  const id = crypto.randomUUID();
  memoryState = [...memoryState, { id, ...input }];
  emit();

  window.setTimeout(() => {
    memoryState = memoryState.filter((t) => t.id !== id);
    emit();
  }, 4500);

  return id;
}

export function dismissToast(id: string) {
  memoryState = memoryState.filter((t) => t.id !== id);
  emit();
}

export function useToast() {
  const [toasts, setToasts] = React.useState<ToastItem[]>(memoryState);

  React.useEffect(() => {
    listeners.push(setToasts);
    return () => {
      listeners = listeners.filter((listener) => listener !== setToasts);
    };
  }, []);

  return { toasts, toast, dismiss: dismissToast };
}
