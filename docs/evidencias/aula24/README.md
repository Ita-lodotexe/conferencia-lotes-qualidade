# Pacote de evidências — Aula 24 (Seção 5.7)

Artefatos da rodada final da camada de indicadores operacionais.

- `relatorio_conferencia_lotes.xlsx` — Excel de 8 abas, gerado a partir de um
  dataset **sintético** de 10 dias (o dataset real de avaliação,
  `inspecao_lotes_10dias.xlsx`, não é distribuído neste repositório — ver
  ["O dataset real e o gabarito"](../../../README.md#o-dataset-real-e-o-gabarito)).
- `resumo_executivo.md` — resumo executivo gerado a partir do **mesmo**
  objeto `OperationalIndicators` usado no Excel acima.
- `execucao.json` — os mesmos indicadores em JSON, para conferência
  programática de que o Excel e o resumo executivo contam a mesma história
  (total, regra mais acionada, ganho estimado). O pipeline das Aulas 22/23
  não gerava JSON de execução — este arquivo é novo, introduzido nesta etapa
  só como evidência, não como uma saída do pipeline em produção.
- `pytest_v.log` — saída completa de `pytest tests/ -v --tb=short` da rodada
  final (151 passed, 4 skipped, 1 xfailed).
- `pytest_cobertura.log` — saída completa de
  `pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=80`
  da mesma rodada (99.19% de cobertura).

Para reproduzir: veja
[`docs/evidencias/aula24/gerar_evidencias.py`](gerar_evidencias.py) — usa um
dataset sintético de 10 dias (não o dataset real da avaliação) só para
exercitar o pipeline de ponta a ponta e produzir estes artefatos.
