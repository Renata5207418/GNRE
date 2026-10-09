import { useEffect, useState } from "react";
import {
  FileText,
  FileCheck2,
  FileWarning,
  RefreshCw,
  ArrowRight,
} from "lucide-react";
import { Link } from "react-router-dom";


type Resumo = {
  total_guias: number;
  guias_com_pdf: number;
  guias_sem_pdf: number;
  por_status: {
    status: string;
    quantidade: number;
  }[];
};


export default function DashboardPage() {
  const [dados, setDados] = useState<Resumo | null>(null);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function carregar() {
      setCarregando(true);
      setErro("");

      try {
        const resposta = await fetch(
          "/api/dashboard/resumo",
          { signal: controller.signal }
        );

        if (!resposta.ok) {
          throw new Error(
            `Erro ao carregar dashboard: HTTP ${resposta.status}`
          );
        }

        const resultado = await resposta.json();

        if (!controller.signal.aborted) {
          setDados(resultado);
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          setErro(
            e instanceof Error ? e.message : "Erro inesperado."
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setCarregando(false);
        }
      }
    }

    void carregar();

    return () => controller.abort();
  }, [versao]);

  const indicadores = [
    {
      titulo: "Total de guias",
      valor: dados?.total_guias ?? 0,
      icone: FileText,
      cor: "bg-[#EEF0ED] text-[#52655E]",
    },
    {
      titulo: "PDFs disponíveis",
      valor: dados?.guias_com_pdf ?? 0,
      icone: FileCheck2,
      cor: "bg-[#E6EFE9] text-[#38684A]",
    },
    {
      titulo: "Sem PDF",
      valor: dados?.guias_sem_pdf ?? 0,
      icone: FileWarning,
      cor: "bg-[#F5EBDC] text-[#9A7949]",
    },
  ];

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-gnre-text">
            Visão geral
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Acompanhe os registros e resultados das guias GNRE.
          </p>
        </div>

        <button
          className="botao-secundario"
          onClick={() => setVersao((v) => v + 1)}
          disabled={carregando}
        >
          <RefreshCw size={16} />
          Atualizar
        </button>
      </div>

      {erro && (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {erro}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {indicadores.map((indicador) => {
          const Icone = indicador.icone;

          return (
            <div key={indicador.titulo} className="card-gnre p-5">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">
                  {indicador.titulo}
                </span>

                <div className={`rounded-xl p-2.5 ${indicador.cor}`}>
                  <Icone size={21} />
                </div>
              </div>

              <div className="mt-5 text-3xl font-bold tabular-nums text-gnre-text">
                {carregando && !dados
                  ? "..."
                  : indicador.valor.toLocaleString("pt-BR")}
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <section className="card-gnre p-6 xl:col-span-2">
          <h3 className="text-lg font-semibold">
            Distribuição por status
          </h3>

          <p className="mt-1 text-sm text-gray-500">
            Quantidade de registros em cada situação.
          </p>

          <div className="mt-7 space-y-6">
            {!dados?.por_status.length && !carregando && (
              <p className="text-sm text-gray-500">
                Nenhum registro encontrado.
              </p>
            )}

            {dados?.por_status.map((item) => {
              const percentual = dados.total_guias
                ? (item.quantidade / dados.total_guias) * 100
                : 0;

              return (
                <div key={item.status}>
                  <div className="mb-2 flex justify-between gap-3 text-sm">
                    <span className="font-medium">
                      {item.status}
                    </span>
                    <span className="tabular-nums text-gray-500">
                      {item.quantidade.toLocaleString("pt-BR")}
                    </span>
                  </div>

                  <div className="h-2.5 overflow-hidden rounded-full bg-[#E9ECE7]">
                    <div
                      className="h-full rounded-full bg-gnre-green"
                      style={{
                        width: `${percentual}%`,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="card-gnre flex flex-col justify-between p-6">
          <div>
            <h3 className="text-lg font-semibold">
              Acesso rápido
            </h3>

            <p className="mt-2 text-sm leading-6 text-gray-500">
              Consulte documentos existentes ou valide
              uma nova planilha GNRE.
            </p>
          </div>

          <div className="mt-8 space-y-3">
            <Link
              to="/guias"
              className="botao-primario w-full"
            >
              Acompanhar guias
              <ArrowRight size={16} />
            </Link>

            <Link
              to="/importar"
              className="botao-secundario w-full"
            >
              Importar planilha
              <ArrowRight size={16} />
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
