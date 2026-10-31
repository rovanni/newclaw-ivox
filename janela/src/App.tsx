/**
 * A janela de voz: entrada com a senha do NewClaw, depois a tela da maquete aprovada (docs/referencia-visual), ligada ao
 * motor de voz do harness e ao contrato do turno do NewClaw.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { Centro, type EstiloDoCentro } from './Centro';
import { AcoesDaResposta, TextoFormatado } from './Resposta';
import { Configuracoes } from './Configuracoes';
import { Conversa, type EsperaAntesDeEnviar, type JeitoDeFalar, type Mensagem, type Quadro } from './conversa';
import { listarConversasDeVoz, mensagensDaConversa, rotuloDaConversa, type ConversaGuardada } from './historico';
import { podeParar } from './estado';
import { ajustarOciosidade, carregarModelo, descarregarModelo, intervaloDeLeitura, lerModelo, ondeFala, resumoDoModelo, type EstadoDoModelo } from './modelo';
import { LigacaoComOMotor, VELOCIDADE_MAXIMA, VELOCIDADE_MINIMA, type Voz } from './motor';
import { gravarPref, idDaConversa, lerPref, novaConversa, usarConversa } from './preferencias';
import { comecouAOuvir, terminouDeOuvir } from './sons';
import { detalhe, hora, partesDaFala, tempoDecorrido } from './textos';
import { carregarClienteDoTurno } from './turnos';

type Tema = 'claro' | 'escuro';

interface InfoDaVoz {
  ouvir: { motor: string; modelo: string | null } | null;
  falar: { motor: string; modelo: string | null; voz: string | null } | null;
  idioma: string | null;
  dispositivo: string;
}

const PEDIDOS = [
  { titulo: 'Resumo do dia', sub: 'como está tudo hoje', pedido: 'Bom dia! Me dê um resumo de como está tudo hoje.', icone: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z' },
  { titulo: 'Analisar logs', sub: 'erros de hoje', pedido: 'Analise os logs de hoje e me diga se há erros.', icone: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-4.3-4.3' },
  { titulo: 'Planejar', sub: 'tarefas da semana', pedido: 'Me ajude a planejar as tarefas da semana.', icone: 'M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM8 2v4M16 2v4M3 10h18' },
  { titulo: 'Serviços', sub: 'o que está fora do ar', pedido: 'Quais serviços estão fora do ar?', icone: 'M6 3l14 9-14 9z' },
  { titulo: 'Relatório', sub: 'o que foi feito hoje', pedido: 'Gere um relatório do que foi feito hoje.', icone: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h5' },
];

function temaInicial(): Tema {
  const salvo = lerPref('ivox-tema');
  if (salvo === 'claro' || salvo === 'escuro') return salvo;
  return matchMedia('(prefers-color-scheme: light)').matches ? 'claro' : 'escuro';
}

/** Agrupa na ordem em que o motor manda (misturas, português, os outros idiomas). */
function gruposDeVozes(vozes: Voz[]): [string, Voz[]][] {
  const grupos = new Map<string, Voz[]>();
  for (const v of vozes) {
    const g = v.grupo ?? 'Vozes';
    grupos.set(g, [...(grupos.get(g) ?? []), v]);
  }
  return [...grupos.entries()];
}

function Icone({ d }: { d: string }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>;
}

// ─── Entrada ────────────────────────────────────────────────────────────────

