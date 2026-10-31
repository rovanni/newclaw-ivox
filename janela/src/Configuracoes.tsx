/**
 * Ajustes da janela, em quatro grupos, fora da tela principal (pedido de 31/10/2026):
 *  - Áudio: voz, velocidade e volume da fala, microfone — parâmetros dos serviços de voz;
 *  - Aparência: tema, centro, modo econômico, foco — só desta tela;
 *  - Interação: jeito de falar, espera antes de enviar, sons;
 *  - Conexão: o que está ligado, só leitura.
 *
 * Só oferece o que os serviços aceitam de verdade: velocidade na faixa do Kokoro, volume na reprodução deste navegador.
 * O microfone é o padrão do sistema (a janela não escolhe dispositivo) e o modelo de linguagem é do NewClaw — a tela não
 * escolhe nenhum dos dois, só mostra o que sabe.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { EstiloDoCentro } from './Centro';
import type { EsperaAntesDeEnviar, JeitoDeFalar } from './conversa';
import { VELOCIDADE_MAXIMA, VELOCIDADE_MINIMA, type Voz } from './motor';

export type Grupo = 'audio' | 'aparencia' | 'interacao' | 'conexao';
const GRUPOS: { id: Grupo; nome: string }[] = [
  { id: 'audio', nome: 'Áudio' },
  { id: 'aparencia', nome: 'Aparência' },
  { id: 'interacao', nome: 'Interação' },
  { id: 'conexao', nome: 'Conexão' },
];

export interface InfoDaVoz {
  ouvir?: { modelo?: string | null; motor: string } | null;
  falar?: { motor: string } | null;
  idioma?: string | null;
  dispositivo: string;
}

interface Props {
  aoFechar: () => void;
  // Áudio
  vozes: Voz[];
  vozAtual: string | null;
  aoTrocarVoz: (nome: string) => void;
  gruposDeVozes: (v: Voz[]) => [string, Voz[]][];
  velocidade: number;
  aoMudarVelocidade: (v: number) => void;
  volume: number;
  aoMudarVolume: (v: number) => void;
  semMicrofone: string | null;
  micAberto: boolean;
  // Aparência
  tema: 'claro' | 'escuro';
  aoMudarTema: (t: 'claro' | 'escuro') => void;
  estilo: EstiloDoCentro;
  aoMudarEstilo: (e: EstiloDoCentro) => void;
  economico: boolean;
  aoMudarEconomico: (v: boolean) => void;
  foco: boolean;
  aoMudarFoco: (v: boolean) => void;
  // Interação
  jeito: JeitoDeFalar;
  aoMudarJeito: (j: JeitoDeFalar) => void;
  espera: EsperaAntesDeEnviar;
  aoMudarEspera: (e: EsperaAntesDeEnviar) => void;
  sons: boolean;
  aoMudarSons: (v: boolean) => void;
  // Conexão
  ligado: 'ligando' | 'ligado' | 'falhou';
  info: InfoDaVoz | null;
  conversa: string;
}

function Linha({ rotulo, dica, children }: { rotulo: string; dica?: string; children: ReactNode }) {
  return (
    <div className="ajuste">
      <div className="ajuste-rotulo"><b>{rotulo}</b>{dica && <small>{dica}</small>}</div>
      <div className="ajuste-valor">{children}</div>
    </div>
  );
}

function Segmento<T extends string>({ valor, opcoes, aoMudar, rotulo }: {
  valor: T; opcoes: [T, string][]; aoMudar: (v: T) => void; rotulo: string;
}) {
  return (
    <div className="segmento" role="radiogroup" aria-label={rotulo}>
      {opcoes.map(([v, nome]) => (
        <button key={v} role="radio" aria-checked={valor === v} className={valor === v ? 'ativo' : ''} onClick={() => aoMudar(v)}>{nome}</button>
      ))}
    </div>
  );
}

export function Configuracoes(p: Props) {
  const [grupo, setGrupo] = useState<Grupo>('audio');
  const caixa = useRef<HTMLDivElement>(null);
  useEffect(() => {
    caixa.current?.focus();
    const tecla = (ev: globalThis.KeyboardEvent) => { if (ev.key === 'Escape') p.aoFechar(); };
    addEventListener('keydown', tecla);
    return () => removeEventListener('keydown', tecla);
  }, [p]);

  return (
    <div className="ajustes-fundo" onClick={p.aoFechar}>
      <div className="ajustes" role="dialog" aria-modal="true" aria-label="Ajustes" tabIndex={-1} ref={caixa} onClick={(e) => e.stopPropagation()}>
        <nav className="ajustes-grupos" aria-label="Grupos de ajustes">
          <h2>Ajustes</h2>
          {GRUPOS.map((g) => (
            <button key={g.id} className={grupo === g.id ? 'ativo' : ''} aria-current={grupo === g.id} onClick={() => setGrupo(g.id)}>{g.nome}</button>
          ))}
        </nav>
        <section className="ajustes-corpo">
          <div className="ajustes-topo">
            <h3>{GRUPOS.find((g) => g.id === grupo)!.nome}</h3>
            <button className="btn mini" onClick={p.aoFechar} title="Fechar (Esc)">Fechar</button>
          </div>

          {grupo === 'audio' && <>
            <Linha rotulo="Voz" dica="Vozes do Kokoro instaladas e as misturas da pasta vozes/">
              {p.vozes.length > 0 ? (
                <select className="btn" value={p.vozAtual ?? ''} onChange={(e) => p.aoTrocarVoz(e.target.value)} aria-label="Voz">
                  {p.vozAtual === null && <option value="" disabled>Escolha uma voz</option>}
                  {p.gruposDeVozes(p.vozes).map(([g, lista]) => (
                    <optgroup key={g} label={g}>{lista.map((v) => <option key={v.nome} value={v.nome}>{v.rotulo}</option>)}</optgroup>
                  ))}
                </select>
              ) : <span className="vazio">Disponível quando a voz ligar.</span>}
            </Linha>
            <Linha rotulo="Velocidade da fala" dica={`${String(VELOCIDADE_MINIMA).replace('.', ',')}x a ${VELOCIDADE_MAXIMA}x, a faixa do Kokoro; vale a partir da próxima frase`}>
              <input type="range" min={VELOCIDADE_MINIMA} max={VELOCIDADE_MAXIMA} step={0.05} value={p.velocidade}
                onChange={(e) => p.aoMudarVelocidade(Number(e.target.value))} aria-label="Velocidade da fala" disabled={p.ligado !== 'ligado'} />
              <output>{p.velocidade.toFixed(2).replace('.', ',')}x</output>
            </Linha>
            <Linha rotulo="Volume da voz" dica="Só a reprodução neste navegador">
              <input type="range" min={0} max={1} step={0.05} value={p.volume} onChange={(e) => p.aoMudarVolume(Number(e.target.value))} aria-label="Volume da voz" />
              <output>{Math.round(p.volume * 100)}%</output>
            </Linha>
            <Linha rotulo="Microfone" dica="O padrão do sistema; troque nas configurações de som do Windows ou do navegador">
              <span className={`indicador ${p.semMicrofone ? 'fora' : p.micAberto ? 'ok' : ''}`}>
                {p.semMicrofone ? `Sem microfone: ${p.semMicrofone}` : p.micAberto ? '● Aberto' : 'Silenciado'}
              </span>
            </Linha>
          </>}

          {grupo === 'aparencia' && <>
            <Linha rotulo="Tema"><Segmento rotulo="Tema" valor={p.tema} aoMudar={p.aoMudarTema} opcoes={[['escuro', 'Escuro'], ['claro', 'Claro']]} /></Linha>
            <Linha rotulo="Centro" dica="Os dois reagem aos mesmos estados reais">
              <Segmento rotulo="Estilo do centro" valor={p.estilo} aoMudar={p.aoMudarEstilo} opcoes={[['circulo', 'Círculo'], ['particulas', 'Partículas']]} />
            </Linha>
            <Linha rotulo="Modo econômico" dica="Menos pontos, metade dos quadros, sem brilho: menos uso da placa de vídeo">
              <label className="chave"><input type="checkbox" checked={p.economico} onChange={(e) => p.aoMudarEconomico(e.target.checked)} /> Animação mais leve</label>
            </Linha>
            <Linha rotulo="Modo foco" dica="Só o centro e a resposta (tecla F)">
              <label className="chave"><input type="checkbox" checked={p.foco} onChange={(e) => p.aoMudarFoco(e.target.checked)} /> Ligado</label>
            </Linha>
          </>}

          {grupo === 'interacao' && <>
            <Linha rotulo="Jeito de falar" dica={p.jeito === 'livre' ? 'Microfone aberto; ele percebe quando você termina' : 'Segure Espaço (ou o botão do microfone) enquanto fala'}>
              <Segmento rotulo="Jeito de falar" valor={p.jeito} aoMudar={p.aoMudarJeito} opcoes={[['livre', 'Mãos livres'], ['segurar', 'Segurar espaço']]} />
            </Linha>
            <Linha rotulo="Espera antes de enviar" dica="Quanto silêncio, nas mãos livres, encerra o pedido">
              <Segmento rotulo="Espera antes de enviar" valor={p.espera} aoMudar={p.aoMudarEspera} opcoes={[['curta', 'Curta'], ['media', 'Média'], ['longa', 'Longa']]} />
            </Linha>
            <Linha rotulo="Sons" dica="Ao começar e terminar de ouvir">
              <label className="chave"><input type="checkbox" checked={p.sons} onChange={(e) => p.aoMudarSons(e.target.checked)} /> Ligados</label>
            </Linha>
            <Linha rotulo="Atalhos de teclado">
              <span className="atalhos-teclado">Enter envia · Shift+Enter quebra a linha · Espaço fala (segurar) · F foco · Esc fecha</span>
            </Linha>
          </>}

          {grupo === 'conexao' && <>
            <Linha rotulo="Motor de voz">
              <span className={`indicador ${p.ligado === 'ligado' ? 'ok' : 'fora'}`}>{p.ligado === 'ligado' ? '● Ligado' : p.ligado === 'ligando' ? 'Ligando…' : 'Não ligou'}</span>
            </Linha>
            <Linha rotulo="Ouvir (transcrição)">
              <span>{p.info?.ouvir ? `${p.info.ouvir.modelo ?? '—'} · ${p.info.ouvir.motor === 'local' ? 'neste computador' : 'servidor'}` : 'não configurado'}</span>
            </Linha>
            <Linha rotulo="Falar (síntese)">
              <span>{p.info?.falar ? `Kokoro · ${p.info.falar.motor === 'local' ? 'neste computador' : 'servidor'}` : 'não configurado'}</span>
            </Linha>
            <Linha rotulo="Idioma"><span>{p.info?.idioma ?? 'não informado'}</span></Linha>
            <Linha rotulo="Dispositivo"><span>{p.info?.dispositivo ?? '—'}</span></Linha>
            <Linha rotulo="Conversa" dica="Sessão no NewClaw (canal web)"><code>{p.conversa}</code></Linha>
            <Linha rotulo="Modelo de linguagem" dica="O NewClaw escolhe; o contrato do turno ainda não informa qual (planejado no ADR da evolução do contrato)">
              <span>Gerenciado pelo NewClaw</span>
            </Linha>
          </>}
        </section>
      </div>
    </div>
  );
}
