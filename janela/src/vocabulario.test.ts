import { describe, expect, it } from 'vitest';
import {
  aprender, DicionarioIndisponivel, editar, emOrdemDeImportancia, gravarVocabulario, lerVocabulario, ListaMudou,
  motivoParaNaoEnsinar, palavrasParaOMotor, trechoTrocado, type PalavraDaVoz,
} from './vocabulario';

const AGORA = '2026-11-07T12:00:00.000Z';
const p = (palavra: string, vezes = 1, atualizadaEm = AGORA, ouvia: string[] = []): PalavraDaVoz =>
  ({ palavra, ouvia, vezes, criadaEm: AGORA, atualizadaEm });

describe('dicionário da voz — o trecho trocado na correção (ADR-039)', () => {
  it('casos reais: um trecho trocado, com palavras iguais em volta', () => {
    expect(trechoTrocado('E o Rigger?', 'E o River?')).toEqual({ ouvido: 'Rigger', certo: 'River' });
    expect(trechoTrocado('Qual a previsão do tempo para a Cornelia Procobre?', 'Qual a previsão do tempo para Cornélio Procópio?'))
      .toEqual({ ouvido: 'a Cornelia Procobre', certo: 'Cornélio Procópio' });
    expect(trechoTrocado('Qual a senhor do tempo?', 'Qual a previsão do tempo?')).toEqual({ ouvido: 'senhor', certo: 'previsão' });
  });

  it('maiúsculas e pontuação nas pontas não contam como troca', () => {
    expect(trechoTrocado('e o river?', 'E o River.')).toBeNull();
  });

  it('frase reescrita inteira, só apagar palavras, ou nada mudado: nada a propor', () => {
    expect(trechoTrocado('Romântica básica.', 'Como está o tempo hoje?')).toBeNull();
    expect(trechoTrocado('E o River aí?', 'E o River?')).toBeNull();
    expect(trechoTrocado('E o River?', 'E o River?')).toBeNull();
  });
});

describe('dicionário da voz — a lista', () => {
  it('aprender: palavra nova entra com o "eu ouvia"; repetida soma e guarda o novo', () => {
    let l = aprender([], ' River ', 'Rigger', AGORA);
    expect(l).toEqual([{ palavra: 'River', ouvia: ['Rigger'], vezes: 1, criadaEm: AGORA, atualizadaEm: AGORA }]);
    l = aprender(l, 'river', 'River AEM', '2026-11-07T13:00:00.000Z');
    expect(l).toHaveLength(1);
    expect(l[0]).toMatchObject({ palavra: 'River', vezes: 2, ouvia: ['Rigger', 'River AEM'], atualizadaEm: '2026-11-07T13:00:00.000Z' });
    l = aprender(l, 'River', 'rigger', AGORA);
    expect(l[0].ouvia).toEqual(['Rigger', 'River AEM']);  // sem repetir
  });

  it('editar corrige a palavra digitada errada e recusa o que não serve', () => {
    const l = [p('Rivre', 1, AGORA, ['Rigger']), p('Cornélio Procópio')];
    const ok = editar(l, 0, 'River', ['Rigger', 'river', ''], AGORA);
    expect(Array.isArray(ok) && ok[0]).toMatchObject({ palavra: 'River', ouvia: ['Rigger'] });
    expect(editar(l, 0, '  ', [], AGORA)).toBe('Escreva a palavra.');
    expect(editar(l, 0, 'cornélio procópio', [], AGORA)).toBe('"cornélio procópio" já está na lista.');
    expect(editar(l, 0, 'x'.repeat(61), [], AGORA)).toMatch(/no máximo 60/);
  });

  it('ensinar: recusa vazia, longa e lista cheia; repetida é reforço, não recusa', () => {
    expect(motivoParaNaoEnsinar([], '')).toBe('Escreva a palavra.');
    expect(motivoParaNaoEnsinar([], 'x'.repeat(61))).toMatch(/60/);
    const cheia = Array.from({ length: 200 }, (_, i) => p(`p${i}`));
    expect(motivoParaNaoEnsinar(cheia, 'nova')).toMatch(/200/);
    expect(motivoParaNaoEnsinar(cheia, 'P3')).toBeNull();
  });

  it('ordem para o Whisper: as mais corrigidas primeiro; no empate, as mais recentes', () => {
    const l = [p('A', 1, '2026-11-01T00:00:00Z'), p('B', 3), p('C', 1, '2026-11-06T00:00:00Z')];
    expect(emOrdemDeImportancia(l).map((x) => x.palavra)).toEqual(['B', 'C', 'A']);
    expect(palavrasParaOMotor(l)).toEqual(['B', 'C', 'A']);
  });
});

describe('dicionário da voz — a rota pelo harness', () => {
  const resposta = (status: number, corpo: unknown) => new Response(JSON.stringify(corpo), { status, headers: { 'Content-Type': 'application/json' } });

  it('lê e grava com a revisão', async () => {
    const pedidos: { url: string; init?: RequestInit }[] = [];
    const v = await lerVocabulario(async (url, init) => { pedidos.push({ url, init }); return resposta(200, { success: true, revisao: 2, palavras: [p('River')] }); });
    expect(v.revisao).toBe(2);
    expect(pedidos[0].url).toBe('/newclaw/api/voz/vocabulario');
    const g = await gravarVocabulario(2, [], async (url, init) => { pedidos.push({ url, init }); return resposta(200, { success: true, revisao: 3, palavras: [] }); });
    expect(g.revisao).toBe(3);
    expect(pedidos[1].init?.method).toBe('PUT');
    expect(JSON.parse(String(pedidos[1].init?.body))).toEqual({ revisao: 2, palavras: [] });
  });

  it('409: outra janela gravou antes, e a lista atual vem junto', async () => {
    const erro = await gravarVocabulario(1, [], async () => resposta(409, { success: false, error: 'mudou', revisao: 5, palavras: [p('River')] })).catch((e) => e);
    expect(erro).toBeInstanceOf(ListaMudou);
    expect((erro as ListaMudou).atual.revisao).toBe(5);
  });

  it('404: NewClaw ou harness sem a rota, dito com palavras', async () => {
    const erro = await lerVocabulario(async () => resposta(404, { erro: 'rota fora do contrato do turno' })).catch((e) => e);
    expect(erro).toBeInstanceOf(DicionarioIndisponivel);
    expect(String(erro.message)).toMatch(/atualize/);
  });

  it('outros erros chegam como vieram', async () => {
    const erro = await lerVocabulario(async () => resposta(500, { success: false, error: 'valor guardado estragado' })).catch((e) => e);
    expect(String(erro.message)).toBe('valor guardado estragado');
  });
});
