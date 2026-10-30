/**
 * Tipos do cliente público do turno do NewClaw (`turn-client.js`, contrato do turno versão 1).
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

export interface EstadoDoTurno {
  turnId: string;
  phase: FaseDoTurno;
  elapsedMs: number;
  approvals: Aprovacao[];
  progress: Progresso | null;
}

export interface Entrega {
  kind: 'delivered';
  text: string;
  attachments: unknown[];
  options?: unknown;
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
    signal?: AbortSignal;
  }): Promise<ResultadoDaEspera>;
}

export const VERSAO_DO_CONTRATO = 1;

/** Carrega o cliente público servido pelo NewClaw, através do repasse do harness (mesma origem, cookie da sessão). */
export async function carregarClienteDoTurno(): Promise<ClienteDoTurno> {
  const caminho = '/newclaw/turn-client.js';
  const modulo = await import(/* @vite-ignore */ caminho);
  if (modulo.TURN_CONTRACT_VERSION !== VERSAO_DO_CONTRATO) {
    throw new Error(
      `o NewClaw serve o cliente do turno na versão ${modulo.TURN_CONTRACT_VERSION}; esta janela usa a ${VERSAO_DO_CONTRATO}`,
    );
  }
  return modulo.createTurnClient({ baseUrl: '/newclaw' }) as ClienteDoTurno;
}
