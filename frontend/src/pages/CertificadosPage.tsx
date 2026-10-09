import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  AlertCircle,
  CalendarClock,
  CheckCircle2,
  FileKey2,
  Link2,
  RefreshCw,
  ShieldCheck,
  ShieldOff,
  Upload,
} from "lucide-react";

type Certificado = {
  id: number;
  nome: string;
  titular: string;
  emissor: string;
  fingerprint_sha256: string;
  valido_de: string;
  valido_ate: string;
  ativo: boolean;
  situacao: "valido" | "vencido" | "desativado" | "ainda_nao_valido";
  cadastrado_por: string;
  cadastrado_em: string;
};

type Vinculo = {
  codigo_dominio: string;
  certificado_id: number;
  vinculado_por: string;
  vinculado_em: string;
};

function mensagemErro(dados: unknown, codigo: number): string {
  if (typeof dados === "object" && dados !== null && "detail" in dados) {
    const detalhe = (dados as { detail?: unknown }).detail;
    if (typeof detalhe === "string") return detalhe;
    if (Array.isArray(detalhe)) {
      return detalhe
        .map((item) => typeof item?.msg === "string" ? item.msg : "Valor inválido")
        .join("; ");
    }
  }
  return `Não foi possível completar a operação (HTTP ${codigo}).`;
}

async function apiCertificados<T>(
  caminho: string,
  opcoes: RequestInit = {},
): Promise<T> {
  const resposta = await fetch(`/api/certificados${caminho}`, {
    ...opcoes,
    credentials: "include",
    cache: "no-store",
  });

  if (!resposta.ok) {
    const corpo: unknown = await resposta.json().catch(() => null);
    throw new Error(mensagemErro(corpo, resposta.status));
  }
  return await resposta.json() as T;
}

function dataBR(texto: string): string {
  if (!texto) return "—";
  const data = new Date(`${texto.replace(/Z$/, "").split("+")[0]}Z`);
  return Number.isNaN(data.getTime())
    ? texto.slice(0, 10)
    : new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC", dateStyle: "short" }).format(data);
}

function nomeSituacao(situacao: Certificado["situacao"]): string {
  return {
    valido: "Válido",
    vencido: "Vencido",
    desativado: "Desativado",
    ainda_nao_valido: "Ainda não válido",
  }[situacao] ?? situacao;
}

function corSituacao(situacao: Certificado["situacao"]): string {
  if (situacao === "valido") return "bg-[#E7F0F3] text-[#044055]";
  if (situacao === "desativado") return "bg-slate-100 text-slate-600";
  return "bg-amber-50 text-amber-800";
}

