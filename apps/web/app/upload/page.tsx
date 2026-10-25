"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { UploadCloud } from "lucide-react";
import { API_URL, api } from "../../../../packages/contracts/client";
import { Button } from "../../components/ui/button";
import { requireData } from "../../components/domain";
const urlSchema = z.object({
  url: z.url({ message: "Informe uma URL válida" }),
  permitted: z.boolean().refine((v) => v, "Confirme a permissão de uso"),
});
export default function Upload() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const form = useForm<z.infer<typeof urlSchema>>({
    resolver: zodResolver(urlSchema),
    defaultValues: { url: "", permitted: false },
  });
  function choose(candidate: File | undefined) {
    if (!candidate) return;
    if (!/\.(mp3|mp4)$/i.test(candidate.name)) {
      setError("Escolha um arquivo MP3 ou MP4");
      return;
    }
    setFile(candidate);
    setError("");
  }
  function uploadFile() {
    if (!file) return;
    setBusy(true);
    setError("");
    const request = new XMLHttpRequest();
    request.open("POST", `${API_URL}/api/v1/analyses/uploads`);
    request.upload.onprogress = (e) => {
      if (e.lengthComputable)
        setProgress(Math.round((e.loaded / e.total) * 100));
    };
    request.onerror = () => {
      setBusy(false);
      setError("Falha de rede; verifique a API");
    };
    request.onload = () => {
      setBusy(false);
      try {
        const data: unknown = JSON.parse(request.responseText);
        if (
          request.status === 202 &&
          data &&
          typeof data === "object" &&
          "id" in data &&
          typeof data.id === "string"
        ) {
          router.push(`/analyses/${data.id}`);
        } else {
          setError(
            "Upload recusado. Verifique formato, disco e serviços locais.",
          );
        }
      } catch {
        setError("Resposta inválida da API");
      }
    };
    const body = new FormData();
    body.append("file", file);
    request.send(body);
  }
  return (
    <div className="mx-auto max-w-3xl">
      <p className="label mb-3">Nova análise</p>
      <h1 className="mb-3 text-3xl font-semibold">
        Comece pela fonte original
      </h1>
      <p className="mb-8 text-slate-600">
        Use mídia que você tem permissão para processar. O tempo de análise
        depende dos recursos disponíveis.
      </p>
      <section className="panel">
        <h2 className="mb-4 text-xl font-semibold">Enviar arquivo</h2>
        <div
          className="rounded-xl border-2 border-dashed border-teal-300 bg-teal-50 p-8 text-center"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (!busy) choose(e.dataTransfer.files[0]);
          }}
        >
          <UploadCloud className="mx-auto mb-3 text-teal-700" />
          <label htmlFor="media" className="mb-4 block font-medium">
            Arraste MP3/MP4 ou selecione um arquivo
          </label>
          <input
            id="media"
            disabled={busy}
            type="file"
            accept=".mp3,.mp4,audio/mpeg,video/mp4"
            onChange={(e) => choose(e.target.files?.[0])}
            className="w-full"
          />
          {file && (
            <p className="mt-3 break-all text-sm">
              {file.name} · {(file.size / 1048576).toFixed(1)} MB
            </p>
          )}
        </div>
        {busy && (
          <div className="my-4">
            <label htmlFor="upload-progress">Enviando: {progress}%</label>
            <progress
              id="upload-progress"
              className="w-full"
              value={progress}
              max={100}
            />
          </div>
        )}
        <Button className="mt-5" disabled={!file || busy} onClick={uploadFile}>
          Enviar e analisar
        </Button>
      </section>
      <form
        className="panel mt-6"
        onSubmit={form.handleSubmit(async (values) => {
          setBusy(true);
          setError("");
          try {
            const item = requireData(
              await api.POST("/api/v1/analyses/from-url", {
                body: { url: values.url, permitted: true },
              }),
            );
            router.push(`/analyses/${item.id}`);
          } catch (e) {
            setError(e instanceof Error ? e.message : "Falha no envio");
          } finally {
            setBusy(false);
          }
        })}
      >
        <h2 className="text-xl font-semibold">
          URL de vídeo público — experimental
        </h2>
        <p className="my-3 text-sm text-slate-600">
          YouTube, TikTok e Instagram. Requer o adaptador experimental Docker
          habilitado. Pré-requisitos e bloqueios da plataforma serão informados;
          não contornamos login, DRM ou acesso privado. Prefira upload.
        </p>
        <label className="block" htmlFor="url">
          URL pública
        </label>
        <input id="url" className="my-2 w-full" {...form.register("url")} />
        <p className="text-sm text-red-800">
          {form.formState.errors.url?.message}
        </p>
        <label className="my-4 flex items-start gap-3">
          <input type="checkbox" {...form.register("permitted")} />
          Tenho permissão para processar esta mídia pública, sem contornar
          restrições.
        </label>
        <p className="text-sm text-red-800">
          {form.formState.errors.permitted?.message}
        </p>
        <Button type="submit" variant="outline" disabled={busy}>
          Enviar URL
        </Button>
      </form>
      {error && (
        <p role="alert" className="mt-5 rounded-lg bg-red-50 p-4 text-red-900">
          {error}
        </p>
      )}
    </div>
  );
}
