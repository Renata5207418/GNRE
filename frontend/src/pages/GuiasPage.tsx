import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Download,
  FileSpreadsheet,
  RefreshCw,
  X,
} from "lucide-react";

import {
  baixarLoteGNRE,
  baixarPdfGNRE,
  exportarExcelGNRE,
} from "../services/arquivosGNRE";

type Guia = {
  id: number;
  codigo_dominio: string;
  uf_favorecida: string;
  mes: number;
  ano: number;
  status: string;
  valor_tipo_11: string | number;
  data_vencimento: string;
  numero_recibo: string | null;
  erro_mensagem: string | null;
  tem_pdf: boolean;
};

type Resultado = {
  total: number;
  pagina: number;
  por_pagina: number;
  total_paginas: number;
  items: Guia[];
};

type Filtros = {
  codigo_dominio: string;
  mes: string;
  ano: string;
  status: string;
  uf_favorecida: string;
};

type ResumoStatus = {
  por_status: { status: string; quantidade: number }[];
};

const FILTROS_VAZIOS: Filtros = {
  codigo_dominio: "",
  mes: "",
  ano: "",
  status: "",
  uf_favorecida: "",
};

const STATUS_PADRAO = [
  "Pendente",
  "Enviado",
  "Processado",
  "Erro no Envio",
  "Erro na Consulta",
  "Erro de Validação",
];

function formatarData(data: string): string {
  const partes = data?.slice(0, 10).split("-");
  return partes?.length === 3 ? partes.reverse().join("/") : data || "—";
}

