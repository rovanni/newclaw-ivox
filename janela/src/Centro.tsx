/**
 * O centro da janela: círculo (SVG) ou partículas (canvas), na cor do estado, reagindo ao volume de verdade — o da pessoa
 * quando ela fala, o do motor quando o NewClaw fala. Nos outros estados, um movimento calmo próprio de cada um.
 *
 * A animação lê o estado e os volumes por referência a cada quadro, sem re-renderizar o React.
 */
import { useEffect, useRef } from 'react';
import type { EstadoDaTela } from './estado';
import { NOMES } from './estado';
import type { Niveis } from './motor';

export type EstiloDoCentro = 'circulo' | 'particulas';

const N_BARRAS = 96;
const R0 = 104;
const N_PONTOS = 700;
/** No estado "Pronto", o centro acompanha de leve o microfone: a pessoa vê que ele está vivo antes de o VAD confirmar a fala. */
const ECO_DO_MICROFONE_PRONTO = 0.5;
/** Amplitude própria de cada estado quando não há voz tocando (movimento calmo, sem fingir fala). */
const AMPLITUDE_PARADA: Record<EstadoDaTela, number> = {
  pronto: 0.05, ouvindo: 0.05, fila: 0.1, pensando: 0.15, falando: 0.1, aprovacao: 0.5, erro: 0.1,
};

interface Props {
  estado: EstadoDaTela;
  estilo: EstiloDoCentro;
  niveis: Niveis;
  tempo: string;
}

