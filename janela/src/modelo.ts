/**
 * O modelo de reconhecimento de voz (ADR-037 do NewClaw): a janela pede para carregar e descarregar; quem decide e mede
 * é o motor (`GET/POST /api/modelo` do harness). Iniciar a integração, carregar o modelo e abrir a janela são três coisas
 * separadas: abrir a janela não carrega nada, a não ser que a pessoa tenha pedido ("Carregar ao abrir a janela").
 */

export type FaseDoModelo = 'descarregado' | 'carregando' | 'carregado' | 'descarregando' | 'falha';

export interface MemoriaGpu { nome: string; total_bytes: number; usada_bytes: number; livre_bytes: number }

export interface EstadoDoModelo {
  estado: FaseDoModelo;
  em_uso: number;
  modelo?: string;
  dispositivo?: string | null;
  tipo?: string | null;
  motivo?: string;
  erro?: string;
  /** O motor pergunta: "tentar na CPU ou cancelar" (falta de memória medida, ou falha na GPU). */
  pergunta?: 'cpu';
  aviso?: string;
  memoria_antes?: MemoriaGpu[] | null;
  memoria_depois?: MemoriaGpu[] | null;
  consumo_medido_bytes?: number | null;
  consumo_bytes?: number;
  consumo_fonte?: string;
  liberado_bytes?: number;
  segundos_para_carregar?: number;
  sintese?: { motor: string; provedores: string[] | null } | null;
  ajustes?: { descarregar_apos_min?: number | null };
}

type Buscar = (url: string, init?: RequestInit) => Promise<Response>;
const buscarPadrao: Buscar = (url, init) => fetch(url, { credentials: 'same-origin', ...init });

async function pedir(buscar: Buscar, url: string, corpo?: unknown): Promise<EstadoDoModelo> {
  const r = await buscar(url, corpo === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.erro ?? `o harness respondeu HTTP ${r.status}`);
  return d as EstadoDoModelo;
}

export const lerModelo = (buscar: Buscar = buscarPadrao) => pedir(buscar, '/api/modelo');
export const carregarModelo = (naCpu = false, buscar: Buscar = buscarPadrao) => pedir(buscar, '/api/modelo/carregar', { na_cpu: naCpu });
export const descarregarModelo = (buscar: Buscar = buscarPadrao) => pedir(buscar, '/api/modelo/descarregar', {});
export const ajustarOciosidade = (minutos: number | null, buscar: Buscar = buscarPadrao) =>
  pedir(buscar, '/api/modelo/ajustes', { descarregar_apos_min: minutos });

/** Com que frequência perguntar o estado: rápido enquanto muda, devagar parado (outra janela pode ter mudado). */
export function intervaloDeLeitura(e: EstadoDoModelo | null): number {
  return e && (e.estado === 'carregando' || e.estado === 'descarregando') ? 1000 : 5000;
}

export function gb(bytes: number | null | undefined): string {
  return bytes === null || bytes === undefined ? '—' : `${(bytes / 2 ** 30).toFixed(1).replace('.', ',')} GB`;
}

const ONDE: Record<string, string> = { cuda: 'GPU', cpu: 'CPU' };

/** Título e explicação do reconhecimento, em palavras, a partir só do que o motor informou. */
export function resumoDoModelo(e: EstadoDoModelo | null): { titulo: string; texto: string } {
  if (!e) return { titulo: 'Sem resposta do motor', texto: 'Não consegui ler o estado do reconhecimento de voz.' };
  const onde = e.dispositivo ? ONDE[e.dispositivo] ?? e.dispositivo : null;
  switch (e.estado) {
    case 'carregando':
      return { titulo: `Carregando${onde ? ` na ${onde}` : ''}`, texto: 'O modelo Whisper está entrando na memória.' };
    case 'carregado': {
      const ocupa = e.dispositivo === 'cuda' && e.consumo_bytes !== undefined ? ` Ocupou ${gb(e.consumo_bytes)} de VRAM.` : '';
      return { titulo: `Modelo carregado${onde ? ` · ${onde}` : ''}`, texto: `Pode falar.${ocupa}` };
    }
    case 'descarregando':
      return { titulo: 'Descarregando', texto: e.em_uso > 0 ? 'Esperando a transcrição em andamento terminar.' : 'Liberando a memória.' };
    case 'falha':
      return { titulo: 'O modelo não carregou', texto: e.erro ?? 'Falha sem mensagem do motor.' };
    default: {
      if (e.aviso) return { titulo: 'Memória insuficiente na GPU', texto: e.aviso };
      const liberou = e.liberado_bytes !== undefined ? ` Liberou ${gb(e.liberado_bytes)} de VRAM.` : '';
      return {
        titulo: 'Modelo descarregado',
        texto: `O Whisper não está ocupando memória. Você pode continuar escrevendo e ouvindo as respostas.${liberou}`,
      };
    }
  }
}

/** Onde a fala roda, pelos provedores que o kokoro-onnx escolheu nesta instalação (só a CPU, ou os outros que ele usa). */
export function ondeFala(e: EstadoDoModelo | null): string {
  const p = e?.sintese?.provedores;
  if (!e?.sintese) return 'não configurada';
  if (!p) return 'Kokoro · não medido';
  const outros = p.filter((x) => x !== 'CPUExecutionProvider');
  return `Kokoro · ${outros.length ? outros.join(', ') : 'CPU'}`;
}