function Entrar({ aoEntrar }: { aoEntrar: () => void }) {
  const [senha, setSenha] = useState('');
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);

  async function entrar(ev: FormEvent) {
    ev.preventDefault();
    setEnviando(true);
    setErro('');
    try {
      const r = await fetch('/entrar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ senha }) });
      const corpo = await r.json().catch(() => ({}));
      if (r.ok) aoEntrar();
      else if (r.status === 401) setErro('Senha incorreta. É a mesma senha do painel do NewClaw.');
      else if (r.status === 429) setErro('Muitas tentativas. Espere um pouco e tente de novo.');
      else setErro(corpo.erro ?? `HTTP ${r.status}`);
    } catch (e) {
      setErro(`Sem resposta do harness: ${String(e)}`);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="tela-entrar">
      <form className="cartao" onSubmit={entrar}>
        <div className="marca"><div className="marca-n">N</div><div><h1>NEWCLAW</h1><small>Interface de voz</small></div></div>
        <p>Use a <b>senha do painel do NewClaw</b>. A voz não tem senha própria: é uma senha só para tudo.</p>
        <input type="password" autoFocus autoComplete="current-password" placeholder="Senha do painel do NewClaw"
          value={senha} onChange={(e) => setSenha(e.target.value)} aria-label="Senha do painel do NewClaw" />
        <div className="erro" role="alert">{erro}</div>
        <button className="btn primario" disabled={enviando || !senha}>{enviando ? 'Entrando…' : 'Entrar'}</button>
        <div className="ajuda-senha">
          <p><b>Criar ou trocar a senha:</b> no painel do NewClaw, em Configurações → Segurança → Senha do Dashboard.</p>
          <p><b>Esqueceu a senha?</b> No computador onde o NewClaw está instalado, abra o terminal e rode <code>newclaw passwd</code>.</p>
          <p>Depois de entrar, esta janela lembra o login por 30 dias.</p>
        </div>
      </form>
    </div>
  );
}

// ─── Janela ─────────────────────────────────────────────────────────────────

function Janela({ aoSair, semSenha }: { aoSair: () => void; semSenha: boolean }) {
  const [tema, setTema] = useState<Tema>(temaInicial);
  const [foco, setFoco] = useState(lerPref('ivox-foco') === 'sim');
  const [jeito, setJeito] = useState<JeitoDeFalar>(lerPref('ivox-fala') === 'segurar' ? 'segurar' : 'livre');
  const [estilo, setEstilo] = useState<EstiloDoCentro>(lerPref('ivox-centro') === 'particulas' ? 'particulas' : 'circulo');
  const [sons, setSons] = useState(lerPref('ivox-sons') !== 'nao');
  const [economico, setEconomico] = useState(lerPref('ivox-economico') === 'sim');
  const [ajustes, setAjustes] = useState(false);
  // Velocidade e volume da fala, lembrados neste navegador; fora da faixa (preferência antiga ou editada), o padrão.
  const [velocidade, setVelocidade] = useState(() => {
    const v = Number(lerPref('ivox-velocidade'));
    return v >= VELOCIDADE_MINIMA && v <= VELOCIDADE_MAXIMA ? v : 1;
  });
  const [volume, setVolume] = useState(() => {
    const v = Number(lerPref('ivox-volume') ?? '1');
    return v >= 0 && v <= 1 ? v : 1;
  });
  const [espera, setEspera] = useState<EsperaAntesDeEnviar>(() => {
    const e = lerPref('ivox-espera');
    return e === 'curta' || e === 'longa' ? e : 'media';
  });
  const [quadro, setQuadro] = useState<Quadro | null>(null);
  // A voz "fala" desde a resposta pronta até o fim do áudio. O motor também avisa que parou entre duas frases: só depois de
  // um silêncio curto (800 ms) o foco troca as frases pela resposta formatada — sem isso o balão piscava entre as duas.
  const falandoAgora = !!quadro && (quadro.fatos.motorFalando || quadro.fatos.aguardandoFala);
  const [vozFalando, setVozFalando] = useState(false);
  useEffect(() => {
    if (falandoAgora) { setVozFalando(true); return; }
    const id = setTimeout(() => setVozFalando(false), 800);
    return () => clearTimeout(id);
  }, [falandoAgora]);
  const [ligado, setLigado] = useState<'ligando' | 'ligado' | 'falhou'>('ligando');
  const [falha, setFalha] = useState('');
  const [vozes, setVozes] = useState<Voz[]>([]);
  const [vozAtual, setVozAtual] = useState<string | null>(null);
  const [info, setInfo] = useState<InfoDaVoz | null>(null);
  // O modelo de reconhecimento (ADR-037): o estado vem do motor; a janela só pede. Abrir a janela não carrega nada, a não
  // ser que a pessoa tenha pedido "Carregar ao abrir a janela" (desligado por padrão).
  const [modelo, setModelo] = useState<EstadoDoModelo | null>(null);
  const [erroDoModelo, setErroDoModelo] = useState('');
  const [carregarAoAbrir, setCarregarAoAbrir] = useState(lerPref('ivox-carregar-ao-abrir') === 'sim');
  const [texto, setTexto] = useState('');
  const [micAberto, setMicAberto] = useState(true);
  const [agora, setAgora] = useState(Date.now());
  // Conversas de voz anteriores (guardadas no NewClaw), mostradas no lugar da conversa atual quando abertas.
  const [historico, setHistorico] = useState<{ itens: { c: ConversaGuardada; rotulo: string; mensagens: Mensagem[] }[] | null; erro: string } | null>(null);
  const [sessaoAtual, setSessaoAtual] = useState(idDaConversa);
  // O Chrome só libera o som da página depois do primeiro clique ou tecla (ver microfone.ts).
  const [somLiberado, setSomLiberado] = useState(() => navigator.userActivation?.hasBeenActive ?? true);
  useEffect(() => {
    if (somLiberado) return;
    const liberar = () => setSomLiberado(true);
    addEventListener('pointerdown', liberar, { once: true });
    addEventListener('keydown', liberar, { once: true });
    return () => { removeEventListener('pointerdown', liberar); removeEventListener('keydown', liberar); };
  }, [somLiberado]);
  const campo = useRef<HTMLTextAreaElement>(null);
  const conversaRef = useRef<Conversa | null>(null);
  const [, setMudouMicrofone] = useState(0);
  const motor = useMemo(() => new LigacaoComOMotor(() => conversaRef.current!, () => setMudouMicrofone((v) => v + 1)), []);

  // Liga tudo uma vez: cliente do turno (do próprio NewClaw), conversa e motor de voz.
  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const turnos = await carregarClienteDoTurno();
        if (!vivo) return;
        conversaRef.current = new Conversa({ motor, turnos, sessionId: idDaConversa(), aoMudar: (q) => vivo && setQuadro(q) });
        conversaRef.current.definirJeitoDeFalar(jeito);
        conversaRef.current.definirEspera(espera);
        setQuadro(conversaRef.current.quadro());
        // A conversa continua de onde parou: as últimas mensagens dela voltam à coluna (sem elas, a janela parecia vazia).
        void (async () => {
          try {
            const sessao = idDaConversa();
            const guardada = (await listarConversasDeVoz()).find((c) => c.sessionId === sessao);
            if (!guardada || !vivo) return;
            const msgs = await mensagensDaConversa(guardada);
            // Só se a pessoa ainda não começou a falar ou escrever: o histórico chega depois de o microfone abrir.
            const agoraNaTela = conversaRef.current?.quadro();
            if (vivo && agoraNaTela && agoraNaTela.mensagens.length === 0 && !agoraNaTela.legenda) {
              conversaRef.current?.trocarDeConversa(sessao, msgs);
            }
          } catch { /* sem histórico: a conversa segue, só começa com a coluna vazia */ }
        })();
        await motor.conectar();
        if (!vivo) return;
        if (jeito === 'segurar') { motor.microfone(false); setMicAberto(false); }
        setLigado('ligado');
        const lista = await motor.vozes().catch(() => ({ vozes: [], atual: null }));
        if (!vivo) return;
        setVozes(lista.vozes);
        setVozAtual(lista.atual);
        // Velocidade lembrada: o motor nasce em 1x a cada ligação.
        const v = Number(lerPref('ivox-velocidade'));
        if (v >= VELOCIDADE_MINIMA && v <= VELOCIDADE_MAXIMA && v !== 1) await motor.velocidade(v).catch(() => undefined);
        // O motor nasce sem voz quando o .env não traz uma: volta a que a pessoa escolheu da última vez neste navegador.
        const lembrada = lerPref('ivox-voz');
        if (lista.atual === null && lembrada && lista.vozes.some((v) => v.nome === lembrada)) {
          try { await motor.trocarVoz(lembrada); if (vivo) setVozAtual(lembrada); } catch { /* fica para escolher na lista */ }
        }
      } catch (e) {
        if (vivo) { setLigado('falhou'); setFalha(String(e instanceof Error ? e.message : e)); }
      }
    })();
    fetch('/voz').then((r) => (r.ok ? r.json() : null)).then((d) => vivo && setInfo(d)).catch(() => undefined);
    return () => {
      vivo = false;
      conversaRef.current?.encerrar();
      void motor.desconectar();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [motor]);

  // Estado do modelo: lido do motor, rápido enquanto muda e devagar parado (outra janela pode ter carregado ou descarregado).
  useEffect(() => {
    let vivo = true;
    let id: ReturnType<typeof setTimeout>;
    const ler = async () => {
      let lido: EstadoDoModelo | null = null;
      try { lido = await lerModelo(); if (vivo) setModelo(lido); } catch { if (vivo) setModelo(null); }
      if (vivo) id = setTimeout(ler, intervaloDeLeitura(lido));
    };
    void ler();
    return () => { vivo = false; clearTimeout(id); };
  }, []);
  const pedirModelo = useCallback(async (pedido: () => Promise<EstadoDoModelo>) => {
    setErroDoModelo('');
    try { setModelo(await pedido()); } catch (e) { setErroDoModelo(String(e instanceof Error ? e.message : e)); }
  }, []);
  const abriuComPedido = useRef(false);
  useEffect(() => {
    if (abriuComPedido.current || !modelo || !carregarAoAbrir) return;
    abriuComPedido.current = true;
    if (modelo.estado === 'descarregado' && !modelo.pergunta) void pedirModelo(() => carregarModelo(false));
  }, [modelo, carregarAoAbrir, pedirModelo]);
  useEffect(() => { gravarPref('ivox-carregar-ao-abrir', carregarAoAbrir ? 'sim' : 'nao'); }, [carregarAoAbrir]);

  // Tema, foco e preferências.
  useEffect(() => { document.documentElement.dataset.tema = tema; gravarPref('ivox-tema', tema); }, [tema]);
  useEffect(() => { document.body.classList.toggle('foco', foco); gravarPref('ivox-foco', foco ? 'sim' : 'nao'); }, [foco]);
  useEffect(() => { gravarPref('ivox-centro', estilo); }, [estilo]);
  useEffect(() => { gravarPref('ivox-sons', sons ? 'sim' : 'nao'); }, [sons]);
  useEffect(() => { document.body.classList.toggle('economico', economico); gravarPref('ivox-economico', economico ? 'sim' : 'nao'); }, [economico]);
  useEffect(() => { motor.definirVolume(volume); gravarPref('ivox-volume', String(volume)); }, [volume, motor]);
  useEffect(() => { gravarPref('ivox-espera', espera); conversaRef.current?.definirEspera(espera); }, [espera]);
  useEffect(() => {
    gravarPref('ivox-fala', jeito);
    conversaRef.current?.definirJeitoDeFalar(jeito);
    if (ligado === 'ligado') { const aberto = jeito === 'livre'; motor.microfone(aberto); setMicAberto(aberto); }
  }, [jeito, ligado, motor]);

  // Relógio da tela (tempo no estado e hora do topo).
  useEffect(() => { const id = setInterval(() => setAgora(Date.now()), 500); return () => clearInterval(id); }, []);

  // Sons ao começar e terminar de ouvir.
  const estadoAnterior = useRef<string>('pronto');
  useEffect(() => {
    const e = quadro?.estado ?? 'pronto';
    if (sons && e !== estadoAnterior.current) {
      if (e === 'ouvindo') comecouAOuvir();
      else if (estadoAnterior.current === 'ouvindo') terminouDeOuvir();
    }
    estadoAnterior.current = e;
  }, [quadro?.estado, sons]);

  // A caixa de texto cresce com o conteúdo.
  useEffect(() => {
    const c = campo.current;
    if (!c) return;
    c.style.height = 'auto';
    c.style.height = `${c.scrollHeight}px`;
  }, [texto]);

  // Segurar espaço: a barra de espaço é o botão de falar. F liga o foco.
  const segurar = useCallback((apertou: boolean) => {
    const c = conversaRef.current;
    if (!c) return;
    motor.microfone(apertou);
    setMicAberto(apertou);
    if (apertou) c.comecouASegurar(); else c.soltou();
  }, [motor]);
  useEffect(() => {
    const digitando = (ev: globalThis.KeyboardEvent) =>
      ev.target instanceof HTMLElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(ev.target.tagName);
    const baixo = (ev: globalThis.KeyboardEvent) => {
      if (digitando(ev) || ajustes) return;  // com os ajustes abertos, Espaço e F são dos controles de lá
      if (ev.key === 'f' || ev.key === 'F') { setFoco((v) => !v); return; }
      if (ev.code === 'Space' && jeito === 'segurar') { ev.preventDefault(); if (!ev.repeat) segurar(true); }
    };
    const cima = (ev: globalThis.KeyboardEvent) => {
      if (ev.code === 'Space' && jeito === 'segurar' && !digitando(ev)) { ev.preventDefault(); segurar(false); }
    };
    addEventListener('keydown', baixo);
    addEventListener('keyup', cima);
    return () => { removeEventListener('keydown', baixo); removeEventListener('keyup', cima); };
  }, [jeito, segurar, ajustes]);

  const enviar = () => {
    const c = conversaRef.current;
    if (!c) return;
    if (quadro && podeParar(quadro.estado)) { void c.parar(); return; }
    if (texto.trim()) { c.enviarTexto(texto); setTexto(''); }
  };
  const teclaNaCaixa = (ev: KeyboardEvent<HTMLTextAreaElement>) => {
    if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); if (texto.trim()) { conversaRef.current?.enviarTexto(texto); setTexto(''); } }
  };
  const botaoMic = () => {
    if (jeito === 'segurar') return; // no modo segurar, o microfone é a barra de espaço (ou segurar o botão)
    const aberto = !micAberto;
    motor.microfone(aberto);
    setMicAberto(aberto);
  };
  const trocarVoz = async (nome: string) => {
    const anterior = vozAtual;
    setVozAtual(nome);
    try { await motor.trocarVoz(nome); gravarPref('ivox-voz', nome); } catch { setVozAtual(anterior); }
  };
  const comecarConversaNova = () => {
    const c = conversaRef.current;
    if (!c || c.ocupada()) return;
    const id = novaConversa();
    c.trocarDeConversa(id);
    setSessaoAtual(id);
    setHistorico(null);
  };
  const abrirHistorico = async () => {
    if (historico) { setHistorico(null); return; }
    setHistorico({ itens: null, erro: '' });
    try {
      const lista = (await listarConversasDeVoz()).slice(0, 15);
      const itens = await Promise.all(lista.map(async (c) => {
        const mensagens = await mensagensDaConversa(c).catch(() => [] as Mensagem[]);
        return { c, mensagens, rotulo: rotuloDaConversa(mensagens, c) };
      }));
      setHistorico({ itens, erro: '' });
    } catch (e) {
      setHistorico({ itens: [], erro: String(e instanceof Error ? e.message : e) });
    }
  };
  const retomar = (item: { c: ConversaGuardada; mensagens: Mensagem[] }) => {
    const c = conversaRef.current;
    if (!c || !c.trocarDeConversa(item.c.sessionId, item.mensagens)) return;
    usarConversa(item.c.sessionId);
    setSessaoAtual(item.c.sessionId);
    setHistorico(null);
  };
  // A velocidade vai ao motor ao soltar o controle (cada passo seria um pedido); a tela mostra o valor na hora.
  const temporizadorVelocidade = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mudarVelocidade = (v: number) => {
    setVelocidade(v);
    if (temporizadorVelocidade.current) clearTimeout(temporizadorVelocidade.current);
    temporizadorVelocidade.current = setTimeout(() => {
      motor.velocidade(v).then(() => gravarPref('ivox-velocidade', String(v))).catch(() => undefined);
    }, 250);
  };
  const sair = async () => {
    await fetch('/sair', { method: 'POST' }).catch(() => undefined);
    aoSair();
  };

  const q = quadro;
  const estado = q?.estado ?? 'pronto';
  const parar = podeParar(estado);
  const podeOuvir = ligado === 'ligado' && vozAtual !== null;
  // Sem o modelo carregado, o microfone não tem quem transcreva: fica desligado, e a janela diz por quê.
  const ouvirConfigurado = !!info?.ouvir;
  const modeloPronto = !ouvirConfigurado || modelo?.estado === 'carregado';
  const resumo = resumoDoModelo(modelo);
  const h = new Date(agora).getHours();
  // A saudação vai no balão (antes era um título grande acima do centro, que ocupava espaço — pedido da operadora, 30/10).
  const saudacao = h < 12 ? 'Bom dia!' : h < 18 ? 'Boa tarde!' : 'Boa noite!';
  const mostraTempo = parar || estado === 'ouvindo' || estado === 'aprovacao';
  const tempo = q && mostraTempo ? tempoDecorrido(agora - q.desde) : '';
  const [antes, atual, depois] = q?.fala ? partesDaFala(q.fala.texto, q.fala.fraseAtual) : ['', '', ''];
  const textoParado = ligado === 'falhou'
    ? `Não consegui ligar a voz: ${falha}`
    : ligado === 'ligando' ? 'Ligando o motor de voz…'
      : motor.semMicrofone ? `Sem microfone (${motor.semMicrofone}). Você pode escrever abaixo; a resposta continua falada.`
        : !modeloPronto ? `${saudacao} O reconhecimento de voz está desligado: escreva abaixo, ou carregue o modelo de voz para falar.`
          : `${saudacao} Como posso ajudar hoje? Fale comigo pelo microfone ou escreva abaixo.`;

  return (
    <div className="app">
      <header>
        <div className="marca"><div className="marca-n">N</div><div><h1>NEWCLAW</h1><small>Interface de voz</small></div></div>
        <div className="lema">“Conhecimento. Organização. Execução.”</div>
        <div className="topo-dir">
          <span className={`online ${ligado === 'ligado' && !q?.fatos.erro ? 'ok' : 'fora'}`}>
            <span className="ponto" />{ligado === 'ligado' && !q?.fatos.erro ? 'Voz ligada' : ligado === 'ligando' ? 'Ligando' : 'Sem voz'}
          </span>
          <span className="relogio">{hora(agora)}</span>
          <button className="botao-tema" onClick={() => setAjustes(true)} title="Ajustes: áudio, aparência, interação e conexão">
            <Icone d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
            <span>Ajustes</span>
          </button>
          <button className="botao-tema" onClick={() => setFoco(!foco)} title="Modo foco: só o centro e a conversa (tecla F)">
            <Icone d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3" />
            <span>{foco ? 'Sair do foco' : 'Foco'}</span>
          </button>
          <button className="botao-tema" onClick={() => setTema(tema === 'claro' ? 'escuro' : 'claro')} title="Trocar tema">
            <Icone d={tema === 'claro' ? 'M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z' : 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4'} />
            <span>{tema === 'claro' ? 'Escuro' : 'Claro'}</span>
          </button>
          {!semSenha && <button className="botao-tema" onClick={sair} title="Sair: esquece o login neste navegador"><span>Sair</span></button>}
        </div>
      </header>

      <main>
        <section className="coluna esq">
          <div className="cartao recursos">
            <h2>Voz neste computador</h2>
            <div className="linha"><span className="rot">Integração</span>
              <span className={`indicador ${ligado === 'ligado' ? 'ok' : 'fora'}`}>{ligado === 'ligado' ? '● Conectada' : ligado === 'ligando' ? 'Conectando…' : 'Não conectou'}</span></div>
            {ouvirConfigurado && (
              <div className="reconhecimento" data-fase={modelo?.estado ?? 'sem-resposta'}>
                <div className="linha"><span className="rot">Reconhecimento de voz</span><b>{resumo.titulo}</b></div>
                <p className="nota-modelo">{resumo.texto}</p>
                {modelo?.pergunta === 'cpu' ? (
                  <div className="botoes">
                    <button className="btn primario" onClick={() => void pedirModelo(() => carregarModelo(true))}>Tentar na CPU</button>
                    <button className="btn" onClick={() => void pedirModelo(descarregarModelo)}>Cancelar</button>
                  </div>
                ) : modelo?.estado === 'carregado' ? (
                  <button className="btn" onClick={() => void pedirModelo(descarregarModelo)}
                    title="Tira o Whisper da memória; a integração continua ligada">Descarregar modelo de voz</button>
                ) : modelo?.estado === 'descarregado' || modelo?.estado === 'falha' ? (
                  <button className="btn primario" onClick={() => void pedirModelo(() => carregarModelo(false))}
                    title={`Carrega o Whisper ${info?.ouvir?.modelo ?? ''} (dispositivo: ${info?.dispositivo ?? '—'})`}>Carregar modelo de voz</button>
                ) : null}
                {erroDoModelo && <p className="nota-modelo erro" role="alert">{erroDoModelo}</p>}
              </div>
            )}
            <div className="linha"><span className="rot">Síntese de voz</span><span>{info?.falar ? `${ondeFala(modelo)} · disponível` : 'não configurada'}</span></div>
            <div className="linha"><span className="rot">Recursos</span>
              <span>{carregarAoAbrir || modelo?.ajustes?.descarregar_apos_min ? 'Automático' : 'Manual'}</span></div>
            {!carregarAoAbrir && !modelo?.ajustes?.descarregar_apos_min && (
              <div className="nota">A janela pode ficar aberta sem o modelo de reconhecimento carregado.</div>
            )}
          </div>
          <div className="cartao voz-escolha">
            <h2><label htmlFor="voz">Voz</label></h2>
            {vozes.length > 0 ? (
              <select className="btn" id="voz" value={vozAtual ?? ''} onChange={(e) => void trocarVoz(e.target.value)}>
                {vozAtual === null && <option value="" disabled>Escolha uma voz</option>}
                {gruposDeVozes(vozes).map(([grupo, lista]) => (
                  <optgroup key={grupo} label={grupo}>
                    {lista.map((v) => <option key={v.nome} value={v.nome}>{v.rotulo}</option>)}
                  </optgroup>
                ))}
              </select>
            ) : <div className="vazio">{ligado === 'ligado' ? 'A síntese local não está ligada neste motor.' : 'Disponível quando a voz ligar.'}</div>}
          </div>
        </section>

        <section className="centro" data-cor={estado} data-modelo={modeloPronto ? 'pronto' : 'desligado'}>
          <Centro estado={estado} estilo={estilo} economico={economico} niveis={motor.niveis} tempo={tempo} />
          <div className="detalhe">
            <div className="topo"><b>{q ? detalhe(q) : 'Pronto'}</b></div>
            <div className={`trilho ${parar || estado === 'ouvindo' ? 'indeterminado' : ''}`}><i /></div>
          </div>
          <div className="legenda" aria-live="polite">
            {q?.legenda || estado === 'ouvindo'
              ? <><span className="rotulo">Você</span>{q?.legenda}{estado === 'ouvindo' && <span className="cursor" />}</>
              : null}
          </div>
          {/* No foco a coluna da conversa some, e o balão mostra a resposta inteira. Fora dele a resposta já está na
              coluna: o balão mostra só a frase que está sendo falada, como legenda, para não repetir (pedido de 30/10). */}
          {/* No foco, terminada a fala, o balão mostra a resposta inteira formatada, com copiar e ouvir de novo. */}
          {/* Enquanto a voz fala (inclusive na pausa entre duas frases), as frases; sem isso o balão piscava entre as duas vistas. */}
          <div className={`balao ${q?.fala && atual ? 'lendo' : ''} ${q?.fala && foco && !vozFalando ? 'resposta' : ''}`}>
            {q?.fala && foco && vozFalando
              ? <>{antes && <span className="frase">{antes}</span>}{atual && <span className="frase atual">{atual}</span>}{depois && <span className="frase">{depois}</span>}</>
              : q?.fala && foco
                ? <><TextoFormatado texto={q.fala.texto} /><AcoesDaResposta texto={q.fala.texto} podeOuvir={podeOuvir} aoOuvir={() => conversaRef.current?.repetir(q.fala!.texto)} /></>
                : q?.fala && atual ? <span className="frase atual">{atual}</span>
                  : textoParado}
          </div>
          <div className="atalhos">
            {PEDIDOS.map((p) => (
              <button key={p.titulo} className="atalho" title={p.pedido} onClick={() => conversaRef.current?.enviarTexto(p.pedido)}>
                <Icone d={p.icone} /><b>{p.titulo}</b><small>{p.sub}</small>
              </button>
            ))}
          </div>
        </section>

        <section className="coluna dir">
          <div className="cartao">
            <div className="titulo-conversa">
              <h2>{historico ? 'Conversas anteriores' : 'Conversa'}</h2>
              <div className="acoes-conversa">
                <button className="btn mini" onClick={() => void abrirHistorico()} title={historico ? 'Voltar à conversa atual' : 'Ver e retomar conversas de voz anteriores'}>
                  {historico ? 'Voltar' : 'Anteriores'}
                </button>
                <button className="btn mini" onClick={comecarConversaNova} disabled={parar || ligado !== 'ligado'}
                  title={parar ? 'Espere o pedido em andamento terminar' : 'Começa uma conversa nova; a atual fica no histórico'}>
                  Nova
                </button>
              </div>
            </div>
            {historico ? (
              <div className="conversa">
                {historico.itens === null && <div className="vazio">Carregando…</div>}
                {historico.erro && <div className="vazio">Não consegui ler o histórico: {historico.erro}</div>}
                {historico.itens?.length === 0 && !historico.erro && <div className="vazio">Nenhuma conversa de voz guardada ainda.</div>}
                {historico.itens?.map((item) => (
                  <button key={item.c.sessionId} className={`conversa-antiga ${item.c.sessionId === sessaoAtual ? 'atual' : ''}`}
                    disabled={parar || item.c.sessionId === sessaoAtual} onClick={() => retomar(item)}>
                    <b>{item.rotulo}</b>
                    <small>{new Date(item.c.atualizadaEm).toLocaleString()}{item.c.sessionId === sessaoAtual ? ' · atual' : ''}</small>
                  </button>
                ))}
              </div>
            ) : (
            <div className="conversa">
              {(q?.mensagens.length ?? 0) === 0 && (q?.aprovacoes.length ?? 0) === 0 && <div className="vazio">Nada por aqui ainda.</div>}
              {q?.mensagens.map((m, i) => (
                <div key={i} className={`msg ${m.quem}`}>
                  {m.quem === 'newclaw' ? <TextoFormatado texto={m.texto} /> : m.texto}
                  <small>{hora(m.em)}{m.porVoz ? ' · por voz' : ''}</small>
                  {m.quem === 'newclaw' && <AcoesDaResposta texto={m.texto} podeOuvir={podeOuvir} aoOuvir={() => conversaRef.current?.repetir(m.texto)} />}
                </div>
              ))}
              {/* Resposta em andamento: a fase real do turno (fila, pensando) e o último relato de progresso do NewClaw. */}
              {(estado === 'fila' || estado === 'pensando') && (
                <div className="msg newclaw andamento" role="status">
                  <span className="pontos" aria-hidden="true"><i /><i /><i /></span>
                  {q?.progresso || (estado === 'fila' ? 'Na fila do NewClaw…' : 'Preparando a resposta…')}
                </div>
              )}
              {q?.aprovacoes.map((a) => (
                <div key={a.txnId} className="aprovacao">
                  <b>Precisa da sua aprovação</b>
                  <code>{a.detail || a.tool}</code>
                  <div className="botoes">
                    <button className="btn primario" onClick={() => void conversaRef.current?.decidir(a.txnId, 'approved')}>Aprovar</button>
                    <button className="btn" onClick={() => void conversaRef.current?.decidir(a.txnId, 'rejected')}>Recusar</button>
                  </div>
                </div>
              ))}
            </div>
            )}
          </div>
          <div className="cartao modo-voz">
            <div className="topo"><span>MODO VOZ</span><span className={ligado === 'ligado' ? 'estado-ok' : ''}>{ligado === 'ligado' ? 'ATIVO' : '—'}</span></div>
            <div className="segmento" role="radiogroup" aria-label="Jeito de falar">
              <button className={jeito === 'livre' ? 'ativo' : ''} onClick={() => setJeito('livre')} title="O microfone fica aberto e ele percebe quando você para de falar">Mãos livres</button>
              <button className={jeito === 'segurar' ? 'ativo' : ''} onClick={() => setJeito('segurar')} title="Segure a barra de espaço enquanto fala">Segurar espaço</button>
            </div>
            <div className="segmento" role="radiogroup" aria-label="Estilo do centro">
              <button className={estilo === 'circulo' ? 'ativo' : ''} onClick={() => setEstilo('circulo')}>Círculo</button>
              <button className={estilo === 'particulas' ? 'ativo' : ''} onClick={() => setEstilo('particulas')}>Partículas</button>
            </div>
            <div className="nota">
              {motor.semMicrofone ? `Sem microfone: ${motor.semMicrofone}.` : jeito === 'livre'
                ? 'O microfone fica aberto; ele percebe sozinho quando você termina. O botão do microfone silencia.'
                : 'Segure a barra de espaço (ou o botão do microfone) enquanto fala e solte quando terminar.'}
            </div>
            <button className="btn mini mais-ajustes" onClick={() => setAjustes(true)}>Espera, sons, velocidade, volume e mais…</button>
          </div>
        </section>
      </main>

      {ajustes && (
        <Configuracoes
          aoFechar={() => setAjustes(false)}
          vozes={vozes} vozAtual={vozAtual} aoTrocarVoz={(n) => void trocarVoz(n)} gruposDeVozes={gruposDeVozes}
          velocidade={velocidade} aoMudarVelocidade={mudarVelocidade} volume={volume} aoMudarVolume={setVolume}
          semMicrofone={motor.semMicrofone} micAberto={micAberto}
          tema={tema} aoMudarTema={setTema} estilo={estilo} aoMudarEstilo={setEstilo}
          economico={economico} aoMudarEconomico={setEconomico} foco={foco} aoMudarFoco={setFoco}
          jeito={jeito} aoMudarJeito={setJeito} espera={espera} aoMudarEspera={setEspera} sons={sons} aoMudarSons={setSons}
          ligado={ligado} info={info} conversa={sessaoAtual}
          modelo={modelo} resumoDoModelo={resumo} ouvirConfigurado={ouvirConfigurado}
          aoCarregar={(naCpu) => void pedirModelo(() => carregarModelo(naCpu))} aoDescarregar={() => void pedirModelo(descarregarModelo)}
          carregarAoAbrir={carregarAoAbrir} aoMudarCarregarAoAbrir={setCarregarAoAbrir}
          aoMudarOciosidade={(m) => void pedirModelo(() => ajustarOciosidade(m))}
        />
      )}

      <footer>
        <div className="entrada-wrap">
          <div className="entrada">
            <textarea ref={campo} rows={1} value={texto} onChange={(e) => setTexto(e.target.value)} onKeyDown={teclaNaCaixa}
              placeholder="Digite sua pergunta ou comando… (Shift+Enter quebra a linha)" aria-label="Mensagem para o NewClaw" />
            <button
              className={`icone mic ${jeito === 'livre' ? (micAberto ? 'ativo' : 'mudo') : micAberto ? 'ativo' : ''}`}
              disabled={!!motor.semMicrofone || ligado !== 'ligado' || !modeloPronto}
              title={!modeloPronto ? 'Carregue o modelo de voz para falar' : motor.semMicrofone ? `Sem microfone: ${motor.semMicrofone}` : jeito === 'livre' ? (micAberto ? 'Silenciar o microfone' : 'Abrir o microfone') : 'Segure para falar'}
              onClick={botaoMic}
              onPointerDown={() => jeito === 'segurar' && segurar(true)}
              onPointerUp={() => jeito === 'segurar' && segurar(false)}
              onPointerLeave={() => jeito === 'segurar' && micAberto && segurar(false)}
            >
              <Icone d={micAberto || jeito === 'segurar' ? 'M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3zM19 10v1a7 7 0 0 1-14 0v-1M12 18v4' : 'M2 2l20 20M9 9v2a3 3 0 0 0 5.1 2.1M15 9.3V5a3 3 0 0 0-5.9-.8M19 10v1a7 7 0 0 1-.6 2.9M5 10v1a7 7 0 0 0 11.5 5.4M12 18v4'} />
            </button>
            <button className={`icone ${parar ? 'parar' : 'enviar'}`} title={parar ? 'Parar' : 'Enviar'} onClick={enviar}>
              {parar
                ? <svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
                : <Icone d="M22 2 11 13M22 2l-7 20-4-9-9-4z" />}
            </button>
          </div>
          <div className={`situacao-mic ${!somLiberado ? 'alerta' : ''}`} role="status">
            {!somLiberado ? 'Clique em qualquer lugar da janela para liberar o som (exigência do navegador).'
              : ligado === 'ligando' ? 'Ligando a voz… o microfone abre quando ela estiver pronta.'
                : motor.semMicrofone ? `Sem microfone: ${motor.semMicrofone}.`
                  : !modeloPronto ? 'Reconhecimento de voz desligado — carregue o modelo de voz para falar'
                  : jeito === 'segurar' ? (micAberto ? '● Ouvindo enquanto você segura' : 'Segure Espaço (ou o botão do microfone) para falar')
                    : micAberto ? '● Microfone aberto — pode falar' : 'Microfone silenciado — clique no microfone para abrir'}
          </div>
          <div className="dica">Enter envia · Shift+Enter quebra a linha · F liga o foco</div>
        </div>
      </footer>
    </div>
  );
}

// ─── Raiz ───────────────────────────────────────────────────────────────────

export function App() {
  const [entrou, setEntrou] = useState<boolean | null>(null);
  // Painel do NewClaw sem senha: a janela entra direto, e "Sair" some (sairia e entraria de novo na hora).
  const [semSenha, setSemSenha] = useState(false);
  useEffect(() => {
    document.documentElement.dataset.tema = temaInicial();
    fetch('/sessao').then((r) => r.json()).then((d) => { setSemSenha(!!d.sem_senha); setEntrou(!!d.entrou); })
      .catch(() => setEntrou(false));
  }, []);
  if (entrou === null) return null;
  return entrou ? <Janela semSenha={semSenha} aoSair={() => setEntrou(false)} /> : <Entrar aoEntrar={() => setEntrou(true)} />;
}
