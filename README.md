# newclaw-ivox

Interface de voz opcional para o [NewClaw](https://github.com/rovanni/NewClaw): uma janela que ouve, mostra o andamento
das tarefas e fala as respostas. "ivox" vem de "interface de voz", e "vox" porque a interface pode ter várias vozes.

É um **harness**: usa o NewClaw só pelas rotas públicas e pelo contrato do turno (`docs/CONTRATO_DO_TURNO.md` no NewClaw).
O NewClaw não depende dele (ADR-030 e ADR-031 do NewClaw). O harness não tem modelo de linguagem, memória nem persona: quem
pensa, lembra e executa é o NewClaw.

## Estado

Em desenvolvimento, em sprints — ver [docs/SPRINTS.md](docs/SPRINTS.md). Ainda não há voz funcionando: a Sprint 1 entregou a
configuração, a divisão do texto para a fala e o protocolo entre a janela e o motor de voz, tudo com testes.

## Configuração

Copie `.env.example` para `.env` e preencha só o que você tem: um servidor de transcrição e/ou um de síntese compatíveis com
a API OpenAI. Campo vazio desliga o recurso; nada é adivinhado.

```bash
python -m newclaw_ivox diagnostico
```

Saída `0` = pronto, `1` = erro de configuração, `2` = nada configurado. `--json` dá a mesma informação para outro programa
ler. A chave nunca aparece, só se ela existe.

## Testes

```bash
python -m unittest discover -s tests -t .
```

## Licença

MIT (código deste repositório). As dependências de terceiros, quando entrarem, têm licenças próprias; o inventário e os
avisos vêm antes de qualquer publicação (ADR-030, decisão L1). Este projeto não declara conformidade jurídica.
