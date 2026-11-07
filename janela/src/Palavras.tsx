/**
 * O dicionário da voz na tela (ADR-039 do NewClaw, Revisão 2), pensado para quem não conhece o sistema:
 * - o cartão depois de uma correção: "Quer que eu aprenda X? Eu tinha ouvido Y", com Aprender, Mudar a palavra e Agora
 *   não. Nada é aprendido sem a pessoa pedir;
 * - o aviso com "Desfazer", logo depois de aprender, editar ou apagar (sem caixa de "tem certeza?");
 * - a tela "Palavras que eu conheço": editar a palavra e o que ele ouvia, apagar, ensinar palavra nova e buscar.
 */
import { useEffect, useState, type FormEvent } from 'react';
import {
  editar, emOrdemDeImportancia, motivoParaNaoEnsinar, type ContaDoMotor, type PalavraDaVoz, type Vocabulario,
} from './vocabulario';

export interface Proposta { certo: string; ouvido: string }

/** Depois de uma correção por voz: propõe a palavra; a pessoa decide. "Mudar a palavra" pega o erro de digitação antes. */
export function CartaoAprender({ proposta, aoAprender, aoRecusar, aoVerPalavras }: {
  proposta: Proposta; aoAprender: (palavra: string) => void; aoRecusar: () => void; aoVerPalavras: () => void;
}) {
  const [mudando, setMudando] = useState(false);
  const [palavra, setPalavra] = useState(proposta.certo);
  useEffect(() => { setMudando(false); setPalavra(proposta.certo); }, [proposta]);
  const motivo = motivoParaNaoEnsinar([], palavra);
  const aprender = (ev?: FormEvent) => { ev?.preventDefault(); if (!motivo) aoAprender(palavra); };
  return (
    <div className="cartao-aprender" role="dialog" aria-label="Aprender palavra">
      {mudando ? (
        <form onSubmit={aprender}>
          <label>Como a palavra deve ser escrita?
            <input value={palavra} onChange={(e) => setPalavra(e.target.value)} autoFocus maxLength={80}
              onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); setMudando(false); setPalavra(proposta.certo); } }} />
          </label>
          {motivo && <small className="erro">{motivo}</small>}
          <div className="acoes-resposta">
            <button type="submit" className="btn mini primario" disabled={!!motivo}>Aprender</button>
            <button type="button" className="btn mini" onClick={() => { setMudando(false); setPalavra(proposta.certo); }}>Voltar</button>
          </div>
        </form>
      ) : (
        <>
          <p>Quer que eu aprenda <b>{proposta.certo}</b>?
            {proposta.ouvido && <> Eu tinha ouvido “{proposta.ouvido}”.</>}</p>
          <div className="acoes-resposta">
            <button className="btn mini primario" onClick={() => aprender()} title="Da próxima vez eu escrevo assim">Aprender</button>
            <button className="btn mini" onClick={() => setMudando(true)} title="Arrumar como a palavra é escrita antes de aprender">Mudar a palavra</button>
            <button className="btn mini" onClick={aoRecusar} title="Não guardar nada">Agora não</button>
          </div>
          <button className="link" onClick={aoVerPalavras}>ver as palavras que eu conheço</button>
        </>
      )}
    </div>
  );
}

/** "Aprendi X. [Desfazer]": some sozinho depois de um tempo, ou ao fechar. */
export function AvisoDesfazer({ texto, aoDesfazer, aoFechar }: { texto: string; aoDesfazer: () => void; aoFechar: () => void }) {
  useEffect(() => { const id = setTimeout(aoFechar, 12_000); return () => clearTimeout(id); }, [texto, aoFechar]);
  return (
    <div className="aviso-desfazer" role="status">
      <span>{texto}</span>
      <button className="btn mini" onClick={aoDesfazer}>Desfazer</button>
      <button className="btn mini" onClick={aoFechar} aria-label="Fechar aviso">×</button>
    </div>
  );
}

/** A partir de quantas palavras a busca aparece (com poucas, a lista inteira cabe na tela). */
const BUSCA_A_PARTIR_DE = 10;

