/**
 * Dicionário da voz (ADR-039 do NewClaw, Revisão 2, 07/11/2026): as palavras que a pessoa ensina para o reconhecimento
 * acertar nomes próprios e termos raros ("River", e não "Rigger").
 *
 * - A lista mora no NewClaw (`GET`/`PUT /api/voz/vocabulario`, pelo harness), para ir no backup dele.
 * - Quem decide o que entra é sempre a pessoa: depois de uma correção, a janela só PROPÕE a palavra (o cartão), e a pessoa
 *   aprende, muda ou recusa. Errar é comum: a lista inteira é editável, e "Desfazer" grava a lista anterior.
 * - A janela manda a lista ao motor, em ordem de importância (o Whisper corta o fim quando não cabe).
 *
 * Tudo aqui é determinístico e testado sem navegador (`vocabulario.test.ts`): a comparação de textos olha só a forma.
 */

export interface PalavraDaVoz {
  /** Como deve aparecer na transcrição. */
  palavra: string;
  /** Como o reconhecimento tinha escrito, nas correções que a pessoa confirmou. */
  ouvia: string[];
  /** Quantas vezes a pessoa confirmou esta palavra. */
  vezes: number;
  criadaEm: string;
  atualizadaEm: string;
}

export interface Vocabulario {
  revisao: number;
  palavras: PalavraDaVoz[];
}

/** O que o motor respondeu: quantas palavras, do começo da lista, cabem no Whisper carregado. */
export interface ContaDoMotor {
  usadas: number;
  total: number;
  tokens: number;
  teto: number;
}

/** Outra janela gravou antes: a lista atual vem junto, para a pessoa conferir. */
export class ListaMudou extends Error {
  constructor(readonly atual: Vocabulario) {
    super('A lista mudou em outra janela. Confira e tente de novo.');
  }
}

/** O NewClaw (ou o harness) não tem a rota: versão anterior à Revisão 2 da ADR-039. */
export class DicionarioIndisponivel extends Error {}

type Buscar = (url: string, init?: RequestInit) => Promise<Response>;
const buscarPadrao: Buscar = (url, init) => fetch(url, { credentials: 'same-origin', ...init });
const ROTA = '/newclaw/api/voz/vocabulario';

async function corpoDe(r: Response): Promise<Record<string, unknown>> {
  return (await r.json().catch(() => ({}))) as Record<string, unknown>;
}

function comoVocabulario(d: Record<string, unknown>): Vocabulario {
  if (typeof d.revisao !== 'number' || !Array.isArray(d.palavras)) throw new Error('o NewClaw respondeu sem a lista de palavras');
  return { revisao: d.revisao, palavras: d.palavras as PalavraDaVoz[] };
}

function motivo(r: Response, d: Record<string, unknown>): string {
  return String(d.error ?? d.erro ?? `o NewClaw respondeu HTTP ${r.status}`);
}

export async function lerVocabulario(buscar: Buscar = buscarPadrao): Promise<Vocabulario> {
  const r = await buscar(ROTA);
  const d = await corpoDe(r);
  if (r.status === 404) throw new DicionarioIndisponivel('Este NewClaw ainda não guarda o dicionário da voz: atualize o NewClaw e a voz.');
  if (!r.ok) throw new Error(motivo(r, d));
  return comoVocabulario(d);
}

export async function gravarVocabulario(revisao: number, palavras: PalavraDaVoz[], buscar: Buscar = buscarPadrao): Promise<Vocabulario> {
  const r = await buscar(ROTA, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ revisao, palavras }),
  });
  const d = await corpoDe(r);
  if (r.status === 409) throw new ListaMudou(comoVocabulario(d));
  if (r.status === 404) throw new DicionarioIndisponivel('Este NewClaw ainda não guarda o dicionário da voz: atualize o NewClaw e a voz.');
  if (!r.ok) throw new Error(motivo(r, d));
  return comoVocabulario(d);
}

// ─── A comparação da correção ───────────────────────────────────────────────

/** Palavra para comparar: minúsculas e sem pontuação nas pontas ("Procobre?" e "procobre" são a mesma). */
const normal = (p: string) => p.toLocaleLowerCase('pt-BR').replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '');
const semPontuacaoNasPontas = (t: string) => t.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '');

/**
 * O trecho que a pessoa trocou, se a correção for de forma "troquei estas palavras": um único trecho diferente, com pelo
 * menos uma palavra igual antes ou depois dele. Frase reescrita inteira, só apagar palavras, ou nada mudado: `null` (não
 * há palavra para propor). Não interpreta sentido: quem decide se é erro de escuta é a pessoa, no cartão.
 */
