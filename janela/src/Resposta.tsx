/**
 * Texto de uma mensagem do NewClaw em Markdown (títulos, listas, tabelas, código), e as ações dela: copiar e ouvir de novo.
 * Nas falas da pessoa: copiar e "Corrigir e reenviar" (quando a transcrição errou).
 *
 * Seguro por construção: o `react-markdown` não interpreta HTML embutido (vira texto) e só aceita links http(s), mailto
 * e âncoras; os links abrem numa aba nova, sem acesso a esta página. Nada aqui reescreve o conteúdo — a tela mostra o
 * que o NewClaw respondeu, como ele respondeu.
 */
import { useState, type KeyboardEvent } from 'react';
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

function BotaoCopiar({ texto, dica }: { texto: string; dica: string }) {
  const [copiado, setCopiado] = useState<'sim' | 'falhou' | null>(null);
  return (
    <button className="btn mini" onClick={async () => { setCopiado((await copiar(texto)) ? 'sim' : 'falhou'); setTimeout(() => setCopiado(null), 1500); }}
      title={dica}>
      {copiado === 'sim' ? 'Copiado' : copiado === 'falhou' ? 'Não copiou' : 'Copiar'}
    </button>
  );
}

export function AcoesDaResposta({ texto, aoOuvir, podeOuvir }: { texto: string; aoOuvir: () => void; podeOuvir: boolean }) {
  return (
    <div className="acoes-resposta">
      <BotaoCopiar texto={texto} dica="Copiar a resposta (com a formatação em Markdown)" />
      <button className="btn mini" onClick={aoOuvir} disabled={!podeOuvir}
        title={podeOuvir ? 'Ouvir de novo: a voz lê o mesmo texto, sem pedir nada ao NewClaw' : 'Escolha uma voz para ouvir'}>
        Ouvir de novo
      </button>
    </div>
  );
}

/**
 * Uma fala (ou mensagem escrita) da pessoa, com copiar e "Corrigir e reenviar". Corrigir abre o texto para editar ali
 * mesmo; "Enviar" manda o texto certo como pedido novo. Com pedido em andamento o botão é "Parar e corrigir": para o
 * pedido na hora e abre o texto, porque quem corrige já sabe que o pedido foi entendido errado (decisão D2, operadora em
 * 07/11/2026). Depois de corrigir, o botão é "Enviar".
 */
export function FalaDaPessoa({ texto, emAndamento, aoPararParaCorrigir, aoReenviar, iniciarEditando = false }: {
  texto: string; emAndamento: boolean; aoPararParaCorrigir: () => void; aoReenviar: (texto: string) => boolean;
  iniciarEditando?: boolean;
}) {
  const [editando, setEditando] = useState(iniciarEditando);
  const [novo, setNovo] = useState(texto);
  const mudou = novo.trim() !== '' && novo.trim() !== texto.trim();
  const reenviar = () => { if (mudou && aoReenviar(novo)) setEditando(false); };
  const tecla = (ev: KeyboardEvent<HTMLTextAreaElement>) => {
    if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); reenviar(); }
    if (ev.key === 'Escape') { ev.stopPropagation(); setEditando(false); setNovo(texto); }
  };
  if (editando) {
    return (
      <div className="corrigir">
        <textarea value={novo} onChange={(e) => setNovo(e.target.value)} onKeyDown={tecla} autoFocus rows={2}
          aria-label="Texto corrigido" />
        <div className="acoes-resposta">
          <button className="btn mini primario" onClick={reenviar} disabled={!mudou}
            title={mudou ? 'Manda o texto corrigido ao NewClaw (Enter)' : 'Mude o texto para enviar'}>
            Enviar
          </button>
          <button className="btn mini" onClick={() => { setEditando(false); setNovo(texto); }} title="Desistir da correção (Esc)">Cancelar</button>
        </div>
      </div>
    );
  }
  return (
    <div className="acoes-resposta">
      <BotaoCopiar texto={texto} dica="Copiar o que você disse ou escreveu" />
      <button className="btn mini" onClick={() => { if (emAndamento) aoPararParaCorrigir(); setNovo(texto); setEditando(true); }}
        title={emAndamento ? 'Entendeu errado? Para o pedido agora e abre o texto para corrigir'
          : 'A transcrição errou? Corrija o texto e mande de novo'}>
        {emAndamento ? 'Parar e corrigir' : 'Corrigir e reenviar'}
      </button>
    </div>
  );
}
