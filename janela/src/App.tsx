/**
 * A janela de voz: entrada com a senha do NewClaw, depois a tela da maquete aprovada (docs/referencia-visual), ligada ao
 * motor de voz do harness e ao contrato do turno do NewClaw.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { Centro, type EstiloDoCentro } from './Centro';
import { Conversa, type EsperaAntesDeEnviar, type JeitoDeFalar, type Quadro } from './conversa';
import { podeParar } from './estado';
import { LigacaoComOMotor, type Voz } from './motor';
import { gravarPref, idDaConversa, lerPref } from './preferencias';
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
        <p>Entre com a senha do painel do NewClaw. Ela vai direto para o NewClaw; esta janela não a guarda.</p>
        <input type="password" autoFocus autoComplete="current-password" placeholder="Senha do NewClaw"
          value={senha} onChange={(e) => setSenha(e.target.value)} aria-label="Senha do NewClaw" />
        <div className="erro" role="alert">{erro}</div>
        <button className="btn primario" disabled={enviando || !senha}>{enviando ? 'Entrando…' : 'Entrar'}</button>
      </form>
    </div>
  );
}

// ─── Janela ─────────────────────────────────────────────────────────────────

function Janela({ aoSair }: { aoSair: () => void }) {
  const [tema, setTema] = useState<Tema>(temaInicial);
  const [foco, setFoco] = useState(lerPref('ivox-foco') === 'sim');
  const [jeito, setJeito] = useState<JeitoDeFalar>(lerPref('ivox-fala') === 'segurar' ? 'segurar' : 'livre');
  const [estilo, setEstilo] = useState<EstiloDoCentro>(lerPref('ivox-centro') === 'particulas' ? 'particulas' : 'circulo');
  const [sons, setSons] = useState(lerPref('ivox-sons') !== 'nao');
  const [espera, setEspera] = useState<EsperaAntesDeEnviar>(() => {
    const e = lerPref('ivox-espera');
    return e === 'curta' || e === 'longa' ? e : 'media';
  });
  const [quadro, setQuadro] = useState<Quadro | null>(null);
  const [ligado, setLigado] = useState<'ligando' | 'ligado' | 'falhou'>('ligando');
  const [falha, setFalha] = useState('');
  const [vozes, setVozes] = useState<Voz[]>([]);
  const [vozAtual, setVozAtual] = useState<string | null>(null);
  const [info, setInfo] = useState<InfoDaVoz | null>(null);
  const [texto, setTexto] = useState('');
  const [micAberto, setMicAberto] = useState(true);
  const [agora, setAgora] = useState(Date.now());
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
        await motor.conectar();
        if (!vivo) return;
        if (jeito === 'segurar') { motor.microfone(false); setMicAberto(false); }
        setLigado('ligado');
        const lista = await motor.vozes().catch(() => ({ vozes: [], atual: null }));
        if (vivo) { setVozes(lista.vozes); setVozAtual(lista.atual); }
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

  // Tema, foco e preferências.
  useEffect(() => { document.documentElement.dataset.tema = tema; gravarPref('ivox-tema', tema); }, [tema]);
  useEffect(() => { document.body.classList.toggle('foco', foco); gravarPref('ivox-foco', foco ? 'sim' : 'nao'); }, [foco]);
  useEffect(() => { gravarPref('ivox-centro', estilo); }, [estilo]);
  useEffect(() => { gravarPref('ivox-sons', sons ? 'sim' : 'nao'); }, [sons]);
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
      if (digitando(ev)) return;
      if (ev.key === 'f' || ev.key === 'F') { setFoco((v) => !v); return; }
      if (ev.code === 'Space' && jeito === 'segurar') { ev.preventDefault(); if (!ev.repeat) segurar(true); }
    };
    const cima = (ev: globalThis.KeyboardEvent) => {
      if (ev.code === 'Space' && jeito === 'segurar' && !digitando(ev)) { ev.preventDefault(); segurar(false); }
    };
    addEventListener('keydown', baixo);
    addEventListener('keyup', cima);
    return () => { removeEventListener('keydown', baixo); removeEventListener('keyup', cima); };
  }, [jeito, segurar]);

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
    try { await motor.trocarVoz(nome); } catch { setVozAtual(anterior); }
  };
  const sair = async () => {
    await fetch('/sair', { method: 'POST' }).catch(() => undefined);
    aoSair();
  };

  const q = quadro;
  const estado = q?.estado ?? 'pronto';
  const parar = podeParar(estado);
  const h = new Date(agora).getHours();
  const saudacao = h < 12 ? 'Bom dia.' : h < 18 ? 'Boa tarde.' : 'Boa noite.';
  const mostraTempo = parar || estado === 'ouvindo' || estado === 'aprovacao';
  const tempo = q && mostraTempo ? tempoDecorrido(agora - q.desde) : '';
  const [antes, atual, depois] = q?.fala ? partesDaFala(q.fala.texto, q.fala.fraseAtual) : ['', '', ''];
  const textoParado = ligado === 'falhou'
    ? `Não consegui ligar a voz: ${falha}`
    : ligado === 'ligando' ? 'Ligando o motor de voz…'
      : motor.semMicrofone ? `Sem microfone (${motor.semMicrofone}). Você pode escrever abaixo; a resposta continua falada.`
        : 'Fale comigo pelo microfone ou escreva abaixo. Você pode me interromper falando por cima.';

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
          <button className="botao-tema" onClick={() => setFoco(!foco)} title="Modo foco: só o centro e a conversa (tecla F)">
            <Icone d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3" />
            <span>{foco ? 'Sair do foco' : 'Foco'}</span>
          </button>
          <button className="botao-tema" onClick={() => setTema(tema === 'claro' ? 'escuro' : 'claro')} title="Trocar tema">
            <Icone d={tema === 'claro' ? 'M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z' : 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4'} />
            <span>{tema === 'claro' ? 'Escuro' : 'Claro'}</span>
          </button>
          <button className="botao-tema" onClick={sair} title="Sair (a senha não fica guardada)"><span>Sair</span></button>
        </div>
      </header>

      <main>
        <section className="coluna esq">
          <div className="cartao">
            <h2>Voz neste computador</h2>
            {info ? (
              <>
                <div className="linha"><span className="rot">Ouvir</span><span>{info.ouvir ? `${info.ouvir.modelo ?? '—'} · ${info.ouvir.motor === 'local' ? 'local' : 'servidor'}` : 'não configurado'}</span></div>
                <div className="linha"><span className="rot">Falar</span><span>{info.falar ? `Kokoro · ${info.falar.motor === 'local' ? 'local' : 'servidor'}` : 'não configurado'}</span></div>
                <div className="linha"><span className="rot">Idioma</span><span>{info.idioma ?? 'não informado'}</span></div>
                <div className="linha"><span className="rot">Dispositivo</span><span>{info.dispositivo}</span></div>
              </>
            ) : <div className="vazio">Carregando…</div>}
          </div>
          <div className="cartao voz-escolha">
            <h2><label htmlFor="voz">Voz</label></h2>
            {vozes.length > 0 ? (
              <select className="btn" id="voz" value={vozAtual ?? ''} onChange={(e) => void trocarVoz(e.target.value)}>
                {vozAtual === null && <option value="" disabled>Escolha uma voz</option>}
                {vozes.map((v) => <option key={v.nome} value={v.nome}>{v.rotulo}</option>)}
              </select>
            ) : <div className="vazio">{ligado === 'ligado' ? 'A síntese local não está ligada neste motor.' : 'Disponível quando a voz ligar.'}</div>}
          </div>
        </section>

        <section className="centro" data-cor={estado}>
          <div className="saudacao"><h2>{saudacao}</h2><p>Como posso ajudar hoje?</p></div>
          <Centro estado={estado} estilo={estilo} niveis={motor.niveis} tempo={tempo} />
          <div className="detalhe">
            <div className="topo"><b>{q ? detalhe(q) : 'Pronto'}</b></div>
            <div className={`trilho ${parar || estado === 'ouvindo' ? 'indeterminado' : ''}`}><i /></div>
          </div>
          <div className="legenda" aria-live="polite">
            {q?.legenda || estado === 'ouvindo'
              ? <><span className="rotulo">Você</span>{q?.legenda}{estado === 'ouvindo' && <span className="cursor" />}</>
              : null}
          </div>
          <div className={`balao ${q?.fala && atual ? 'lendo' : ''}`}>
            {q?.fala
              ? <>{antes && <span className="frase">{antes}</span>}{atual && <span className="frase atual">{atual}</span>}{depois && <span className="frase">{depois}</span>}</>
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
            <h2>Conversa</h2>
            <div className="conversa">
              {(q?.mensagens.length ?? 0) === 0 && (q?.aprovacoes.length ?? 0) === 0 && <div className="vazio">Nada por aqui ainda.</div>}
              {q?.mensagens.map((m, i) => (
                <div key={i} className={`msg ${m.quem}`}>
                  {m.texto}
                  <small>{hora(m.em)}{m.porVoz ? ' · por voz' : ''}</small>
                </div>
              ))}
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
            <div className="rotulo-opcao">Espera antes de enviar</div>
            <div className="segmento" role="radiogroup" aria-label="Espera antes de enviar">
              <button className={espera === 'curta' ? 'ativo' : ''} onClick={() => setEspera('curta')} title="Envia com ~1,4 s de silêncio">Curta</button>
              <button className={espera === 'media' ? 'ativo' : ''} onClick={() => setEspera('media')} title="Envia com ~2 s de silêncio">Média</button>
              <button className={espera === 'longa' ? 'ativo' : ''} onClick={() => setEspera('longa')} title="Envia com ~3 s de silêncio (para quem pensa enquanto fala)">Longa</button>
            </div>
            <label className="chave"><input type="checkbox" checked={sons} onChange={(e) => setSons(e.target.checked)} /> Sons ao começar e terminar de ouvir</label>
            <div className="nota">
              {motor.semMicrofone ? `Sem microfone: ${motor.semMicrofone}.` : jeito === 'livre'
                ? 'O microfone fica aberto; ele percebe sozinho quando você termina. O botão do microfone silencia.'
                : 'Segure a barra de espaço (ou o botão do microfone) enquanto fala e solte quando terminar.'}
            </div>
          </div>
        </section>
      </main>

      <footer>
        <div className="entrada-wrap">
          <div className="entrada">
            <textarea ref={campo} rows={1} value={texto} onChange={(e) => setTexto(e.target.value)} onKeyDown={teclaNaCaixa}
              placeholder="Digite sua pergunta ou comando… (Shift+Enter quebra a linha)" aria-label="Mensagem para o NewClaw" />
            <button
              className={`icone mic ${jeito === 'livre' ? (micAberto ? 'ativo' : 'mudo') : micAberto ? 'ativo' : ''}`}
              disabled={!!motor.semMicrofone || ligado !== 'ligado'}
              title={motor.semMicrofone ? `Sem microfone: ${motor.semMicrofone}` : jeito === 'livre' ? (micAberto ? 'Silenciar o microfone' : 'Abrir o microfone') : 'Segure para falar'}
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
  useEffect(() => {
    document.documentElement.dataset.tema = temaInicial();
    fetch('/sessao').then((r) => r.json()).then((d) => setEntrou(!!d.entrou)).catch(() => setEntrou(false));
  }, []);
  if (entrou === null) return null;
  return entrou ? <Janela aoSair={() => setEntrou(false)} /> : <Entrar aoEntrar={() => setEntrou(true)} />;
}
