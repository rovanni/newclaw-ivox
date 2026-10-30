# Referência visual da janela de voz (Etapa 4)

Em 28/10/2026 a operadora mandou uma imagem com o visual que ela queria para a nova janela de conversa, um painel
futurista escuro e azul. A imagem não está neste repositório: tinha nome de personagem de terceiros e dados reais da rede
dela. A referência daqui é a `maquete.html`, feita a partir dela e aprovada pela operadora em 30/10.

O que a imagem pedia:
- tema escuro azul, estilo painel futurista (linhas finas, brilho, cantos arredondados);
- no centro, um globo com o "N" do NewClaw e anéis girando, com saudação ("Olá, …. Como posso ajudar hoje?") e uma fala
  do assistente logo abaixo;
- em volta, cartões: status do sistema, modelos de IA, atividades recentes, infraestrutura, próximas tarefas e atalhos
  (Chat, Analisar, Planejar, Executar, Documentar);
- embaixo, a caixa de texto com anexar, microfone e enviar, e um indicador de voz ativa com a onda do áudio.

Temas (pedido dela em 29/10/2026): **modo claro e modo escuro**. O escuro é o da imagem; o claro mantém o mesmo desenho
(globo, anéis, cartões, azul como cor de destaque) sobre fundo claro. Segue o tema do sistema por padrão e tem um botão
para trocar, que fica lembrado.

Decisões dela sobre a maquete (`maquete.html`, 29–30/10/2026):
- No centro, um **círculo de voz** em vez do globo, **sem o "N"** (ela não gosta). No meio fica só uma luz que acende com
  a voz. O que reage à fala é esse círculo, não a onda do canto (que saiu).
- **Você fala:** azul, barras em volta reagindo ao microfone. **NewClaw fala:** amarelo, luz do centro pulsando e ondas
  saindo do centro. Cores primárias; **nada de rosa**. Vermelho só para "precisa de você" e erro.
- **Sete estados com cor**, inspirados no "Model state" do Strata: Pronto (cinza), Ouvindo você (azul), Na fila (amarelo
  claro), Pensando (amarelo), Falando (amarelo forte), Precisa de você (vermelho piscando), Erro (vermelho). **Mudança de
  30/10, a pedido dela:** em vez da faixa com todos os estados, aparece **só o estado atual, num rótulo no meio** do círculo
  ou das partículas (nome e tempo), e o centro inteiro muda para a cor dele. Embaixo fica a linha de detalhe com o último
  aviso de progresso. Todos esses estados já existem no contrato do turno ou na própria janela.
- Aprovadas por ela em 30/10: **legenda ao vivo** (sua fala sendo escrita; a frase dele destacada palavra a palavra no
  balão), **modo foco** (botão e tecla F), **jeito de falar** (mãos livres ou segurar espaço), **atalhos como pedidos
  prontos** e **sons discretos** com liga/desliga. Também em 30/10: **estilo do centro escolhível** — Círculo ou
  Partículas (esfera de pontos girando; mesmas cores e estados), lembrado entre sessões. Aprovação de ação perigosa **nunca por voz**, só por clique.
- "Lendo arquivo", "pesquisando" etc. exigem um campo novo no contrato (atividade atual, vinda da ferramenta em
  execução); não deduzir do texto do aviso.

Cuidados ao implementar:
- nome de personagem de filme foi vetado pela operadora; o indicador de modo da imagem vira "Modo voz";
- nada de marca, logotipo, fonte ou som de filme: só o estilo geral (escuro, azul, painel), que não é de ninguém;
- os cartões dependem de dados que o contrato público do turno não expõe hoje (VMs, infraestrutura, tarefas). Para a
  Etapa 4, decidir com ela o que entra na primeira versão.
