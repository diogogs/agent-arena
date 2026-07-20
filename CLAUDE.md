# CLAUDE.md — agent-arena ("A Liga", nome provisório)

> Uma liga pública de agentes de trading em paper: 3-4 filosofias clássicas gerem
> carteiras gémeas intradiárias (sessão US, decisões a cada 15-30 min) contra o
> benchmark — que é concorrente de pleno direito. A pergunta pública: *consegue um
> agente autónomo fazer melhor do que não fazer nada?* Resposta esperada: **não** —
> e a liga mede quanto, com custos honestos. Objetivos reais: aprender mercados
> (autor não é conhecedor — é parte do interesse), engenharia de agentes com
> avaliação rigorosa, e track record que acumula sozinho durante as candidaturas.
> Criado 2026-07-20. Comunicação com o autor em PT; código/commits/ADRs em EN;
> superfícies públicas em PT. **Lição fundadora do portfólio: VISUAL PRIMEIRO** —
> a experiência final prototipa-se e aprova-se antes de o motor existir.

## Regras de charter (não negociáveis)

1. **Paper até prova em contrário**: critérios go/no-go para dinheiro real
   pré-registados e commitados ANTES da época começar. Não cumpre → não se discute.
2. **Custos sempre modelados** (spread + slippage + mín. 2 pb/lado) — a rotação é
   um adversário tão real como o índice (lição do ensaio sintético J1: a Reversão
   fez 96 round-trips num dia e ficou última).
3. **Insert-only**: decisões registadas antes do resultado; histórico imutável.
4. **Não é aconselhamento financeiro** — banner permanente em toda a superfície pública.
5. **Custo de infra zero**; segredos só em .env locais/GitHub Secrets.
6. Decisões de arquitetura ⇒ ADR. Descobertas de mundo real ⇒ teste.

## A liga — época 1 (~60 sessões ≈ 3 meses)

| Agente | Papel |
|---|---|
| Benchmark (SPY buy & hold) | O adversário a bater |
| Cash | O controlo ("não fazer nada") |
| Momentum (breakout da abertura + trailing stop) | "A força continua" |
| Reversão (desvios ao VWAP) | A religião oposta — o duelo é o curso |
| Comentador LLM (não negoceia) | Resume o dia, explica os duelos; 1-2 chamadas/dia free tier |

Época 1.5: agente ML. Época 2: comentador promovível a trader. Máx. 4 traders/época.

## Produto e stack

**A Arena**: site estático (GitHub Pages, sem cold start): curvas de capital ao vivo
na sessão US (14h30-21h00 Lisboa), trades com justificação de uma linha, tabela
classificativa, comentário diário, track record da época. Universo: SPY, QQQ +
4-6 megacaps (ultra-líquidos). Dados: Alpaca IEX (gratuito; fills aproximados —
IEX ≈ 2-3% do volume, documentado). Execução: simulador próprio transparente e
testável. Disparo: cron-job.org → GitHub Actions dispatch a cada 15-30 min
(lição energia ADR-013: nunca confiar no scheduler do Actions). LLM: Gemini flash
free tier (padrão dr-watch). Python + uv.

## Avaliação

Por agente/época: P&L líquido vs benchmark, custos pagos, nº trades, drawdown
máx., IC bootstrap da diferença para o benchmark. Relatório de meia época +
write-up final, incluindo onde falha.

## Estado (2026-07-20)

**J0 fechada**: charter aprovado pelo autor (plano em conversa, 2026-07-20),
repo local criado. **J1 em curso**: maquete visual da arena — dia sintético
(gerado com algoritmos reais de momentum/reversão + custos) em replay de ~60 s,
publicada como Artifact para aprovação do autor. Sem remoto GitHub ainda (criar
público quando o autor aprovar).

## Jornadas

- [x] **J0 — Charter + repo** (2026-07-20)
- [ ] **J1 — Maquete visual da arena** (replay do dia sintético) → aprovação dos olhos
- [ ] **J2 — Motor**: dados IEX, executor com custos, momentum + reversão +
  benchmark/cash, estado insert-only, testes (incl. verificação da conta Alpaca/KYC)
- [ ] **J3 — Arena ao vivo**: site estático + pipeline Actions/cron
- [ ] **J4 — Comentador LLM + pré-registo commitado + arranque da ÉPOCA 1**
- [ ] **J5 — Meia época**: relatório; agente ML (época 1.5)
- [ ] **J6 — Fim da época**: write-up honesto + decisão go/no-go

## Convenções

Herdadas do portfólio (C:\dev\CLAUDE.md): `uv` sempre, commits convencionais EN
pequenos, identidade visual navy (#1e2a38 → #2a5a8c).
