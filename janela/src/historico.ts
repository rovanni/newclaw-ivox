/**
 * Conversas de voz guardadas no NewClaw: a lista para retomar uma e as mensagens de uma delas.
 *
 * Só usa rotas que o contrato do turno já repassa (`GET /api/conversations` e `.../:id/messages`, ver `servidor.py`).
 * A janela não guarda histórico: quem tem a verdade da conversa é o NewClaw. As conversas desta janela são as de
 * `sessionId` começado por `voz-` (ver `preferencias.ts`); as escritas no painel ficam de fora da lista.
 */
import type { Mensagem } from './conversa';

export const PREFIXO_DA_VOZ = 'voz-';

export interface ConversaGuardada {
  /** O que vai de volta no turno (`sessionId`). */
  sessionId: string;
  /** Chave do NewClaw para ler as mensagens (`canal:usuário`); não é o `sessionId`. */
  id: string;
  atualizadaEm: number;
}

interface LinhaDoServidor { id: string; sessionId?: string; user_id?: string; updated_at: string }
interface MensagemDoServidor { role: string; content: string; created_at: string }

type Buscar = (url: string) => Promise<Response>;
const buscarPadrao: Buscar = (url) => fetch(url, { credentials: 'same-origin' });

async function json<T>(buscar: Buscar, url: string): Promise<T> {
  const r = await buscar(url);
  if (!r.ok) throw new Error(`o NewClaw respondeu HTTP ${r.status}`);
  return (await r.json()) as T;
}

/** Conversas de voz, a mais recente primeiro. */
export async function listarConversasDeVoz(buscar: Buscar = buscarPadrao): Promise<ConversaGuardada[]> {
  const d = await json<{ conversations?: LinhaDoServidor[] }>(buscar, '/newclaw/api/conversations');
  return (d.conversations ?? [])
    .map((c) => ({ sessionId: c.sessionId ?? c.user_id ?? '', id: c.id, atualizadaEm: new Date(c.updated_at).getTime() }))
    .filter((c) => c.sessionId.startsWith(PREFIXO_DA_VOZ))
    .sort((a, b) => b.atualizadaEm - a.atualizadaEm);
}

/** As últimas mensagens da conversa, da mais antiga para a mais nova, no formato da tela. */
export async function mensagensDaConversa(c: ConversaGuardada, buscar: Buscar = buscarPadrao, limite = 50): Promise<Mensagem[]> {
  const d = await json<{ messages?: MensagemDoServidor[] }>(
    buscar, `/newclaw/api/conversations/${encodeURIComponent(c.id)}/messages?limit=${limite}`,
  );
  return (d.messages ?? [])
    .filter((m) => m.content && (m.role === 'user' || m.role === 'assistant' || m.role === 'bot'))
    .map((m): Mensagem => ({ quem: m.role === 'user' ? 'voce' : 'newclaw', texto: m.content, em: new Date(m.created_at).getTime() }))
    .sort((a, b) => a.em - b.em);
}

/** Rótulo da conversa na lista: a primeira frase da pessoa entre as mensagens lidas, ou a data. */
export function rotuloDaConversa(mensagens: Mensagem[], c: ConversaGuardada): string {
  const primeira = mensagens.find((m) => m.quem === 'voce');
  if (primeira) return primeira.texto.length > 50 ? `${primeira.texto.slice(0, 50)}…` : primeira.texto;
  return new Date(c.atualizadaEm).toLocaleString();
}
