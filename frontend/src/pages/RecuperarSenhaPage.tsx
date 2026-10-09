import {
  useEffect,
  useState,
  type FormEvent,
} from "react";

import { Link, Navigate } from "react-router-dom";
import { Mail } from "lucide-react";

import AuthLayout from "../components/AuthLayout";
import { useAuth } from "../contexts/AuthContext";
import { requisicaoAuth } from "../services/authAPI";


export default function RecuperarSenhaPage() {
  const { usuario } = useAuth();

  const [email, setEmail] = useState("");

  const [disponivel, setDisponivel] =
    useState<boolean | null>(null);

  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState(false);


  useEffect(() => {
    let ativo = true;

    void requisicaoAuth<{ disponivel: boolean }>(
      "/recuperacao-disponivel"
    )
      .then((retorno) => {
        if (ativo) {
          setDisponivel(retorno.disponivel);
        }
      })
      .catch(() => {
        if (ativo) {
          setDisponivel(false);
        }
      });

    return () => {
      ativo = false;
    };
  }, []);


  if (usuario) {
    return <Navigate to="/dashboard" replace />;
  }


  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();

    setErro("");
    setEnviando(true);

    try {
      await requisicaoAuth<{ mensagem: string }>(
        "/esqueci-senha",
        {
          method: "POST",
          body: JSON.stringify({
            email: email.trim(),
          }),
        }
      );

      setSucesso(true);

    } catch (ex) {
      setErro(
        ex instanceof Error
          ? ex.message
          : "Não foi possível enviar o e-mail."
      );

    } finally {
      setEnviando(false);
    }
  }


  return (
    <AuthLayout
      titulo="Recuperar acesso"
      descricao="Enviaremos um link temporário ao e-mail cadastrado."
    >
      {sucesso ? (
        <div
          role="status"
          className="rounded-xl border border-[#C9DEDA] bg-[#E7F0F3] p-4 text-sm text-[#044055]"
        >
          Se o e-mail estiver cadastrado, você receberá
          instruções para redefinir sua senha.
        </div>

      ) : (
        <form
          onSubmit={(e) => void enviar(e)}
          className="space-y-5"
        >
          <div>
            <label
              htmlFor="rec-email"
              className="mb-2 block text-sm font-medium"
            >
              E-mail da conta
            </label>

            <input
              id="rec-email"
              type="email"
              className="campo-gnre"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          {disponivel === false && (
            <div
              role="status"
              className="rounded-xl bg-amber-50 p-3 text-sm text-amber-800"
            >
              A recuperação por e-mail ainda não está
              configurada neste ambiente. Solicite a
              configuração do Microsoft 365.
            </div>
          )}

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
            disabled={disponivel !== true || enviando}
          >
            <Mail size={17} />

            {enviando
              ? "Enviando..."
              : "Enviar link de recuperação"}
          </button>
        </form>
      )}

      <Link
        to="/login"
        className="mt-6 block text-center text-sm font-semibold text-gnre-green hover:underline"
      >
        Voltar ao login
      </Link>
    </AuthLayout>
  );
}
