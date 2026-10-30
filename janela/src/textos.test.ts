import { describe, expect, it } from 'vitest';
import type { Quadro } from './conversa';
import { FATOS_INICIAIS } from './estado';
import { detalhe, partesDaFala, tempoDecorrido } from './textos';

const q = (p: Partial<Quadro>): Quadro => ({
  estado: 'pronto', fatos: FATOS_INICIAIS, desde: 0, legenda: '', fala: null, progresso: null, aprovacoes: [], mensagens: [], ...p,
});

describe('detalhe', () => {
  it('pensando mostra o progresso do NewClaw quando existe', () => {
    expect(detalhe(q({ estado: 'pensando', progresso: 'conferindo os serviços' }))).toBe('conferindo os serviços');
    expect(detalhe(q({ estado: 'pensando' }))).toBe('O NewClaw está trabalhando');
    expect(detalhe(q({ estado: 'pensando', fatos: { ...FATOS_INICIAIS, aguardandoFala: true } }))).toBe('Preparando a fala da resposta');
  });

  it('erro mostra o motivo como veio', () => {
    expect(detalhe(q({ estado: 'erro', fatos: { ...FATOS_INICIAIS, erro: 'Sem resposta do NewClaw (HTTP 502).' } })))
      .toBe('Sem resposta do NewClaw (HTTP 502).');
  });
});

describe('partesDaFala', () => {
  it('destaca a frase em curso', () => {
    expect(partesDaFala('Primeira. Segunda frase. Terceira.', 'Segunda frase.'))
      .toEqual(['Primeira. ', 'Segunda frase.', ' Terceira.']);
  });

  it('sem frase ou com frase que não aparece igual no texto, não destaca nada', () => {
    expect(partesDaFala('Texto **com** marcação.', null)).toEqual(['Texto **com** marcação.', '', '']);
    expect(partesDaFala('Texto **com** marcação.', 'Texto com marcação.')).toEqual(['Texto **com** marcação.', '', '']);
  });
});

describe('tempoDecorrido', () => {
  it('segundos e minutos', () => {
    expect(tempoDecorrido(4_900)).toBe('4 s');
    expect(tempoDecorrido(125_000)).toBe('2 min 5 s');
    expect(tempoDecorrido(-10)).toBe('0 s');
  });
});
