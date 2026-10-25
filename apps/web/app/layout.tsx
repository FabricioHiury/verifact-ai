import type { Metadata } from "next";
import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { Providers } from "../components/providers";
import "./globals.css";
export const metadata: Metadata = {
  title: "Verifact AI",
  description:
    "Afirmações políticas, evidências verificáveis e inferência local.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <Providers>
          <a href="#conteudo" className="sr-only focus:not-sr-only">
            Ir ao conteúdo
          </a>
          <header className="border-b border-slate-200 bg-white">
            <nav
              className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-5"
              aria-label="Principal"
            >
              <Link
                className="flex items-center gap-2 text-xl font-bold tracking-tight"
                href="/"
              >
                <ShieldCheck aria-hidden className="text-teal-700" />
                Verifact <span className="font-normal text-teal-700">AI</span>
              </Link>
              <div className="flex gap-6 text-sm">
                <Link href="/">Histórico</Link>
                <Link href="/upload">Nova análise</Link>
              </div>
            </nav>
          </header>
          <main id="conteudo" className="mx-auto max-w-6xl px-5 py-12">
            {children}
          </main>
          <footer className="mx-auto max-w-6xl px-5 py-8 text-sm text-slate-600">
            Inferência local · Evidências verificáveis · Sem rankings de
            candidatos
            <br />
            Avaliações podem conter erros e vieses. Consulte as fontes
            originais.
          </footer>
        </Providers>
      </body>
    </html>
  );
}
