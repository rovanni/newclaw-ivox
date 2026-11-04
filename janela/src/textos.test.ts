import { describe, expect, it } from 'vitest';
import type { Quadro } from './conversa';
import { FATOS_INICIAIS } from './estado';
import { detalhe, MARCA_DA_ETAPA, partesDaFala, seloDoResultado, tempoDecorrido } from './textos';

const q = (p: Partial<Quadro>): Quadro => ({
  estado: 'pronto', fatos: FATOS_INICIAIS, desde: 0, legenda: '', fala: null, progresso: null, etapas: null, aprovacoes: [], mensagens: [], ...p,
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

describe('seloDoResultado (contrato do turno v2)', () => {
  it('tarefa concluída inteira ou sem resultado não ganha selo', () => {
    expect(seloDoResultado(undefined)).toBeNull();
    expect(seloDoResultado({ state: 'concluido', steps: { total: 3, done: 3 } })).toBeNull();
  });
  it('parcial, falha e cancelamento dizem quantas etapas ficaram prontas', () => {
    expect(seloDoResultado({ state: 'parcial', steps: { total: 3, done: 2 } })).toBe('Concluída em parte (2 de 3 etapas)');
    expect(seloDoResultado({ state: 'falhou', steps: { total: 4, done: 1 } })).toBe('Não concluída (1 de 4 etapas)');
    expect(seloDoResultado({ state: 'cancelado', steps: { total: 0, done: 0 } })).toBe('Cancelada');
  });
  it('todo estado de etapa tem marca', () => {
    expect(Object.keys(MARCA_DA_ETAPA).sort()).toEqual(['concluida', 'executando', 'falhou', 'pendente', 'pulada']);
  });
});
