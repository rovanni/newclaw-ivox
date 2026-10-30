import { describe, expect, it } from 'vitest';
import { Conversa, type Quadro, type Relogio } from './conversa';
import type { ClienteDoTurno, EstadoDoTurno, ResultadoDaEspera, ResultadoDoEnvio } from './turnos';

/** Relógio manual: o tempo só anda quando o teste manda. */
class RelogioFalso implements Relogio {
  t = 0;
  private alarmes: { em: number; fn: () => void; vivo: boolean }[] = [];
  agora() { return this.t; }
  depois(ms: number, fn: () => void) {
    const a = { em: this.t + ms, fn, vivo: true };
    this.alarmes.push(a);
    return () => { a.vivo = false; };
  }
  andar(ms: number) {
    this.t += ms;
    for (const a of this.alarmes.filter((x) => x.vivo && x.em <= this.t)) { a.vivo = false; a.fn(); }
  }
}

class MotorFalso {
  falas: string[] = [];
  interrupcoes = 0;
  falar(t: string) { this.falas.push(t); }
  interromper() { this.interrupcoes++; }
}

/** Cliente do turno falso: o teste decide quando cada turno muda de fase e termina. */
class TurnosFalsos implements ClienteDoTurno {
  enviados: string[] = [];
  decisoes: { txnId: string; decision: string }[] = [];
  respostaDoEnvio: ResultadoDoEnvio | null = null;
  private n = 0;
  private turnos = new Map<string, { onState?: (s: EstadoDoTurno) => void; fim: (r: ResultadoDaEspera) => void }>();

  async send({ message }: { sessionId: string; message: string }): Promise<ResultadoDoEnvio> {
    this.enviados.push(message);
    return this.respostaDoEnvio ?? { kind: 'accepted', turnId: `t${++this.n}`, sessionId: 's' };
  }
  cancel(a: { sessionId: string }) { return this.send({ ...a, message: '/cancelar' }); }
  async decide({ txnId, decision }: { sessionId: string; txnId: string; decision: 'approved' | 'rejected' }) {
    this.decisoes.push({ txnId, decision });
    return { kind: 'decided' as const, text: 'Feito: espaço liberado.', attachments: [] };
  }
  waitForTurn({ turnId, onState }: { sessionId: string; turnId: string; onState?: (s: EstadoDoTurno) => void }) {
    return new Promise<ResultadoDaEspera>((fim) => this.turnos.set(turnId, { onState, fim }));
  }
  fase(turnId: string, phase: EstadoDoTurno['phase'], extra: Partial<EstadoDoTurno> = {}) {
    this.turnos.get(turnId)!.onState?.({ turnId, phase, elapsedMs: 0, approvals: [], progress: null, ...extra });
  }
  terminar(turnId: string, r: ResultadoDaEspera) { this.turnos.get(turnId)!.fim(r); }
}

const tick = () => new Promise((r) => setTimeout(r, 0));

function montar(pausa = 1000) {
  const relogio = new RelogioFalso();
  const motor = new MotorFalso();
  const turnos = new TurnosFalsos();
  const quadros: Quadro[] = [];
  const c = new Conversa({ motor, turnos, sessionId: 's', relogio, pausaParaEnviarMs: pausa, aoMudar: (q) => quadros.push(q) });
  const ultimo = () => quadros[quadros.length - 1];
  return { c, relogio, motor, turnos, ultimo };
}