function formatarMoeda(valor: string | number): string {
  return Number(valor).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function estiloStatus(status: string): string {
  const normalizado = status.toLocaleLowerCase("pt-BR");
  if (/erro|rejeit|falha/.test(normalizado)) {
    return "bg-red-50 text-red-700";
  }
  if (normalizado.includes("pendente")) {
    return "bg-amber-50 text-amber-800";
  }
  if (normalizado.includes("processado")) {
    return "bg-[#E7F0F3] text-[#044055]";
  }
  return "bg-[#F3EFE7] text-[#82663C]";
}

function StatusGuia({
  guia,
  onAbrir,
}: {
  guia: Guia;
  onAbrir: (guia: Guia) => void;
}) {
  const possuiDetalhes =
    Boolean(guia.erro_mensagem?.trim()) ||
    /erro|rejeit|falha/i.test(guia.status);

  const classe = [
    "inline-flex max-w-full items-center gap-1 rounded-full",
    "px-2.5 py-1 text-[11px] font-semibold break-words",
    estiloStatus(guia.status),
  ].join(" ");

  if (!possuiDetalhes) {
    return <span className={classe}>{guia.status}</span>;
  }

  return (
    <button
      type="button"
      onClick={() => onAbrir(guia)}
      aria-label={`Ver detalhes do processamento da guia ${guia.id}`}
      title="Clique para visualizar a mensagem completa"
      className="group flex max-w-full flex-col items-start gap-1 text-left"
    >
      <span className={`${classe} group-hover:ring-2 group-hover:ring-red-200`}>
        <AlertCircle size={12} className="shrink-0" />
        {guia.status}
      </span>
      <span className="text-[11px] text-red-700 group-hover:underline">
        Ver detalhes
      </span>
    </button>
  );
}

function ModalErro({
  guia,
  aoFechar,
}: {
  guia: Guia;
  aoFechar: () => void;
}) {
  const modalRef = useRef<HTMLDivElement>(null);
  const fecharRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const elementoAnterior = document.activeElement;
    const overflowAnterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    fecharRef.current?.focus();

    function aoTeclar(evento: KeyboardEvent) {
      if (evento.key === "Escape") {
        evento.preventDefault();
        aoFechar();
      }
      if (evento.key === "Tab" && modalRef.current) {
        const botoes = Array.from(
          modalRef.current.querySelectorAll<HTMLButtonElement>(
            'button:not([disabled])'
          )
        );
        if (!botoes.length) return;
        const primeiro = botoes[0];
        const ultimo = botoes[botoes.length - 1];
        if (evento.shiftKey && document.activeElement === primeiro) {
          evento.preventDefault();
          ultimo.focus();
        } else if (!evento.shiftKey && document.activeElement === ultimo) {
          evento.preventDefault();
          primeiro.focus();
        }
      }
    }

    document.addEventListener("keydown", aoTeclar);
    return () => {
      document.body.style.overflow = overflowAnterior;
      document.removeEventListener("keydown", aoTeclar);
      if (elementoAnterior instanceof HTMLElement) elementoAnterior.focus();
    };
  }, [aoFechar]);

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4"
      onMouseDown={(evento) => {
        if (evento.target === evento.currentTarget) aoFechar();
      }}
    >
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="titulo-erro-gnre"
        aria-describedby="mensagem-erro-gnre"
        className="w-full max-w-xl overflow-hidden rounded-2xl bg-white shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-6 py-5">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-red-50 p-3 text-red-700">
              <AlertCircle size={22} />
            </div>
            <div>
              <h2 id="titulo-erro-gnre" className="text-lg font-bold text-slate-800">
                Detalhes do processamento
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Informações registradas para esta guia
              </p>
            </div>
          </div>
          <button
            ref={fecharRef}
            type="button"
            aria-label="Fechar detalhes do erro"
            onClick={aoFechar}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"
          >
            <X size={20} />
          </button>
        </div>

        <div className="max-h-[65vh] space-y-5 overflow-y-auto px-6 py-5">
          <div className="grid grid-cols-2 gap-4 rounded-xl bg-[#F2F2F0] p-4 text-sm">
            <div>
              <p className="text-xs text-slate-500">Código Domínio</p>
              <p className="mt-1 font-semibold">{guia.codigo_dominio}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">UF favorecida</p>
              <p className="mt-1 font-semibold">{guia.uf_favorecida}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Competência</p>
              <p className="mt-1 font-semibold">
                {String(guia.mes).padStart(2, "0")}/{guia.ano}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Valor</p>
              <p className="mt-1 font-semibold">{formatarMoeda(guia.valor_tipo_11)}</p>
            </div>
            <div className="col-span-2">
              <p className="text-xs text-slate-500">Número do recibo</p>
              <p className="mt-1 break-all font-semibold">
                {guia.numero_recibo || "Não informado"}
              </p>
            </div>
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Situação da guia
            </p>
            <span className={`inline-flex rounded-full px-3 py-1.5 text-xs font-semibold ${estiloStatus(guia.status)}`}>
              {guia.status}
            </span>
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Mensagem completa
            </p>
            <div
              id="mensagem-erro-gnre"
              className="rounded-xl border border-red-100 bg-red-50 p-4"
            >
              <p className="whitespace-pre-wrap break-words text-sm leading-6 text-red-800">
                {guia.erro_mensagem?.trim() ||
                  "Este registro não possui uma descrição de erro armazenada no banco."}
              </p>
            </div>
          </div>
        </div>

        <div className="flex justify-end border-t border-slate-100 bg-[#FAFAF9] px-6 py-4">
          <button type="button" className="botao-primario" onClick={aoFechar}>
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}

