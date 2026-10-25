"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { API_URL, api } from "../../../packages/contracts/client";
import { Button } from "./ui/button";
import {
  requireData,
  statuses,
  stages,
  timestamp,
  verdicts,
  type Claim,
} from "./domain";

function ClaimCard({
  claim,
  onSeek,
}: {
  claim: Claim;
  onSeek: (time: number) => void;
}) {
  return (
    <article className="panel">
      <div className="mb-3 flex flex-wrap justify-between gap-3">
        <span className="rounded-md bg-teal-50 px-3 py-1 text-sm font-semibold text-teal-900">
          {claim.verdict
            ? verdicts[claim.verdict.classification]
            : "Avaliação pendente"}
        </span>
        <button
          className="text-sm underline"
          onClick={() => onSeek(claim.start_time)}
        >
          {timestamp(claim.start_time)}
        </button>
      </div>
      <h3 className="text-lg font-semibold">“{claim.statement}”</h3>
      {claim.transcript_context && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer font-medium">
            Contexto original da fala
          </summary>
          <blockquote className="mt-2 border-l-2 border-slate-300 pl-3">
            {claim.transcript_context}
          </blockquote>
        </details>
      )}
      <p className="mt-3 text-sm text-slate-600">{claim.context}</p>
      {claim.verdict && (
        <>
          <p className="mt-3">{claim.verdict.reasoning}</p>
          <ul className="my-3 list-inside list-disc text-sm text-slate-600">
            {claim.verdict.limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
          <p className="break-all text-xs text-slate-500">
            {claim.verdict.model} · {claim.verdict.prompt_version}
          </p>
        </>
      )}
      <details className="mt-4">
        <summary className="cursor-pointer font-medium">
          Como pesquisamos
        </summary>
        {(claim.research_queries ?? []).map((query) => (
          <div key={query.id} className="mt-3 text-sm">
            <p className="font-medium">{query.query}</p>
            <p className="text-slate-600">
              {query.purpose} · {query.outcome}
            </p>
            {(query.sources ?? []).map((source) => (
              <details key={source.id} className="mt-2">
                <summary>Documento recuperado: {source.title}</summary>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="break-all text-teal-800 underline"
                >
                  {source.url}
                </a>
                <p>{source.excerpt}</p>
                <p className="text-xs">
                  Recuperado em{" "}
                  {new Date(source.retrieved_at).toLocaleString("pt-BR")}.
                  Recuperação não equivale a apoio à afirmação.
                </p>
              </details>
            ))}
          </div>
        ))}
      </details>
      <details className="mt-4">
        <summary className="cursor-pointer font-medium">
          Evidências e fontes ({claim.evidence.length})
        </summary>
        {claim.evidence.length === 0 && (
          <p className="mt-3 text-sm">
            Nenhuma evidência recuperada disponível. Isso não demonstra
            falsidade.
          </p>
        )}
        {claim.evidence.map((e) => (
          <div key={e.id} className="mt-4 border-l-2 border-teal-600 pl-4">
            <p className="label">
              {e.stance === "SUPPORTING"
                ? "Apoio"
                : e.stance === "CONTRADICTING"
                  ? "Contradição"
                  : "Contexto"}
            </p>
            <blockquote className="my-2">{e.excerpt}</blockquote>
            <p className="text-sm">{e.assessment}</p>
            <a
              className="mt-2 block break-all text-sm text-teal-800 underline"
              href={e.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {e.title}
            </a>
            <p className="mt-1 text-xs text-slate-500">
              {e.publisher} · Publicação: {e.publication_date ?? "desconhecida"}{" "}
              · Consulta: {new Date(e.retrieved_at).toLocaleDateString("pt-BR")}{" "}
              · Período: {e.applicable_period ?? "não determinado"}
            </p>
          </div>
        ))}
      </details>
    </article>
  );
}
export function AnalysisView({
  id,
  report = false,
}: {
  id: string;
  report?: boolean;
}) {
  const client = useQueryClient();
  const player = useRef<HTMLVideoElement>(null);
  const [message, setMessage] = useState("");
  const [classification, setClassification] = useState("");
  const [speaker, setSpeaker] = useState("");
  const [topic, setTopic] = useState("");
  const [offset, setOffset] = useState(0);
  const [claimOffset, setClaimOffset] = useState(0);
  const analysis = useQuery({
    queryKey: ["analysis", id],
    queryFn: async () =>
      requireData(
        await api.GET("/api/v1/analyses/{id}", { params: { path: { id } } }),
      ),
    refetchInterval: 3000,
  });
  const transcript = useQuery({
    queryKey: ["transcript", id, offset],
    queryFn: async () =>
      requireData(
        await api.GET("/api/v1/analyses/{id}/transcript", {
          params: { path: { id }, query: { offset, limit: 100 } },
        }),
      ),
    refetchInterval: 5000,
  });
  const speakers = useQuery({
    queryKey: ["speakers", id],
    queryFn: async () =>
      requireData(
        await api.GET("/api/v1/analyses/{id}/speakers", {
          params: { path: { id } },
        }),
      ),
    refetchInterval: 5000,
  });
  const claims = useQuery({
    queryKey: ["claims", id, classification, speaker, topic, claimOffset],
    queryFn: async () =>
      requireData(
        await api.GET("/api/v1/analyses/{id}/claims", {
          params: {
            path: { id },
            query: {
              classification: classification || undefined,
              speaker: speaker || undefined,
              topic: topic || undefined,
              offset: claimOffset,
              limit: 50,
            },
          },
        }),
      ),
    refetchInterval: 5000,
  });
  useEffect(() => {
    const events = new EventSource(`${API_URL}/api/v1/analyses/${id}/events`);
    events.addEventListener("status", () =>
      client.invalidateQueries({ queryKey: ["analysis", id] }),
    );
    events.onerror = () => events.close();
    return () => events.close();
  }, [id, client]);
  const seek = (time: number) => {
    if (player.current) {
      player.current.currentTime = time;
      player.current.focus();
    }
  };
  async function action(kind: "cancel" | "resume") {
    try {
      const result =
        kind === "cancel"
          ? await api.POST("/api/v1/analyses/{id}/cancel", {
              params: { path: { id } },
            })
          : await api.POST("/api/v1/analyses/{id}/resume", {
              params: { path: { id } },
            });
      requireData(result);
      await client.invalidateQueries();
      setMessage("");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Falha na operação");
    }
  }
  if (analysis.isPending) return <p role="status">Carregando análise…</p>;
  if (!analysis.data)
    return (
      <p role="alert">
        Análise indisponível. Verifique a API ou o identificador.
      </p>
    );
  const item = analysis.data;
  const active = ["QUEUED", "RUNNING", "CANCEL_REQUESTED"].includes(
    item.status,
  );
  return (
    <>
      <Link href="/" className="text-sm text-teal-800 underline">
        Voltar ao histórico
      </Link>
      <div className="my-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="label mb-2">
            {report ? "Relatório de evidências" : "Análise local"}
          </p>
          <h1 className="break-all text-3xl font-semibold">{item.title}</h1>
          <p className="mt-3 text-slate-600" role="status">
            {statuses[item.status]} · Etapa: {stages[item.stage] ?? item.stage}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={!active}
            onClick={() => action("cancel")}
          >
            Cancelar
          </Button>
          <Button disabled={active} onClick={() => action("resume")}>
            Retomar / atualizar relatório
          </Button>
        </div>
      </div>
      {item.error && (
        <p
          role="alert"
          className="mb-5 rounded-xl bg-amber-50 p-5 text-amber-950"
        >
          {item.error}
        </p>
      )}
      {message && <p role="alert">{message}</p>}
      {item.limitations.length > 0 && (
        <section className="panel mb-5">
          <h2 className="font-semibold">Limitações registradas</h2>
          <ul className="mt-2 list-inside list-disc text-sm">
            {item.limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </section>
      )}
      <div className="mb-6 flex flex-wrap gap-4 text-sm">
        <Link href={`/reports/${id}`} className="text-teal-800 underline">
          Ver relatório
        </Link>
        <a
          href={`${API_URL}/api/v1/analyses/${id}/report`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-teal-800 underline"
        >
          HTML auditável
        </a>
        <a
          href={`${API_URL}/api/v1/analyses/${id}/report.pdf`}
          className="text-teal-800 underline"
        >
          Baixar PDF
        </a>
      </div>
      <video
        ref={player}
        controls
        preload="metadata"
        className="mb-8 w-full rounded-xl bg-slate-900"
        src={`${API_URL}/api/v1/analyses/${id}/media`}
        aria-label="Mídia original"
      />
      {!report && (
        <div className="mb-10 grid gap-6 lg:grid-cols-[2fr_1fr]">
          <section className="panel">
            <h2 className="mb-4 text-xl font-semibold">Transcrição</h2>
            {transcript.error && (
              <p role="alert">Falha ao carregar transcrição.</p>
            )}
            {transcript.data?.length === 0 && (
              <p className="text-slate-600">Nenhum trecho disponível ainda.</p>
            )}
            <div className="max-h-96 space-y-4 overflow-y-auto">
              {transcript.data?.map((s) => (
                <div key={s.id} className="border-b border-slate-100 pb-3">
                  <button
                    className="text-sm font-semibold text-teal-800 underline"
                    onClick={() => seek(s.start_time)}
                  >
                    {timestamp(s.start_time)}
                  </button>
                  <p className="mt-1">{s.text}</p>
                  <label className="mt-2 block text-xs">
                    Interlocutor{" "}
                    <select
                      aria-label={`Interlocutor em ${timestamp(s.start_time)}`}
                      disabled={active}
                      value={s.manual_speaker_id ?? s.speaker_id ?? ""}
                      onChange={async (e) => {
                        if (!e.target.value) return;
                        try {
                          const sp = speakers.data?.find(
                            (x) => x.id === e.target.value,
                          );
                          requireData(
                            await api.PATCH(
                              "/api/v1/analyses/{id}/speakers/{speaker_id}",
                              {
                                params: {
                                  path: { id, speaker_id: e.target.value },
                                },
                                body: {
                                  name: sp?.manual_name,
                                  segment_ids: [s.id],
                                },
                              },
                            ),
                          );
                          await client.invalidateQueries();
                        } catch {
                          setMessage(
                            "Não foi possível corrigir o interlocutor",
                          );
                        }
                      }}
                    >
                      <option value="">Não atribuído</option>
                      {speakers.data?.map((sp) => (
                        <option key={sp.id} value={sp.id}>
                          {sp.manual_name ?? sp.cluster}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              ))}
            </div>
            <div className="mt-4 flex gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={!offset}
                onClick={() => setOffset(Math.max(0, offset - 100))}
              >
                Anterior
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={(transcript.data?.length ?? 0) < 100}
                onClick={() => setOffset(offset + 100)}
              >
                Próximos trechos
              </Button>
            </div>
          </section>
          <section className="panel">
            <h2 className="mb-3 text-xl font-semibold">Interlocutores</h2>
            <p className="mb-4 text-sm text-slate-600">
              Clusters de voz não comprovam identidade. Atribua nomes
              manualmente após conferir a mídia.
            </p>
            {speakers.data?.map((sp) => (
              <form
                key={`${sp.id}-${sp.manual_name}`}
                className="mb-4"
                onSubmit={async (e) => {
                  e.preventDefault();
                  const form = new FormData(e.currentTarget);
                  try {
                    requireData(
                      await api.PATCH(
                        "/api/v1/analyses/{id}/speakers/{speaker_id}",
                        {
                          params: { path: { id, speaker_id: sp.id } },
                          body: { name: String(form.get("name")) },
                        },
                      ),
                    );
                    await client.invalidateQueries();
                  } catch {
                    setMessage("Não foi possível salvar o nome");
                  }
                }}
              >
                <label className="block text-xs" htmlFor={sp.id}>
                  {sp.cluster}
                </label>
                <input
                  id={sp.id}
                  name="name"
                  maxLength={120}
                  defaultValue={sp.manual_name ?? ""}
                  className="my-2 w-full"
                  placeholder="Nome atribuído manualmente"
                />
                <Button disabled={active} size="sm" variant="outline">
                  Salvar nome
                </Button>
              </form>
            ))}
          </section>
        </div>
      )}
      <section>
        <h2 className="mb-4 text-2xl font-semibold">Afirmações e evidências</h2>
        <div className="mb-5 flex flex-wrap gap-3">
          <label className="text-sm">
            Classificação
            <select
              className="ml-2"
              value={classification}
              onChange={(e) => {
                setClassification(e.target.value);
                setClaimOffset(0);
              }}
            >
              <option value="">Todas</option>
              {Object.entries(verdicts).map(([v, l]) => (
                <option value={v} key={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Interlocutor
            <select
              className="ml-2"
              value={speaker}
              onChange={(e) => {
                setSpeaker(e.target.value);
                setClaimOffset(0);
              }}
            >
              <option value="">Todos</option>
              {speakers.data?.map((s) => (
                <option value={s.id} key={s.id}>
                  {s.manual_name ?? s.cluster}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Tema
            <input
              className="ml-2"
              value={topic}
              onChange={(e) => {
                setTopic(e.target.value);
                setClaimOffset(0);
              }}
            />
          </label>
        </div>
        {claims.error && <p role="alert">Falha ao carregar afirmações.</p>}
        {claims.data?.length === 0 && (
          <p className="panel">
            Nenhuma afirmação disponível para estes filtros. Isso não constitui
            uma avaliação da mídia.
          </p>
        )}
        <div className="grid gap-5">
          {claims.data?.map((c) => (
            <ClaimCard key={c.id} claim={c} onSeek={seek} />
          ))}
        </div>
        <div className="mt-4 flex gap-2">
          <Button
            variant="outline"
            disabled={!claimOffset}
            onClick={() => setClaimOffset(Math.max(0, claimOffset - 50))}
          >
            Anterior
          </Button>
          <Button
            variant="outline"
            disabled={(claims.data?.length ?? 0) < 50}
            onClick={() => setClaimOffset(claimOffset + 50)}
          >
            Próximas afirmações
          </Button>
        </div>
      </section>
    </>
  );
}
