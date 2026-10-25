# Operação local

## Primeira instalação

Requisitos: Node.js 24, pnpm 10.25, Python 3 com venv/pip para bootstrap do uv,
Docker com Compose, FFmpeg/FFprobe e Make. O projeto fixa Python 3.12 pelo uv.
Em Apple Silicon, instale Pango/Harfbuzz/Fontconfig para WeasyPrint (por exemplo,
`brew install pango`). O launcher reconhece /opt/homebrew/lib no macOS.

```sh
make setup
make infra-up
make migrate
make setup-media
make models-pull
make dev
```

`make setup` gera .env com credenciais aleatórias somente se ele não existir.
Não há token Hugging Face fornecido pelo projeto. Revise .env sem publicá-lo.
`make setup-media` instala MLX e pyannote; não é necessário para testes comuns.
As dependências são resolvidas em uv.lock e pnpm-lock.yaml.

Acesse http://localhost:3000, API http://localhost:8000/docs, MinIO console
http://localhost:9001 e SearXNG http://localhost:8080. Ollama usa :11434.
Credenciais MinIO estão no .env local. A API só deve ser usada em localhost.
Não exponha as portas sem um projeto separado de autenticação e segurança.

## Memória e Docker

Ollama, MinIO, PostgreSQL, Redis e SearXNG rodam em Docker. MLX permanece nativo
por precisar de Metal; API, worker e Next.js também rodam no host. Ollama usa CPU
no Docker/macOS. A configuração de inferência usa num_batch=64 para reduzir buffers,
4096 de contexto inicial, um modelo e uma requisição por vez. Modelos descarregam
após cada chamada. Pesos no volume não significam modelos carregados.

O teste com VM Colima de 2 GB encerrou o runner do Qwen3 1.7B por falta de memória.
O mantenedor autorizou aumentar a VM para 4 GB. Essa é uma configuração experimental,
não uma garantia de que Qwen3 4B e todos os serviços caibam em qualquer Mac de 8 GB.
Para reproduzir a mudança (interrompe todos os containers da VM):

```sh
colima stop
colima start --memory 4
make infra-up
```

Use Activity Monitor (pressão de memória/swap), `vm_stat`, `memory_pressure`,
`docker stats --no-stream` e `docker-compose exec -T ollama ollama ps`.
`make infra-down` preserva volumes; nunca use `down -v` como manutenção rotineira.
O limite de disco da aplicação não inclui pesos no volume Ollama ou volumes Docker;
monitore o uso do Docker separadamente. Não há limite fixo de duração de mídia.

## Diarização e modo degradado explícito

Aceite os termos em https://huggingface.co/pyannote/speaker-diarization-community-1,
crie token de leitura em https://huggingface.co/settings/tokens e configure
HUGGINGFACE_TOKEN no .env. Reinicie API/worker. Sem esse requisito, a análise pausa
com orientação; a transcrição já concluída permanece em checkpoint.

Para aceitar explicitamente saída sem atribuição automática de vozes, configure
DIARIZATION_ENABLED=false e reinicie o worker, depois use Retomar na interface.
Não há sucesso fictício de diarização. Clusters são locais ao chunk e nomes são
humanos; continuidade entre chunks exige correção manual.

Para diagnóstico temporário sem alterar .env:

```sh
DIARIZATION_ENABLED=false make dev-worker
```

Não inicie um segundo worker para o mesmo trabalho enquanto outro estiver ativo.
O lock PostgreSQL e o lock de arquivo impedem trabalho pesado duplicado.

## Recuperação e limites

Cada chunk bem-sucedido e cada afirmação avaliada têm checkpoints transacionais.
Falhas transitórias têm tentativas limitadas; falta de pré-requisito pausa, e
falha de validação falha explicitamente. Retomar reutiliza apenas versões válidas.
Alterar modelo/prompt pode exigir nova análise; desativar diarização antes de seu
primeiro checkpoint não invalida uma transcrição anterior.

Correção manual preserva clusters automáticos, incrementa revisão e invalida o
relatório da revisão anterior. Retome para gerar relatório atualizado. Um erro de
PDF não inventa arquivo: HTML permanece disponível e a limitação é registrada.
Logs locais de subprocessos podem conter diagnósticos e caminhos; não publique
sem revisar. Não há exclusão automática de dados. Faça backup e remova dados locais
somente após conferir referências, checkpoints e objetos MinIO.

URLs sociais são experimentais e desativadas por padrão. Execute `make setup-social`,
configure SOCIAL_DOWNLOAD_ENABLED=true e reinicie o worker para tentar obtenção pública.
O downloader fica em rede Docker interna, sem saída direta; um proxy CONNECT bloqueia
IPs internos e fixa o endereço público validado. Esse isolamento foi testado; uma
amostra YouTube tentou acesso e retornou vídeo indisponível, sem bypass. Não há
validação bem-sucedida de download nas três plataformas. A análise pausa com motivo
explícito em falhas; upload MP3/MP4 continua sendo o caminho validado. Não há bypass de
login, DRM, paywall ou conteúdo privado. Fontes HTML/texto são suportadas; documentos
PDF de terceiros ainda não são extraídos. Fontes podem negar acesso ou mudar.

## Comandos de qualidade

```sh
make lint
make typecheck
make test
make test-e2e
make evaluate
make health
make contracts
pnpm build
```

`make test-e2e` exige `pnpm --filter @verifact/web exec playwright install chromium`.
Os testes E2E com fixtures identificam explicitamente dados sintéticos. Teste de
PostgreSQL real: `RUN_POSTGRES_TESTS=1 .venv/bin/pytest tests/integration/test_postgres.py`.
Não existe benchmark de qualidade ou avaliação política representativa concluída.
As medições e execuções efetivamente realizadas constam em ../VALIDATION.md.

## MinIO sem depender do registro legado

A imagem oficial já em cache foi validada, mas os registros remotos recusaram a
obtenção. A configuração de exemplo agora permite build por código-fonte oficial
fixado no commit `07c3a429bfed433e49018cb0f78a52145d4bedeb`:
`make minio-build`, depois `MINIO_IMAGE=verifact-minio:source-20250907 make infra-up`.
Uma instalação nova usa essa imagem local em .env.example. O .env desta máquina
preservou inicialmente o digest da imagem oficial em cache. O build pode precisar
de vários GB livres na VM; o limite de disco da aplicação não cobre cache de build.
Não remova volumes de outros projetos para liberar espaço. O repositório upstream
está arquivado; a construção local não fornece manutenção de segurança adicional.

O build MinIO por código-fonte foi concluído após limpar imagens e caches de outros
projetos, com autorização do mantenedor. A tentativa de aumentar o disco para 120 GB
não foi aplicada porque qemu-img não estava instalado; o valor de configuração foi
restaurado para os 100 GB originais. Nenhum volume de dados foi excluído.
