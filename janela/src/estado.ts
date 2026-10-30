/**
 * Estado da tela, derivado de fatos (nunca do texto das mensagens).
 *
 * Os fatos vêm de duas fontes: o motor de voz (a pessoa está falando? o motor está falando?) e o contrato do turno do
 * NewClaw (em que fase está o pedido). A tela só traduz; quem decide a fase do turno é o NewClaw.
 */

export type EstadoDaTela = 'pronto' | 'ouvindo' | 'fila' | 'pensando' | 'falando' | 'aprovacao' | 'erro';

/** Fases do contrato do turno, versão 1 (`phaseFromActive` do `turn-client.js`). */
export type FaseDoTurno = 'accepted' | 'running' | 'awaiting_approval' | 'finished';

export interface Fatos {
  /** A ligação com o motor ou com o NewClaw caiu; o texto é o motivo, para mostrar como veio. */
  erro: string | null;
  /** O VAD do motor detectou a pessoa falando. */
  pessoaFalando: boolean;
  /**
   * A pessoa parou, mas ainda dentro da pausa que encerra a fala: o VAD diz "parou" em qualquer silêncio de 0,2 s, e a tela
   * saía de "Ouvindo" a cada respiro (achado da prova com a operadora, 30/10/2026). A tela segue o mesmo critério do envio.
   */
  emPausa: boolean;
  /** O motor está tocando áudio. */
  motorFalando: boolean;
  /** Fase mais relevante dos turnos em andamento (null: nenhum). */
  turno: FaseDoTurno | null;
  /** A resposta chegou e foi mandada ao motor, que ainda não começou a tocar. */
  aguardandoFala: boolean;
}

export const FATOS_INICIAIS: Fatos = {
  erro: null, pessoaFalando: false, emPausa: false, motorFalando: false, turno: null, aguardandoFala: false,
};

/**
 * Ordem das perguntas:
 *  1. erro de ligação vence tudo (nada mais na tela é confiável);
 *  2. a pessoa falando, ou numa pausa da fala, vence o resto (ela pode estar interrompendo o motor);
 *  3. aprovação pendente: o trabalho está parado esperando um clique;
 *  4. o motor tocando a resposta;
 *  5. o pedido aceito, ainda sem nada rastreável → na fila;
 *  6. o pedido em execução, ou a resposta pronta esperando o motor começar → pensando;
 *  7. nada disso → pronto.
 */
export function estadoDaTela(f: Fatos): EstadoDaTela {
  if (f.erro) return 'erro';
  if (f.pessoaFalando || f.emPausa) return 'ouvindo';
  if (f.turno === 'awaiting_approval') return 'aprovacao';
  if (f.motorFalando) return 'falando';
  if (f.turno === 'accepted') return 'fila';
  if (f.turno === 'running' || f.aguardandoFala) return 'pensando';
  return 'pronto';
}

/** Com vários turnos da mesma conversa em andamento, a tela mostra o que mais pede atenção. */
const PRIORIDADE: Record<FaseDoTurno, number> = { awaiting_approval: 3, running: 2, accepted: 1, finished: 0 };

export function faseMaisRelevante(fases: Iterable<FaseDoTurno>): FaseDoTurno | null {
  let melhor: FaseDoTurno | null = null;
  for (const f of fases) {
    if (f === 'finished') continue;
    if (melhor === null || PRIORIDADE[f] > PRIORIDADE[melhor]) melhor = f;
  }
  return melhor;
}

export const NOMES: Record<EstadoDaTela, string> = {
  pronto: 'Pronto',
  ouvindo: 'Ouvindo você',
  fila: 'Na fila',
  pensando: 'Pensando',
  falando: 'Falando',
  aprovacao: 'Precisa de você',
  erro: 'Erro',
};

/** Estados em que há trabalho do NewClaw que o botão Parar pode interromper. */
export function podeParar(e: EstadoDaTela): boolean {
  return e === 'fila' || e === 'pensando' || e === 'falando';
}