export default function CertificadosPage() {
  const [certificados, setCertificados] = useState<Certificado[]>([]);
  const [vinculos, setVinculos] = useState<Vinculo[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");
  const [recarregar, setRecarregar] = useState(0);

  const [nome, setNome] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [senha, setSenha] = useState("");
  const [limparArquivo, setLimparArquivo] = useState(0);
  const [dominio, setDominio] = useState("");
  const [certificadoSelecionado, setCertificadoSelecionado] = useState("");

  const carregar = useCallback(async (signal: AbortSignal) => {
    setCarregando(true);
    setErro("");
    try {
      const [lista, listaVinculos] = await Promise.all([
        apiCertificados<Certificado[]>("", { signal }),
        apiCertificados<Vinculo[]>("/vinculos", { signal }),
      ]);
      if (!signal.aborted) {
        setCertificados(lista);
        setVinculos(listaVinculos);
      }
    } catch (error) {
      if (!signal.aborted) {
        setErro(error instanceof Error ? error.message : "Erro ao carregar certificados.");
      }
    } finally {
      if (!signal.aborted) setCarregando(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void carregar(controller.signal);
    return () => controller.abort();
  }, [carregar, recarregar]);

  const certificadosValidos = useMemo(
    () => certificados.filter((item) => item.situacao === "valido"),
    [certificados]
  );

  function avisarErro(error: unknown) {
    setErro(error instanceof Error ? error.message : "Ocorreu um erro inesperado.");
    setSucesso("");
  }

  async function cadastrar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (!arquivo) return setErro("Selecione um certificado PFX ou P12.");
    if (!/\.(pfx|p12)$/i.test(arquivo.name)) return setErro("O arquivo precisa ser .pfx ou .p12.");
    if (arquivo.size > 5 * 1024 * 1024) return setErro("O limite é de 5 MB por certificado.");

    const dados = new FormData();
    dados.append("arquivo", arquivo);
    dados.append("nome_exibicao", nome.trim());
    dados.append("senha", senha);

    setOcupado(true);
    setErro("");
    setSucesso("");
    try {
      const criado = await apiCertificados<Certificado>("", {
        method: "POST",
        body: dados,
      });
      setSucesso(`Certificado “${criado.nome}” cadastrado com sucesso.`);
      setNome("");
      setArquivo(null);
      setSenha("");
      setLimparArquivo((anterior) => anterior + 1);
      setRecarregar((anterior) => anterior + 1);
    } catch (error) {
      avisarErro(error);
    } finally {
      setOcupado(false);
    }
  }

  async function vincular(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (!certificadoSelecionado || !dominio.trim()) {
      return setErro("Informe o código Domínio e selecione o certificado.");
    }
    const existente = vinculos.find((v) => v.codigo_dominio === dominio.trim());
    if (existente && !window.confirm(
      `O domínio ${dominio.trim()} já possui um certificado. Deseja substituir esse vínculo?`
    )) return;

    setOcupado(true);
    setErro("");
    setSucesso("");
    try {
      await apiCertificados<Vinculo>("/vinculos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          codigo_dominio: dominio.trim(),
          certificado_id: Number(certificadoSelecionado),
        }),
      });
      setSucesso(`Vínculo do domínio ${dominio.trim()} salvo com sucesso.`);
      setDominio("");
      setCertificadoSelecionado("");
      setRecarregar((atual) => atual + 1);
    } catch (error) {
      avisarErro(error);
    } finally {
      setOcupado(false);
    }
  }

  async function desativar(certificado: Certificado) {
    const quantidade = vinculos.filter((v) => v.certificado_id === certificado.id).length;
    const aviso = quantidade
      ? `Este certificado possui ${quantidade} vínculo(s) com códigos Domínio. Desativá-lo impedirá sua utilização nesses vínculos. Confirmar?`
      : `Desativar o certificado “${certificado.nome}”?`;
    if (!window.confirm(aviso)) return;

    setOcupado(true);
    setErro("");
    setSucesso("");
    try {
      await apiCertificados<unknown>(`/${certificado.id}/desativar`, {
        method: "PATCH",
      });
      setSucesso(`Certificado “${certificado.nome}” desativado.`);
      setRecarregar((atual) => atual + 1);
    } catch (error) {
      avisarErro(error);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="min-w-0 space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gnre-text">Certificados digitais</h2>
          <p className="mt-1 text-sm text-slate-500">
            Cadastre certificados A1 e vincule-os aos códigos Domínio das empresas.
          </p>
        </div>
        <button
          type="button"
          className="botao-secundario"
          onClick={() => setRecarregar((atual) => atual + 1)}
          disabled={carregando || ocupado}
        >
          <RefreshCw size={16} /> Atualizar
        </button>
      </div>

      {erro && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{erro}</div>}
      {sucesso && <div role="status" className="rounded-xl border border-[#C9DEDA] bg-[#E7F0F3] p-4 text-sm text-[#044055]">{sucesso}</div>}

      <div className="grid gap-5 xl:grid-cols-2">
        <form onSubmit={(e) => void cadastrar(e)} className="card-gnre space-y-4 p-6">
          <div className="flex items-center gap-2">
            <Upload size={20} className="text-gnre-green" />
            <h3 className="text-lg font-semibold">Cadastrar certificado A1</h3>
          </div>
          <p className="text-sm leading-6 text-slate-500">
            Aceita arquivos .pfx ou .p12, até 5 MB. A senha serve apenas para importar o certificado e não é armazenada.
          </p>
          <div>
            <label htmlFor="cert-nome" className="mb-2 block text-sm font-medium">Identificação do certificado</label>
            <input id="cert-nome" className="campo-gnre" required maxLength={120}
              placeholder="Ex.: Certificado Escritório - 2026" value={nome}
              onChange={(e) => setNome(e.target.value)} />
          </div>
          <div>
            <label htmlFor="cert-arquivo" className="mb-2 block text-sm font-medium">Arquivo PFX/P12</label>
            <input key={limparArquivo} id="cert-arquivo" type="file" accept=".pfx,.p12" required
              className="campo-gnre" onChange={(e) => setArquivo(e.target.files?.[0] ?? null)} />
          </div>
          <div>
            <label htmlFor="cert-senha" className="mb-2 block text-sm font-medium">Senha do certificado</label>
            <input id="cert-senha" type="password" className="campo-gnre" autoComplete="off"
              value={senha} onChange={(e) => setSenha(e.target.value)}
              placeholder="Senha do arquivo A1" />
          </div>
          <button type="submit" disabled={ocupado} className="botao-primario">
            <FileKey2 size={17} /> {ocupado ? "Aguarde..." : "Cadastrar certificado"}
          </button>
        </form>

        <form onSubmit={(e) => void vincular(e)} className="card-gnre space-y-4 p-6">
          <div className="flex items-center gap-2">
            <Link2 size={20} className="text-gnre-green" />
            <h3 className="text-lg font-semibold">Vincular certificado ao Domínio</h3>
          </div>
          <p className="text-sm leading-6 text-slate-500">
            Um código Domínio terá um certificado A1 associado. Salvar um vínculo existente substitui o certificado anterior.
          </p>
          <div>
            <label htmlFor="cert-dominio" className="mb-2 block text-sm font-medium">Código Domínio</label>
            <input id="cert-dominio" className="campo-gnre" required maxLength={100}
              placeholder="Ex.: 2384" value={dominio}
              onChange={(e) => setDominio(e.target.value)} />
          </div>
          <div>
            <label htmlFor="cert-selecionado" className="mb-2 block text-sm font-medium">Certificado válido</label>
            <select id="cert-selecionado" className="campo-gnre" required
              value={certificadoSelecionado} onChange={(e) => setCertificadoSelecionado(e.target.value)}>
              <option value="">Selecione um certificado</option>
              {certificadosValidos.map((c) => (
                <option key={c.id} value={c.id}>{c.nome} (ID {c.id})</option>
              ))}
            </select>
          </div>
          <button type="submit" className="botao-primario" disabled={ocupado || !certificadosValidos.length}>
            <Link2 size={17} /> {ocupado ? "Aguarde..." : "Salvar vínculo"}
          </button>
        </form>
      </div>

      <section className="card-gnre overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-6 py-5">
          <div>
            <h3 className="text-lg font-semibold">Certificados cadastrados</h3>
            <p className="mt-1 text-xs text-slate-500">{certificados.length} certificado(s) no sistema</p>
          </div>
          <ShieldCheck className="text-gnre-green" size={22} />
        </div>
        {carregando ? (
          <p role="status" className="p-6 text-sm text-slate-500">Carregando certificados...</p>
        ) : certificados.length === 0 ? (
          <p className="p-6 text-sm text-slate-500">Nenhum certificado cadastrado.</p>
        ) : (
          <div className="grid gap-4 p-5 lg:grid-cols-2">
            {certificados.map((c) => {
              const quantidade = vinculos.filter((v) => v.certificado_id === c.id).length;
              return (
                <div key={c.id} className="min-w-0 rounded-xl border border-slate-200 bg-[#FAFBFA] p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h4 className="break-words font-semibold text-slate-800">{c.nome}</h4>
                      <p className="mt-1 text-xs text-slate-500">Identificação #{c.id}</p>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${corSituacao(c.situacao)}`}>
                      {nomeSituacao(c.situacao)}
                    </span>
                  </div>
                  <div className="mt-4 space-y-2 text-xs text-slate-600">
                    <p className="break-words"><strong>Titular:</strong> {c.titular}</p>
                    <p className="flex items-center gap-2"><CalendarClock size={14} /> Validade: {dataBR(c.valido_de)} a {dataBR(c.valido_ate)}</p>
                    <p><strong>Vínculos:</strong> {quantidade}</p>
                    <p className="break-words"><strong>Cadastrado por:</strong> {c.cadastrado_por}</p>
                  </div>
                  {c.ativo && (
                    <button type="button" className="mt-4 inline-flex items-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                      disabled={ocupado} onClick={() => void desativar(c)}>
                      <ShieldOff size={15} /> Desativar certificado
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="card-gnre overflow-hidden">
        <div className="border-b border-slate-100 px-6 py-5">
          <h3 className="text-lg font-semibold">Vínculos de empresas</h3>
          <p className="mt-1 text-xs text-slate-500">Associações de códigos Domínio aos certificados digitais.</p>
        </div>
        {!carregando && vinculos.length === 0 ? (
          <p className="p-6 text-sm text-slate-500">Nenhum vínculo cadastrado.</p>
        ) : (
          <div className="grid gap-3 p-5 md:grid-cols-2">
            {vinculos.map((v) => {
              const certificado = certificados.find((c) => c.id === v.certificado_id);
              return (
                <div key={v.codigo_dominio} className="flex min-w-0 items-start gap-3 rounded-xl border border-slate-200 p-4">
                  {certificado?.situacao === "valido"
                    ? <CheckCircle2 className="shrink-0 text-[#044055]" size={19} />
                    : <AlertCircle className="shrink-0 text-amber-700" size={19} />}
                  <div className="min-w-0">
                    <p className="font-semibold">Domínio {v.codigo_dominio}</p>
                    <p className="mt-1 break-words text-sm text-slate-600">{certificado?.nome ?? `Certificado ID ${v.certificado_id}`}</p>
                    <p className="mt-1 text-xs text-slate-500">Vinculado por {v.vinculado_por} • {dataBR(v.vinculado_em)}</p>
                    {certificado?.situacao !== "valido" && <p className="mt-2 text-xs text-amber-800">Certificado não disponível para novas operações.</p>}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
      <p className="flex items-start gap-2 text-xs leading-5 text-slate-500">
        <AlertCircle size={15} className="mt-0.5 shrink-0" />
        O cadastro ou vínculo do certificado não emite guias. A emissão GNRE continuará desabilitada até a homologação.
      </p>
    </div>
  );
}
