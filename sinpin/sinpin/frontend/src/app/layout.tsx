import type { Metadata } from "next";
import { Suspense, type ReactNode } from "react";
import { Topo } from "@/components/Topo";
import { SessaoProvider } from "@/lib/session";
import "./globals.css";

export const metadata: Metadata = {
  title: "SINPIN — Sistema Nacional de Pesquisa e Inteligência Normativa",
  description: "CONHECER, COMPREENDER e PRODUZIR a partir da norma vigente, com rastreabilidade de fonte e vigência.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <SessaoProvider>
          <Topo />
          <main>
            <Suspense fallback={<div className="vazio">Carregando…</div>}>{children}</Suspense>
          </main>
        </SessaoProvider>
      </body>
    </html>
  );
}
