"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, FileAudio, Plus } from "lucide-react";
import { api } from "../../../packages/contracts/client";
import { Button } from "../components/ui/button";
import { requireData, statuses } from "../components/domain";
import { useState } from "react";
export default function Dashboard() {
  const [offset, setOffset] = useState(0);
  const history = useQuery({
    queryKey: ["analyses", offset],
    queryFn: async () =>
      requireData(
        await api.GET("/api/v1/analyses", {
          params: { query: { offset, limit: 20 } },
        }),
      ),
    refetchInterval: 5000,
  });
  return (
    <>
      <div className="mb-10 flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="label mb-3">Observatório de afirmações</p>
          <h1 className="text-4xl font-semibold tracking-tight">
            Mais contexto.
            <br />
            Evidências à vista.
          </h1>
          <p className="mt-4 max-w-xl text-slate-600">
            Examine discursos e debates brasileiros com transcrição local e
            fontes rastreáveis.
          </p>
        </div>
        <Button asChild>
          <Link href="/upload">
            <Plus size={18} />
            Nova análise
          </Link>
        </Button>
      </div>
      <section className="panel mb-8 flex items-start gap-4">
        <FileAudio className="shrink-0 text-teal-700" />
        <div>
          <h2 className="font-semibold">Sua mídia, uma afirmação por vez</h2>
          <p className="mt-1 text-sm text-slate-600">
            Envie MP3 ou MP4. O processamento ocorre em etapas para respeitar os
            recursos da máquina. Nenhuma avaliação representa uma nota de
            honestidade.
          </p>
        </div>
      </section>
      <h2 className="mb-4 text-xl font-semibold">Histórico local</h2>
      {history.isPending && <p role="status">Carregando histórico…</p>}
      {history.error && (
        <p role="alert">
          Não foi possível consultar a API. Verifique os serviços locais.{" "}
          <button onClick={() => history.refetch()} className="underline">
            Tentar novamente
          </button>
        </p>
      )}
      {history.data?.items.length === 0 && (
        <div className="panel text-slate-600">
          Nenhuma análise nesta página. Envie sua primeira mídia para começar.
        </div>
      )}
      <div className="grid gap-4">
        {history.data?.items.map((item) => (
          <Link
            className="panel flex items-center justify-between gap-4 hover:border-teal-600"
            href={`/analyses/${item.id}`}
            key={item.id}
          >
            <div>
              <h3 className="font-semibold">{item.title}</h3>
              <p className="mt-2 text-sm text-slate-600">
                {statuses[item.status]} ·{" "}
                {new Date(item.created_at).toLocaleString("pt-BR")}
              </p>
            </div>
            <ArrowUpRight aria-hidden className="shrink-0 text-teal-700" />
          </Link>
        ))}
      </div>
      <div className="mt-5 flex gap-3">
        <Button
          variant="outline"
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 20))}
        >
          Anterior
        </Button>
        <Button
          variant="outline"
          disabled={offset + 20 >= (history.data?.total ?? 0)}
          onClick={() => setOffset(offset + 20)}
        >
          Próxima
        </Button>
      </div>
    </>
  );
}
