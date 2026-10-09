import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut, UserRound } from "lucide-react";

import { useAuth } from "../contexts/AuthContext";

export default function ContaPage() {
  const { usuario, sair } = useAuth();
  const navegar = useNavigate();

  const [saindo, setSaindo] = useState(false);
  const [erro, setErro] = useState("");

  async function sairDaConta() {
    setSaindo(true);
    setErro("");

    try {
      await sair();
      navegar("/login", { replace: true });
    } catch (ex) {
      setErro(
        ex instanceof Error
          ? ex.message
          : "Falha ao sair da conta."
      );
    } finally {
      setSaindo(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gnre-text">
          Minha conta
        </h2>

        <p className="mt-1 text-sm text-slate-500">
          Seus dados de acesso ao sistema GNRE.
        </p>
      </div>

      <section className="card-gnre p-6">
        <div className="mb-6 flex items-center gap-3">
          <div className="rounded-xl bg-[#E7F0F3] p-3 text-gnre-green">
            <UserRound size={26} />
          </div>

          <div>
            <h3 className="font-semibold">
              Perfil do usuário
            </h3>

            <p className="text-xs text-slate-500">
              Conta individual
            </p>
          </div>
        </div>

        <dl className="grid gap-5 sm:grid-cols-2">
          <div>
            <dt className="text-xs text-slate-500">
              Nome
            </dt>

            <dd className="mt-1 font-medium">
              {usuario?.nome}
            </dd>
          </div>

          <div>
            <dt className="text-xs text-slate-500">
              E-mail
            </dt>

            <dd className="mt-1 break-all font-medium">
              {usuario?.email}
            </dd>
          </div>
        </dl>

        <div className="mt-7 border-t border-slate-100 pt-6">
          <p className="mb-4 text-sm text-slate-500">
            Todos os usuários cadastrados possuem acesso
            às funcionalidades operacionais do GNRE.
          </p>

          {erro && (
            <p
              role="alert"
              className="mb-4 rounded-xl bg-red-50 p-3 text-sm text-red-700"
            >
              {erro}
            </p>
          )}

          <button
            type="button"
            className="botao-secundario"
            disabled={saindo}
            onClick={() => void sairDaConta()}
          >
            <LogOut size={17} />
            {saindo
              ? "Saindo..."
              : "Sair da minha conta"}
          </button>
        </div>
      </section>
    </div>
  );
}
