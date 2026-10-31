import { describe, expect, it } from 'vitest';
import { carregarModelo, intervaloDeLeitura, ondeFala, resumoDoModelo, type EstadoDoModelo } from './modelo';

const base: EstadoDoModelo = { estado: 'descarregado', em_uso: 0 };

describe('modelo de reconhecimento', () => {
  it('estado inicial: descarregado, sem ocupar memória, e a pessoa pode escrever', () => {
    const r = resumoDoModelo(base);
    expect(r.titulo).toBe('Modelo descarregado');
    expect(r.texto).toContain('continuar escrevendo');
  });

  it('memória insuficiente mostra o aviso medido pelo motor', () => {
    const r = resumoDoModelo({ ...base, pergunta: 'cpu', aviso: 'A GPU tem 1.0 GB livres e este modelo ocupou 2.2 GB na última carga.' });
    expect(r.titulo).toBe('Memória insuficiente na GPU');
    expect(r.texto).toContain('1.0 GB livres');
  });

  it('carregado na GPU mostra o consumo medido; sem medida, não inventa', () => {
    expect(resumoDoModelo({ ...base, estado: 'carregado', dispositivo: 'cuda', consumo_bytes: 2.2 * 2 ** 30 }).texto).toContain('2,2 GB');
    expect(resumoDoModelo({ ...base, estado: 'carregado', dispositivo: 'cuda' }).texto).toBe('Pode falar.');
  });

  it('falha mostra a mensagem como veio', () => {
    expect(resumoDoModelo({ ...base, estado: 'falha', erro: 'RuntimeError: CUDA failed with error out of memory' }).texto)
      .toContain('out of memory');
  });

  it('descarregando espera a transcrição em andamento', () => {
    expect(resumoDoModelo({ ...base, estado: 'descarregando', em_uso: 1 }).texto).toContain('transcrição em andamento');
  });

  it('lê rápido enquanto muda e devagar parado', () => {
    expect(intervaloDeLeitura({ ...base, estado: 'carregando' })).toBe(1000);
    expect(intervaloDeLeitura(base)).toBe(5000);
  });

  it('onde a fala roda vem dos provedores que o kokoro-onnx escolheu', () => {
    expect(ondeFala({ ...base, sintese: { motor: 'local', provedores: ['CUDAExecutionProvider', 'CPUExecutionProvider'] } }))
      .toBe('Kokoro · CUDAExecutionProvider');
    expect(ondeFala({ ...base, sintese: { motor: 'local', provedores: ['CPUExecutionProvider'] } })).toBe('Kokoro · CPU');
    expect(ondeFala({ ...base, sintese: null })).toBe('não configurada');
  });

  it('carregar na CPU manda o pedido explícito e repassa a recusa do motor', async () => {
    const pedidos: unknown[] = [];
    const ok = async (_u: string, init?: RequestInit) => { pedidos.push(JSON.parse(String(init?.body))); return new Response(JSON.stringify({ ...base, estado: 'carregando' })); };
    expect((await carregarModelo(true, ok)).estado).toBe('carregando');
    expect(pedidos).toEqual([{ na_cpu: true }]);
    const recusa = async () => new Response(JSON.stringify({ erro: 'o modelo está sendo descarregado' }), { status: 409 });
    await expect(carregarModelo(false, recusa)).rejects.toThrow('sendo descarregado');
  });
});
