# Vozes misturadas

Cada arquivo `.json` desta pasta é **uma voz nova**, feita da média ponderada de vozes do Kokoro (licença Apache-2.0).
Não imitam nenhuma pessoa. Ao iniciar, o motor lê a pasta inteira e as vozes aparecem na janela, antes das 54 vozes normais,
em ordem alfabética pelo nome do arquivo.

## Como adicionar uma voz

1. Crie um arquivo novo aqui, com o mesmo nome da voz: `minha-voz.json`.
2. Escreva isto dentro:

```json
{
  "nome": "minha-voz",
  "rotulo": "Minha Voz (60% George / 40% Alex)",
  "mistura": { "bm_george": 0.6, "pm_alex": 0.4 }
}
```

3. Reinicie o motor de voz (Configurações → Integrações → Desligar e Ligar) e recarregue a janela.

## Regras (o motor avisa o motivo se alguma falhar)

- `nome`: sem espaços, e diferente de qualquer voz que já exista (inclusive as do Kokoro).
- `rotulo`: o texto que aparece na lista da janela. Vale escrever os percentuais nele.
- `mistura`: duas vozes ou mais, cada uma com um peso maior que zero, e **os pesos somam 1**.
- As vozes usadas precisam existir no Kokoro instalado (ex.: `bm_george`, `bm_daniel`, `bm_fable`, `am_michael`, `pm_alex`).
  Para ver todas: `python -m newclaw_ivox modelos --vozes`.
- Um arquivo com erro faz o motor recusar a lista toda e dizer qual arquivo está errado; nada é ignorado em silêncio.

## Voz que não é mistura

Uma voz com um vetor próprio (por exemplo, treinada por você) não cabe aqui: esta pasta só combina vozes que o Kokoro já tem.
Se isso for necessário, vira outro mecanismo. Avise.

## De onde vieram

- `george-alex-1/2/3`: pedido da operadora, 29/10/2026.
- as outras seis: criadas no Voice-Studio e trazidas em 30/10/2026 (cada mistura conferida contra o vetor gravado lá).