export function trechoTrocado(ouvido: string, corrigido: string): { ouvido: string; certo: string } | null {
  const a = ouvido.split(/\s+/).filter(Boolean);
  const b = corrigido.split(/\s+/).filter(Boolean);
  let ini = 0;
  while (ini < a.length && ini < b.length && normal(a[ini]) === normal(b[ini])) ini++;
  let fim = 0;
  while (fim < a.length - ini && fim < b.length - ini && normal(a[a.length - 1 - fim]) === normal(b[b.length - 1 - fim])) fim++;
  if (ini === 0 && fim === 0) return null;  // nada igual em volta: é outra frase
  const certo = semPontuacaoNasPontas(b.slice(ini, b.length - fim).join(' '));
  const errado = semPontuacaoNasPontas(a.slice(ini, a.length - fim).join(' '));
  if (!certo || normal(certo) === normal(errado)) return null;
  return { ouvido: errado, certo };
}

// ─── A lista ────────────────────────────────────────────────────────────────

/** Os mesmos tetos de proteção da rota do NewClaw; não são o tamanho bom da lista (esse vem da medição, D1). */
export const TETO_DE_PALAVRAS = 200;
export const TETO_DE_CARACTERES = 60;
export const TETO_DE_OUVIDAS = 10;

const igual = (x: string, y: string) => x.toLocaleLowerCase('pt-BR') === y.toLocaleLowerCase('pt-BR');
const limpo = (t: string) => t.split(/\s+/).filter(Boolean).join(' ');

/**
 * Aprender (ou reforçar) uma palavra. Já existe (sem diferença de maiúsculas): soma uma vez e guarda o "eu ouvia" novo;
 * os mais antigos saem quando passa do teto. Não existe: entra no fim.
 */
export function aprender(lista: PalavraDaVoz[], palavra: string, ouvido: string | null, agora: string): PalavraDaVoz[] {
  const p = limpo(palavra);
  const o = ouvido ? limpo(ouvido) : '';
  if (!p) return lista;
  const i = lista.findIndex((x) => igual(x.palavra, p));
  const ouviaNovo = (antes: string[]) =>
    (o && !igual(o, p) && !antes.some((x) => igual(x, o)) ? [...antes, o] : antes).slice(-TETO_DE_OUVIDAS);
  if (i >= 0) {
    return lista.map((x, j) => (j === i ? { ...x, vezes: x.vezes + 1, ouvia: ouviaNovo(x.ouvia), atualizadaEm: agora } : x));
  }
  return [...lista, { palavra: p, ouvia: ouviaNovo([]), vezes: 1, criadaEm: agora, atualizadaEm: agora }];
}

/** Editar uma linha da tela. Recusa (com o motivo) palavra vazia, longa demais ou igual a outra da lista. */
export function editar(lista: PalavraDaVoz[], indice: number, palavra: string, ouvia: string[], agora: string): PalavraDaVoz[] | string {
  const p = limpo(palavra);
  if (!p) return 'Escreva a palavra.';
  if (p.length > TETO_DE_CARACTERES) return `Use no máximo ${TETO_DE_CARACTERES} letras.`;
  if (lista.some((x, j) => j !== indice && igual(x.palavra, p))) return `"${p}" já está na lista.`;
  const os = ouvia.map(limpo).filter((o) => o && !igual(o, p)).filter((o, k, arr) => arr.findIndex((y) => igual(y, o)) === k);
  if (os.some((o) => o.length > TETO_DE_CARACTERES)) return `Cada "eu ouvia" com no máximo ${TETO_DE_CARACTERES} letras.`;
  return lista.map((x, j) => (j === indice ? { ...x, palavra: p, ouvia: os.slice(-TETO_DE_OUVIDAS), atualizadaEm: agora } : x));
}

/** Por que não dá para ensinar esta palavra agora (ou null se dá). */
export function motivoParaNaoEnsinar(lista: PalavraDaVoz[], palavra: string): string | null {
  const p = limpo(palavra);
  if (!p) return 'Escreva a palavra.';
  if (p.length > TETO_DE_CARACTERES) return `Use no máximo ${TETO_DE_CARACTERES} letras.`;
  if (!lista.some((x) => igual(x.palavra, p)) && lista.length >= TETO_DE_PALAVRAS) return `A lista já tem ${TETO_DE_PALAVRAS} palavras.`;
  return null;
}

/**
 * A ordem em que as palavras valem: as mais corrigidas primeiro e, no empate, as mais recentes. O Whisper corta o fim da
 * lista quando ela não cabe, então o que fica de fora é o menos usado.
 */
export function emOrdemDeImportancia(lista: PalavraDaVoz[]): PalavraDaVoz[] {
  return [...lista].sort((x, y) => y.vezes - x.vezes || y.atualizadaEm.localeCompare(x.atualizadaEm));
}

export const palavrasParaOMotor = (lista: PalavraDaVoz[]) => emOrdemDeImportancia(lista).map((x) => x.palavra);
