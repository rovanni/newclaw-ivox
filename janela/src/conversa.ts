/**
 * Controlador da conversa: liga o que o motor de voz percebe ao turno do NewClaw e devolve a resposta ao motor para falar.
 *
 * Não depende de React, do Pipecat nem do navegador: o motor e o cliente do turno entram por interfaces, e o relógio é
 * injetável. Assim a lógica inteira é testada com falsos (`conversa.test.ts`).
 *
 * O que ele NÃO faz (ADR-030): não tem LLM, não decide nada sobre o pedido e não aprova nada por voz. Aprovação só por
 * `decidir()`, que a tela chama a partir de um clique.
 */
import { estadoDaTela, FATOS_INICIAIS, faseMaisRelevante, type EstadoDaTela, type FaseDoTurno, type Fatos } from './estado';
import type { Aprovacao, ClienteDoTurno, Entrega, Etapa, EstadoDoTurno, ResultadoDaTarefa } from './turnos';

/** O que a janela pede ao motor de voz (protocolo v3 do `controle.py`). */
export interface Motor {
  falar(texto: string): void;
  interromper(): void;
}

export interface Relogio {
  agora(): number;
  depois(ms: number, fn: () => void): () => void;
}

export const RELOGIO_REAL: Relogio = {
  agora: () => Date.now(),
  depois: (ms, fn) => {
    const id = setTimeout(fn, ms);
    return () => clearTimeout(id);
  },
};

export type JeitoDeFalar = 'livre' | 'segurar';

export interface Mensagem {
  quem: 'voce' | 'newclaw' | 'aviso';
  texto: string;
  em: number;
  porVoz?: boolean;
  /** A pessoa corrigiu esta fala e reenviou o texto certo (a fala continua na coluna, marcada). */
  corrigida?: boolean;
  /** Contrato v2: o resultado que o NewClaw decidiu para a tarefa desta resposta (só em objetivo). */
  resultado?: ResultadoDaTarefa;
  /** Esta mensagem é a correção da fala anterior marcada como `corrigida`. */
  correcao?: boolean;
}

export interface Quadro {
  estado: EstadoDaTela;
  fatos: Fatos;
  /** Desde quando a tela está no estado atual (ms do relógio). */
  desde: number;
  /** O que a pessoa está dizendo agora (legenda ao vivo). */
  legenda: string;
  /** A resposta que o motor está falando e a frase em curso, para destacar. */
  fala: { texto: string; fraseAtual: string | null } | null;
  progresso: string | null;
  /** Contrato v2: as etapas reais do objetivo em andamento; `null` quando não há objetivo (ou o NewClaw é da versão 1). */
  etapas: Etapa[] | null;
  aprovacoes: Aprovacao[];
  mensagens: Mensagem[];
}

export interface OpcoesDaConversa {
  motor: Motor;
  turnos: ClienteDoTurno;
  sessionId: string;
  aoMudar: (q: Quadro) => void;
  relogio?: Relogio;
  /**
   * Mãos livres: quanto silêncio, depois de o motor fechar o último trecho, encerra o pedido. O motor já espera 0,8 s de
   * silêncio para fechar um trecho (`PAUSA_QUE_FECHA_O_TRECHO_S` no motor.py); somando esta espera, o pedido sai com
   * cerca de 1,4 s de silêncio. Ela ainda junta trechos de uma mesma fala separados por uma pausa mais longa.
   */
  pausaParaEnviarMs?: number;
}

/**
 * Quanto a pessoa pode hesitar antes de o pedido sair, escolhido por ela no cartão "Modo voz". O valor é a espera da janela;
 * o silêncio total até o envio soma os 0,8 s que o motor leva para fechar o trecho. A curta (~1,4 s) dividia uma fala com
 * hesitação em dois pedidos ("Então, eu..." / "com três monitor utilizado.") — prova com a operadora, 30/10/2026, e ela
 * pediu ~2 s.
 */
export type EsperaAntesDeEnviar = 'curta' | 'media' | 'longa';
export const ESPERA_ANTES_DE_ENVIAR_MS: Record<EsperaAntesDeEnviar, number> = { curta: 600, media: 1200, longa: 2200 };
export const PAUSA_PARA_ENVIAR_PADRAO_MS = ESPERA_ANTES_DE_ENVIAR_MS.media;

