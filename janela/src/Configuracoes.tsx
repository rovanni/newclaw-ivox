/**
 * Ajustes da janela, numa aba própria (pedido de 04/11/2026: a caixa por cima da conversa parecia exigir pressa; antes,
 * em 31/10, os ajustes já tinham saído da tela principal):
 *  - Áudio: voz, velocidade e volume da fala, microfone — parâmetros dos serviços de voz;
 *  - Aparência: tema, fundo, cores e estilo do centro, atalhos de pedido, modo econômico, foco — só desta tela;
 *  - Interação: jeito de falar, espera antes de enviar, sons;
 *  - Recursos: o modelo de reconhecimento (carregar, descarregar, ao abrir, sem uso) — ADR-037 do NewClaw;
 *  - Conexão: o que está ligado, só leitura.
 *
 * Só oferece o que os serviços aceitam de verdade: velocidade na faixa do Kokoro, volume na reprodução deste navegador.
 * O microfone é o padrão do sistema (a janela não escolhe dispositivo) e o modelo de linguagem é do NewClaw — a tela não
 * escolhe nenhum dos dois, só mostra o que sabe.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { EstiloDoCentro } from './Centro';
import type { EsperaAntesDeEnviar, JeitoDeFalar } from './conversa';
import type { AtalhosDePedido, CoresDoCentro, FundoDaTela, Tema } from './estado';
import { gb, type EstadoDoModelo } from './modelo';
import { VELOCIDADE_MAXIMA, VELOCIDADE_MINIMA, type Voz } from './motor';

export type Grupo = 'audio' | 'aparencia' | 'interacao' | 'recursos' | 'conexao';
const GRUPOS: { id: Grupo; nome: string }[] = [
  { id: 'audio', nome: 'Áudio' },
  { id: 'aparencia', nome: 'Aparência' },
  { id: 'interacao', nome: 'Interação' },
  { id: 'recursos', nome: 'Recursos' },
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
  tema: Tema;
  aoMudarTema: (t: Tema) => void;
  fundo: FundoDaTela;
  aoMudarFundo: (f: FundoDaTela) => void;
  cores: CoresDoCentro;
  aoMudarCores: (c: CoresDoCentro) => void;
  atalhos: AtalhosDePedido;
  aoMudarAtalhos: (a: AtalhosDePedido) => void;
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
  // Recursos
  modelo: EstadoDoModelo | null;
  resumoDoModelo: { titulo: string; texto: string };
  ouvirConfigurado: boolean;
  aoCarregar: (naCpu: boolean) => void;
  aoDescarregar: () => void;
  carregarAoAbrir: boolean;
  aoMudarCarregarAoAbrir: (v: boolean) => void;
  aoMudarOciosidade: (minutos: number | null) => void;
  /** Grupo aberto ao abrir (padrão: Áudio). */
  grupoInicial?: Grupo;
}