export default function GuiasPage() {
  const [filtros, setFiltros] = useState<Filtros>({ ...FILTROS_VAZIOS });
  const [aplicados, setAplicados] = useState<Filtros>({ ...FILTROS_VAZIOS });
  const [statusDisponiveis, setStatusDisponiveis] = useState(STATUS_PADRAO);
  const [dados, setDados] = useState<Resultado | null>(null);
  const [pagina, setPagina] = useState(1);
  const [selecionadas, setSelecionadas] = useState<number[]>([]);
  const [carregando, setCarregando] = useState(false);
  const [executando, setExecutando] = useState(false);
  const [erro, setErro] = useState("");
  const [versao, setVersao] = useState(0);
  const [guiaErro, setGuiaErro] = useState<Guia | null>(null);
  const buscaPendente = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fecharModal = useCallback(() => setGuiaErro(null), []);

  useEffect(() => {
    const controller = new AbortController();
    async function carregarStatus() {
      try {
        const resposta = await fetch("/api/dashboard/resumo", {
          signal: controller.signal,
          credentials: "include",
        });
        if (!resposta.ok) return;
        const resumo: ResumoStatus = await resposta.json();
        const reais = (resumo.por_status ?? [])
          .map((item) => item.status)
          .filter((status): status is string => Boolean(status));
        const lista = [...new Set([...STATUS_PADRAO, ...reais])]
          .sort((a, b) => a.localeCompare(b, "pt-BR"));
        if (!controller.signal.aborted) setStatusDisponiveis(lista);
      } catch {
        // Mantém a lista padrão se o resumo estiver indisponível.
      }
    }
    void carregarStatus();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    async function carregarGuias() {
      setCarregando(true);
      setErro("");
      setSelecionadas([]);
      const params = new URLSearchParams({
        pagina: String(pagina),
        por_pagina: "30",
      });
      Object.entries(aplicados).forEach(([campo, valor]) => {
        if (valor.trim()) params.set(campo, valor.trim());
      });
      try {
        const resposta = await fetch(`/api/guias?${params}`, {
          signal: controller.signal,
          credentials: "include",
        });
        if (!resposta.ok) {
          throw new Error(`Erro ao consultar guias: HTTP ${resposta.status}`);
        }
        const resultado: Resultado = await resposta.json();
        if (!controller.signal.aborted) setDados(resultado);
      } catch (e) {
        if (!controller.signal.aborted) {
          setErro(e instanceof Error ? e.message : "Erro inesperado.");
          setDados(null);
        }
      } finally {
        if (!controller.signal.aborted) setCarregando(false);
      }
    }
    void carregarGuias();
    return () => controller.abort();
  }, [aplicados, pagina, versao]);

  useEffect(() => {
    return () => {
      if (buscaPendente.current) clearTimeout(buscaPendente.current);
    };
  }, []);

  function alterarFiltro(campo: keyof Filtros, valor: string) {
    const proximos = { ...filtros, [campo]: valor };
    setFiltros(proximos);
    if (buscaPendente.current) {
      clearTimeout(buscaPendente.current);
      buscaPendente.current = null;
    }
    const aplicar = () => {
      setPagina(1);
      setAplicados(proximos);
      buscaPendente.current = null;
    };
    if (campo === "mes" || campo === "status") {
      aplicar();
    } else {
      buscaPendente.current = setTimeout(aplicar, 400);
    }
  }

  function limparFiltros() {
    if (buscaPendente.current) {
      clearTimeout(buscaPendente.current);
      buscaPendente.current = null;
    }
    setFiltros({ ...FILTROS_VAZIOS });
    setPagina(1);
    setAplicados({ ...FILTROS_VAZIOS });
  }

  const guias = dados?.items ?? [];
  const guiasComPdf = guias.filter((guia) => guia.tem_pdf);
  const todasMarcadas =
    guiasComPdf.length > 0 &&
    guiasComPdf.every((guia) => selecionadas.includes(guia.id));

  function marcarGuia(id: number, marcar: boolean) {
    setSelecionadas((atual) =>
      marcar
        ? [...new Set([...atual, id])]
        : atual.filter((selecionada) => selecionada !== id)
    );
  }

  function marcarTodas(marcar: boolean) {
    setSelecionadas(marcar ? guiasComPdf.map((guia) => guia.id) : []);
  }

  async function executar(acao: () => Promise<void>) {
    setExecutando(true);
    setErro("");
    try {
      await acao();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao realizar a operação.");
    } finally {
      setExecutando(false);
    }
  }

  function exportar() {
    return exportarExcelGNRE({
      codigo_dominio: aplicados.codigo_dominio || undefined,
      mes: aplicados.mes ? Number(aplicados.mes) : undefined,
      ano: aplicados.ano ? Number(aplicados.ano) : undefined,
      status: aplicados.status || undefined,
      uf_favorecida: aplicados.uf_favorecida || undefined,
    });
  }

  function pdfDaGuia(guia: Guia) {
    if (!guia.tem_pdf) {
      return <span className="text-[11px] text-slate-400">Indisponível</span>;
    }
    return (
      <button
        type="button"
        title="Baixar PDF"
        aria-label={`Baixar PDF da guia ${guia.id}`}
        disabled={executando}
        onClick={() => void executar(() => baixarPdfGNRE(guia.id))}
        className="inline-flex items-center justify-center rounded-lg p-2 text-[#044055] hover:bg-[#E7F0F3] disabled:opacity-50"
      >
        <Download size={17} />
      </button>
    );
  }

  return (
    <div className="min-w-0 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gnre-text">Acompanhamento de guias</h2>
          <p className="mt-1 text-sm text-slate-500">
            Consulte, filtre e baixe as guias GNRE registradas.
          </p>
        </div>
        <button
          type="button"
          className="botao-secundario"
          disabled={carregando}
          onClick={() => setVersao((v) => v + 1)}
        >
          <RefreshCw size={16} /> Atualizar
        </button>
      </div>

      <div className="card-gnre space-y-4 p-5">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <input
            className="campo-gnre min-w-0"
            aria-label="Filtrar por código Domínio"
            placeholder="Código Domínio"
            value={filtros.codigo_dominio}
            onChange={(e) => alterarFiltro("codigo_dominio", e.target.value)}
          />
          <select
            className="campo-gnre min-w-0"
            aria-label="Filtrar por mês"
            value={filtros.mes}
            onChange={(e) => alterarFiltro("mes", e.target.value)}
          >
            <option value="">Todos os meses</option>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((mes) => (
              <option key={mes} value={mes}>
                {String(mes).padStart(2, "0")}
              </option>
            ))}
          </select>
          <input
            className="campo-gnre min-w-0"
            type="number"
            aria-label="Filtrar por ano"
            placeholder="Ano"
            value={filtros.ano}
            onChange={(e) => alterarFiltro("ano", e.target.value)}
          />
          <select
            className="campo-gnre min-w-0"
            aria-label="Filtrar por status"
            value={filtros.status}
            onChange={(e) => alterarFiltro("status", e.target.value)}
          >
            <option value="">Todos os status</option>
            {statusDisponiveis.map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>
          <input
            className="campo-gnre min-w-0"
            aria-label="Filtrar por UF"
            placeholder="UF (ex.: SP)"
            maxLength={2}
            value={filtros.uf_favorecida}
            onChange={(e) => alterarFiltro("uf_favorecida", e.target.value.toUpperCase())}
          />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs text-slate-500">
            A busca é atualizada automaticamente.
          </span>
          <button type="button" className="botao-secundario" onClick={limparFiltros}>
            Limpar filtros
          </button>
        </div>
      </div>

      {erro && (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {erro}
        </div>
      )}

      <section className="card-gnre min-w-0 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 p-5">
          <div>
            <h3 className="font-semibold">Resultados encontrados</h3>
            <p className="mt-1 text-xs text-slate-500">
              {dados?.total ?? 0} guias • {selecionadas.length} selecionadas nesta página
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="botao-secundario"
              disabled={executando || selecionadas.length === 0}
              onClick={() => void executar(() => baixarLoteGNRE(selecionadas))}
            >
              <Download size={16} /> Baixar selecionadas
            </button>
            <button
              type="button"
              className="botao-secundario"
              disabled={executando}
              onClick={() => void executar(exportar)}
            >
              <FileSpreadsheet size={16} /> Exportar Excel
            </button>
          </div>
        </div>

        <table className="hidden w-full table-fixed border-collapse text-left text-xs lg:table">
          <colgroup>
            <col style={{ width: "5%" }} />
            <col style={{ width: "12%" }} />
            <col style={{ width: "17%" }} />
            <col style={{ width: "16%" }} />
            <col style={{ width: "21%" }} />
            <col style={{ width: "19%" }} />
            <col style={{ width: "10%" }} />
          </colgroup>
          <thead className="bg-[#F7F8F6] text-slate-500">
            <tr>
              <th className="px-2 py-4 text-center">
                <input
                  type="checkbox"
                  aria-label="Selecionar PDFs da página"
                  checked={todasMarcadas}
                  onChange={(e) => marcarTodas(e.target.checked)}
                />
              </th>
              <th className="px-2 py-4">Empresa</th>
              <th className="px-2 py-4">Referência</th>
              <th className="px-2 py-4">Valor</th>
              <th className="px-2 py-4">Status</th>
              <th className="px-2 py-4">Recibo</th>
              <th className="px-2 py-4 text-center">PDF</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {carregando && (
              <tr><td colSpan={7} className="px-4 py-10 text-center text-slate-500">Carregando guias...</td></tr>
            )}
            {!carregando && guias.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-10 text-center text-slate-500">Nenhuma guia encontrada.</td></tr>
            )}
            {!carregando && guias.map((guia) => (
              <tr key={guia.id} className="hover:bg-[#F8F9F9]">
                <td className="px-2 py-3 text-center">
                  <input
                    type="checkbox"
                    aria-label={`Selecionar guia ${guia.id}`}
                    disabled={!guia.tem_pdf}
                    checked={selecionadas.includes(guia.id)}
                    onChange={(e) => marcarGuia(guia.id, e.target.checked)}
                  />
                </td>
                <td className="px-2 py-3">
                  <p className="font-semibold text-slate-800">{guia.codigo_dominio}</p>
                  <p className="mt-1 text-[11px] text-slate-500">UF: {guia.uf_favorecida}</p>
                </td>
                <td className="px-2 py-3">
                  <p className="font-medium">{String(guia.mes).padStart(2, "0")}/{guia.ano}</p>
                  <p className="mt-1 text-[11px] text-slate-500">Venc. {formatarData(guia.data_vencimento)}</p>
                </td>
                <td className="px-2 py-3 font-medium tabular-nums">{formatarMoeda(guia.valor_tipo_11)}</td>
                <td className="min-w-0 px-2 py-3">
                  <StatusGuia guia={guia} onAbrir={setGuiaErro} />
                </td>
                <td className="break-all px-2 py-3 text-[11px] text-slate-600">{guia.numero_recibo || "—"}</td>
                <td className="px-2 py-3 text-center">{pdfDaGuia(guia)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="divide-y divide-slate-100 lg:hidden">
          {!carregando && guiasComPdf.length > 0 && (
            <label className="flex items-center gap-2 bg-[#F7F8F6] px-5 py-3 text-xs text-slate-600">
              <input
                type="checkbox"
                checked={todasMarcadas}
                onChange={(e) => marcarTodas(e.target.checked)}
              />
              Selecionar PDFs desta página
            </label>
          )}
          {carregando && <p className="p-6 text-center text-sm text-slate-500">Carregando guias...</p>}
          {!carregando && guias.length === 0 && <p className="p-6 text-center text-sm text-slate-500">Nenhuma guia encontrada.</p>}
          {!carregando && guias.map((guia) => (
            <div key={guia.id} className="space-y-3 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    aria-label={`Selecionar guia ${guia.id}`}
                    disabled={!guia.tem_pdf}
                    checked={selecionadas.includes(guia.id)}
                    onChange={(e) => marcarGuia(guia.id, e.target.checked)}
                  />
                  <div>
                    <p className="font-semibold">Domínio {guia.codigo_dominio}</p>
                    <p className="text-xs text-slate-500">
                      {guia.uf_favorecida} • {String(guia.mes).padStart(2, "0")}/{guia.ano}
                    </p>
                  </div>
                </div>
                <StatusGuia guia={guia} onAbrir={setGuiaErro} />
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <p className="text-slate-500">Valor</p>
                  <p className="mt-1 font-semibold">{formatarMoeda(guia.valor_tipo_11)}</p>
                </div>
                <div>
                  <p className="text-slate-500">Vencimento</p>
                  <p className="mt-1 font-medium">{formatarData(guia.data_vencimento)}</p>
                </div>
                <div className="col-span-2 min-w-0">
                  <p className="text-slate-500">Recibo</p>
                  <p className="mt-1 break-all">{guia.numero_recibo || "—"}</p>
                </div>
              </div>
              {guia.tem_pdf && (
                <button
                  type="button"
                  className="botao-secundario w-full"
                  disabled={executando}
                  onClick={() => void executar(() => baixarPdfGNRE(guia.id))}
                >
                  <Download size={15} /> Baixar PDF
                </button>
              )}
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 p-5">
          <p className="text-xs text-slate-500">
            Página {pagina} de {Math.max(1, dados?.total_paginas ?? 1)}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              className="botao-secundario"
              disabled={pagina <= 1 || carregando}
              onClick={() => setPagina((atual) => atual - 1)}
            >
              Anterior
            </button>
            <button
              type="button"
              className="botao-secundario"
              disabled={carregando || pagina >= (dados?.total_paginas ?? 1)}
              onClick={() => setPagina((atual) => atual + 1)}
            >
              Próxima
            </button>
          </div>
        </div>
      </section>

      {guiaErro && <ModalErro guia={guiaErro} aoFechar={fecharModal} />}
    </div>
  );
}