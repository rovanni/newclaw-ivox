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
import type { Aprovacao, ClienteDoTurno, EstadoDoTurno } from './turnos';

/** O que a janela pede ao motor de voz (protocolo v2 do `controle.py`). */
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
  private aprovacoes: Aprovacao[] = [];
  private mensagens: Mensagem[] = [];
  private fases = new Map<string, FaseDoTurno>();
  private esperas = new Map<string, AbortController>();
  private cancelarEnvio: (() => void) | null = null;
  private jeito: JeitoDeFalar = 'livre';
  private segurando = false;
  private readonly relogio: Relogio;
  private pausaMs: number;

  constructor(private readonly o: OpcoesDaConversa) {
    this.relogio = o.relogio ?? RELOGIO_REAL;
    this.pausaMs = o.pausaParaEnviarMs ?? PAUSA_PARA_ENVIAR_PADRAO_MS;
    this.desde = this.relogio.agora();
  }

  quadro(): Quadro {
    const legenda = [this.legendaFinal, this.legendaParcial].filter(Boolean).join(' ');
    return {
      estado: this.estado, fatos: { ...this.fatos }, desde: this.desde, legenda, fala: this.fala,
      progresso: this.progresso, aprovacoes: this.aprovacoes, mensagens: this.mensagens,
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

  /** Parar: corta a fala do motor e pede ao NewClaw que interrompa o que esta conversa estiver fazendo. */
  async parar(): Promise<void> {
    if (this.fatos.motorFalando || this.fatos.aguardandoFala) this.o.motor.interromper();
    this.mudar({ aguardandoFala: false });
    if (this.fases.size > 0) await this.o.turnos.cancel({ sessionId: this.o.sessionId });
  }

  /** Aprovação de ação perigosa: só por esta chamada, que a tela faz a partir de um clique. */
  async decidir(txnId: string, decisao: 'approved' | 'rejected'): Promise<void> {
    const r = await this.o.turnos.decide({ sessionId: this.o.sessionId, txnId, decision: decisao });
    this.aprovacoes = this.aprovacoes.filter((a) => a.txnId !== txnId);
    if (r.kind === 'decided') {
      if (r.text.trim()) this.responder(r.text);
      else this.publicar();
    } else {
      this.avisar(`O NewClaw recusou a decisão (HTTP ${r.status}): ${r.error}`);
    }
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

  private async enviar(texto: string, porVoz: boolean): Promise<void> {
    this.mensagens = [...this.mensagens, { quem: 'voce', texto, em: this.relogio.agora(), porVoz }];
    this.publicar();
    const r = await this.o.turnos.send({ sessionId: this.o.sessionId, message: texto });
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
      sessionId: this.o.sessionId, turnId: r.turnId, signal: controle.signal,
      onState: (s) => this.aoEstadoDoTurno(s),
    });
    this.esperas.delete(r.turnId);
    this.fases.delete(r.turnId);
    if (this.fases.size === 0) { this.progresso = null; this.aprovacoes = []; }
    const resposta = fim.kind === 'finished' && fim.delivery && fim.delivery.text.trim() ? fim.delivery.text : null;
    if (resposta) {
      // O turno sai e a fala entra na mesma mudança: sem passar por "pronto" entre "pensando" e "falando".
      this.fatos = { ...this.fatos, turno: faseMaisRelevante(this.fases.values()) };
      this.responder(resposta);
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
    if (this.fatos.erro) this.fatos = { ...this.fatos, erro: null };
    this.atualizarTurno();
  }

  private atualizarTurno(): void {
    this.mudar({ turno: faseMaisRelevante(this.fases.values()) });
  }

  private responder(texto: string): void {
    this.mensagens = [...this.mensagens, { quem: 'newclaw', texto, em: this.relogio.agora() }];
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