describe('Conversa — mãos livres', () => {
  it('fala → legenda → pausa → pedido ao NewClaw → fila → pensando → resposta falada → pronto', async () => {
    const { c, relogio, motor, turnos, ultimo } = montar();
    c.pessoaComecouAFalar();
    expect(ultimo().estado).toBe('ouvindo');
    c.transcricao('quais serviços', false);
    expect(ultimo().legenda).toBe('quais serviços');
    c.pessoaParouDeFalar();
    c.transcricao('Quais serviços estão fora do ar?', true);
    expect(ultimo().legenda).toBe('Quais serviços estão fora do ar?');
    expect(turnos.enviados).toEqual([]);

    relogio.andar(1000);
    await tick();
    expect(turnos.enviados).toEqual(['Quais serviços estão fora do ar?']);
    expect(ultimo().estado).toBe('fila');
    expect(ultimo().legenda).toBe('');
    expect(ultimo().mensagens[0]).toMatchObject({ quem: 'voce', porVoz: true });

    turnos.fase('t1', 'running', { progress: { texto: 'conferindo os serviços', em: 1 } });
    expect(ultimo().estado).toBe('pensando');
    expect(ultimo().progresso).toBe('conferindo os serviços');

    turnos.terminar('t1', { kind: 'finished', delivery: { kind: 'delivered', text: 'Só o Nextcloud está fora.', attachments: [] } });
    await tick();
    expect(motor.falas).toEqual(['Só o Nextcloud está fora.']);
    expect(ultimo().estado).toBe('pensando'); // mandada ao motor, que ainda não começou
    expect(ultimo().progresso).toBeNull();

    c.motorComecouAFalar();
    expect(ultimo().estado).toBe('falando');
    c.fraseFalada('Só o Nextcloud está fora.');
    expect(ultimo().fala).toEqual({ texto: 'Só o Nextcloud está fora.', fraseAtual: 'Só o Nextcloud está fora.' });
    c.motorParouDeFalar();
    expect(ultimo().estado).toBe('pronto');
    expect(ultimo().fala?.texto).toBe('Só o Nextcloud está fora.');
  });

  it('trechos com pausa curta viram um pedido só', async () => {
    const { c, relogio, turnos } = montar(1000);
    c.pessoaComecouAFalar(); c.pessoaParouDeFalar(); c.transcricao('Quais serviços', true);
    relogio.andar(600);
    c.pessoaComecouAFalar(); c.pessoaParouDeFalar(); c.transcricao('estão fora do ar?', true);
    relogio.andar(600);
    expect(turnos.enviados).toEqual([]);
    relogio.andar(400);
    await tick();
    expect(turnos.enviados).toEqual(['Quais serviços estão fora do ar?']);
  });

  it('voltar a falar antes da pausa adia o envio', async () => {
    const { c, relogio, turnos } = montar(1000);
    c.pessoaParouDeFalar(); c.transcricao('Oi', true);
    relogio.andar(900);
    c.pessoaComecouAFalar();
    relogio.andar(5000);
    expect(turnos.enviados).toEqual([]);
  });

  it('silêncio sem nada transcrito não manda pedido vazio', () => {
    const { c, relogio, turnos } = montar();
    c.pessoaComecouAFalar(); c.pessoaParouDeFalar(); c.transcricao('  ', true);
    relogio.andar(5000);
    expect(turnos.enviados).toEqual([]);
  });

  it('falar por cima do motor mostra "ouvindo" (o motor já se interrompe sozinho)', () => {
    const { c, motor, ultimo } = montar();
    c.motorComecouAFalar();
    c.pessoaComecouAFalar();
    expect(ultimo().estado).toBe('ouvindo');
    expect(motor.interrupcoes).toBe(0);
  });
});

describe('Conversa — segurar espaço', () => {
  it('nada é enviado enquanto segura; ao soltar, envia depois da última transcrição', async () => {
    const { c, relogio, turnos } = montar(1000);
    c.definirJeitoDeFalar('segurar');
    c.comecouASegurar();
    c.pessoaComecouAFalar(); c.pessoaParouDeFalar(); c.transcricao('Planeje a semana', true);
    relogio.andar(5000);
    expect(turnos.enviados).toEqual([]);
    c.soltou();
    relogio.andar(1000);
    await tick();
    expect(turnos.enviados).toEqual(['Planeje a semana']);
  });
});

