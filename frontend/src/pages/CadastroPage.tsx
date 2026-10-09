import { useState, type FormEvent } from "react";
import {
  Link,
  Navigate,
  useNavigate,
} from "react-router-dom";

import { UserRoundPlus } from "lucide-react";

import AuthLayout from "../components/AuthLayout";
import { useAuth } from "../contexts/AuthContext";

import {
  requisicaoAuth,
  type UsuarioGNRE,
} from "../services/authAPI";

export default function CadastroPage() {
  const { usuario } = useAuth();
  const navegar = useNavigate();

  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  if (usuario) {
    return <Navigate to="/dashboard" replace />;
  }

  async function cadastrar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErro("");

    if (senha !== confirmacao) {
      setErro("As senhas não coincidem.");
      return;
    }

    if (senha.length < 12 || senha.length > 128) {
      setErro(
        "A senha deve ter entre 12 e 128 caracteres."
      );
      return;
    }

    setEnviando(true);

    try {
      await requisicaoAuth<UsuarioGNRE>("/cadastro", {
        method: "POST",
        body: JSON.stringify({
          nome: nome.trim(),
          email: email.trim(),
          senha,
        }),
      });

      navegar("/login", {
        replace: true,
        state: {
          email: email.trim(),
        },
      });
    } catch (ex) {
      setErro(
        ex instanceof Error
          ? ex.message
          : "Erro ao criar conta."
      );
    } finally {
      setEnviando(false);
    }
  }

  return (
    <AuthLayout
      titulo="Criar minha conta"
      descricao="Cadastre seus dados para ter acesso às ferramentas do GNRE."
    >
      <form
        onSubmit={(e) => void cadastrar(e)}
        className="space-y-4"
      >
        <div>
          <label
            htmlFor="cadastro-nome"
            className="mb-2 block text-sm font-medium"
          >
            Nome completo
          </label>

          <input
            id="cadastro-nome"
            className="campo-gnre"
            autoComplete="name"
            required
            minLength={2}
            maxLength={120}
            value={nome}
            onChange={(e) => setNome(e.target.value)}
          />
        </div>

        <div>
          <label
            htmlFor="cadastro-email"
            className="mb-2 block text-sm font-medium"
          >
            E-mail
          </label>

          <input
            id="cadastro-email"
            className="campo-gnre"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div>
          <label
            htmlFor="cadastro-senha"
            className="mb-2 block text-sm font-medium"
          >
            Senha
          </label>

          <input
            id="cadastro-senha"
            className="campo-gnre"
            type="password"
            autoComplete="new-password"
            minLength={12}
            maxLength={128}
            required
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />

          <p className="mt-1 text-xs text-slate-500">
            Mínimo de 12 caracteres.
          </p>
        </div>

        <div>
          <label
            htmlFor="cadastro-confirme"
            className="mb-2 block text-sm font-medium"
          >
            Confirmar senha
          </label>

          <input
            id="cadastro-confirme"
            className="campo-gnre"
            type="password"
            autoComplete="new-password"
            minLength={12}
            maxLength={128}
            required
            value={confirmacao}
            onChange={(e) => setConfirmacao(e.target.value)}
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
          <UserRoundPlus size={17} />
          {enviando ? "Criando conta..." : "Criar conta"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-600">
        Já tem conta?{" "}
        <Link
          to="/login"
          className="font-semibold text-gnre-green hover:underline"
        >
          Entrar
        </Link>
      </p>
    </AuthLayout>
  );
}
