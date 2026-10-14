import { useEffect, useState, type FormEvent } from "react";


const API_URL = (
  import.meta.env.VITE_API_URL ?? ""
).replace(/\/$/, "");

type Linha = {
  linha_excel: number;
  status: "valida" | "ignorada" | "erro";
  erros: string[];
  avisos: string[];
  dados: Record<string, string | number>;
};

type Resultado = {
  arquivo: string;
  hash_arquivo: string;
  total_linhas: number;
  validas: number;
  ignoradas: number;
  com_erro: number;
  pronta_para_confirmacao: boolean;
  previa_limitada: boolean;
  linhas: Linha[];
  observacao: string;
};

type ResultadoWorker = {
  total_resultados: number;
  processadas: number;
  erro_validacao: number;
  erro_consulta: number;
  ignoradas: number;
  itens: {
    linha_excel?: number;
    status?: string;
    acao?: string;
    mensagem?: string;
    numero_recibo?: string;
  }[];
};

type LoteGNRE = {
  lote_id: string;
  arquivo: string;
  status: "processando" | "concluido" | "erro_revisao";
  mensagem?: string;
  resultado?: ResultadoWorker;
};

export default function ImportarPlanilhaGNRE() {
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState("");

  const [mostrarConfirmacao, setMostrarConfirmacao] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [lote, setLote] = useState<LoteGNRE | null>(null);

  async function validar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();

    if (!arquivo) {
      setErro("Selecione uma planilha .xlsx.");
      return;
    }

    setErro("");
    setResultado(null);
    setCarregando(true);

    try {
      const dados = new FormData();
      dados.append("arquivo", arquivo);

      const resposta = await fetch(`${API_URL}/api/planilhas/validar`, {
        method: "POST",
        body: dados,
      });

      const corpo = await resposta.json();

      if (!resposta.ok) {
        throw new Error(
          typeof corpo.detail === "string"
            ? corpo.detail
            : "Não foi possível validar a planilha."
        );
      }

      setResultado(corpo as Resultado);
    } catch (error) {
      setErro(
        error instanceof Error ? error.message : "Erro inesperado."
      );
        } finally {
      setCarregando(false);
    }
  }

    useEffect(() => {
      let ativo = true;

      async function recuperarLote() {
        try {
          const resposta = await fetch(
            `${API_URL}/api/planilhas/lotes`,
            {
              credentials: "include",
              cache: "no-store",
            }
          );

          if (!resposta.ok) {
            return;
          }

          const dados = await resposta.json() as {
            lotes: LoteGNRE[];
          };

          const pendente = dados.lotes.find(
            (item) =>
              item.status === "processando" ||
              item.status === "erro_revisao"
          );

          if (ativo && pendente) {
            setLote(pendente);
          }

        } catch {
          // A recuperação de status não impede
          // o uso da tela de validação.
        }
      }

      void recuperarLote();

      return () => {
        ativo = false;
      };
    }, []);

  async function confirmarEmissao() {
    if (
      !arquivo ||
      !resultado ||
      !resultado.hash_arquivo ||
      !resultado.pronta_para_confirmacao ||
      resultado.validas <= 0 ||
      resultado.com_erro > 0
    ) {
      setErro("Valide uma planilha sem erros antes de emitir.");
      return;
    }

    setEnviando(true);
    setErro("");

    try {
      const dados = new FormData();

      dados.append("arquivo", arquivo);
      dados.append("hash_validado", resultado.hash_arquivo);
      dados.append("confirmacao_explicita", "true");

      const resposta = await fetch(
        `${API_URL}/api/planilhas/confirmar`,
        {
          method: "POST",
          body: dados,
          credentials: "include",
        }
      );

      const corpo = await resposta.json();

      if (!resposta.ok) {
        throw new Error(
          typeof corpo.detail === "string"
            ? corpo.detail
            : "Não foi possível iniciar a emissão."
        );
      }

      setLote(corpo as LoteGNRE);
      setMostrarConfirmacao(false);

    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Erro ao confirmar a emissão."
      );

    } finally {
      setEnviando(false);
    }
  }

  useEffect(() => {
    if (!lote || lote.status !== "processando") {
      return;
    }

    let ativo = true;

    async function consultarLote() {
      try {
        const resposta = await fetch(
          `${API_URL}/api/planilhas/lotes/${lote!.lote_id}`,
          {
            credentials: "include",
            cache: "no-store",
          }
        );

        if (!resposta.ok) {
          throw new Error(
            "Não foi possível consultar o andamento do lote."
          );
        }

        const dados = await resposta.json();

        if (ativo) {
          setLote(dados as LoteGNRE);
        }

      } catch (error) {
        if (ativo) {
          setErro(
            error instanceof Error
              ? error.message
              : "Erro ao consultar o lote."
          );
        }
      }
    }

    void consultarLote();

    const intervalo = window.setInterval(() => {
      void consultarLote();
    }, 3000);

    return () => {
      ativo = false;
      window.clearInterval(intervalo);
    };

  }, [lote?.lote_id, lote?.status]);


  return (
    <section className="mx-auto max-w-5xl space-y-6 p-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-slate-900">
          Importar planilha GNRE
        </h1>
        <p className="text-sm text-slate-600">
          Baixe o modelo oficial do sistema, preencha e valide antes
          de confirmar as emissões. Nesta tela nenhuma GNRE é emitida.
        </p>
      </header>

      <div className="rounded-2xl border border-[#DCE5E8] bg-[#F5F9F9] p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-2xl">
            <h2 className="text-base font-semibold text-[#044055]">
              Modelo padrão da planilha
            </h2>

            <p className="mt-2 text-sm leading-6 text-slate-600">
              Utilize o modelo oficial do sistema para evitar erros
              no preenchimento. O vencimento é calculado no mês
              seguinte à competência.
            </p>
          </div>

          <a
            href={`${API_URL}/api/planilhas/modelo`}
            download
            className="botao-primario shrink-0"
          >
            Baixar modelo Excel
          </a>
        </div>
      </div>

      <form
        onSubmit={validar}
        className="space-y-4 rounded-xl border border-slate-200 bg-white p-5"
      >
        <label
          htmlFor="arquivo-gnre"
          className="block text-sm font-medium text-slate-800"
        >
          Selecione a planilha preenchida
        </label>
        <input
          id="arquivo-gnre"
          type="file"
          accept=".xlsx"
            onChange={(e) => {
            setArquivo(e.target.files?.[0] ?? null);
            setResultado(null);
            setLote(null);
            setMostrarConfirmacao(false);
            setErro("");
          }}
          disabled={enviando || lote?.status === "processando"}
          className="block w-full rounded-lg border border-slate-200 p-3 text-sm"
        />
        <p className="text-xs text-slate-500">
          Aceita .xlsx, até 5 MB e 5.000 linhas preenchidas.
        </p>
        <button
          type="submit"
          disabled={
            !arquivo ||
            carregando ||
            enviando ||
            lote?.status === "processando"
          }
          className="botao-primario"
        >
          {carregando ? "Validando..." : "Validar planilha"}
        </button>
      </form>

      {erro && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {erro}
        </div>
      )}

      {resultado && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-slate-900">
            Resultado da validação: {resultado.arquivo}
          </h2>
          <div className="grid gap-3 sm:grid-cols-4">
            {[
              ["Linhas", resultado.total_linhas],
              ["Válidas", resultado.validas],
              ["Ignoradas", resultado.ignoradas],
              ["Com erro", resultado.com_erro],
            ].map(([rotulo, numero]) => (
              <div
                key={rotulo}
                className="rounded-xl border border-slate-200 bg-white p-4"
              >
                <p className="text-sm text-slate-600">{rotulo}</p>
                <p className="mt-2 text-2xl font-semibold text-slate-950">
                  {numero}
                </p>
              </div>
            ))}
          </div>

          <p className="rounded-lg bg-slate-100 p-4 text-sm text-slate-700">
            {resultado.observacao}
          </p>

          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-4 py-3">Linha Excel</th>
                  <th className="px-4 py-3">Situação</th>
                  <th className="px-4 py-3">Código Domínio</th>
                  <th className="px-4 py-3">Vencimento</th>
                  <th className="px-4 py-3">Detalhes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {resultado.linhas.map((linha) => (
                  <tr key={linha.linha_excel}>
                    <td className="px-4 py-3">{linha.linha_excel}</td>
                    <td className="px-4 py-3 capitalize">{linha.status}</td>
                    <td className="px-4 py-3">
                      {linha.dados.codigo_dominio ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      {linha.dados.data_vencimento_calculada ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      {linha.erros.length ? (
                        <ul className="list-disc pl-4 text-red-700">
                          {linha.erros.map((mensagem, i) => (
                            <li key={i}>{mensagem}</li>
                          ))}
                        </ul>
                      ) : linha.avisos.length ? (
                        <ul className="list-disc pl-4 text-amber-700">
                          {linha.avisos.map((mensagem, i) => (
                            <li key={i}>{mensagem}</li>
                          ))}
                        </ul>
                      ) : (
                        <span className="font-medium text-green-700">Validada</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {resultado.previa_limitada && (
            <p className="text-sm text-slate-600">
              Exibindo somente as primeiras 200 linhas; todos os registros
              foram verificados e contabilizados.
            </p>
          )}


          {resultado.com_erro > 0 && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
              <p className="text-sm font-medium text-amber-900">
                A emissão está bloqueada porque existem erros na planilha.
              </p>

              <p className="mt-2 text-sm text-amber-800">
                Corrija os dados no Excel e valide novamente.
                Nenhuma guia foi enviada.
              </p>
            </div>
          )}

          {resultado.pronta_para_confirmacao &&
            resultado.validas > 0 &&
            resultado.com_erro === 0 &&
            !lote && (
              <div className="rounded-xl border border-green-200 bg-green-50 p-5">
                <h3 className="font-semibold text-green-900">
                  Planilha pronta para emissão
                </h3>

                <p className="mt-2 text-sm text-green-800">
                  {resultado.validas} linha(s) válida(s) para processamento.
                  Confira os valores, contribuintes e vencimentos
                  antes de continuar.
                </p>

                <button
                  type="button"
                  className="botao-primario mt-4"
                  disabled={enviando}
                  onClick={() => setMostrarConfirmacao(true)}
                >
                  Revisar e confirmar emissões
                </button>
              </div>
            )}
        </section>
      )}

      {lote && (
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold text-slate-900">
            Acompanhamento do lote
          </h2>

          <p className="text-sm text-slate-600">
            Arquivo: {lote.arquivo}
          </p>

          {lote.status === "processando" && (
            <div
              role="status"
              className="rounded-lg bg-blue-50 p-4 text-sm text-blue-800"
            >
              Processamento em andamento. A consulta do resultado
              é atualizada automaticamente.
            </div>
          )}

          {lote.status === "erro_revisao" && (
            <div
              role="alert"
              className="rounded-lg bg-red-50 p-4 text-sm text-red-800"
            >
              {lote.mensagem ??
                "O processamento exige revisão manual antes de outra emissão."}
            </div>
          )}

          {lote.status === "concluido" && lote.resultado && (
            <div className="space-y-4">
              <div
                role="status"
                className="rounded-lg bg-green-50 p-4 text-sm text-green-800"
              >
                O processamento do lote terminou.
                Confira os resultados individuais abaixo.
              </div>

              <div className="grid gap-3 sm:grid-cols-4">
                {[
                  ["Processadas", lote.resultado.processadas],
                  ["Erros de validação", lote.resultado.erro_validacao],
                  ["Erros de consulta", lote.resultado.erro_consulta],
                  ["Ignoradas", lote.resultado.ignoradas],
                ].map(([rotulo, quantidade]) => (
                  <div
                    key={rotulo}
                    className="rounded-xl border border-slate-200 p-4"
                  >
                    <p className="text-sm text-slate-600">
                      {rotulo}
                    </p>

                    <p className="mt-2 text-2xl font-semibold text-slate-950">
                      {quantidade}
                    </p>
                  </div>
                ))}
              </div>

              <div className="overflow-x-auto rounded-xl border border-slate-200">
                <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-4 py-3">Linha</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Ação</th>
                      <th className="px-4 py-3">Detalhes</th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-slate-100">
                    {lote.resultado.itens.slice(0, 100).map(
                      (item, index) => (
                        <tr key={`${item.linha_excel ?? "item"}-${index}`}>
                          <td className="px-4 py-3">
                            {item.linha_excel ?? "—"}
                          </td>

                          <td className="px-4 py-3">
                            {item.status ?? "—"}
                          </td>

                          <td className="px-4 py-3">
                            {item.acao ?? "—"}
                          </td>

                          <td className="px-4 py-3">
                            {item.mensagem ?? "—"}
                          </td>
                        </tr>
                      )
                    )}
                  </tbody>
                </table>
              </div>

              {lote.resultado.itens.length > 100 && (
                <p className="text-xs text-slate-500">
                  Exibindo os primeiros 100 resultados deste lote.
                </p>
              )}
            </div>
          )}
        </section>
      )}

      {mostrarConfirmacao && resultado && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="titulo-confirmar-gnre"
            className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl"
          >
            <h2
              id="titulo-confirmar-gnre"
              className="text-xl font-semibold text-slate-900"
            >
              Confirmar emissão GNRE
            </h2>

            <p className="mt-4 text-sm leading-6 text-slate-700">
              Você está prestes a iniciar o processamento
              de <strong>{resultado.validas}</strong> linha(s)
              válida(s) da planilha.
            </p>

            <p className="mt-3 text-sm leading-6 text-slate-700">
              O sistema verificará guias já existentes e poderá
              transmitir novas solicitações ao webservice GNRE.
            </p>

            <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
              Confirme somente após revisar os contribuintes,
              valores, receitas e vencimentos.
            </p>

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                className="botao-secundario"
                disabled={enviando}
                onClick={() => setMostrarConfirmacao(false)}
              >
                Cancelar
              </button>

              <button
                type="button"
                className="botao-primario"
                disabled={enviando}
                onClick={() => void confirmarEmissao()}
              >
                {enviando
                  ? "Iniciando..."
                  : "Confirmar e emitir"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

