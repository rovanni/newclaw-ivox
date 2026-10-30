import { describe, expect, it } from 'vitest';
import { nivelPercebido } from './microfone';

describe('nivelPercebido', () => {
  it('silêncio fica em 0 e fala alta chega a 1', () => {
    expect(nivelPercebido(0)).toBe(0);
    expect(nivelPercebido(0.0005)).toBe(0); // abaixo de -60 dB
    expect(nivelPercebido(0.5)).toBe(1); // acima de -10 dB
  });

  it('fala normal (RMS 0,02 a 0,1) cai no meio da faixa, visível na animação', () => {
    expect(nivelPercebido(0.02)).toBeGreaterThan(0.4);
    expect(nivelPercebido(0.1)).toBeGreaterThan(0.7);
    expect(nivelPercebido(0.1)).toBeLessThan(1);
  });

  it('cresce com o volume', () => {
    expect(nivelPercebido(0.01)).toBeLessThan(nivelPercebido(0.05));
  });
});
