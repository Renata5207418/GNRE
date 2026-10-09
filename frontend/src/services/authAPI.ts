export type UsuarioGNRE = {
  id: number;
  nome: string;
  email: string;
};

type OpcaoAPI = RequestInit & {
  signal?: AbortSignal;
};

export async function requisicaoAuth<T>(
  caminho: string,
  opcoes: OpcaoAPI = {},
): Promise<T> {
  const resposta = await fetch(`/api/auth${caminho}`, {
    ...opcoes,
    credentials: "include",
    cache: "no-store",
    headers: {
      ...(opcoes.body && !(opcoes.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...opcoes.headers,
    },
  });

  if (!resposta.ok) {
    let mensagem =
      `Não foi possível concluir a operação (HTTP ${resposta.status}).`;

    try {
      const corpo: {
        detail?: string | { msg?: string }[];
      } = await resposta.json();

      if (typeof corpo.detail === "string") {
        mensagem = corpo.detail;
      } else if (Array.isArray(corpo.detail)) {
        mensagem = corpo.detail
          .map((item) => item.msg ?? "Dados inválidos")
          .join("; ");
      }
    } catch {
      // Respostas de proxy podem não ser JSON.
    }

    throw new Error(mensagem);
  }

  return (await resposta.json()) as T;
}
