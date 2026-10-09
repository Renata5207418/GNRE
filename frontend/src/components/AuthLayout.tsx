
import type { ReactNode } from "react";
import { ShieldCheck } from "lucide-react";

export default function AuthLayout({
  titulo,
  descricao,
  children,
}: {
  titulo: string;
  descricao: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-dvh bg-gnre-bg lg:grid lg:grid-cols-[43%_57%]">

      {/* =====================================
          PAINEL ESQUERDO - INSTITUCIONAL
         ===================================== */}

      <aside
        className="
          relative hidden min-h-dvh
          overflow-hidden bg-[#044055]
          px-10 py-12 text-white
          lg:flex lg:items-center lg:justify-center
        "
      >
        {/* Detalhes discretos no fundo */}

        <div className="pointer-events-none absolute -bottom-40 -left-32 h-80 w-80 rounded-full border border-white/10" />

        <div className="pointer-events-none absolute -bottom-28 -left-20 h-64 w-64 rounded-full border border-white/10" />

        {/* Conteúdo centralizado */}

        <div className="relative z-10 w-full max-w-[440px]">

          <div className="mb-7 flex items-center gap-3">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10">
              <ShieldCheck
                size={28}
                aria-hidden="true"
              />
            </div>

            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/70">
                Plataforma GNRE
              </p>

              <p className="mt-1 text-sm text-white/50">
                Gestão de Guias
              </p>
            </div>
          </div>

          <h2 className="text-3xl font-semibold leading-tight tracking-tight xl:text-4xl">
            Gestão de guias com clareza e segurança.
          </h2>

          <p className="mt-6 max-w-[390px] text-sm leading-7 text-white/75 xl:text-base">
            Em um só lugar: acompanhamento, arquivos,
            planilhas e certificados digitais.
          </p>

          <div className="mt-9 h-px w-24 bg-[#B39C74]" />
        </div>

        {/* Rodapé do painel */}

        <p className="absolute bottom-8 left-10 text-xs text-white/45">
          GNRE • Sistema de uso interno
        </p>
      </aside>


      {/* =====================================
          PAINEL DIREITO - FORMULÁRIO
         ===================================== */}

      <main
        className="
          flex min-h-dvh items-center justify-center
          px-5 py-10 sm:px-10
        "
      >
        <div className="w-full max-w-md">

          <div className="card-gnre p-6 shadow-sm sm:p-9">

            {/* LOGO INTEGRADA AO CARTÃO BRANCO */}

            <div className="mb-7 flex justify-start">
              <img
                src="/gnre.png"
                alt="GNRE - Gestão de Guias"
                className="h-[72px] w-auto max-w-[210px] object-contain"
              />
            </div>

            {/* TÍTULO */}

            <h1 className="text-2xl font-bold tracking-tight text-gnre-text">
              {titulo}
            </h1>

            {/* DESCRIÇÃO */}

            <p className="mb-7 mt-2 text-sm leading-6 text-slate-500">
              {descricao}
            </p>

            {/* CAMPOS DA PÁGINA */}

            {children}

          </div>

          {/* RODAPÉ */}

          <p className="mt-6 text-center text-xs text-slate-500">
            Utilize sua conta individual para acessar o GNRE.
          </p>

        </div>
      </main>
    </div>
  );
}
