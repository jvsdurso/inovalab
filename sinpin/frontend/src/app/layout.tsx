import type { Metadata } from "next";
import { Suspense, type ReactNode } from "react";
import { Shell } from "@/components/Shell";
import { SessaoProvider } from "@/lib/session";
import { MARCA } from "@/lib/marca";
import "./globals.css";

export const metadata: Metadata = {
  title: `${MARCA.nome} • ${MARCA.orgaoSigla} | ${MARCA.extenso}`,
  description: "CONHECER, COMPREENDER e PRODUZIR a partir da norma vigente, com rastreabilidade de fonte e vigência.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <head>
        {/* Fontes do protótipo (carregadas pelo navegador; sem elas, cai para as fontes do sistema) */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap" rel="stylesheet" />
      </head>
      <body>
        <SessaoProvider>
          <Suspense fallback={<div className="vazio">Carregando…</div>}>
            <Shell>{children}</Shell>
          </Suspense>
        </SessaoProvider>
      </body>
    </html>
  );
}