const OCIOSIDADE: [string, string][] = [['nunca', 'Nunca'], ['15', '15 min'], ['30', '30 min'], ['60', '1 h']];
const NOMES_DOS_TEMAS: [Tema, string][] = [['escuro', 'Escuro'], ['claro', 'Claro'], ['neon', 'Neon']];
const NOMES_DOS_FUNDOS: [FundoDaTela, string][] = [['padrao', 'Do tema'], ['azul-claro', 'Azul claro'], ['marinho', 'Marinho'], ['grafite', 'Grafite']];
const NOMES_DAS_CORES: [CoresDoCentro, string][] = [['estados', 'Por estado'], ['azul', 'Azul'], ['ciano', 'Ciano'], ['verde', 'Verde'], ['roxo', 'Roxo']];

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
  const [grupo, setGrupo] = useState<Grupo>(p.grupoInicial ?? 'audio');
  const caixa = useRef<HTMLDivElement>(null);
  useEffect(() => {
    caixa.current?.focus();
    const tecla = (ev: globalThis.KeyboardEvent) => { if (ev.key === 'Escape') p.aoFechar(); };
    addEventListener('keydown', tecla);
    return () => removeEventListener('keydown', tecla);
  }, [p]);

  return (
    <div className="ajustes-pagina" role="tabpanel">
      <div className="ajustes" aria-label="Ajustes" tabIndex={-1} ref={caixa}>
        <nav className="ajustes-grupos" aria-label="Grupos de ajustes">
          <h2>Ajustes</h2>
          {GRUPOS.map((g) => (
            <button key={g.id} className={grupo === g.id ? 'ativo' : ''} aria-current={grupo === g.id} onClick={() => setGrupo(g.id)}>{g.nome}</button>
          ))}
        </nav>
        <section className="ajustes-corpo">
          <div className="ajustes-topo">
            <h3>{GRUPOS.find((g) => g.id === grupo)!.nome}</h3>
            <button className="btn mini" onClick={p.aoFechar} title="Voltar à conversa (Esc)">Voltar à conversa</button>
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
            <Linha rotulo="Tema" dica="Neon: tudo em azul, com brilho nas bordas">
              <Segmento rotulo="Tema" valor={p.tema} aoMudar={p.aoMudarTema} opcoes={NOMES_DOS_TEMAS} />
            </Linha>
            <Linha rotulo="Fundo" dica="A cor atrás de tudo; no tema claro, a versão clara de cada uma">
              <Segmento rotulo="Fundo" valor={p.fundo} aoMudar={p.aoMudarFundo} opcoes={NOMES_DOS_FUNDOS} />
            </Linha>
            <Linha rotulo="Centro" dica="Os dois reagem aos mesmos estados reais">
              <Segmento rotulo="Estilo do centro" valor={p.estilo} aoMudar={p.aoMudarEstilo} opcoes={[['circulo', 'Círculo'], ['particulas', 'Partículas']]} />
            </Linha>
            <Linha rotulo="Cores do centro" dica="Por estado: azul ao ouvir, amarelo quando o NewClaw pensa ou fala. Uma cor só: tudo nela; aprovação e erro continuam vermelhos">
              <Segmento rotulo="Cores do centro" valor={p.cores} aoMudar={p.aoMudarCores} opcoes={NOMES_DAS_CORES} />
            </Linha>
            <Linha rotulo="Atalhos de pedido" dica="Os cartões abaixo do centro (Resumo do dia, Analisar logs…) e a saudação">
              <Segmento rotulo="Atalhos de pedido" valor={p.atalhos} aoMudar={p.aoMudarAtalhos}
                opcoes={[['auto', 'Somem ao começar'], ['sempre', 'Sempre'], ['nunca', 'Nunca']]} />
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

          {grupo === 'recursos' && <>
            {!p.ouvirConfigurado ? (
              <Linha rotulo="Reconhecimento de voz"><span>não configurado neste motor</span></Linha>
            ) : <>
              <Linha rotulo="Reconhecimento de voz" dica={p.resumoDoModelo.texto}>
                <b>{p.resumoDoModelo.titulo}</b>
                {p.modelo?.pergunta === 'cpu' ? <>
                  <button className="btn primario" onClick={() => p.aoCarregar(true)}>Tentar na CPU</button>
                  <button className="btn" onClick={p.aoDescarregar}>Cancelar</button>
                </> : p.modelo?.estado === 'carregado'
                  ? <button className="btn" onClick={p.aoDescarregar}>Descarregar</button>
                  : (p.modelo?.estado === 'descarregado' || p.modelo?.estado === 'falha')
                    ? <button className="btn primario" onClick={() => p.aoCarregar(false)}>Carregar</button> : null}
              </Linha>
              <Linha rotulo="Onde roda" dica={p.modelo?.motivo}>
                <span>{p.modelo?.dispositivo === 'cuda' ? 'GPU (CUDA)' : p.modelo?.dispositivo === 'cpu' ? 'CPU' : 'decidido ao carregar'}{p.modelo?.tipo ? ` · ${p.modelo.tipo}` : ''}</span>
              </Linha>
              <Linha rotulo="Memória da GPU" dica={p.modelo?.consumo_fonte ?? 'Lida do driver da NVIDIA na hora de carregar; sem ele, não é medida'}>
                <span>{(() => {
                  const g = (p.modelo?.memoria_depois ?? p.modelo?.memoria_antes)?.[0];
                  return g ? `${gb(g.livre_bytes)} livres de ${gb(g.total_bytes)} (${g.nome})` : 'não medida';
                })()}</span>
              </Linha>
              <Linha rotulo="Última carga ocupou" dica="Medido nesta máquina; serve de aviso antes de carregar, não de garantia">
                <span>{p.modelo?.consumo_bytes !== undefined ? gb(p.modelo.consumo_bytes) : p.modelo?.consumo_medido_bytes ? gb(p.modelo.consumo_medido_bytes) : 'ainda não medido'}</span>
              </Linha>
              <Linha rotulo="Carregar ao abrir a janela" dica="Desligado: abrir a janela não ocupa a GPU">
                <label className="chave"><input type="checkbox" checked={p.carregarAoAbrir} onChange={(e) => p.aoMudarCarregarAoAbrir(e.target.checked)} /> Ligado</label>
              </Linha>
              <Linha rotulo="Descarregar sem uso" dica="Depois de quanto tempo sem transcrever o modelo sai da memória (vale para todas as janelas)">
                <Segmento rotulo="Descarregar sem uso" aoMudar={(v) => p.aoMudarOciosidade(v === 'nunca' ? null : Number(v))}
                  valor={p.modelo?.ajustes?.descarregar_apos_min ? String(p.modelo.ajustes.descarregar_apos_min) : 'nunca'} opcoes={OCIOSIDADE} />
              </Linha>
            </>}
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
