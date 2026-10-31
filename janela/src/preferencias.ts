/** Preferências da pessoa, lembradas neste navegador. Sem armazenamento disponível, a janela funciona com os padrões. */

export function lerPref(chave: string): string | null {
  try { return localStorage.getItem(chave); } catch { return null; }
}

export function gravarPref(chave: string, valor: string): void {
  try { localStorage.setItem(chave, valor); } catch { /* sem armazenamento: só não lembra */ }
}

/** Id da conversa no NewClaw (o `sessionId` do contrato do turno): fixo por navegador, para o histórico continuar. */
export function idDaConversa(): string {
  const salvo = lerPref('ivox-conversa');
  if (salvo) return salvo;
  return novaConversa();
}

/** "Nova conversa": um id novo, que passa a ser o desta janela. O prefixo `voz-` separa as conversas de voz no histórico. */
export function novaConversa(): string {
  const novo = `voz-${crypto.randomUUID().slice(0, 8)}`;
  gravarPref('ivox-conversa', novo);
  return novo;
}

/** Retomar uma conversa do histórico: ela passa a ser a desta janela. */
export function usarConversa(sessionId: string): void {
  gravarPref('ivox-conversa', sessionId);
}
