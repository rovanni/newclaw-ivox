import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { FalaDaPessoa } from './Resposta';

const nada = () => {};

describe('fala da pessoa: copiar e corrigir', () => {
  it('mostra Copiar e Corrigir e reenviar', () => {
    const h = renderToStaticMarkup(<FalaDaPessoa texto="Qual a previsão do tempo para a Cornelia Procobre?" emAndamento={false}
      aoPararParaCorrigir={nada} aoReenviar={() => true} />);
    expect(h).toContain('>Copiar</button>');
    expect(h).toContain('>Corrigir e reenviar</button>');
  });

  it('com pedido em andamento o botão é "Parar e corrigir" (decisão D2, 07/11/2026)', () => {
    const h = renderToStaticMarkup(<FalaDaPessoa texto="E o Rigger?" emAndamento aoPararParaCorrigir={nada} aoReenviar={() => true} />);
    expect(h).toContain('>Parar e corrigir</button>');
    expect(h).not.toContain('>Corrigir e reenviar</button>');
  });

  it('corrigindo: o texto abre para editar, e Enviar só liga com texto diferente', () => {
    for (const emAndamento of [false, true]) {
      const h = renderToStaticMarkup(<FalaDaPessoa texto="E o Rigger?" emAndamento={emAndamento} aoPararParaCorrigir={nada}
        aoReenviar={() => true} iniciarEditando />);
      expect(h).toContain('aria-label="Texto corrigido"');
      expect(h).toContain('E o Rigger?</textarea>');
      expect(h).toMatch(/disabled="" title="Mude o texto para enviar">Enviar</);  // igual ao original
    }
  });
});
