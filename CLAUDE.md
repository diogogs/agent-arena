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
| Momentum (breakout da abertura + trailing stop) | "A força continua" — só NVDA/TSLA (emenda 2) |
| Reversão (desvios ao VWAP) | A religião oposta — só NVDA/TSLA (emenda 2) |

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

## Estado (2026-07-20, fim do dia de fundação — J0→J4 + pré-época num dia)

**TUDO LIVE E 100% AUTÓNOMO** — [arena](https://diogogs.github.io/agent-arena/) ·
[ginásio](https://diogogs.github.io/agent-arena/ginasio.html) ·
[pré-época](https://diogogs.github.io/agent-arena/preepoca.html) ·
[repo](https://github.com/diogogs/agent-arena). 19 testes verdes.

- **Ritmo semanal sem intervenção**: seg 11:45 UTC torneio do ginásio (+promoção
  se passar o gate) → seg-sex 13:30-20:00 UTC jornadas (ciclos 15 min via
  cron-job.org→Actions, fallback cron do Actions) → jornada fecha às ~20:10 →
  site regenera a cada ciclo. Jornada inaugural (época 0, 07-20): venceu o
  momentum +436 €; benchmark último, −934 € (um dia = ruído, regra da casa).
- **Época 1 arranca 2026-07-21** (60 jornadas, reset a 100k testado). Pré-registo
  + **3 emendas datadas de 07-20** (fundamentadas na pré-época, apendadas antes
  do kickoff): (1) promoção exige mediana POSITIVA do torneio rolante de 6
  janelas que bata a incumbente; (2) traders intradiários só negoceiam
  **NVDA/TSLA** (todo o edge vive lá; o resto pagava custos); (3) objetivo de
  treino com penalização de rotação (`vs_bench − custos`).
- **Super pré-época publicada** (as 3 lições): torneio de estabilidade — spreads
  de validação atravessam zero (split único = lotaria); amigável de 2 anos —
  benchmark +69,9k vs momentum +0 (**agentes flat-overnight doam o prémio de
  risco — o achado estrutural central**); stress de custos — a 4× o momentum
  sobrevive por +101 € após pagar 6,7k.
- **Diversificação declarada (época 1.5, por implementar)**: swing multi-dia +
  carteira de risco-alvo (SPY / vol inversa) — cobrem o eixo overnight; entram
  pelo mesmo gate. Máx. 4 traders mantido.
- Infra: custo zero auditado; risco nº1 = yfinance em IPs do Actions (1ª semana
  é o teste de fogo; plano B: conta Alpaca — pendente opcional do autor). PAT
  `cron-agent-arena-dispatch` expira ~2026-10-18 (checklist mestre).

## Jornadas

- [x] **J0 — Charter + repo** (2026-07-20)
- [x] **J1 — Maquete visual da arena** (2026-07-20): replay do dia sintético com
  algoritmos reais + custos, publicada como Artifact; aprovada pelo autor, com
  duas direções novas dele: jornadas/época e aprendizagem geracional (→ ADR-002)
- [x] **J2 — Motor + Ginásio** (2026-07-20): yfinance verificado (15m×60d,
  1h×730d), arquivo insert-only, no-lookahead por construção + testes,
  walk-forward Optuna, gerações g001 registadas (conta Alpaca: pendente, opcional)
- [x] **J3 — Arena live** (2026-07-20): ciclo idempotente, ledger de jornadas,
  site do ledger real, GO-LIVE (repo público + Pages + 1º ciclo remoto ✓);
  falta do autor: PAT + cron-job.org (página Ginásio: fica para a J4)
- [x] **J4 — Pré-registo commitado + ÉPOCA 1** (2026-07-20):
  `docs/pre-registration-season-1.md` commitado ANTES da 1ª jornada oficial —
  época de 60 jornadas a partir de 2026-07-21, lineup g001 congelado, promoções
  só à 2ª-feira com critério de validação, go/no-go com IC bootstrap (resultado
  esperado declarado: no-go), documento imutável (amendments só por apêndice).
  Rollover automático com reset de capital testado
- [ ] **J5 — Época 1.5**: implementar swing + risco-alvo no ginásio (entram pelo
  gate numa 2ª-feira, por emenda datada); relatório de meia época à jornada 30
  (`uv run python -m arena.metrics`)
- [ ] **J6 — Fim da época**: write-up honesto + decisão go/no-go (esperado: no-go)

## Convenções

Herdadas do portfólio (C:\dev\CLAUDE.md): `uv` sempre, commits convencionais EN
pequenos, identidade visual navy (#1e2a38 → #2a5a8c).