export class Conversa {
  private fatos: Fatos = { ...FATOS_INICIAIS };
  private estado: EstadoDaTela = 'pronto';
  private desde: number;
  private legendaFinal = '';
  private legendaParcial = '';
  private fala: Quadro['fala'] = null;
  private progresso: string | null = null;
  private etapas: Etapa[] | null = null;
  private aprovacoes: Aprovacao[] = [];
  private mensagens: Mensagem[] = [];
  private fases = new Map<string, FaseDoTurno>();
  private esperas = new Map<string, AbortController>();
  private cancelarEnvio: (() => void) | null = null;
  private jeito: JeitoDeFalar = 'livre';
  private segurando = false;
  private readonly relogio: Relogio;
  private pausaMs: number;
  private sessionId: string;
  /** Pedidos entre o envio e o aceite do NewClaw (ainda sem `turnId` em `fases`). */
  private enviando = 0;

  constructor(private readonly o: OpcoesDaConversa) {
    this.sessionId = o.sessionId;
    this.relogio = o.relogio ?? RELOGIO_REAL;
    this.pausaMs = o.pausaParaEnviarMs ?? PAUSA_PARA_ENVIAR_PADRAO_MS;
    this.desde = this.relogio.agora();
  }

  quadro(): Quadro {
    const legenda = [this.legendaFinal, this.legendaParcial].filter(Boolean).join(' ');
    return {
      estado: this.estado, fatos: { ...this.fatos }, desde: this.desde, legenda, fala: this.fala,
      progresso: this.progresso, etapas: this.etapas, aprovacoes: this.aprovacoes, mensagens: this.mensagens,
    };
  }

  // ─── O que o motor percebe ─────────────────────────────────────────────────

  pessoaComecouAFalar(): void {
    this.desarmarEnvio();
    this.mudar({ pessoaFalando: true });
  }

  pessoaParouDeFalar(): void {
    // Começa a pausa: a tela continua em "Ouvindo" até o pedido sair (ou até ficar claro que não houve fala).
    this.mudar({ pessoaFalando: false, emPausa: true });
    this.armarEnvio();
  }

  /** Transcrição do Whisper. `final` fecha o trecho; o parcial só aparece na legenda. */
  transcricao(texto: string, final: boolean): void {
    const t = texto.trim();
    if (final) {
      if (t) this.legendaFinal = this.legendaFinal ? `${this.legendaFinal} ${t}` : t;
      this.legendaParcial = '';
      // O Whisper termina o trecho depois de o VAD dizer "parou": a pausa recomeça a contar daqui.
      if (!this.fatos.pessoaFalando) {
        if (t && !this.fatos.emPausa) this.mudar({ emPausa: true });
        this.armarEnvio();
      }
    } else {
      this.legendaParcial = t;
    }
    this.publicar();
  }

  motorComecouAFalar(): void {
    this.mudar({ motorFalando: true, aguardandoFala: false });
  }

  /**
   * O texto da última resposta continua na tela depois que o áudio acaba (entre uma frase e outra o motor também "para"):
   * só uma resposta nova o substitui.
   */
  motorParouDeFalar(): void {
    if (this.fala) this.fala = { ...this.fala, fraseAtual: null };
    this.mudar({ motorFalando: false });
  }

  /** O motor avisa qual frase está tocando (evento `bot-tts-text`). */
  fraseFalada(texto: string): void {
    if (this.fala) {
      this.fala = { ...this.fala, fraseAtual: texto };
      this.publicar();
    }
  }

  /** O motor recusou um pedido de fala (por exemplo, nenhuma voz escolhida): sem isso a tela ficaria em "pensando". */
  motorRecusou(motivo: string): void {
    this.mudar({ aguardandoFala: false });
    this.avisar(`O motor de voz não falou a resposta: ${motivo}`);
  }

  ligacaoCaiu(motivo: string): void {
    this.mudar({ erro: motivo, pessoaFalando: false, motorFalando: false });
  }

  ligacaoVoltou(): void {
    this.mudar({ erro: null });
  }

  // ─── O que a pessoa faz na tela ────────────────────────────────────────────

  definirEspera(e: EsperaAntesDeEnviar): void {
    this.pausaMs = ESPERA_ANTES_DE_ENVIAR_MS[e];
  }

  definirJeitoDeFalar(j: JeitoDeFalar): void {
    this.jeito = j;
    this.segurando = false;
  }

  /** Segurar espaço: enquanto a tecla estiver apertada, nada é enviado e a tela fica em "Ouvindo". */
  comecouASegurar(): void {
    this.segurando = true;
    this.desarmarEnvio();
    this.mudar({ emPausa: true });
  }

  soltou(): void {
    this.segurando = false;
    this.armarEnvio();
  }

  enviarTexto(texto: string): void {
    const t = texto.trim();
    if (t) void this.enviar(t, false);
  }

