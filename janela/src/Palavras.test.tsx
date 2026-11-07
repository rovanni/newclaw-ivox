import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { CartaoAprender, TelaDePalavras } from './Palavras';
import type { PalavraDaVoz } from './vocabulario';

const nada = () => {};
const AGORA = '2026-11-07T12:00:00.000Z';
const p = (palavra: string, vezes = 1, ouvia: string[] = []): PalavraDaVoz => ({ palavra, ouvia, vezes, criadaEm: AGORA, atualizadaEm: AGORA });

describe('dicionário da voz: o cartão depois da correção (ADR-039)', () => {
  it('pergunta antes, com a palavra e o que ele tinha ouvido, e deixa mudar ou recusar', () => {
    const h = renderToStaticMarkup(<CartaoAprender proposta={{ certo: 'River', ouvido: 'Rigger' }} aoAprender={nada} aoRecusar={nada} aoVerPalavras={nada} />);
    expect(h).toContain('Quer que eu aprenda <b>River</b>?');
    expect(h).toContain('Eu tinha ouvido “Rigger”.');
    for (const b of ['Aprender', 'Mudar a palavra', 'Agora não']) expect(h).toContain(`>${b}</button>`);
    expect(h).toContain('ver as palavras que eu conheço');
  });
});

describe('dicionário da voz: a tela "Palavras que eu conheço"', () => {
  const tela = (extra: Partial<Parameters<typeof TelaDePalavras>[0]> = {}) => renderToStaticMarkup(
    <TelaDePalavras vocab={{ revisao: 1, palavras: [p('Cornélio Procópio'), p('River', 3, ['Rigger', 'River AEM'])] }} erro="" conta={null}
      modeloCarregado={false} motorLigado ocupado={false} aoEnsinar={nada} aoSalvar={nada} aoApagar={nada} {...extra} />);

  it('lista em ordem de importância, com o que ele ouvia, editar e apagar', () => {
    const h = tela();
    expect(h.indexOf('<b>River</b>')).toBeLessThan(h.indexOf('<b>Cornélio Procópio</b>'));  // 3 vezes antes de 1
    expect(h).toContain('eu ouvia: Rigger, River AEM · 3 vezes');
    expect(h).toContain('ensinada por você · 1 vez');
    expect(h.match(/>Editar<\/button>/g)).toHaveLength(2);
    expect(h.match(/>Apagar<\/button>/g)).toHaveLength(2);
    expect(h).toContain('vão junto no backup');
  });

  it('diz quantas cabem só quando o motor contou; sem o modelo, explica', () => {
    expect(tela()).toContain('aparece quando o modelo de voz carregar');
    expect(tela({ conta: { usadas: 2, total: 2, tokens: 10, teto: 223 }, modeloCarregado: true })).toContain('2 palavras, todas valendo');
    const parte = tela({ conta: { usadas: 1, total: 2, tokens: 5, teto: 223 }, modeloCarregado: true });
    expect(parte).toContain('1 de 2 palavras cabem');
    expect(parte).toContain('não cabe agora');
    expect(tela({ motorLigado: false })).toContain('quando a voz ligar');
  });

  it('sem lista ainda: o motivo, ou "lendo"', () => {
    const base = { conta: null, modeloCarregado: false, motorLigado: true, ocupado: false, aoEnsinar: nada, aoSalvar: nada, aoApagar: nada };
    expect(renderToStaticMarkup(<TelaDePalavras vocab={null} erro="" {...base} />)).toContain('Lendo as palavras');
    expect(renderToStaticMarkup(<TelaDePalavras vocab={null} erro="Este NewClaw ainda não guarda o dicionário da voz: atualize o NewClaw e a voz." {...base} />))
      .toContain('atualize o NewClaw');
  });

  it('a busca só aparece com a lista longa', () => {
    expect(tela()).not.toContain('aria-label="Buscar palavra"');
    const muitas = Array.from({ length: 10 }, (_, i) => p(`p${i}`));
    expect(tela({ vocab: { revisao: 1, palavras: muitas } })).toContain('aria-label="Buscar palavra"');
  });
});
