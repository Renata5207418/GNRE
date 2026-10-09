const API_URL = (
  import.meta.env.VITE_API_URL ?? ""
).replace(/\/$/, "");

export type FiltrosExportacaoGNRE = {
  ids?: number[];
  codigo_dominio?: string;
  mes?: number;
  ano?: number;
  status?: string;
  uf_favorecida?: string;
};

function nomeNoHeader(header: string | null, fallback: string): string {
  const match = header?.match(/filename="([^"]+)"/);
  return match?.[1] ?? fallback;
}

async function lerErro(resposta: Response): Promise<string> {
  try {
    const dados = await resposta.json();
    if (typeof dados.detail === "string") return dados.detail;
    if (Array.isArray(dados.detail)) {
      return dados.detail.map((x: { msg?: string }) => x.msg ?? "Parâmetro inválido").join("; ");
    }
  } catch {
    // Resposta não JSON (ex.: erro em proxy).
  }
  return `Erro HTTP ${resposta.status}`;
}

async function salvarDownload(resposta: Response, nomePadrao: string): Promise<void> {
  if (!resposta.ok) throw new Error(await lerErro(resposta));

  const blob = await resposta.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nomeNoHeader(resposta.headers.get("Content-Disposition"), nomePadrao);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/** Botão "Baixar PDF" em uma guia. */
export async function baixarPdfGNRE(guiaId: number): Promise<void> {
  const resposta = await fetch(`${API_URL}/api/guias/${guiaId}/pdf`, {
    credentials: "include",
  });
  await salvarDownload(resposta, `gnre_${guiaId}.pdf`);
}

/** Botão "Baixar selecionadas": selecionadas = lista de IDs da tabela. */
export async function baixarLoteGNRE(selecionadas: number[]): Promise<void> {
  if (selecionadas.length === 0) throw new Error("Selecione pelo menos uma guia.");
  const resposta = await fetch(`${API_URL}/api/guias/download-lote`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: selecionadas }),
  });
  await salvarDownload(resposta, "guias_selecionadas.zip");
}

/** Botão "Exportar Excel": mesmos filtros usados na consulta da tabela. */
export async function exportarExcelGNRE(
  filtros: FiltrosExportacaoGNRE = {},
): Promise<void> {
  const params = new URLSearchParams();
  for (const [chave, valor] of Object.entries(filtros)) {
    if (valor === undefined || valor === null || valor === "") continue;
    params.set(chave, Array.isArray(valor) ? valor.join(",") : String(valor));
  }
  const sufixo = params.size ? `?${params.toString()}` : "";
  const resposta = await fetch(`${API_URL}/api/guias/exportar/excel${sufixo}`, {
    credentials: "include",
  });
  await salvarDownload(resposta, "resultado_gnre.xlsx");
}
