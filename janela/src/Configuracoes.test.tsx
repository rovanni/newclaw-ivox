import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { Configuracoes } from './Configuracoes';

const base = {
  aoFechar: () => undefined, vozes: [{ nome: 'pf_dora', rotulo: 'Dora', grupo: 'Português (Brasil)' }], vozAtual: 'pf_dora',
  aoTrocarVoz: () => undefined, gruposDeVozes: (v: { nome: string; rotulo: string }[]) => [['Português (Brasil)', v]] as never,
  velocidade: 1.25, aoMudarVelocidade: () => undefined, volume: 0.8, aoMudarVolume: () => undefined,
  semMicrofone: null, micAberto: true, tema: 'escuro' as const, aoMudarTema: () => undefined,
  estilo: 'particulas' as const, aoMudarEstilo: () => undefined,
  fundo: 'padrao' as const, aoMudarFundo: () => undefined, cores: 'estados' as const, aoMudarCores: () => undefined,
  atalhos: 'auto' as const, aoMudarAtalhos: () => undefined, economico: false, aoMudarEconomico: () => undefined,
  foco: false, aoMudarFoco: () => undefined, jeito: 'livre' as const, aoMudarJeito: () => undefined,
  espera: 'media' as const, aoMudarEspera: () => undefined, sons: true, aoMudarSons: () => undefined,
  ligado: 'ligado' as const, info: null, conversa: 'voz-1234',
  modelo: { estado: 'descarregado' as const, em_uso: 0 }, resumoDoModelo: { titulo: 'Modelo descarregado', texto: 'x' },
  ouvirConfigurado: true, aoCarregar: () => undefined, aoDescarregar: () => undefined,
  carregarAoAbrir: false, aoMudarCarregarAoAbrir: () => undefined, aoMudarOciosidade: () => undefined,
};

describe('ajustes', () => {
  it('abre em Áudio, com os cinco grupos e só parâmetros que o motor aceita', () => {
    const h = renderToStaticMarkup(<Configuracoes {...base} />);
    for (const g of ['Áudio', 'Aparência', 'Interação', 'Recursos', 'Conexão']) expect(h).toContain(`>${g}</button>`);
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

  it('recursos: descarregado por padrão, carregar só por botão, nada ao abrir a janela', () => {
    const h = renderToStaticMarkup(<Configuracoes {...base} grupoInicial="recursos" />);
    expect(h).toContain('Modelo descarregado');
    expect(h).toContain('>Carregar</button>');
    expect(h).toContain('ainda não medido');
    expect(h).toContain('não medida');
    expect(h).not.toMatch(/type="checkbox" checked=""/);  // "Carregar ao abrir a janela" desligado
    expect(h).toMatch(/aria-checked="true" class="ativo">Nunca</);  // descarregar sem uso: desligado
  });

  it('recursos: a pergunta da CPU aparece só quando o motor pergunta', () => {
    const h = renderToStaticMarkup(<Configuracoes {...base} grupoInicial="recursos"
      modelo={{ estado: 'falha', em_uso: 0, pergunta: 'cpu', erro: 'out of memory' }} />);
    expect(h).toContain('Tentar na CPU');
    expect(h).toContain('>Cancelar</button>');
    expect(renderToStaticMarkup(<Configuracoes {...base} grupoInicial="recursos" />)).not.toContain('Tentar na CPU');
  });

  it('é uma aba da janela, não uma caixa por cima da conversa', () => {
    const h = renderToStaticMarkup(<Configuracoes {...base} />);
    expect(h).toContain('role="tabpanel"');
    expect(h).not.toContain('aria-modal');
    expect(h).toContain('Voltar à conversa');
  });

  it('aparência: temas, fundos, cores do centro e atalhos, com o escolhido marcado', () => {
    const h = renderToStaticMarkup(<Configuracoes {...base} grupoInicial="aparencia" tema="neon" fundo="azul-claro" cores="azul" />);
    for (const o of ['Escuro', 'Claro', 'Neon', 'Do tema', 'Azul claro', 'Marinho', 'Grafite', 'Por estado', 'Ciano', 'Verde', 'Roxo', 'Somem ao começar', 'Sempre', 'Nunca']) {
      expect(h).toContain(`>${o}</button>`);
    }
    expect(h).toMatch(/aria-checked="true" class="ativo">Neon</);
    expect(h).toMatch(/aria-checked="true" class="ativo">Azul claro</);
    expect(h).toMatch(/aria-checked="true" class="ativo">Azul</);
    expect(h).toMatch(/aria-checked="true" class="ativo">Somem ao começar</);
  });
});