export function TelaDePalavras({ vocab, erro, conta, modeloCarregado, motorLigado, ocupado, aoEnsinar, aoSalvar, aoApagar }: {
  vocab: Vocabulario | null;
  erro: string;
  conta: ContaDoMotor | null;
  modeloCarregado: boolean;
  motorLigado: boolean;
  ocupado: boolean;
  aoEnsinar: (palavra: string) => void;
  aoSalvar: (lista: PalavraDaVoz[], aviso: string) => void;
  aoApagar: (palavra: PalavraDaVoz) => void;
}) {
  const [nova, setNova] = useState('');
  const [busca, setBusca] = useState('');
  const [editando, setEditando] = useState<string | null>(null);
  const [rascunho, setRascunho] = useState({ palavra: '', ouvia: '' });
  const [motivoDaEdicao, setMotivoDaEdicao] = useState('');

  if (!vocab) return <p className="nota">{erro || 'Lendo as palavras…'}</p>;

  const ordem = emOrdemDeImportancia(vocab.palavras);
  const n = vocab.palavras.length;
  const quantas = `${n} ${n === 1 ? 'palavra' : 'palavras'}`;
  const cabem = conta ? conta.usadas : null;
  const filtro = busca.trim().toLocaleLowerCase('pt-BR');
  const visiveis = ordem
    .map((p, posicao) => ({ p, posicao }))
    .filter(({ p }) => !filtro || p.palavra.toLocaleLowerCase('pt-BR').includes(filtro) || p.ouvia.some((o) => o.toLocaleLowerCase('pt-BR').includes(filtro)));
  const motivoNova = nova.trim() ? motivoParaNaoEnsinar(vocab.palavras, nova) : null;
  const ensinar = (ev: FormEvent) => {
    ev.preventDefault();
    if (!nova.trim() || motivoNova) return;
    aoEnsinar(nova);
    setNova('');
  };
  const salvarEdicao = (original: PalavraDaVoz) => {
    const i = vocab.palavras.findIndex((x) => x.palavra === original.palavra);
    const r = editar(vocab.palavras, i, rascunho.palavra, rascunho.ouvia.split(','), new Date().toISOString());
    if (typeof r === 'string') { setMotivoDaEdicao(r); return; }
    aoSalvar(r, `Mudei "${original.palavra}".`);
    setEditando(null);
  };

  return (
    <div className="palavras">
      <p className="nota">
        Nomes e palavras que o reconhecimento errou e você ensinou. Eles ficam guardados no NewClaw e vão junto no backup dele.
      </p>
      {erro && <p className="nota erro" role="alert">{erro}</p>}

      <form className="ensinar" onSubmit={ensinar}>
        <input value={nova} onChange={(e) => setNova(e.target.value)} placeholder="Ensinar uma palavra nova (como deve ser escrita)"
          aria-label="Palavra nova" maxLength={80} />
        <button type="submit" className="btn mini primario" disabled={!nova.trim() || !!motivoNova || ocupado}>Ensinar</button>
      </form>
      {motivoNova && <small className="erro">{motivoNova}</small>}

      <p className="nota conta">
        {n === 0 ? 'Nenhuma palavra ainda.'
          : !motorLigado ? `${quantas}. O reconhecimento usa a lista quando a voz ligar.`
            : conta ? (conta.usadas === conta.total
              ? (n === 1 ? '1 palavra, valendo no reconhecimento.' : `${quantas}, todas valendo no reconhecimento.`)
              : `${conta.usadas} de ${conta.total} palavras cabem no reconhecimento agora. As menos corrigidas ficam de fora.`)
              : modeloCarregado ? `${quantas}.`
                : `${quantas}. Quantas cabem no reconhecimento aparece quando o modelo de voz carregar.`}
      </p>

      {vocab.palavras.length >= BUSCA_A_PARTIR_DE && (
        <input className="buscar" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar" aria-label="Buscar palavra" />
      )}

      <ul className="lista-de-palavras">
        {visiveis.map(({ p, posicao }) => (
          <li key={p.palavra} className={cabem !== null && posicao >= cabem ? 'fora' : ''}>
            {editando === p.palavra ? (
              <form onSubmit={(e) => { e.preventDefault(); salvarEdicao(p); }}>
                <label>Palavra certa
                  <input value={rascunho.palavra} onChange={(e) => setRascunho({ ...rascunho, palavra: e.target.value })} autoFocus maxLength={80} />
                </label>
                <label>Eu ouvia (separe com vírgula)
                  <input value={rascunho.ouvia} onChange={(e) => setRascunho({ ...rascunho, ouvia: e.target.value })} />
                </label>
                {motivoDaEdicao && <small className="erro">{motivoDaEdicao}</small>}
                <div className="acoes-resposta">
                  <button type="submit" className="btn mini primario" disabled={ocupado}>Salvar</button>
                  <button type="button" className="btn mini" onClick={() => setEditando(null)}>Cancelar</button>
                </div>
              </form>
            ) : (
              <>
                <div className="palavra">
                  <b>{p.palavra}</b>
                  <small>
                    {p.ouvia.length > 0 ? `eu ouvia: ${p.ouvia.join(', ')}` : 'ensinada por você'}
                    {' · '}{p.vezes === 1 ? '1 vez' : `${p.vezes} vezes`}
                    {cabem !== null && posicao >= cabem ? ' · não cabe agora' : ''}
                  </small>
                </div>
                <div className="acoes-resposta">
                  <button className="btn mini" disabled={ocupado} onClick={() => {
                    setEditando(p.palavra); setMotivoDaEdicao(''); setRascunho({ palavra: p.palavra, ouvia: p.ouvia.join(', ') });
                  }}>Editar</button>
                  <button className="btn mini" disabled={ocupado} onClick={() => aoApagar(p)}>Apagar</button>
                </div>
              </>
            )}
          </li>
        ))}
      </ul>
      {filtro && visiveis.length === 0 && <p className="nota">Nenhuma palavra com “{busca.trim()}”.</p>}
    </div>
  );
}
