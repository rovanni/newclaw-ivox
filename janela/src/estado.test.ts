import { describe, expect, it } from 'vitest';
import { estadoDaTela, FATOS_INICIAIS, faseMaisRelevante, podeParar, type Fatos } from './estado';

const f = (p: Partial<Fatos>): Fatos => ({ ...FATOS_INICIAIS, ...p });

describe('estadoDaTela', () => {
  it('sem nada acontecendo, está pronto', () => {
    expect(estadoDaTela(FATOS_INICIAIS)).toBe('pronto');
  });

  it('cada fase do turno vira um estado', () => {
    expect(estadoDaTela(f({ turno: 'accepted' }))).toBe('fila');
    expect(estadoDaTela(f({ turno: 'running' }))).toBe('pensando');
    expect(estadoDaTela(f({ turno: 'awaiting_approval' }))).toBe('aprovacao');
    expect(estadoDaTela(f({ turno: 'finished' }))).toBe('pronto');
  });

  it('resposta pronta esperando o motor começar ainda é "pensando"', () => {
    expect(estadoDaTela(f({ aguardandoFala: true }))).toBe('pensando');
  });

  it('o motor tocando é "falando", mesmo com outro pedido na fila', () => {
    expect(estadoDaTela(f({ motorFalando: true }))).toBe('falando');
    expect(estadoDaTela(f({ motorFalando: true, turno: 'accepted' }))).toBe('falando');
  });

  it('a pessoa falando vence o motor falando (é a interrupção)', () => {
    expect(estadoDaTela(f({ pessoaFalando: true, motorFalando: true }))).toBe('ouvindo');
  });

  it('aprovação pendente vence o motor falando: o trabalho está parado esperando um clique', () => {
    expect(estadoDaTela(f({ turno: 'awaiting_approval', motorFalando: true }))).toBe('aprovacao');
  });

  it('erro de ligação vence tudo', () => {
    expect(estadoDaTela(f({ erro: 'caiu', pessoaFalando: true, turno: 'running' }))).toBe('erro');
  });
});

describe('faseMaisRelevante', () => {
  it('escolhe o que mais pede atenção e ignora turnos terminados', () => {
    expect(faseMaisRelevante([])).toBeNull();
    expect(faseMaisRelevante(['finished'])).toBeNull();
    expect(faseMaisRelevante(['accepted', 'running'])).toBe('running');
    expect(faseMaisRelevante(['running', 'awaiting_approval', 'accepted'])).toBe('awaiting_approval');
  });
});

describe('podeParar', () => {
  it('só quando há trabalho do NewClaw ou fala do motor', () => {
    expect(['fila', 'pensando', 'falando'].every((e) => podeParar(e as never))).toBe(true);
    expect(['pronto', 'ouvindo', 'aprovacao', 'erro'].some((e) => podeParar(e as never))).toBe(false);
  });
});
