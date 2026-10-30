/**
 * Ligação com o motor de voz do harness: Pipecat (cliente RTVI) com o transporte SmallWebRTC, pela sinalização do próprio
 * harness (`/api/offer`, que exige a sessão). Nenhum servidor STUN/TURN de terceiros: a ligação é local.
 *
 * Traduz os eventos do motor para a `Conversa` e implementa o protocolo v2 da janela → motor (`controle.py`): falar,
 * interromper, vozes, voz.
 */
import { PipecatClient } from '@pipecat-ai/client-js';
import { SmallWebRTCTransport } from '@pipecat-ai/small-webrtc-transport';
import type { Conversa, Motor } from './conversa';
import { aoPrimeiroGesto, medirVolume, MicrofoneLocal } from './microfone';

type OpcoesDoTransporte = NonNullable<ConstructorParameters<typeof SmallWebRTCTransport>[0]>;

export interface Voz {
  nome: string;
  rotulo: string;
  mistura?: Record<string, number>;
}

/** Volume de 0 a 1, atualizado pelos eventos do transporte; lido a cada quadro pela animação, sem re-renderizar a tela. */
export interface Niveis {
  voce: number;
  motor: number;
}

const ESPERA_RESPOSTA_MS = 15_000;

function motivoDoErro(e: unknown): string {
  if (e && typeof e === 'object') {
    const o = e as Record<string, unknown>;
    const d = o.data as Record<string, unknown> | undefined;
    if (d && typeof d.error === 'string') return d.error;
    if (typeof o.message === 'string') return o.message;
  }
  return String(e);
}

export class LigacaoComOMotor implements Motor {
  readonly niveis: Niveis = { voce: 0, motor: 0 };
  private cliente: PipecatClient | null = null;
  private audio: HTMLAudioElement;
  private pararVolumeDoMotor: (() => void) | null = null;

  /** Motivo de o microfone não ter aberto (a ligação segue só com texto); null quando abriu. */
  semMicrofone: string | null = null;

  constructor(private readonly conversa: () => Conversa, private readonly aoMudarMicrofone: () => void = () => undefined) {
    this.audio = new Audio();
    this.audio.autoplay = true;
  }

  async conectar(): Promise<void> {
    // Microfone próprio no lugar do DailyMediaManager padrão, que baixaria código do CDN do Daily (ver microfone.ts).
    const transporte = new SmallWebRTCTransport({
      webrtcRequestParams: { endpoint: '/api/offer' },
      mediaManager: new MicrofoneLocal((motivo) => { this.semMicrofone = motivo; this.aoMudarMicrofone(); }) as unknown as OpcoesDoTransporte['mediaManager'],
    });
    const c = this.conversa;
    this.cliente = new PipecatClient({
      transport: transporte,
      enableMic: true,
      enableCam: false,
      callbacks: {
        onUserStartedSpeaking: () => c().pessoaComecouAFalar(),
        onUserStoppedSpeaking: () => c().pessoaParouDeFalar(),
        onUserTranscript: (d) => c().transcricao(d.text, d.final),
        onBotStartedSpeaking: () => c().motorComecouAFalar(),
        onBotStoppedSpeaking: () => c().motorParouDeFalar(),
        onBotTtsText: (d) => c().fraseFalada(d.text),
        onLocalAudioLevel: (nivel) => { this.niveis.voce = nivel; },
        onTrackStarted: (trilha, participante) => {
          // O áudio do motor chega como trilha remota: toca num <audio> e o volume é medido aqui mesmo.
          if (trilha.kind === 'audio' && !participante?.local) {
            const fluxo = new MediaStream([trilha]);
            this.audio.srcObject = fluxo;
            // Sem interação ainda na página, o Chrome recusa tocar: tenta de novo no primeiro clique ou tecla.
            void this.audio.play().catch(() => aoPrimeiroGesto(() => void this.audio.play().catch(() => undefined)));
            this.pararVolumeDoMotor?.();
            this.pararVolumeDoMotor = medirVolume(fluxo, (n) => { this.niveis.motor = n; });
          }
        },
        onDisconnected: () => c().ligacaoCaiu('A ligação com o motor de voz caiu.'),
      },
    });
    await this.cliente.initDevices();
    await this.cliente.connect();
    c().ligacaoVoltou();
  }

  async desconectar(): Promise<void> {
    this.pararVolumeDoMotor?.();
    this.pararVolumeDoMotor = null;
    await this.cliente?.disconnect();
    this.cliente = null;
  }

  // ─── Motor (protocolo v2) ──────────────────────────────────────────────────

  falar(texto: string): void {
    if (!this.cliente) return this.conversa().motorRecusou('o motor de voz não está ligado');
    this.cliente.sendClientRequest('falar', { texto }, ESPERA_RESPOSTA_MS)
      .catch((e) => this.conversa().motorRecusou(motivoDoErro(e)));
  }

  interromper(): void {
    this.cliente?.sendClientMessage('interromper');
  }

  async vozes(): Promise<{ vozes: Voz[]; atual: string | null }> {
    if (!this.cliente) return { vozes: [], atual: null };
    const r = (await this.cliente.sendClientRequest('vozes', {}, ESPERA_RESPOSTA_MS)) as { vozes?: Voz[]; atual?: string | null };
    return { vozes: r?.vozes ?? [], atual: r?.atual ?? null };
  }

  async trocarVoz(nome: string): Promise<void> {
    if (!this.cliente) throw new Error('o motor de voz não está ligado');
    await this.cliente.sendClientRequest('voz', { voz: nome }, ESPERA_RESPOSTA_MS);
  }

  /** Segurar espaço: o microfone só fica aberto enquanto a tecla estiver apertada. */
  microfone(aberto: boolean): void {
    this.cliente?.enableMic(aberto);
  }
}
