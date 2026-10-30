/**
 * Microfone local para o transporte SmallWebRTC, sem o daily-js.
 *
 * Por quê: o gerenciador padrão do transporte (DailyMediaManager) carrega, ao abrir, um script do CDN do Daily
 * (`c.daily.co/.../call-machine-object-bundle.js`) — código de terceiros baixado em tempo de execução, que a política de
 * conteúdo do harness bloqueia (achado da prova real, 30/10/2026). O alternativo do pacote (WavMediaManager) carrega
 * worklets por blob e não informa volume. Este usa só o navegador: `getUserMedia` e um `AnalyserNode` para o volume.
 *
 * Implementa o que o transporte chama no gerenciador (conferido no código do @pipecat-ai/small-webrtc-transport 1.10.8):
 * setClientOptions, initialize, connect, disconnect, tracks, enableMic, isMicEnabled, getAllMics/Cams/Speakers,
 * update*, selected*, enableCam, enableScreenShare, isCamEnabled, isSharingScreen, supportsScreenShare.
 */

type Callbacks = {
  onLocalAudioLevel?: (nivel: number) => void;
  onAvailableMicsUpdated?: (mics: MediaDeviceInfo[]) => void;
  onDeviceError?: (erro: unknown) => void;
};

/** O erro do navegador em palavras (os nomes vêm da especificação de getUserMedia). */
export function motivoDoMicrofone(e: unknown): string {
  const nome = e instanceof DOMException ? e.name : '';
  switch (nome) {
    case 'NotAllowedError': return 'o navegador não deu permissão ao microfone';
    case 'NotFoundError': return 'nenhum microfone encontrado';
    case 'NotReadableError': return 'o microfone está em uso por outro programa';
    case 'SecurityError': return 'a página não é segura (abra por https ou localhost)';
    default: return e instanceof Error ? e.message : String(e);
  }
}

/**
 * O Chrome deixa o áudio de uma página suspenso até a primeira interação (clique ou tecla). Ao recarregar a janela já com a
 * sessão aberta, ninguém clicou ainda: a medição do volume ficava em zero e a resposta do motor não tocava (achado da
 * prova com a operadora, 30/10/2026). Isto retoma o áudio na primeira interação.
 */
export function aoPrimeiroGesto(acao: () => void): void {
  const uma = () => {
    removeEventListener('pointerdown', uma, true);
    removeEventListener('keydown', uma, true);
    acao();
  };
  addEventListener('pointerdown', uma, true);
  addEventListener('keydown', uma, true);
}

/** Faixa de volume mostrada: -60 dB (silêncio de sala) vira 0; -10 dB (fala alta perto do microfone) vira 1. */
const PISO_DB = -60;
const TETO_DB = -10;

/**
 * Volume como o ouvido percebe (escala em dB), de 0 a 1. O RMS cru de uma fala normal fica entre 0,01 e 0,1 — a animação
 * mexia poucos pixels e parecia parada (achado da prova com a operadora, 30/10/2026).
 */
export function nivelPercebido(rms: number): number {
  if (rms <= 0) return 0;
  const db = 20 * Math.log10(rms);
  return Math.min(1, Math.max(0, (db - PISO_DB) / (TETO_DB - PISO_DB)));
}

/** Mede o volume (0 a 1, em escala percebida) de um MediaStream; devolve a função que para a medição. */
export function medirVolume(fluxo: MediaStream, aoMedir: (nivel: number) => void): () => void {
  const ctx = new AudioContext();
  if (ctx.state !== 'running') aoPrimeiroGesto(() => void ctx.resume());
  const analisador = ctx.createAnalyser();
  analisador.fftSize = 512;
  ctx.createMediaStreamSource(fluxo).connect(analisador);
  const amostras = new Float32Array(analisador.fftSize);
  const id = setInterval(() => {
    analisador.getFloatTimeDomainData(amostras);
    let soma = 0;
    for (const a of amostras) soma += a * a;
    aoMedir(nivelPercebido(Math.sqrt(soma / amostras.length)));
  }, 50);
  return () => { clearInterval(id); void ctx.close(); };
}

export class MicrofoneLocal {
  private _callbacks: Callbacks = {};
  private _options: unknown = null;
  private _micEnabled = true;
  private fluxo: MediaStream | null = null;
  private pararMedicao: (() => void) | null = null;

  /**
   * Sem microfone (permissão negada, nenhum aparelho), a ligação segue só de ida: a pessoa escreve e ouve a resposta.
   * `aoFalhar` recebe o motivo em palavras, para a tela mostrar.
   */
  constructor(private readonly aoFalhar: (motivo: string) => void = () => undefined) {}

  setUserAudioCallback(): void { /* o áudio vai pela trilha WebRTC, não por callback */ }

  setClientOptions(options: { callbacks?: Callbacks; enableMic?: boolean }, override = false): void {
    if (this._options && !override) return;
    this._options = options;
    this._callbacks = options.callbacks ?? {};
    this._micEnabled = options.enableMic ?? true;
  }

  async initialize(): Promise<void> {
    if (this.fluxo) return;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new DOMException('página não segura (use https ou localhost)', 'SecurityError');
      this.fluxo = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (e) {
      this.aoFalhar(motivoDoMicrofone(e));
      return;
    }
    this.aplicarMicrofone();
    this.pararMedicao = medirVolume(this.fluxo, (n) => this._callbacks.onLocalAudioLevel?.(this._micEnabled ? n : 0));
    this._callbacks.onAvailableMicsUpdated?.(await this.getAllMics());
  }

  async connect(): Promise<void> { await this.initialize(); }

  async disconnect(): Promise<void> {
    this.pararMedicao?.();
    this.pararMedicao = null;
    this.fluxo?.getTracks().forEach((t) => t.stop());
    this.fluxo = null;
  }

  tracks(): { local: { audio?: MediaStreamTrack } } {
    const audio = this.fluxo?.getAudioTracks()[0];
    return { local: audio ? { audio } : {} };
  }

  enableMic(ligado: boolean): void {
    this._micEnabled = ligado;
    this.aplicarMicrofone();
  }

  get isMicEnabled(): boolean { return this._micEnabled; }
  get isCamEnabled(): boolean { return false; }
  get isSharingScreen(): boolean { return false; }
  get supportsScreenShare(): boolean { return false; }
  get selectedMic(): MediaDeviceInfo | Record<string, never> { return {}; }
  get selectedCam(): Record<string, never> { return {}; }
  get selectedSpeaker(): Record<string, never> { return {}; }

  async getAllMics(): Promise<MediaDeviceInfo[]> {
    return (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'audioinput');
  }
  async getAllCams(): Promise<MediaDeviceInfo[]> { return []; }
  async getAllSpeakers(): Promise<MediaDeviceInfo[]> {
    return (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'audiooutput');
  }
  updateMic(): void { /* troca de microfone: fica para quando a janela tiver o seletor */ }
  updateCam(): void { /* sem câmera */ }
  updateSpeaker(): void { /* o áudio do motor toca no alto-falante padrão */ }
  enableCam(): void { /* sem câmera */ }
  enableScreenShare(): void { /* sem tela */ }

  /** Silenciar é desligar a trilha (`enabled = false`): o WebRTC passa a mandar silêncio, sem renegociar. */
  private aplicarMicrofone(): void {
    this.fluxo?.getAudioTracks().forEach((t) => { t.enabled = this._micEnabled; });
  }
}
