import { useState, type FormEvent } from "react";


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
  total_linhas: number;
  validas: number;
  ignoradas: number;
  com_erro: number;
  pronta_para_confirmacao: boolean;
  previa_limitada: boolean;
  linhas: Linha[];
  observacao: string;
};

export default function ImportarPlanilhaGNRE() {
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState("");

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
            setErro("");
          }}
          className="block w-full rounded-lg border border-slate-200 p-3 text-sm"
        />
        <p className="text-xs text-slate-500">
          Aceita .xlsx, até 5 MB e 5.000 linhas preenchidas.
        </p>
        <button
          type="submit"
          disabled={!arquivo || carregando}
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
                        <span className="text-green-700">Tudo certo</span>
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

          {resultado.pronta_para_confirmacao && (
            <p className="text-sm text-green-800">
              A pré-validação passou. A confirmação de emissão será
              implementada depois da integração com o worker GNRE.
            </p>
          )}
        </section>
      )}
    </section>
  );
}
