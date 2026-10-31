import { describe, expect, it } from 'vitest';
import { listarConversasDeVoz, mensagensDaConversa, rotuloDaConversa } from './historico';

/** Resposta falsa do repasse `/newclaw/api/...`: guarda as URLs pedidas. */
function servidor(rotas: Record<string, unknown>, status = 200) {
  const pedidas: string[] = [];
  const buscar = async (url: string) => {
    pedidas.push(url);
    const corpo = Object.entries(rotas).find(([k]) => url.startsWith(k))?.[1];
    return new Response(JSON.stringify(corpo ?? {}), { status });
  };
  return { buscar, pedidas };
}

describe('histórico das conversas de voz', () => {
  it('lista só as conversas da voz, a mais recente primeiro', async () => {
    const { buscar } = servidor({
      '/newclaw/api/conversations': {
        conversations: [
          { id: 'web:voz-a', sessionId: 'voz-a', updated_at: '2026-10-30T10:00:00Z' },
          { id: 'web:conv_1', sessionId: 'conv_1', updated_at: '2026-10-31T10:00:00Z' },
          { id: 'web:voz-b', user_id: 'voz-b', updated_at: '2026-10-31T09:00:00Z' },
        ],
      },
    });
    const lista = await listarConversasDeVoz(buscar);
    expect(lista.map((c) => c.sessionId)).toEqual(['voz-b', 'voz-a']);
    expect(lista[0].id).toBe('web:voz-b');
  });

  it('lê as mensagens pela chave do NewClaw (codificada) e as põe em ordem', async () => {
    const { buscar, pedidas } = servidor({
      '/newclaw/api/conversations/': {
        messages: [
          { role: 'assistant', content: 'Opa!', created_at: '2026-10-30T19:47:20Z' },
          { role: 'user', content: 'Bom dia.', created_at: '2026-10-30T19:47:19Z' },
          { role: 'system', content: 'interno', created_at: '2026-10-30T19:47:18Z' },
        ],
      },
    });
    const c = { sessionId: 'voz-a', id: 'web:voz-a', atualizadaEm: 0 };
    const msgs = await mensagensDaConversa(c, buscar);
    expect(pedidas[0]).toBe('/newclaw/api/conversations/web%3Avoz-a/messages?limit=50');
    expect(msgs.map((m) => [m.quem, m.texto])).toEqual([['voce', 'Bom dia.'], ['newclaw', 'Opa!']]);
    expect(rotuloDaConversa(msgs, c)).toBe('Bom dia.');
  });

  it('erro do NewClaw sobe, para a tela dizer', async () => {
    const { buscar } = servidor({}, 502);
    await expect(listarConversasDeVoz(buscar)).rejects.toThrow('HTTP 502');
  });

  it('rótulo corta frase longa e, sem frase da pessoa, usa a data', () => {
    const c = { sessionId: 'voz-a', id: 'web:voz-a', atualizadaEm: Date.UTC(2026, 9, 30) };
    expect(rotuloDaConversa([{ quem: 'voce', texto: 'x'.repeat(60), em: 1 }], c)).toBe(`${'x'.repeat(50)}…`);
    expect(rotuloDaConversa([], c)).toBe(new Date(c.atualizadaEm).toLocaleString());
  });
});
