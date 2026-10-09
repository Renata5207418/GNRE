import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  requisicaoAuth,
  type UsuarioGNRE,
} from "../services/authAPI";

type ContextoAuth = {
  usuario: UsuarioGNRE | null;
  carregando: boolean;
  entrar: (
    email: string,
    senha: string,
    lembrar: boolean
  ) => Promise<void>;
  sair: () => Promise<void>;
  atualizarUsuario: () => Promise<void>;
};

const AuthContext = createContext<ContextoAuth | null>(null);

export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [usuario, setUsuario] =
    useState<UsuarioGNRE | null>(null);

  const [carregando, setCarregando] = useState(true);

  const atualizarUsuario = useCallback(async () => {
    try {
      const perfil =
        await requisicaoAuth<UsuarioGNRE>("/me");

      setUsuario(perfil);
    } catch {
      setUsuario(null);
    }
  }, []);

  useEffect(() => {
    let ativo = true;

    void requisicaoAuth<UsuarioGNRE>("/me")
      .then((perfil) => {
        if (ativo) setUsuario(perfil);
      })
      .catch(() => {
        if (ativo) setUsuario(null);
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });

    return () => {
      ativo = false;
    };
  }, []);

  const entrar = useCallback(
    async (
      email: string,
      senha: string,
      lembrar: boolean
    ) => {
      const perfil =
        await requisicaoAuth<UsuarioGNRE>("/login", {
          method: "POST",
          body: JSON.stringify({
            email,
            senha,
            lembrar,
          }),
        });

      setUsuario(perfil);
    },
    []
  );

  const sair = useCallback(async () => {
    await requisicaoAuth<{ ok: boolean }>("/logout", {
      method: "POST",
    });

    setUsuario(null);
  }, []);

  const valor = useMemo(
    () => ({
      usuario,
      carregando,
      entrar,
      sair,
      atualizarUsuario,
    }),
    [usuario, carregando, entrar, sair, atualizarUsuario]
  );

  return (
    <AuthContext.Provider value={valor}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const contexto = useContext(AuthContext);

  if (!contexto) {
    throw new Error(
      "useAuth deve ficar dentro de AuthProvider."
    );
  }

  return contexto;
}
