import type { components } from "../../../packages/contracts/schema";
export type Analysis = components["schemas"]["AnalysisOut"];
export type Claim = components["schemas"]["ClaimOut"];
export const statuses: Record<string, string> = {
  QUEUED: "Na fila",
  RUNNING: "Em processamento",
  PAUSED: "Aguardando ação",
  CANCEL_REQUESTED: "Cancelando",
  CANCELLED: "Cancelada",
  FAILED: "Falha",
  PARTIALLY_COMPLETED: "Concluída com limitações",
  COMPLETED: "Concluída",
};
export const verdicts: Record<string, string> = {
  TRUE: "Verdadeiro",
  FALSE: "Falso",
  PARTIALLY_TRUE: "Parcialmente verdadeiro",
  MISLEADING_CONTEXT: "Contexto enganoso",
  INCONCLUSIVE: "Inconclusivo",
  NOT_CHECKABLE: "Não verificável",
};
export function timestamp(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}
export function requireData<T>({
  data,
  error,
}: {
  data?: T;
  error?: unknown;
}): T {
  if (error || data === undefined) {
    const detail =
      error && typeof error === "object" && "error" in error
        ? JSON.stringify(error.error)
        : "Serviço indisponível";
    throw new Error(detail);
  }
  return data;
}

export const stages: Record<string, string> = {
  INGESTING: "Validando mídia",
  TRANSCRIBING: "Transcrevendo",
  DIARIZING: "Agrupando vozes",
  EXTRACTING_CLAIMS: "Extraindo afirmações",
  RESEARCHING: "Pesquisando fontes",
  EVALUATING: "Avaliando evidências",
  GENERATING_REPORT: "Gerando relatório",
};
