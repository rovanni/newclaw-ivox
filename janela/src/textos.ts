/** Textos derivados do quadro da conversa, puros para serem testados. */
import type { Quadro } from './conversa';

/** A linha de detalhe embaixo do centro: o que está acontecendo, em palavras. */
export function detalhe(q: Quadro): string {
  switch (q.estado) {
    case 'ouvindo': return 'Você está falando';
    case 'fila': return 'O NewClaw recebeu o pedido e vai começar';
    case 'pensando': return q.progresso ?? (q.fatos.aguardandoFala ? 'Preparando a fala da resposta' : 'O NewClaw está trabalhando');
    case 'falando': return 'O NewClaw está respondendo';
    case 'aprovacao': return 'Aguardando você aprovar ou recusar uma ação';
    case 'erro': return q.fatos.erro ?? 'Erro';
    default: return 'Pronto';
  }
}

export function tempoDecorrido(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
}

/**
 * Divide a resposta em três partes para destacar a frase que o motor está falando. O motor fala o texto já limpo
 * (sem marcação); quando a frase não aparece igual no original, não há destaque — melhor que destacar o trecho errado.
 */
export function partesDaFala(texto: string, fraseAtual: string | null): [string, string, string] {
  if (!fraseAtual) return [texto, '', ''];
  const i = texto.indexOf(fraseAtual.trim());
  if (i < 0) return [texto, '', ''];
  const fim = i + fraseAtual.trim().length;
  return [texto.slice(0, i), texto.slice(i, fim), texto.slice(fim)];
}

export function hora(ms: number): string {
  return new Date(ms).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}
