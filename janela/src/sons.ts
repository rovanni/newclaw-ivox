/** Sons discretos: um "tum" subindo quando o motor começa a ouvir a pessoa e outro descendo quando ela termina. */
let contexto: AudioContext | null = null;

export function tom(de: number, para: number): void {
  try {
    contexto = contexto ?? new AudioContext();
    const o = contexto.createOscillator();
    const g = contexto.createGain();
    const t0 = contexto.currentTime;
    o.frequency.setValueAtTime(de, t0);
    o.frequency.linearRampToValueAtTime(para, t0 + 0.12);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(0.08, t0 + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.18);
    o.connect(g).connect(contexto.destination);
    o.start(t0);
    o.stop(t0 + 0.2);
  } catch { /* sem áudio no navegador: segue sem som */ }
}

export const comecouAOuvir = () => tom(520, 780);
export const terminouDeOuvir = () => tom(780, 520);
