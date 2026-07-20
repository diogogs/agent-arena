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

Época 1.5+: agente ML e o Capitão (alocador). LLM: backlog (fora do caminho
crítico, decisão do autor 2026-07-20). Máx. 4 traders/época.

## Ginásio e Arena (ADR-002 — o coração do desenho)

**Ginásio** = simulador point-in-time sobre histórico intradiário (no-lookahead
por arquitetura + testes): é onde se aprende, rápido (Optuna walk-forward;
gerações em minutos). **Arena** = paper live: é o exame, lento. Promoções
Ginásio→Arena no máx. 1×/semana, registo insert-only por geração. Cada geração
publica 3 números: treino / validação / live — o fosso entre eles é métrica
pública de primeira classe. Jornadas: cada sessão live é uma jornada (resultado
próprio + replay); a época acumula a classificação geral. A manchete de longo
prazo: a curva geracional ("cada geração perde menos na Arena?").

## Produto e stack

**A Arena**: site estático (GitHub Pages, sem cold start): curvas de capital ao vivo
na sessão US (14h30-21h00 Lisboa), trades com justificação de uma linha, tabela
classificativa, comentário diário, track record da época. Universo: SPY, QQQ +
4-6 megacaps (ultra-líquidos). Dados: Alpaca IEX (gratuito; fills aproximados —
IEX ≈ 2-3% do volume, documentado). Execução: simulador próprio transparente e
testável. Disparo: cron-job.org → GitHub Actions dispatch a cada 15-30 min
(lição energia ADR-013: nunca confiar no scheduler do Actions). Histórico para o
Ginásio: Alpaca IEX / Polygon free (~2 anos de barras de minuto), cacheado em
parquet — verificar fontes e limites logo no arranque da J2. Python + uv.

## Avaliação

Por agente/época: P&L líquido vs benchmark, custos pagos, nº trades, drawdown
máx., IC bootstrap da diferença para o benchmark. Relatório de meia época +
write-up final, incluindo onde falha.

## Estado (2026-07-20)

**J0+J1 fechadas; J2 (Motor + Ginásio) FUNCIONAL** (2026-07-20). Verificado live:
yfinance sem chave dá 15m/5m×60 dias e 1h×730 dias — o arquivo próprio
insert-only (`data/archive/`, commitado, 6 símbolos) cresce a cada ingestão e
torna-se mais fundo que a fonte. Motor: MarketView point-in-time (no-lookahead
POR CONSTRUÇÃO — a view só contém cópias do passado), executor com custos
(2 pb + 1 pb slippage; bug de fee-sem-cobertura apanhado por teste), 7 testes
verdes (lookahead, conservação, custo exato do round-trip, flatten EOD,
determinismo). Ginásio: walk-forward Optuna → primeiras gerações treinadas em
dados reais (60 sessões, abr-jul 2026) e registadas insert-only:
`momentum-g001` (val +3 475 €, +2 283 vs bench — 12 sessões = ruído, ler com
ICs) e `reversao-g001` (val +327 €, −865 vs bench). Pendente do autor: conta
Alpaca (upgrade de dados, não bloqueia). **Próximo: J3 — Arena live** (loop
paper cron→Actions, jornadas, site estático). Sem remoto GitHub ainda.

## Jornadas

- [x] **J0 — Charter + repo** (2026-07-20)
- [x] **J1 — Maquete visual da arena** (2026-07-20): replay do dia sintético com
  algoritmos reais + custos, publicada como Artifact; aprovada pelo autor, com
  duas direções novas dele: jornadas/época e aprendizagem geracional (→ ADR-002)
- [ ] **J2 — Motor + Ginásio**: histórico intradiário verificado + cache,
  simulador point-in-time com testes de no-lookahead, custos, momentum +
  reversão, treino walk-forward (Optuna), registo de gerações
  (+ verificação da conta Alpaca/KYC e limites do free tier)
- [ ] **J3 — Arena live**: loop paper (cron→Actions), jornadas + classificação,
  site estático (páginas Arena e Ginásio)
- [ ] **J4 — Pré-registo commitado + arranque da ÉPOCA 1** (geração v1 do ginásio)
- [ ] **J5 — Meia época**: relatório; agente ML / o Capitão (época 1.5)
- [ ] **J6 — Fim da época**: write-up honesto + decisão go/no-go

## Convenções

Herdadas do portfólio (C:\dev\CLAUDE.md): `uv` sempre, commits convencionais EN
pequenos, identidade visual navy (#1e2a38 → #2a5a8c).
