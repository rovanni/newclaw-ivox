import { describe, expect, it } from 'vitest';
import { Conversa, type Quadro, type Relogio } from './conversa';
import type { ClienteDoTurno, Entrega, EstadoDoTurno, ResultadoDaEspera, ResultadoDoEnvio } from './turnos';
import { versaoAceita } from './turnos';

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
  private turnos = new Map<string, { onState?: (s: EstadoDoTurno) => void; onProvisional?: (e: Entrega) => void; fim: (r: ResultadoDaEspera) => void }>();

  sessoes: string[] = [];

  async send({ sessionId, message }: { sessionId: string; message: string }): Promise<ResultadoDoEnvio> {
    this.enviados.push(message);
    this.sessoes.push(sessionId);
    return this.respostaDoEnvio ?? { kind: 'accepted', turnId: `t${++this.n}`, sessionId: 's' };
  }
  cancel(a: { sessionId: string }) { return this.send({ ...a, message: '/cancelar' }); }
  async decide({ txnId, decision }: { sessionId: string; txnId: string; decision: 'approved' | 'rejected' }) {
    this.decisoes.push({ txnId, decision });
    return { kind: 'decided' as const, text: 'Feito: espaço liberado.', attachments: [] };
  }
  waitForTurn({ turnId, onState, onProvisional }: { sessionId: string; turnId: string; onState?: (s: EstadoDoTurno) => void; onProvisional?: (e: Entrega) => void }) {
    return new Promise<ResultadoDaEspera>((fim) => this.turnos.set(turnId, { onState, onProvisional, fim }));
  }
  provisorio(turnId: string, text: string) {
    this.turnos.get(turnId)!.onProvisional?.({ kind: 'delivered', text, attachments: [], provisional: true });
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

  it('entre "pensando" e "falando" a tela não passa por "pronto" (achado da prova real, 30/10)', async () => {
    const { c, turnos, ultimo } = montar();
    const vistos: string[] = [];
    c.enviarTexto('oi');
    await tick();
    turnos.fase('t1', 'running');
    const antes = ultimo();
    expect(antes.estado).toBe('pensando');
    // Registra cada estado publicado a partir daqui.
    (c as unknown as { o: { aoMudar: (q: Quadro) => void } }).o.aoMudar = (q) => vistos.push(q.estado);
    turnos.fase('t1', 'finished'); // o NewClaw diz "terminado" antes de a entrega ser retirada
    turnos.terminar('t1', { kind: 'finished', delivery: { kind: 'delivered', text: 'Olá!', attachments: [] } });
    await tick();
    c.motorComecouAFalar();
    expect(vistos).not.toContain('pronto');
    expect(vistos.at(-1)).toBe('falando');
  });

  it('pausas curtas no meio da fala não tiram a tela de "Ouvindo" (achado da prova com a operadora, 30/10)', async () => {
    const { c, relogio, ultimo } = montar(1000);
    c.pessoaComecouAFalar();
    c.pessoaParouDeFalar(); // respiro de 0,2 s: o VAD já diz "parou"
    expect(ultimo().estado).toBe('ouvindo');
    c.transcricao('Quais serviços', true);
    relogio.andar(500);
    expect(ultimo().estado).toBe('ouvindo');
    c.pessoaComecouAFalar();
    c.pessoaParouDeFalar();
    c.transcricao('estão fora do ar?', true);
    relogio.andar(999);
    expect(ultimo().estado).toBe('ouvindo');
    relogio.andar(1);
    await tick();
    expect(ultimo().estado).toBe('fila'); // direto, sem passar por "pronto"
  });

  it('ruído sem nada transcrito: depois da pausa a tela volta a "Pronto", sem pedido', () => {
    const { c, relogio, turnos, ultimo } = montar(1000);
    c.pessoaComecouAFalar();
    c.pessoaParouDeFalar();
    c.transcricao('', true);
    expect(ultimo().estado).toBe('ouvindo');
    relogio.andar(1000);
    expect(ultimo().estado).toBe('pronto');
    expect(turnos.enviados).toEqual([]);
  });

  it('espera escolhida pela pessoa: com a média, uma hesitação de 1 s não divide o pedido (prova de 30/10)', async () => {
    const { c, relogio, turnos } = montar();
    c.definirEspera('media'); // 1,2 s depois de o motor fechar o trecho
    c.pessoaComecouAFalar(); c.pessoaParouDeFalar(); c.transcricao('Então, eu...', true);
    relogio.andar(1000);
    c.pessoaComecouAFalar(); c.pessoaParouDeFalar(); c.transcricao('com três monitores.', true);
    relogio.andar(1200);
    await tick();
    expect(turnos.enviados).toEqual(['Então, eu... com três monitores.']);
    c.definirEspera('curta');
    c.pessoaComecouAFalar(); c.pessoaParouDeFalar(); c.transcricao('Oi', true);
    relogio.andar(600);
    await tick();
    expect(turnos.enviados.at(-1)).toBe('Oi');
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

describe('Conversa — trocar de conversa (nova ou retomada do histórico)', () => {
  it('passa a mandar os pedidos para a outra conversa e mostra as mensagens dela', async () => {
    const { c, turnos, ultimo } = montar();
    c.enviarTexto('na primeira');
    await tick();
    turnos.terminar('t1', { kind: 'finished', delivery: { kind: 'delivered', text: 'ok', attachments: [] } });
    await tick();
    c.motorComecouAFalar();
    c.motorParouDeFalar();
    const anteriores = [{ quem: 'voce' as const, texto: 'Bom dia.', em: 1 }, { quem: 'newclaw' as const, texto: 'Opa!', em: 2 }];
    expect(c.trocarDeConversa('voz-antiga', anteriores)).toBe(true);
    expect(ultimo().mensagens).toEqual(anteriores);
    expect(ultimo().estado).toBe('pronto');
    c.enviarTexto('na antiga');
    await tick();
    expect(turnos.sessoes).toEqual(['s', 'voz-antiga']);
  });

  it('recusa enquanto há pedido em andamento (as respostas se misturariam)', async () => {
    const { c, turnos, ultimo } = montar();
    c.enviarTexto('demorado');
    expect(c.ocupada()).toBe(true); // já entre o envio e o aceite
    await tick();
    expect(c.trocarDeConversa('voz-outra')).toBe(false);
    expect(ultimo().mensagens.map((m) => m.texto)).toEqual(['demorado']);
    turnos.terminar('t1', { kind: 'finished', delivery: { kind: 'delivered', text: 'pronto', attachments: [] } });
    await tick();
    expect(c.ocupada()).toBe(false);
    expect(c.trocarDeConversa('voz-outra')).toBe(true);
  });

  it('corta a fala em curso e limpa a legenda', async () => {
    const { c, motor, ultimo } = montar();
    c.pessoaComecouAFalar();
    c.transcricao('meio dito', false);
    expect(c.trocarDeConversa('voz-nova')).toBe(true);
    expect(ultimo().legenda).toBe('');
    expect(ultimo().mensagens).toEqual([]);
    expect(motor.interrupcoes).toBe(0); // nada falando: não interrompe à toa
  });
});

describe('Conversa — ouvir de novo', () => {
  it('manda o mesmo texto ao motor de voz e não pede nada ao NewClaw', () => {
    const { c, motor, turnos, ultimo } = montar();
    c.repetir('Só o Nextcloud está fora.');
    expect(motor.falas).toEqual(['Só o Nextcloud está fora.']);
    expect(turnos.enviados).toEqual([]);
    expect(ultimo().fala).toEqual({ texto: 'Só o Nextcloud está fora.', fraseAtual: null });
  });

  it('corta a fala em curso antes de repetir', () => {
    const { c, motor } = montar();
    c.repetir('primeira');
    c.motorComecouAFalar();
    c.repetir('segunda');
    expect(motor.interrupcoes).toBe(1);
    expect(motor.falas).toEqual(['primeira', 'segunda']);
  });
});

describe('Conversa — corrigir e reenviar (ADR-039 do NewClaw)', () => {
  it('a fala errada fica marcada e o texto certo vai ao NewClaw como pedido novo', async () => {
    const { c, turnos, ultimo } = montar();
    c.enviarTexto('Qual a previsão do tempo para a Cornelia Procobre?');
    await tick();
    turnos.terminar('t1', { kind: 'finished', delivery: { kind: 'delivered', text: 'Qual cidade?', attachments: [] } });
    await tick();
    expect(c.corrigirEReenviar(0, 'Qual a previsão do tempo para Cornélio Procópio?')).toBe(true);
    await tick();
    expect(turnos.enviados).toEqual(['Qual a previsão do tempo para a Cornelia Procobre?', 'Qual a previsão do tempo para Cornélio Procópio?']);
    const m = ultimo().mensagens;
    expect(m[0]).toMatchObject({ quem: 'voce', corrigida: true });
    expect(m[m.length - 1]).toMatchObject({ quem: 'voce', texto: 'Qual a previsão do tempo para Cornélio Procópio?', correcao: true });
  });

  it('Parar e corrigir: para o pedido errado na hora, a tela sai da fila, e a resposta dele é descartada', async () => {
    const { c, motor, turnos, ultimo } = montar();
    c.enviarTexto('E o Rigger?');
    await tick();
    expect(c.emAndamento()).toBe(true);
    expect(ultimo().estado).toBe('fila');
    await c.pararParaCorrigir();
    expect(turnos.enviados).toEqual(['E o Rigger?', '/cancelar']);
    expect(ultimo().estado).toBe('pronto');  // sem esperar o NewClaw encerrar o turno parado
    expect(c.emAndamento()).toBe(false);
    // A fase do turno parado não volta à tela.
    turnos.fase('t1', 'running', { progress: { texto: 'buscando Rigger' } as never });
    expect(ultimo().estado).toBe('pronto');
    expect(ultimo().progresso).toBeNull();
    // A pessoa corrige e envia.
    expect(c.corrigirEReenviar(0, 'E o River?')).toBe(true);
    await tick();
    expect(turnos.enviados).toEqual(['E o Rigger?', '/cancelar', 'E o River?']);  // sem um segundo /cancelar
    // O pedido parado ainda termina (com o aviso do cancelamento ou com a resposta errada): nada disso é falado.
    turnos.terminar('t1', { kind: 'finished', delivery: { kind: 'delivered', text: 'Rigger é um cargo de montagem.', attachments: [] } });
    await tick();
    expect(motor.falas).toEqual([]);
    expect(ultimo().mensagens.map((m) => m.texto)).not.toContain('Rigger é um cargo de montagem.');
    expect(ultimo().estado).toBe('fila');  // a correção continua em andamento
    // A resposta da correção é falada normalmente.
    turnos.terminar('t3', { kind: 'finished', delivery: { kind: 'delivered', text: 'River é uma criptomoeda.', attachments: [] } });
    await tick();
    expect(motor.falas).toEqual(['River é uma criptomoeda.']);
    const m = ultimo().mensagens;
    expect(m[0]).toMatchObject({ quem: 'voce', corrigida: true });
    expect(m.find((x) => x.quem === 'aviso')?.texto).toBe('Parei o pedido para você corrigir.');
  });

  it('com a voz lendo a resposta: Parar e corrigir corta a fala, sem nada a cancelar no NewClaw', async () => {
    const { c, motor, turnos } = montar();
    c.enviarTexto('E o Rigger?');
    await tick();
    turnos.terminar('t1', { kind: 'finished', delivery: { kind: 'delivered', text: 'Rigger é um cargo.', attachments: [] } });
    await tick();
    c.motorComecouAFalar();
    await c.pararParaCorrigir();
    expect(motor.interrupcoes).toBe(1);
    expect(c.corrigirEReenviar(0, 'E o River?')).toBe(true);
    await tick();
    expect(turnos.enviados).toEqual(['E o Rigger?', 'E o River?']);
  });

  it('algo começou enquanto a pessoa editava: Enviar para antes e manda a correção', async () => {
    const { c, motor, turnos } = montar();
    c.enviarTexto('E o Rigger?');
    await tick();
    expect(c.corrigirEReenviar(0, 'E o River?')).toBe(true);
    await tick();
    await tick();
    expect(turnos.enviados).toEqual(['E o Rigger?', '/cancelar', 'E o River?']);
    turnos.terminar('t1', { kind: 'finished', delivery: { kind: 'delivered', text: 'Rigger é um cargo.', attachments: [] } });
    await tick();
    expect(motor.falas).toEqual([]);
  });

  it('sem nada em andamento, Parar e corrigir não faz nada', async () => {
    const { c, turnos, ultimo } = montar();
    await c.pararParaCorrigir();
    expect(turnos.enviados).toEqual([]);
    expect(ultimo()).toBeUndefined();
  });

  it('se o cancelamento falhar, a falha aparece e a correção vai assim mesmo', async () => {
    const { c, turnos, ultimo } = montar();
    c.enviarTexto('E o Rigger?');
    await tick();
    turnos.cancel = () => Promise.reject(new Error('sem rede'));
    await c.pararParaCorrigir();
    expect(ultimo().mensagens.map((m) => m.texto)).toContain('Não consegui parar o pedido anterior: sem rede');
    expect(c.corrigirEReenviar(0, 'E o River?')).toBe(true);
    await tick();
    expect(turnos.enviados).toEqual(['E o Rigger?', 'E o River?']);
  });

  it('só corrige fala da pessoa, e não manda texto vazio', async () => {
    const { c, turnos } = montar();
    c.enviarTexto('oi');
    await tick();
    turnos.terminar('t1', { kind: 'finished', delivery: { kind: 'delivered', text: 'Olá!', attachments: [] } });
    await tick();
    expect(c.corrigirEReenviar(1, 'outra coisa')).toBe(false);  // a resposta do NewClaw
    expect(c.corrigirEReenviar(0, '   ')).toBe(false);
    expect(turnos.enviados).toEqual(['oi']);
  });
});

describe('Conversa — contrato do turno v2 (ADR-033 do NewClaw)', () => {
  it('aceita a versão 1 e as maiores; recusa o que não é versão', () => {
    expect([1, 2, 3].every(versaoAceita)).toBe(true);
    expect([0, 1.5, '2', undefined, null].some(versaoAceita)).toBe(false);
  });

  it('mostra as etapas reais do objetivo e mantém as que já tinha quando nada mudou', async () => {
    const { c, turnos, ultimo } = montar();
    c.enviarTexto('Diagnostique os logs');
    await tick();
    expect(ultimo().etapas).toBeNull();
    const steps = [
      { id: 's1', description: 'Coletar os logs de hoje', state: 'concluida' as const },
      { id: 's2', description: 'Analisar os erros', state: 'executando' as const },
    ];
    turnos.fase('t1', 'running', { plan: { state: 'executando', generation: 1, revision: 3, steps } });
    expect(ultimo().etapas).toEqual(steps);
    turnos.fase('t1', 'running', { plan: { state: 'executando', generation: 1, revision: 3 } });
    expect(ultimo().etapas).toEqual(steps);
    turnos.fase('t1', 'running', { plan: null });
    expect(ultimo().etapas).toBeNull();
  });

  it('o aviso de fila provisório aparece como andamento, não é falado e não encerra o pedido', async () => {
    const { c, motor, turnos, ultimo } = montar();
    c.enviarTexto('E me envia');
    await tick();
    turnos.fase('t1', 'running');
    turnos.provisorio('t1', '🧠 Estou concluindo a tarefa anterior.');
    expect(ultimo().progresso).toBe('🧠 Estou concluindo a tarefa anterior.');
    expect(motor.falas).toEqual([]);
    expect(ultimo().mensagens.filter((m) => m.quem === 'newclaw')).toEqual([]);
    turnos.terminar('t1', { kind: 'finished', delivery: { kind: 'delivered', text: 'Enviado.', attachments: [] } });
    await tick();
    expect(motor.falas).toEqual(['Enviado.']);
    expect(ultimo().etapas).toBeNull();
  });

  it('a resposta guarda o resultado que o NewClaw decidiu', async () => {
    const { c, turnos, ultimo } = montar();
    c.enviarTexto('Gera o relatório');
    await tick();
    const outcome = { state: 'parcial' as const, steps: { total: 3, done: 2 } };
    turnos.terminar('t1', { kind: 'finished', delivery: { kind: 'delivered', text: 'Fiz parte.', attachments: [], outcome } });
    await tick();
    const resposta = ultimo().mensagens.find((m) => m.quem === 'newclaw');
    expect(resposta).toMatchObject({ texto: 'Fiz parte.', resultado: outcome });
  });

  it('com um NewClaw da versão 1 (sem campos novos), nada muda', async () => {
    const { c, turnos, ultimo } = montar();
    c.enviarTexto('oi');
    await tick();
    turnos.fase('t1', 'running');
    turnos.terminar('t1', { kind: 'finished', delivery: { kind: 'delivered', text: 'Olá!', attachments: [] } });
    await tick();
    const resposta = ultimo().mensagens.find((m) => m.quem === 'newclaw');
    expect(resposta && 'resultado' in resposta).toBe(false);
    expect(ultimo().etapas).toBeNull();
  });
});