  /**
   * Corrigir e reenviar (ADR-039 do NewClaw, pedido da operadora em 04/11/2026): a fala na posição `indice` fica marcada
   * como corrigida e o texto certo vai ao NewClaw como pedido novo. Com pedido em andamento, recusa (devolve false): parar
   * a resposta atual é decisão da pessoa, pelo botão Parar, não desta função.
   */
  corrigirEReenviar(indice: number, texto: string): boolean {
    const t = texto.trim();
    const original = this.mensagens[indice];
    if (!t || !original || original.quem !== 'voce' || this.ocupada()) return false;
    this.mensagens = this.mensagens.map((m, i) => (i === indice ? { ...m, corrigida: true } : m));
    void this.enviar(t, false, true);
    return true;
  }

  /** Parar: corta a fala do motor e pede ao NewClaw que interrompa o que esta conversa estiver fazendo. */
  async parar(): Promise<void> {
    if (this.fatos.motorFalando || this.fatos.aguardandoFala) this.o.motor.interromper();
    this.mudar({ aguardandoFala: false });
    if (this.fases.size > 0) await this.o.turnos.cancel({ sessionId: this.sessionId });
  }

  /** Aprovação de ação perigosa: só por esta chamada, que a tela faz a partir de um clique. */
  async decidir(txnId: string, decisao: 'approved' | 'rejected'): Promise<void> {
    const r = await this.o.turnos.decide({ sessionId: this.sessionId, txnId, decision: decisao });
    this.aprovacoes = this.aprovacoes.filter((a) => a.txnId !== txnId);
    if (r.kind === 'decided') {
      if (r.text.trim()) this.responder(r.text);
      else this.publicar();
    } else {
      this.avisar(`O NewClaw recusou a decisão (HTTP ${r.status}): ${r.error}`);
    }
  }

  /**
   * Ouvir de novo uma resposta que já está na tela: o mesmo texto vai ao motor de voz, sem pedido nenhum ao NewClaw (o
   * modelo de linguagem não é chamado). Se a voz estiver falando, a fala atual é cortada antes.
   */
  repetir(texto: string): void {
    if (!texto.trim()) return;
    if (this.fatos.motorFalando || this.fatos.aguardandoFala) this.o.motor.interromper();
    this.fala = { texto, fraseAtual: null };
    this.o.motor.falar(texto);
    this.mudar({ aguardandoFala: true });
  }

  /** Há pedido desta conversa em andamento no NewClaw (trocar de conversa agora misturaria as respostas). */
  ocupada(): boolean {
    return this.fases.size > 0 || this.enviando > 0;
  }

  /**
   * Passa a falar noutra conversa do NewClaw (uma nova ou uma retomada do histórico). `anteriores` são as mensagens que a
   * tela mostra dela. Recusa (devolve false) enquanto houver pedido em andamento; a fala em curso é cortada.
   */
  trocarDeConversa(sessionId: string, anteriores: Mensagem[] = []): boolean {
    if (this.ocupada()) return false;
    this.desarmarEnvio();
    if (this.fatos.motorFalando || this.fatos.aguardandoFala) this.o.motor.interromper();
    this.sessionId = sessionId;
    this.legendaFinal = '';
    this.legendaParcial = '';
    this.fala = null;
    this.progresso = null;
    this.aprovacoes = [];
    this.mensagens = [...anteriores];
    this.mudar({ ...FATOS_INICIAIS });
    return true;
  }

  /** Fechar a janela não cancela os turnos (contrato do turno); só para de acompanhá-los. */
  encerrar(): void {
    this.desarmarEnvio();
    for (const c of this.esperas.values()) c.abort();
    this.esperas.clear();
  }

  // ─── Turnos ────────────────────────────────────────────────────────────────

  /**
   * Fim da fala = uma pausa inteira (`pausaMs`) sem voz depois do último trecho. Aí o pedido sai; se nada foi transcrito
   * (um ruído, uma tosse), a tela volta a "Pronto" sem mandar nada.
   */
  private armarEnvio(): void {
    this.desarmarEnvio();
    if (this.jeito === 'segurar' && this.segurando) return;
    this.cancelarEnvio = this.relogio.depois(this.pausaMs, () => {
      this.cancelarEnvio = null;
      if (this.fatos.pessoaFalando || (this.jeito === 'segurar' && this.segurando)) return;
      const pedido = this.legendaFinal;
      this.legendaFinal = '';
      this.legendaParcial = '';
      if (pedido) void this.enviar(pedido, true);
      else this.mudar({ emPausa: false });
    });
  }

  private desarmarEnvio(): void {
    this.cancelarEnvio?.();
    this.cancelarEnvio = null;
  }

