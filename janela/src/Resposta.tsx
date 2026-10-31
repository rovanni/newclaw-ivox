/**
 * Texto de uma mensagem do NewClaw em Markdown (títulos, listas, tabelas, código), e as ações dela: copiar e ouvir de novo.
 *
 * Seguro por construção: o `react-markdown` não interpreta HTML embutido (vira texto) e só aceita links http(s), mailto
 * e âncoras; os links abrem numa aba nova, sem acesso a esta página. Nada aqui reescreve o conteúdo — a tela mostra o
 * que o NewClaw respondeu, como ele respondeu.
 */
import { useState } from 'react';
import Markdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';

/** Só endereços que um clique pode abrir sem risco; o resto vira link vazio. */
export function enderecoSeguro(url: string): string {
  const limpo = defaultUrlTransform(url);
  return /^(https?:|mailto:|#)/i.test(limpo) ? limpo : '';
}

export function TextoFormatado({ texto }: { texto: string }) {
  return (
    <div className="md">
      <Markdown
        remarkPlugins={[remarkGfm]}
        urlTransform={enderecoSeguro}
        components={{
          a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
          // Imagens de endereço externo carregariam de fora sem a pessoa pedir: ficam como link.
          img: ({ src, alt }) => (typeof src === 'string' && src ? <a href={src} target="_blank" rel="noopener noreferrer">{alt || src}</a> : null),
        }}
      >
        {texto}
      </Markdown>
    </div>
  );
}

/** Copia para a área de transferência; sem a API (página fora de contexto seguro), cai na seleção de texto. */
export async function copiar(texto: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(texto);
    return true;
  } catch {
    const area = document.createElement('textarea');
    area.value = texto;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand('copy');
    area.remove();
    return ok;
  }
}

export function AcoesDaResposta({ texto, aoOuvir, podeOuvir }: { texto: string; aoOuvir: () => void; podeOuvir: boolean }) {
  const [copiado, setCopiado] = useState<'sim' | 'falhou' | null>(null);
  return (
    <div className="acoes-resposta">
      <button className="btn mini" onClick={async () => { setCopiado((await copiar(texto)) ? 'sim' : 'falhou'); setTimeout(() => setCopiado(null), 1500); }}
        title="Copiar a resposta (com a formatação em Markdown)">
        {copiado === 'sim' ? 'Copiado' : copiado === 'falhou' ? 'Não copiou' : 'Copiar'}
      </button>
      <button className="btn mini" onClick={aoOuvir} disabled={!podeOuvir}
        title={podeOuvir ? 'Ouvir de novo: a voz lê o mesmo texto, sem pedir nada ao NewClaw' : 'Escolha uma voz para ouvir'}>
        Ouvir de novo
      </button>
    </div>
  );
}
