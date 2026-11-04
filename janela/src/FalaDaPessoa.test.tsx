import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { FalaDaPessoa } from './Resposta';

describe('fala da pessoa: copiar e corrigir', () => {
  it('mostra Copiar e Corrigir e reenviar', () => {
    const h = renderToStaticMarkup(<FalaDaPessoa texto="Qual a previsão do tempo para a Cornelia Procobre?" podeReenviar aoReenviar={() => true} />);
    expect(h).toContain('>Copiar</button>');
    expect(h).toContain('>Corrigir e reenviar</button>');
  });

  it('corrigindo: o texto abre para editar, e Reenviar só liga com texto diferente e sem pedido em andamento', () => {
    const h = renderToStaticMarkup(<FalaDaPessoa texto="E o Rigger?" podeReenviar aoReenviar={() => true} iniciarEditando />);
    expect(h).toContain('aria-label="Texto corrigido"');
    expect(h).toContain('E o Rigger?</textarea>');
    expect(h).toMatch(/disabled="" title="Manda o texto corrigido ao NewClaw \(Enter\)">Reenviar/);  // igual ao original
    const ocupada = renderToStaticMarkup(<FalaDaPessoa texto="E o Rigger?" podeReenviar={false} aoReenviar={() => true} iniciarEditando />);
    expect(ocupada).toContain('Espere a resposta em andamento terminar, ou aperte Parar');
  });
});
