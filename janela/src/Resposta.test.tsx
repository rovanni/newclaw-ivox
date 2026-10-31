import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { enderecoSeguro, TextoFormatado } from './Resposta';

const html = (texto: string) => renderToStaticMarkup(<TextoFormatado texto={texto} />);

describe('resposta em Markdown', () => {
  it('formata títulos, listas, negrito, código e tabela', () => {
    const h = html('## Diagnóstico\n\n- **disco** cheio\n- `nginx` parado\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```sh\nls\n```');
    expect(h).toContain('<h2>Diagnóstico</h2>');
    expect(h).toContain('<li><strong>disco</strong> cheio</li>');
    expect(h).toContain('<code>nginx</code>');
    expect(h).toContain('<table>');
    expect(h).toContain('<pre><code class="language-sh">ls');
  });

  it('HTML embutido não vira HTML (fica como texto)', () => {
    const h = html('oi <img src=x onerror="alert(1)"> <script>alert(2)</script>');
    expect(h).not.toContain('<img');
    expect(h).not.toContain('<script');
  });

  it('links abrem em aba nova, e só endereços seguros', () => {
    expect(html('[site](https://exemplo.org)')).toContain('href="https://exemplo.org" target="_blank" rel="noopener noreferrer"');
    expect(html('[x](javascript:alert(1))')).not.toContain('javascript:');
    expect(enderecoSeguro('data:text/html,oi')).toBe('');
    expect(enderecoSeguro('mailto:a@exemplo.org')).toBe('mailto:a@exemplo.org');
  });

  it('imagem externa não carrega sozinha: vira link', () => {
    const h = html('![grafico](https://exemplo.org/g.png)');
    expect(h).not.toContain('<img');
    expect(h).toContain('href="https://exemplo.org/g.png"');
  });
});