describe('Conversa — texto, parar, aprovação, falhas', () => {
  it('texto digitado vai direto, sem esperar pausa', async () => {
    const { c, turnos, ultimo } = montar();
    c.enviarTexto('  Relatório de hoje  ');
    await tick();
    expect(turnos.enviados).toEqual(['Relatório de hoje']);
    expect(ultimo().mensagens[0]).toMatchObject({ quem: 'voce', porVoz: false });
  });

  it('Parar corta a fala e cancela o turno no NewClaw', async () => {
    const { c, motor, turnos } = montar();
    c.enviarTexto('algo demorado');
    await tick();
    c.motorComecouAFalar();
    await c.parar();
    expect(motor.interrupcoes).toBe(1);
    expect(turnos.enviados).toEqual(['algo demorado', '/cancelar']);
  });

  it('aprovação: mostra o pedido, decide só por chamada explícita e fala o resultado', async () => {
    const { c, motor, turnos, ultimo } = montar();
    c.enviarTexto('limpe o docker');
    await tick();
    const pedido = { txnId: 'x1', tool: 'exec_command', detail: 'docker system prune -f', createdAt: 1 };
    turnos.fase('t1', 'awaiting_approval', { approvals: [pedido] });
    expect(ultimo().estado).toBe('aprovacao');
    expect(ultimo().aprovacoes).toEqual([pedido]);

    // Dizer "aprova" por voz não aprova nada.
    c.pessoaComecouAFalar(); c.pessoaParouDeFalar(); c.transcricao('aprova', true);
    expect(turnos.decisoes).toEqual([]);

    await c.decidir('x1', 'approved');
    expect(turnos.decisoes).toEqual([{ txnId: 'x1', decision: 'approved' }]);
    expect(motor.falas).toEqual(['Feito: espaço liberado.']);
    expect(ultimo().aprovacoes).toEqual([]);
  });

  it('pedido recusado (limite de envio) vira aviso com o tempo de espera, sem erro de ligação', async () => {
    const { c, turnos, ultimo } = montar();
    turnos.respostaDoEnvio = { kind: 'rejected', status: 429, error: 'Too many requests', retryAfterSec: 30 };
    c.enviarTexto('oi');
    await tick();
    const aviso = ultimo().mensagens.at(-1)!;
    expect(aviso.quem).toBe('aviso');
    expect(aviso.texto).toContain('30 s');
    expect(ultimo().estado).toBe('pronto');
  });

  it('entrega ausente da outbox não inventa resposta: avisa que está no histórico', async () => {
    const { c, motor, turnos, ultimo } = montar();
    c.enviarTexto('oi');
    await tick();
    turnos.terminar('t1', { kind: 'finished', delivery: null });
    await tick();
    expect(motor.falas).toEqual([]);
    expect(ultimo().mensagens.at(-1)!.texto).toContain('histórico');
  });

  it('NewClaw inalcançável vira erro; a próxima consulta boa limpa o erro', async () => {
    const { c, turnos, ultimo } = montar();
    c.enviarTexto('a');
    await tick();
    c.enviarTexto('b');
    await tick();
    turnos.terminar('t1', { kind: 'unreachable', lastError: 'HTTP 502' });
    await tick();
    expect(ultimo().estado).toBe('erro');
    expect(ultimo().fatos.erro).toContain('HTTP 502');
    turnos.fase('t2', 'running');
    expect(ultimo().estado).toBe('pensando');
  });

  it('o motor recusar a fala tira a tela de "pensando" e avisa o motivo', async () => {
    const { c, turnos, ultimo } = montar();
    c.enviarTexto('oi');
    await tick();
    turnos.terminar('t1', { kind: 'finished', delivery: { kind: 'delivered', text: 'Olá!', attachments: [] } });
    await tick();
    expect(ultimo().estado).toBe('pensando');
    c.motorRecusou('nenhuma voz escolhida ainda');
    expect(ultimo().estado).toBe('pronto');
    expect(ultimo().mensagens.at(-1)!.texto).toContain('nenhuma voz escolhida');
  });

  it('o tempo no estado recomeça a cada troca de estado', () => {
    const { c, relogio, ultimo } = montar();
    relogio.andar(500);
    c.pessoaComecouAFalar();
    expect(ultimo().desde).toBe(500);
    relogio.andar(300);
    c.transcricao('a', false);
    expect(ultimo().desde).toBe(500);
  });
});
