"""Comandos que precisam do motor (Pipecat/faster-whisper): rodam com o Python do `.venv`."""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import configuracao as cfg

RAIZ = Path(__file__).resolve().parent.parent


def _valor(argumentos: list[str], nome: str) -> str | None:
    if nome in argumentos:
        i = argumentos.index(nome)
        if i + 1 < len(argumentos):
            return argumentos[i + 1]
    return None


def modelos(argumentos: list[str]) -> int:
    """`modelos [--json] [--pasta P] [--baixar NOME]` (Whisper), `modelos --kokoro [--json] [--baixar]`, `modelos --vozes [--json]`"""
    from . import modelos as m

    pasta = Path(_valor(argumentos, "--pasta") or cfg.carregar(None, RAIZ / ".env", RAIZ).modelos_dir)
    if "--vozes" in argumentos:
        if not m.kokoro_instalado(pasta):
            print(f"Kokoro não está em {m.pasta_kokoro(pasta)}.")
            return 1
        from . import tts_local

        try:
            vozes = tts_local.vozes_disponiveis(pasta)
        except tts_local.TtsIndisponivel as e:
            print(e)
            return 1
        if "--json" in argumentos:
            print(json.dumps(vozes, ensure_ascii=False))
        else:
            for v in vozes:
                print(f"{v['nome']:<16} {v['rotulo'] if v['rotulo'] != v['nome'] else ''}")
        return 0
    if "--kokoro" in argumentos:
        if "--baixar" in argumentos:
            print(f"Baixando o Kokoro para {m.pasta_kokoro(pasta)} …")
            inicio = time.perf_counter()
            destino = m.baixar_kokoro(pasta)
            print(f"Pronto em {time.perf_counter() - inicio:.0f} s: {destino}")
            return 0
        tamanho = m.tamanho_kokoro()
        dados = {
            "instalado": m.kokoro_instalado(pasta), "pasta": str(m.pasta_kokoro(pasta)),
            "bytes": tamanho, "tamanho": m.formatar_bytes(tamanho), "enderecos": list(m.enderecos_kokoro()),
        }
        print(json.dumps(dados, ensure_ascii=False) if "--json" in argumentos else f"{dados['tamanho']}  {dados['pasta']}")
        return 0
    nome = _valor(argumentos, "--baixar")
    if nome:
        if nome not in m.repositorios():
            print(f"Modelo '{nome}' não existe nesta versão do faster-whisper.")
            return 1
        print(f"Baixando '{nome}' para {m.pasta_do_modelo(pasta, nome)} …")
        inicio = time.perf_counter()
        destino = m.baixar(pasta, nome)
        print(f"Pronto em {time.perf_counter() - inicio:.0f} s: {destino}")
        return 0
    lista = [
        {
            "nome": x.nome, "repositorio": x.repositorio, "bytes": x.bytes_, "tamanho": m.formatar_bytes(x.bytes_),
            "instalado": m.instalado(pasta, x.nome), "pasta": str(m.pasta_do_modelo(pasta, x.nome)),
            "licenca": x.licenca,
        }
        for x in m.listar()
    ]
    if "--gravar-lista" in argumentos:
        # Foto da lista para quem escolhe ANTES de instalar (o painel do NewClaw): o faster-whisper só existe depois.
        # Gerada por comando a cada versão, nunca escrita à mão; o instalador confere a escolha contra a lista ao vivo.
        import faster_whisper
        from datetime import date

        foto = {
            "gerado_em": date.today().isoformat(),
            "faster_whisper": faster_whisper.__version__,
            "modelos": [{k: x[k] for k in ("nome", "bytes", "tamanho", "licenca")} for x in lista],
        }
        destino = RAIZ / m.ARQUIVO_DA_LISTA
        destino.write_text(json.dumps(foto, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{len(lista)} modelos gravados em {destino}")
        return 0
    if "--json" in argumentos:
        print(json.dumps(lista, ensure_ascii=False))
    else:
        for x in lista:
            print(f"{x['nome']:<20} {x['tamanho']:>12}  {'baixado' if x['instalado'] else ''}")
    return 0


def exportar_vozes(argumentos: list[str]) -> int:
    """`exportar-vozes --saida arquivo.bin` — grava um arquivo de vozes do Kokoro com as 54 vozes e as misturas.

    O formato é o mesmo do `voices-v1.0.bin` (um .npz de vetores de estilo por nome), então qualquer programa que use o
    kokoro-onnx com esse arquivo passa a conhecer as misturas pelo nome (ex.: `george-alex-1`).
    """
    import numpy as np

    from . import modelos as m
    from . import tts_local

    destino = _valor(argumentos, "--saida")
    if not destino:
        print("uso: exportar-vozes --saida arquivo.bin")
        return 64
    pasta = cfg.carregar(None, RAIZ / ".env", RAIZ).modelos_dir
    if not m.kokoro_instalado(pasta):
        print(f"Kokoro não está em {m.pasta_kokoro(pasta)}.")
        return 1
    _, arquivo_vozes = m.arquivos_kokoro(pasta)
    with np.load(arquivo_vozes) as original:
        vozes = {nome: original[nome] for nome in original.files}
    lista = tts_local.misturas_validas(sorted(vozes))
    for mistura in lista:
        vozes[mistura.nome] = sum(vozes[v] * peso for v, peso in mistura.pesos).astype(vozes[mistura.pesos[0][0]].dtype)
    caminho = Path(destino)
    with open(caminho, "wb") as f:  # arquivo aberto: o numpy não acrescenta ".npz" ao nome
        np.savez(f, **vozes)
    with np.load(caminho) as conferencia:
        faltando = [mistura.nome for mistura in lista if mistura.nome not in conferencia.files]
    if faltando:
        print(f"Falha: {faltando} não ficaram no arquivo.")
        return 1
    print(f"{len(vozes)} vozes ({len(lista)} misturas: {', '.join(x.nome for x in lista)}) gravadas em {caminho}.")
    return 0


# Frase do teste de síntese, uma por idioma aceito. É conteúdo de teste, não escolha de recurso.
FRASE_DE_TESTE = {
    "pt-BR": "Pronto! Criei o relatório com três tópicos. Quer que eu envie por e-mail?",
    "en-US": "Done! I created the report with three topics. Should I send it by email?",
    "es-ES": "¡Listo! Creé el informe con tres temas. ¿Quieres que lo envíe por correo?",
}


def testar_tts(argumentos: list[str]) -> int:
    """`testar-tts [--voz NOME] [--saida arquivo.wav]` — sintetiza a frase de teste frase a frase e mede.

    Sem `--voz`, usa a voz inicial do `.env`; sem nenhuma das duas, diz que a voz é escolhida na interface.

    Se a transcrição local também estiver configurada, faz a ida e volta: transcreve o áudio gerado e mostra o texto, para
    comparar com o original.
    """
    import tempfile

    from . import frases, stt_local, tts_local

    config = cfg.carregar(None, RAIZ / ".env", RAIZ)
    com_stt = config.stt is not None and config.stt.motor == cfg.LOCAL
    taxa = 16_000 if com_stt else tts_local.TAXA_PADRAO_FORA_DO_PIPELINE  # o Whisper espera 16 kHz
    try:
        inicio = time.perf_counter()
        servico = tts_local.criar_servico(config, taxa, voz=_valor(argumentos, "--voz"))
        print(f"Kokoro carregado em {time.perf_counter() - inicio:.1f} s — voz {tts_local.voz_atual(servico)}, idioma {config.idioma}.")
    except tts_local.SemVozEscolhida as e:
        print(f"{e} Para testar uma voz agora: python -m newclaw_ivox testar-tts --voz <nome>")
        return 0
    except tts_local.TtsIndisponivel as e:
        print(f"Síntese local indisponível: {e}")
        return 1

    texto = FRASE_DE_TESTE[config.idioma]
    resultado = tts_local.sintetizar(servico, frases.preparar_para_fala(texto))
    for fala in resultado.falas:
        print(
            f"  {fala.frase!r}: pronta em {fala.segundos_para_sintetizar:.2f} s para {fala.segundos_de_audio:.1f} s de fala"
        )
    destino = Path(_valor(argumentos, "--saida") or Path(tempfile.gettempdir()) / "newclaw-ivox-teste.wav")
    tts_local.gravar_wav(destino, resultado.audio_pcm16, taxa)
    print(f"Áudio gravado em {destino} (para ouvir).")

    if com_stt:
        try:
            stt, escolha = stt_local.criar_servico(config)
        except stt_local.SttIndisponivel as e:
            print(f"Ida e volta pulada: {e}")
            return 0
        stt_local.transcrever(stt, escolha, resultado.audio_pcm16, taxa)  # aquecimento
        volta = stt_local.transcrever(stt, escolha, resultado.audio_pcm16, taxa)
        print(f"Original:    {texto!r}")
        print(f"Transcrito:  {volta.texto!r}")
    return 0


AUDIOS_ACEITOS = (".wav", ".m4a", ".mp3", ".ogg", ".opus", ".webm", ".flac")


def medir_stt(argumentos: list[str]) -> int:
    """`medir-stt --audios PASTA --frases ARQ [--vocabulario ARQ] [--modelos a,b] [--json]`

    Transcreve cada gravação da pasta com cada modelo e cada apoio de vocabulário (sem apoio, `hotwords`,
    `initial_prompt`) pelo mesmo `run_stt` da janela, e mede a taxa de erro de palavras contra o texto dito.

    - As gravações são pareadas com as linhas de `--frases` pela ordem em que foram gravadas (data de modificação); o
      pareamento é impresso para conferir.
    - `--vocabulario`: um termo por linha.
    - `--modelos`: padrão, o modelo configurado; modelo não baixado é relatado como ausente, nunca baixado aqui.
    - Cada modelo é carregado, usado e descarregado antes do próximo.
    """
    import dataclasses

    from . import modelos as m
    from . import stt_local

    pasta_audios = _valor(argumentos, "--audios")
    arquivo_frases = _valor(argumentos, "--frases")
    if not pasta_audios or not arquivo_frases:
        print("uso: medir-stt --audios PASTA --frases ARQUIVO [--vocabulario ARQUIVO] [--modelos a,b] [--json]")
        return 64
    audios = sorted((p for p in Path(pasta_audios).iterdir() if p.suffix.lower() in AUDIOS_ACEITOS),
                    key=lambda p: p.stat().st_mtime)
    frases = [linha.strip() for linha in Path(arquivo_frases).read_text(encoding="utf-8").splitlines() if linha.strip()]
    if len(audios) != len(frases):
        print(f"{len(audios)} gravação(ões) em {pasta_audios} e {len(frases)} frase(s) em {arquivo_frases}: "
              "o número precisa ser igual para parear.")
        return 1
    termos: list[str] = []
    arquivo_vocab = _valor(argumentos, "--vocabulario")
    if arquivo_vocab:
        termos = [t.strip() for t in Path(arquivo_vocab).read_text(encoding="utf-8").splitlines() if t.strip()]

    config = cfg.carregar(None, RAIZ / ".env", RAIZ)
    if config.stt is None or config.stt.motor != cfg.LOCAL:
        print("Transcrição local não configurada (VOZ_STT_MOTOR=local e VOZ_STT_MODELO).")
        return 1
    nomes = [n.strip() for n in (_valor(argumentos, "--modelos") or config.stt.modelo).split(",") if n.strip()]

    apoios: list[tuple[str, str | None, str | None]] = [("sem apoio", None, None)]
    if termos:
        apoios.append(("hotwords", " ".join(termos), None))
        apoios.append(("initial_prompt", None, "Vocabulário: " + ", ".join(termos) + "."))

    print("Pareamento (ordem de gravação):")
    for audio, frase in zip(audios, frases):
        print(f"  {audio.name}  →  {frase}")
    pcm = [stt_local.ler_audio_16k(a) for a in audios]
    com_termo = [any(t.lower() in f.lower() for t in termos) for f in frases]

    resultados: list[dict] = []
    for nome in nomes:
        if not m.instalado(config.modelos_dir, nome):
            print(f"\n{nome}: não baixado em {m.pasta_do_modelo(config.modelos_dir, nome)} — fora da medição.")
            resultados.append({"modelo": nome, "ausente": True})
            continue
        config_m = dataclasses.replace(config, stt=dataclasses.replace(config.stt, modelo=nome))
        dono = stt_local.DonoDoModelo()
        estado = dono.pedir_carga(config_m, esperar=True)
        if estado["estado"] != stt_local.CARREGADO:
            print(f"\n{nome}: não carregou — {estado.get('erro') or estado.get('aviso') or estado['estado']}")
            resultados.append({"modelo": nome, "falha": estado.get("erro") or estado.get("aviso") or estado["estado"]})
            continue
        escolha = stt_local.escolha_do_estado(estado)
        try:
            for rotulo, hotwords, prompt in apoios:
                servico = stt_local.servico_da_linha(config_m, dono, hotwords=hotwords, initial_prompt=prompt)
                stt_local.transcrever(servico, escolha, pcm[0], 16_000)  # aquecimento, fora da conta
                linhas, erros, total, segundos = [], [0, 0], [0, 0], 0.0
                for i, (audio, frase) in enumerate(zip(audios, frases)):
                    volta = stt_local.transcrever(servico, escolha, pcm[i], 16_000)
                    e, n = stt_local.erros_de_palavras(frase, volta.texto)
                    grupo = 0 if com_termo[i] else 1
                    erros[grupo] += e
                    total[grupo] += n
                    segundos += volta.segundos_para_transcrever
                    linhas.append({"audio": audio.name, "dito": frase, "ouvido": volta.texto, "erros": e, "palavras": n})
                resultados.append({
                    "modelo": nome, "apoio": rotulo, "dispositivo": f"{escolha.dispositivo}/{escolha.tipo}",
                    "erros": sum(erros), "palavras": sum(total),
                    "erros_com_termo": erros[0], "palavras_com_termo": total[0],
                    "erros_sem_termo": erros[1], "palavras_sem_termo": total[1],
                    "segundos_para_transcrever": round(segundos, 2), "frases": linhas,
                })
        finally:
            dono.descarregar()

    if "--json" in argumentos:
        print(json.dumps(resultados, ensure_ascii=False, indent=1))
        return 0

    def taxa(e: int, n: int) -> str:
        return f"{100 * e / n:5.1f}%" if n else "   — "

    for r in resultados:
        if "apoio" not in r:
            continue
        print(f"\n── {r['modelo']} · {r['apoio']} ({r['dispositivo']}, {r['segundos_para_transcrever']} s no total)")
        for linha in r["frases"]:
            marca = "  " if linha["erros"] == 0 else "✗ "
            print(f"  {marca}{linha['ouvido']!r}  ({linha['erros']}/{linha['palavras']})")
    print("\nTaxa de erro de palavras (menor é melhor):")
    print(f"  {'modelo':<18} {'apoio':<15} {'geral':>7} {'frases c/ termo':>16} {'frases s/ termo':>16} {'tempo':>8}")
    for r in resultados:
        if "apoio" not in r:
            continue
        print(f"  {r['modelo']:<18} {r['apoio']:<15} {taxa(r['erros'], r['palavras']):>7} "
              f"{taxa(r['erros_com_termo'], r['palavras_com_termo']):>16} "
              f"{taxa(r['erros_sem_termo'], r['palavras_sem_termo']):>16} {r['segundos_para_transcrever']:>7.1f}s")
    return 0


def testar_stt(argumentos: list[str]) -> int:
    """`testar-stt [--audio arquivo.wav]` — carrega o modelo no dispositivo medido e transcreve duas vezes.

    A primeira rodada aquece o dispositivo (na GPU, a primeira de cada processo é bem mais lenta); a segunda é o tempo de
    uso. Sem `--audio`, usa 5 s de silêncio só para provar que o modelo roda e medir o tempo: o Whisper costuma inventar
    texto em silêncio, e no uso real isso não acontece porque o detector de voz só manda trechos com fala.
    """
    from . import stt_local

    config = cfg.carregar(None, RAIZ / ".env", RAIZ)
    try:
        inicio = time.perf_counter()
        servico, escolha = stt_local.criar_servico(config)
        carga = time.perf_counter() - inicio
    except stt_local.SttIndisponivel as e:
        print(f"Transcrição local indisponível: {e}")
        return 1
    print(f"Modelo '{config.stt.modelo}' carregado em {carga:.1f} s — {escolha.motivo}")

    arquivo = _valor(argumentos, "--audio")
    if arquivo:
        audio, taxa = stt_local.ler_wav_pcm16(Path(arquivo))
    else:
        audio, taxa = bytes(5 * 16_000 * 2), 16_000
    aquecimento = stt_local.transcrever(servico, escolha, audio, taxa)
    uso = stt_local.transcrever(servico, escolha, audio, taxa)
    fator = uso.segundos_de_audio / uso.segundos_para_transcrever if uso.segundos_para_transcrever else float("inf")
    print(f"Aquecimento: {aquecimento.segundos_para_transcrever:.2f} s.")
    print(
        f"Uso: {uso.segundos_de_audio:.1f} s de áudio em {uso.segundos_para_transcrever:.2f} s "
        f"({uso.dispositivo}/{uso.tipo}) — {fator:.1f}x {'mais rápido' if fator >= 1 else 'da velocidade'} que a fala."
    )
    if fator < 1:
        print("Mais lento que a fala: a resposta vai atrasar. Um modelo menor, ou uma GPU, deixa a transcrição mais rápida.")
    if arquivo:
        print(f"Texto: {uso.texto!r}")
    return 0
