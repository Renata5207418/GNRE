import {
  useState,
  type FormEvent,
} from "react";

import {
  Link,
  useSearchParams,
} from "react-router-dom";

import { LockKeyhole } from "lucide-react";

import AuthLayout from "../components/AuthLayout";
import { requisicaoAuth } from "../services/authAPI";


export default function RedefinirSenhaPage() {
  const [params] = useSearchParams();

  const token = params.get("token") ?? "";

  const [novaSenha, setNovaSenha] = useState("");
  const [confirmar, setConfirmar] = useState("");

  const [enviando, setEnviando] = useState(false);
  const [sucesso, setSucesso] = useState(false);
  const [erro, setErro] = useState("");


  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();

    setErro("");

    if (novaSenha !== confirmar) {
      setErro("As senhas não coincidem.");
      return;
    }

    setEnviando(true);

    try {
      await requisicaoAuth<{ mensagem: string }>(
        "/redefinir-senha",
        {
          method: "POST",
          body: JSON.stringify({
            token,
            nova_senha: novaSenha,
          }),
        }
      );

      setSucesso(true);

    } catch (ex) {
      setErro(
        ex instanceof Error
          ? ex.message
          : "Link inválido ou expirado."
      );

    } finally {
      setEnviando(false);
    }
  }


  return (
    <AuthLayout
      titulo="Definir nova senha"
      descricao="Escolha uma senha segura para sua conta GNRE."
    >
      {sucesso ? (
        <div className="space-y-5">
          <p
            role="status"
            className="rounded-xl bg-[#E7F0F3] p-4 text-sm text-[#044055]"
          >
            Senha alterada com sucesso. Suas sessões
            anteriores foram encerradas.
          </p>

          <Link
            to="/login"
            className="botao-primario w-full"
          >
            Ir para o login
          </Link>
        </div>

      ) : token.length < 20 ? (
        <div className="space-y-5">
          <p
            role="alert"
            className="rounded-xl bg-red-50 p-4 text-sm text-red-700"
          >
            O link está incompleto. Solicite uma nova
            recuperação de senha.
          </p>

          <Link
            to="/recuperar-senha"
            className="botao-secundario w-full"
          >
            Solicitar outro link
          </Link>
        </div>

      ) : (
        <form
          className="space-y-5"
          onSubmit={(e) => void enviar(e)}
        >
          <div>
            <label
              htmlFor="nova-senha"
              className="mb-2 block text-sm font-medium"
            >
              Nova senha
            </label>

            <input
              id="nova-senha"
              className="campo-gnre"
              type="password"
              autoComplete="new-password"
              minLength={12}
              maxLength={128}
              required
              value={novaSenha}
              onChange={(e) => setNovaSenha(e.target.value)}
            />

            <p className="mt-1 text-xs text-slate-500">
              De 12 a 128 caracteres.
            </p>
          </div>

          <div>
            <label
              htmlFor="confirmar-senha"
              className="mb-2 block text-sm font-medium"
            >
              Confirmar nova senha
            </label>

            <input
              id="confirmar-senha"
              className="campo-gnre"
              type="password"
              autoComplete="new-password"
              minLength={12}
              maxLength={128}
              required
              value={confirmar}
              onChange={(e) => setConfirmar(e.target.value)}
            />
          </div>

          {erro && (
            <p
              role="alert"
              className="rounded-xl bg-red-50 p-3 text-sm text-red-700"
            >
              {erro}
            </p>
          )}

          <button
            type="submit"
            className="botao-primario w-full"
            disabled={enviando}
          >
            <LockKeyhole size={17} />

            {enviando
              ? "Salvando..."
              : "Salvar nova senha"}
          </button>
        </form>
      )}
    </AuthLayout>
  );
}
