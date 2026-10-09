import { useState, type FormEvent } from "react";
import {
  LogIn,
  Eye,
  EyeOff,
} from "lucide-react";
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
} from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { useAuth } from "../contexts/AuthContext";


export default function LoginPage() {
  const { usuario, entrar } = useAuth();

  const navegar = useNavigate();
  const local = useLocation();

  const estado = local.state as {
    from?: string;
    email?: string;
  } | null;

  const destino =
    estado?.from?.startsWith("/") &&
    !estado.from.startsWith("//")
      ? estado.from
      : "/dashboard";

  // ==========================================
  // ESTADOS
  // ==========================================
  const [email, setEmail] = useState(estado?.email ?? "");
  const [senha, setSenha] = useState("");
  const [lembrar, setLembrar] = useState(false);
  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);


  // ==========================================
  // REDIRECIONAMENTO
  // ==========================================
  if (usuario) {
    return <Navigate to={destino} replace />;
  }


  // ==========================================
  // REALIZAR LOGIN
  // ==========================================
  async function enviar(
    e: FormEvent<HTMLFormElement>
  ) {
    e.preventDefault();

    setEnviando(true);
    setErro("");

    try {
      await entrar(
        email.trim(),
        senha,
        lembrar
      );

      navegar(destino, {
        replace: true,
      });

    } catch (ex) {
      setErro(
        ex instanceof Error
          ? ex.message
          : "Não foi possível entrar."
      );

    } finally {
      setEnviando(false);
    }
  }


  // ==========================================
  // INTERFACE
  // ==========================================
  return (
    <AuthLayout
      titulo="Bem-vindo ao GNRE"
      descricao="Entre para acessar suas guias e documentos."
    >
      <form
        onSubmit={(e) => void enviar(e)}
        className="space-y-5"
      >

        {/* ===================================
            CAMPO E-MAIL
           =================================== */}
        <div>
          <label
            htmlFor="login-email"
            className="mb-2 block text-sm font-medium"
          >
            E-mail
          </label>

          <input
            id="login-email"
            className="campo-gnre"
            type="email"
            autoComplete="username"
            placeholder="seu.email@empresa.com.br"
            required
            value={email}
            onChange={(e) =>
              setEmail(e.target.value)
            }
          />
        </div>


        {/* ===================================
            CAMPO SENHA
           =================================== */}
        <div>
          <div className="mb-2 flex items-center justify-between gap-2">
            <label
              htmlFor="login-senha"
              className="text-sm font-medium"
            >
              Senha
            </label>

            <Link
              to="/recuperar-senha"
              className="text-xs font-semibold text-gnre-green hover:underline"
            >
              Esqueci minha senha
            </Link>
          </div>

          <div className="relative">

            <input
              id="login-senha"
              className="campo-gnre pr-12"
              type={
                mostrarSenha
                  ? "text"
                  : "password"
              }
              autoComplete="current-password"
              placeholder="Digite sua senha"
              required
              value={senha}
              onChange={(e) =>
                setSenha(e.target.value)
              }
            />

            <button
              type="button"
              onClick={() =>
                setMostrarSenha((atual) => !atual)
              }
              aria-label={
                mostrarSenha
                  ? "Ocultar senha"
                  : "Mostrar senha"
              }
              aria-pressed={mostrarSenha}
              title={
                mostrarSenha
                  ? "Ocultar senha"
                  : "Mostrar senha"
              }
              className="
                absolute inset-y-0 right-1
                flex w-11 items-center justify-center
                rounded-lg
                text-slate-400
                transition-colors
                hover:text-[#044055]
                focus-visible:outline-2
                focus-visible:outline-[#044055]
              "
            >
              {mostrarSenha ? (
                <EyeOff
                  size={19}
                  aria-hidden="true"
                />
              ) : (
                <Eye
                  size={19}
                  aria-hidden="true"
                />
              )}
            </button>

          </div>
        </div>


        {/* ===================================
            MANTER CONECTADO
           =================================== */}
        <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={lembrar}
            onChange={(e) =>
              setLembrar(e.target.checked)
            }
          />

          Manter conectado por 7 dias
        </label>


        {/* ===================================
            MENSAGEM DE ERRO
           =================================== */}
        {erro && (
          <p
            role="alert"
            className="rounded-xl bg-red-50 p-3 text-sm text-red-700"
          >
            {erro}
          </p>
        )}


        {/* ===================================
            BOTÃO ENTRAR
           =================================== */}
        <button
          type="submit"
          disabled={enviando}
          className="botao-primario w-full"
        >
          <LogIn size={17} />

          {enviando
            ? "Entrando..."
            : "Entrar"}
        </button>

      </form>


      {/* =====================================
          LINK PARA CADASTRO
         ===================================== */}
      <p className="mt-7 text-center text-sm text-slate-600">
        Ainda não tem conta?{" "}

        <Link
          to="/cadastro"
          className="font-semibold text-gnre-green hover:underline"
        >
          Criar conta
        </Link>
      </p>

    </AuthLayout>
  );
}
