/**
 * Tipos do cliente público do turno do NewClaw (`turn-client.js`, contrato do turno versão 1 ou 2).
 *
 * A versão 2 (ADR-033 do NewClaw) é aditiva: as etapas do objetivo, o resultado da tarefa e o aviso de fila provisório
 * chegam em campos novos, todos opcionais aqui. Com um NewClaw da versão 1, a janela funciona como antes.
 *
 * O módulo em si não é copiado para cá: o harness o busca no próprio NewClaw (`/newclaw/turn-client.js`), para existir uma
 * fonte só. Estes tipos descrevem só o que a janela usa.
 */
import type { FaseDoTurno } from './estado';

export interface Aprovacao {
  txnId: string;
  tool: string;
  detail: string;
  createdAt: number;
}

/** Último relato de progresso da conversa (ADR-027), como `GET /api/chat/active` devolve em `progresso`. */
export interface Progresso {
  texto: string;
  em: number;
}

/** v2: uma etapa do plano real do objetivo, como o NewClaw a descreveu. */
export interface Etapa {
  id: string;
  description: string;
  state: 'pendente' | 'executando' | 'concluida' | 'pulada' | 'falhou';
}

/** v2: o objetivo em andamento desta conversa. `steps` ausente: nada mudou desde a revisão pedida. */
export interface PlanoDoTrabalho {
  state: string;
  generation: number;
  revision: number;
  steps?: Etapa[];
}

/** v2: o resultado que o NewClaw decidiu para a tarefa (só em entrega de objetivo). */
export interface ResultadoDaTarefa {
  state: 'concluido' | 'falhou' | 'cancelado' | 'parcial';
  steps: { total: number; done: number };
}

export interface EstadoDoTurno {
  turnId: string;
  phase: FaseDoTurno;
  elapsedMs: number;
  approvals: Aprovacao[];
  progress: Progresso | null;
  plan?: PlanoDoTrabalho | null;
}

export interface Entrega {
  kind: 'delivered';
  text: string;
  attachments: unknown[];
  options?: unknown;
  outcome?: ResultadoDaTarefa;
  provisional?: boolean;
}

export type ResultadoDoEnvio =
  | { kind: 'accepted'; turnId: string; sessionId: string }
  | { kind: 'rejected'; status: number; error: string; retryAfterSec?: number };

export type ResultadoDaEspera =
  | { kind: 'finished'; delivery: Entrega | null }
  | { kind: 'timeout' }
  | { kind: 'unreachable'; lastError: string }
  | { kind: 'rejected'; status: number }
  | { kind: 'aborted' };

export type ResultadoDaDecisao =
  | { kind: 'decided'; text: string; attachments: unknown[] }
  | { kind: 'rejected'; status: number; error: string };

export interface ClienteDoTurno {
  send(a: { sessionId: string; message: string }): Promise<ResultadoDoEnvio>;
  cancel(a: { sessionId: string }): Promise<ResultadoDoEnvio>;
  decide(a: { sessionId: string; txnId: string; decision: 'approved' | 'rejected' }): Promise<ResultadoDaDecisao>;
  waitForTurn(a: {
    sessionId: string;
    turnId: string;
    onState?: (s: EstadoDoTurno) => void;
    /** v2: o aviso de fila; a espera continua até a resposta final. */
    onProvisional?: (e: Entrega) => void;
    signal?: AbortSignal;
  }): Promise<ResultadoDaEspera>;
}

/**
 * A versão mínima do contrato que esta janela entende. O contrato só cresce por campos novos (docs/CONTRATO_DO_TURNO.md,
 * "Versão e compatibilidade"): versão maior continua servindo. Exigir a versão exata quebraria a janela a cada versão nova
 * do NewClaw (achado ao preparar a versão 2, 04/11/2026).
 */
export const VERSAO_MINIMA_DO_CONTRATO = 1;

/** Nome desta janela no contrato do turno (`client`, versão 2): só informativo para o NewClaw. */
export const NOME_DO_CLIENTE = 'newclaw-ivox';

/** A versão do cliente servido pelo NewClaw serve para esta janela? */
export function versaoAceita(versao: unknown): boolean {
  return typeof versao === 'number' && Number.isInteger(versao) && versao >= VERSAO_MINIMA_DO_CONTRATO;
}

/** Carrega o cliente público servido pelo NewClaw, através do repasse do harness (mesma origem, cookie da sessão). */
export async function carregarClienteDoTurno(): Promise<ClienteDoTurno> {
  const caminho = '/newclaw/turn-client.js';
  const modulo = await import(/* @vite-ignore */ caminho);
  if (!versaoAceita(modulo.TURN_CONTRACT_VERSION)) {
    throw new Error(
      `o NewClaw serve o cliente do turno na versão ${modulo.TURN_CONTRACT_VERSION}; esta janela precisa da ${VERSAO_MINIMA_DO_CONTRATO} ou maior`,
    );
  }
  return modulo.createTurnClient({ baseUrl: '/newclaw', client: NOME_DO_CLIENTE }) as ClienteDoTurno;
}
