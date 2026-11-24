"use client";

import { useEffect, useRef, type ReactNode } from "react";

/** <dialog> nativo controlado por `aberto`. */
export function Dialogo({ aberto, aoFechar, children }: { aberto: boolean; aoFechar: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (aberto && !d.open) d.showModal();
    if (!aberto && d.open) d.close();
  }, [aberto]);
  return <dialog ref={ref} onClose={aoFechar} onCancel={aoFechar}>{children}</dialog>;
}