  private async enviar(texto: string, porVoz: boolean, correcao = false): Promise<void> {
    this.mensagens = [...this.mensagens, { quem: 'voce', texto, em: this.relogio.agora(), porVoz, ...(correcao ? { correcao } : {}) }];
    this.publicar();
    this.enviando++;
    let r: Awaited<ReturnType<ClienteDoTurno['send']>>;
    try {
      r = await this.o.turnos.send({ sessionId: this.sessionId, message: texto });
    } finally {
      this.enviando--;
    }
    if (r.kind === 'rejected') {
      this.mudar({ emPausa: false });
      const espera = r.retryAfterSec ? ` Tente de novo em ${r.retryAfterSec} s.` : '';
      this.avisar(`O NewClaw não aceitou o pedido (HTTP ${r.status}): ${r.error}.${espera}`);
      return;
    }
    // A pausa acaba e o turno entra na mesma mudança: de "Ouvindo" direto para "Na fila".
    this.fatos = { ...this.fatos, emPausa: false };
    this.fases.set(r.turnId, 'accepted');
    this.atualizarTurno();
    const controle = new AbortController();
    this.esperas.set(r.turnId, controle);
    const fim = await this.o.turnos.waitForTurn({
      sessionId: this.sessionId, turnId: r.turnId, signal: controle.signal,
      onState: (s) => this.aoEstadoDoTurno(s),
      // v2: o aviso de fila não é a resposta. Aparece como andamento, sem ser falado, e a espera continua.
      onProvisional: (e: Entrega) => { this.progresso = e.text; this.publicar(); },
    });
    this.esperas.delete(r.turnId);
    this.fases.delete(r.turnId);
    if (this.fases.size === 0) { this.progresso = null; this.etapas = null; this.aprovacoes = []; }
    const resposta = fim.kind === 'finished' && fim.delivery && fim.delivery.text.trim() ? fim.delivery.text : null;
    if (resposta) {
      // O turno sai e a fala entra na mesma mudança: sem passar por "pronto" entre "pensando" e "falando".
      this.fatos = { ...this.fatos, turno: faseMaisRelevante(this.fases.values()) };
      this.responder(resposta, fim.kind === 'finished' ? fim.delivery?.outcome : undefined);
      return;
    }
    this.atualizarTurno();
    switch (fim.kind) {
      case 'finished':
        if (!fim.delivery) this.avisar('A resposta não veio pela entrega; ela está no histórico do NewClaw.');
        break;
      case 'timeout':
        this.avisar('Parei de acompanhar este pedido depois de 45 min; ele continua no NewClaw.');
        break;
      case 'unreachable':
        this.mudar({ erro: `Sem resposta do NewClaw (${fim.lastError}).` });
        break;
      case 'rejected':
        this.mudar({ erro: `O NewClaw recusou o acompanhamento (HTTP ${fim.status}); entre de novo.` });
        break;
      case 'aborted':
        break;
    }
  }

  private aoEstadoDoTurno(s: EstadoDoTurno): void {
    // "finished" chega antes de a resposta ser retirada da outbox: a fase anterior continua valendo até `waitForTurn`
    // devolver a entrega (sem isso a tela passava por "pronto" por um instante — achado da prova real, 30/10).
    if (s.phase !== 'finished') this.fases.set(s.turnId, s.phase);
    this.aprovacoes = s.approvals;
    this.progresso = s.progress ? s.progress.texto : null;
    // v2: etapas só quando há objetivo; `steps` ausente quer dizer "nada mudou" e vale o que já está na tela.
    if (!s.plan) this.etapas = null;
    else if (s.plan.steps) this.etapas = s.plan.steps;
    if (this.fatos.erro) this.fatos = { ...this.fatos, erro: null };
    this.atualizarTurno();
  }

  private atualizarTurno(): void {
    this.mudar({ turno: faseMaisRelevante(this.fases.values()) });
  }

  private responder(texto: string, resultado?: ResultadoDaTarefa): void {
    this.mensagens = [...this.mensagens, { quem: 'newclaw', texto, em: this.relogio.agora(), ...(resultado ? { resultado } : {}) }];
    this.fala = { texto, fraseAtual: null };
    this.o.motor.falar(texto);
    this.mudar({ aguardandoFala: true });
  }

  private avisar(texto: string): void {
    this.mensagens = [...this.mensagens, { quem: 'aviso', texto, em: this.relogio.agora() }];
    this.publicar();
  }

  private mudar(parcial: Partial<Fatos>): void {
    this.fatos = { ...this.fatos, ...parcial };
    const novo = estadoDaTela(this.fatos);
    if (novo !== this.estado) {
      this.estado = novo;
      this.desde = this.relogio.agora();
    }
    this.publicar();
  }

  private publicar(): void {
    this.o.aoMudar(this.quadro());
  }
}