export function Centro({ estado, estilo, niveis, tempo }: Props) {
  const area = useRef<HTMLDivElement>(null);
  const barras = useRef<SVGGElement>(null);
  const ondas = useRef<SVGGElement>(null);
  const nucleo = useRef<SVGGElement>(null);
  const halo = useRef<SVGCircleElement>(null);
  const luz = useRef<SVGCircleElement>(null);
  const tela = useRef<HTMLCanvasElement>(null);
  const atual = useRef({ estado, estilo });
  atual.current = { estado, estilo };

  useEffect(() => {
    const NS = 'http://www.w3.org/2000/svg';
    const linhas: { el: SVGLineElement; cos: number; sin: number }[] = [];
    for (let i = 0; i < N_BARRAS; i++) {
      const a = (i / N_BARRAS) * Math.PI * 2 - Math.PI / 2;
      const el = document.createElementNS(NS, 'line');
      barras.current!.appendChild(el);
      linhas.push({ el, cos: Math.cos(a), sin: Math.sin(a) });
    }
    const circulosOnda = [0, 1, 2].map((k) => {
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', '200'); c.setAttribute('cy', '200');
      ondas.current!.appendChild(c);
      return { c, fase: k / 3 };
    });
    // Esfera de pontos (espiral de Fibonacci), com um pouco de ruído por ponto.
    const pontos = Array.from({ length: N_PONTOS }, (_, i) => {
      const y = 1 - (i / (N_PONTOS - 1)) * 2;
      const r = Math.sqrt(1 - y * y);
      const th = i * 2.399963;
      return { x: Math.cos(th) * r, y, z: Math.sin(th) * r, ruido: Math.random() };
    });
    const calmo = matchMedia('(prefers-reduced-motion: reduce)').matches;
    let t = 0, suave = 0, giro = 0, quadro = 0;
    let corChave = '', cor = '#3ea6ff';

    const nivelAgora = (e: EstadoDaTela) => {
      if (e === 'ouvindo') return niveis.voce;
      if (e === 'falando') return niveis.motor;
      const a = AMPLITUDE_PARADA[e];
      if (e === 'pronto') return Math.max(a * (0.6 + 0.4 * Math.sin(t * 1.2)), niveis.voce * ECO_DO_MICROFONE_PRONTO);
      return e === 'aprovacao' ? a * (0.5 + 0.5 * Math.sin(t * 3)) : a * (0.6 + 0.4 * Math.sin(t * 1.2));
    };

    const desenharParticulas = (e: EstadoDaTela, ehNewClaw: boolean) => {
      const c = tela.current!;
      const ctx = c.getContext('2d');
      if (!ctx) return;
      const dpr = window.devicePixelRatio || 1;
      const lado = c.clientWidth;
      if (c.width !== Math.round(lado * dpr)) { c.width = c.height = Math.round(lado * dpr); }
      const esc = (lado * dpr) / 400;
      ctx.setTransform(esc, 0, 0, esc, 0, 0);
      ctx.clearRect(0, 0, 400, 400);
      const chave = `${e}${document.documentElement.dataset.tema}`;
      if (chave !== corChave) {
        corChave = chave;
        cor = getComputedStyle(area.current!).getPropertyValue('--cor-voz').trim() || cor;
      }
      const pensando = e === 'pensando' || e === 'fila';
      giro += pensando ? 0.02 : 0.004 + suave * 0.01;
      const R = 120 * (pensando ? 0.85 + 0.05 * Math.sin(t * 3) : 1) * (e === 'aprovacao' ? 1 + 0.06 * Math.sin(t * 6) : 1);
      const cg = Math.cos(giro), sg = Math.sin(giro), ci = Math.cos(0.35), si = Math.sin(0.35);
      ctx.fillStyle = cor;
      for (const p of pontos) {
        const x = p.x * cg + p.z * sg;
        let z = -p.x * sg + p.z * cg;
        const y = p.y * ci - z * si;
        z = p.y * si + z * ci;
        let k = 1;
        if (e === 'ouvindo') k += suave * (0.25 + 0.6 * p.ruido);
        else if (ehNewClaw) k += suave * 0.22 * Math.sin(p.y * 9 - t * 7);
        else k += 0.02 * Math.sin(t * 1.5 + p.ruido * 6);
        const prof = (z + 1) / 2;
        ctx.globalAlpha = 0.15 + prof * 0.75;
        ctx.beginPath();
        ctx.arc(200 + x * R * k, 200 + y * R * k, 0.6 + prof * 1.6 + (ehNewClaw ? suave * 0.8 : 0), 0, Math.PI * 2);
        ctx.fill();
      }
      const g = ctx.createRadialGradient(200, 200, 0, 200, 200, 70 + suave * 50);
      g.addColorStop(0, cor);
      g.addColorStop(1, 'transparent');
      ctx.globalAlpha = 0.18 + suave * 0.4;
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, 400, 400);
      ctx.globalAlpha = 1;
    };

    const passo = () => {
      t += 0.05;
      const { estado: e, estilo: s } = atual.current;
      suave += (nivelAgora(e) - suave) * 0.3;
      const ehNewClaw = e === 'falando';
      if (s === 'particulas') {
        desenharParticulas(e, ehNewClaw);
      } else {
        // Você fala: as barras em volta reagem (o som "entra"). O NewClaw fala: a luz pulsa e saem ondas (o som "sai").
        for (const o of circulosOnda) {
          const p = (t * 0.25 + o.fase) % 1;
          o.c.setAttribute('r', String(96 + p * 100));
          o.c.setAttribute('stroke-width', String(3 * (1 - p) + 0.5));
          o.c.style.opacity = String(ehNewClaw ? (1 - p) * (0.25 + suave * 0.75) : 0);
        }
        linhas.forEach((b, i) => {
          const faixa = 0.35 + 0.65 * Math.abs(Math.sin(t * 2 + i * 0.37) * Math.cos(t * 1.3 + i * 0.11));
          const comp = 4 + (e === 'pensando' ? 10 * (0.5 + 0.5 * Math.sin(t * 4 + i * 0.4))
            : ehNewClaw || e === 'fila' || e === 'erro' || e === 'aprovacao' ? 3 : faixa * suave * 70);
          const r1 = R0 + (ehNewClaw ? 0 : suave * 10);
          b.el.setAttribute('x1', String(200 + b.cos * r1)); b.el.setAttribute('y1', String(200 + b.sin * r1));
          b.el.setAttribute('x2', String(200 + b.cos * (r1 + comp))); b.el.setAttribute('y2', String(200 + b.sin * (r1 + comp)));
          b.el.style.opacity = String(0.35 + 0.65 * Math.min(1, comp / 30));
        });
        nucleo.current!.style.transform = `scale(${calmo ? 1 : 1 + suave * (ehNewClaw ? 0.18 : 0.12)})`;
        halo.current!.style.opacity = String(0.12 + suave * 0.55);
        halo.current!.style.transform = `scale(${0.85 + suave * 0.35})`;
        luz.current!.style.transform = `scale(${0.7 + suave * 1.3})`;
        luz.current!.style.opacity = String(0.35 + suave * 0.65);
      }
      quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    return () => {
      cancelAnimationFrame(quadro);
      linhas.forEach((b) => b.el.remove());
      circulosOnda.forEach((o) => o.c.remove());
    };
  }, [niveis]);

  return (
    <div className="globo-area" data-centro={estilo} ref={area}>
      <canvas className="particulas" ref={tela} aria-hidden="true" />
      <div className="estado-centro" aria-live="polite">
        <b><span className="ponto" />{NOMES[estado]}</b>
        <small>{tempo}</small>
      </div>
      <svg viewBox="0 0 400 400" aria-hidden="true" className="circulo">
        <defs>
          <radialGradient id="mar" cx="40%" cy="35%" r="70%">
            <stop offset="0%" style={{ stopColor: 'var(--cor-voz)' }} stopOpacity=".55" />
            <stop offset="70%" style={{ stopColor: 'var(--globo-mar)' }} />
          </radialGradient>
          <radialGradient id="haloCor" cx="50%" cy="50%" r="50%">
            <stop offset="55%" style={{ stopColor: 'var(--cor-voz)' }} stopOpacity=".9" />
            <stop offset="100%" style={{ stopColor: 'var(--cor-voz)' }} stopOpacity="0" />
          </radialGradient>
        </defs>
        <g className="anel gira-1">
          <circle cx="200" cy="200" r="190" fill="none" stroke="var(--destaque)" strokeOpacity=".35" strokeWidth="1" strokeDasharray="2 6" />
          <path d="M200 10 A190 190 0 0 1 390 200" fill="none" stroke="var(--destaque-2)" strokeWidth="3" strokeLinecap="round" />
          <path d="M200 390 A190 190 0 0 1 10 200" fill="none" stroke="var(--destaque-2)" strokeWidth="3" strokeLinecap="round" />
        </g>
        <g className="anel gira-2">
          <circle cx="200" cy="200" r="168" fill="none" stroke="var(--destaque)" strokeWidth="6" strokeOpacity=".5" strokeDasharray="1 5" />
          <path d="M68 96 A168 168 0 0 1 200 32" fill="none" stroke="var(--destaque)" strokeWidth="4" strokeLinecap="round" />
          <path d="M332 304 A168 168 0 0 1 200 368" fill="none" stroke="var(--destaque)" strokeWidth="4" strokeLinecap="round" />
        </g>
        <circle className="halo" ref={halo} cx="200" cy="200" r="150" fill="url(#haloCor)" opacity=".15" style={{ transformOrigin: '200px 200px' }} />
        <g className="barras" ref={barras} />
        <g className="ondas" ref={ondas} />
        <g className="nucleo" ref={nucleo}>
          <circle className="borda-nucleo" cx="200" cy="200" r="96" fill="url(#mar)" strokeWidth="2" />
          <circle cx="200" cy="200" r="80" fill="none" style={{ stroke: 'var(--cor-voz)' }} strokeOpacity=".35" strokeWidth="1" />
          <circle className="luz" ref={luz} cx="200" cy="200" r="34" fill="url(#haloCor)" />
          <circle className="luz-miolo" cx="200" cy="200" r="10" />
        </g>
      </svg>
    </div>
  );
}
