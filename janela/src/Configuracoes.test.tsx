import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { Configuracoes } from './Configuracoes';

const base = {
  aoFechar: () => undefined, vozes: [{ nome: 'pf_dora', rotulo: 'Dora', grupo: 'Português (Brasil)' }], vozAtual: 'pf_dora',
  aoTrocarVoz: () => undefined, gruposDeVozes: (v: { nome: string; rotulo: string }[]) => [['Português (Brasil)', v]] as never,
  velocidade: 1.25, aoMudarVelocidade: () => undefined, volume: 0.8, aoMudarVolume: () => undefined,
  semMicrofone: null, micAberto: true, tema: 'escuro' as const, aoMudarTema: () => undefined,
  estilo: 'particulas' as const, aoMudarEstilo: () => undefined, economico: false, aoMudarEconomico: () => undefined,
  foco: false, aoMudarFoco: () => undefined, jeito: 'livre' as const, aoMudarJeito: () => undefined,
  espera: 'media' as const, aoMudarEspera: () => undefined, sons: true, aoMudarSons: () => undefined,
  ligado: 'ligado' as const, info: null, conversa: 'voz-1234',
};

describe('ajustes', () => {
  it('abre em Áudio, com os quatro grupos e só parâmetros que o motor aceita', () => {
    const h = renderToStaticMarkup(<Configuracoes {...base} />);
    for (const g of ['Áudio', 'Aparência', 'Interação', 'Conexão']) expect(h).toContain(`>${g}</button>`);
    expect(h).toMatch(/min="0.5" max="2" step="0.05" aria-label="Velocidade da fala" value="1.25"/);  // a faixa do Kokoro
    expect(h).toContain('0,5x a 2x');
    expect(h).toContain('1,25x');
    expect(h).toContain('80%');
    expect(h).toContain('● Aberto');
  });

  it('sem motor ligado, a velocidade fica travada', () => {
    const h = renderToStaticMarkup(<Configuracoes {...base} ligado="ligando" />);
    expect(h).toMatch(/aria-label="Velocidade da fala" disabled=""/);
  });
});
