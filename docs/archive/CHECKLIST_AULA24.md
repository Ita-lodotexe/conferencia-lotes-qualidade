# Checklist final da automação — Aula 24

Preenchido em 2026-08-19, sobre a branch `feature/indicadores-operacionais`.
Itens marcados com ⚠️ têm uma nota explicando o desvio — não foram deixados
sem justificativa.

## A. Branch e base de código

- [x] Branch `feature/indicadores-operacionais` criada a partir de `develop` atualizada.
  ⚠️ O repositório remoto não tem uma branch `develop` — só `main`. A branch foi
  criada a partir de `feature/dashboard-relatorio` (que descende de `main`), e é
  ancestral direto desta branch (confirmado via `git merge-base --is-ancestor`).
- [x] `pytest` da Aula 23 executado e 100% verde antes do início desta etapa.

## B. Motor de validação (Aulas 22–23, sem alterações de comportamento)

- [x] Regras RN01–RN12 inalteradas; nenhuma lógica de classificação foi tocada nesta etapa.
- [x] Deduplicação continua por dia (RN11), não pela planilha inteira — nada mudou aqui.

## C. Módulo de indicadores

- [x] `src/operational_indicators.py` existe como camada dedicada, com a dataclass
  `OperationalIndicators`. Não importa nada de Excel, Markdown ou pytest.
- [x] `_percentual()` protegida contra divisão por zero, usada em **todos** os
  cálculos percentuais do módulo (nenhum outro trecho calcula percentual "na mão").
- [x] Os 10 indicadores da Seção 4 calculados corretamente, incluindo regra mais
  acionada (`regra_mais_acionada`/`regra_mais_acionada_nome`) e ganho estimado
  (`ganho_estimado_minutos`, com premissas explícitas).

## D. Relatório Excel

- [x] 8 abas presentes com os nomes exatos: Resumo, Todos, Válidos, Divergências,
  Ambíguos, Erros de Entrada, Ranking de Regras, Dicionário — nenhuma mistura de
  classificações (testado).
- [x] Aba Resumo exibe os 10 indicadores (via `OperationalIndicators`, sem
  recontagem local), o gráfico de rosca e o gráfico de evolução, ambos nativos
  do Excel (`openpyxl.chart`).
- [x] Aba Ranking de Regras ordenada da mais para a menos acionada
  (`Counter.most_common()`, reaproveitado de `calcular_indicadores()` — não
  recalculado na aba).
- [x] Aba Dicionário lista o significado de cada código RN01–RN12
  (`REGRAS_DESCRICAO`).

## E. Resumo executivo e testes

- [x] `resumo_executivo.md` gerado a partir do mesmo objeto `OperationalIndicators`
  do Excel — teste de consistência
  (`test_excel_e_resumo_executivo_nascem_do_mesmo_objeto_de_indicadores`) confirma
  que total de registros e regra mais acionada são idênticos nos dois.
- [x] Testes novos escritos e marcados corretamente:
  - `tests/unit/test_operational_indicators.py` (`@pytest.mark.unit`) — cobre
    `_percentual()` e os 10 indicadores, com cenário parametrizado.
  - `tests/unit/test_resumo_executivo.py` (`@pytest.mark.unit`).
  - `tests/integration/test_relatorio_consolidado.py` (`@pytest.mark.integration`) —
    criação física do `.xlsx` em `tmp_path` + presença das 8 abas.
  - `tests/integration/test_webapp_aula22.py` (`@pytest.mark.integration`) —
    novos testes do endpoint `/resumo-executivo` e do teste de consistência.
- [x] Cobertura ≥ 80% comprovada — 99.19% total, incluindo `operational_indicators.py`
  (100%) e `resumo_executivo.py` (100%). Relatório anexado em
  `docs/evidencias/cobertura_aula24.txt` e `docs/evidencias/aula24/pytest_cobertura.log`.

## F. Documentação

- [x] README atualizado: visão geral dos indicadores, premissas do ganho estimado,
  limitações (estimativa didática, não medição real) e como executar
  (pipeline em script e via API).
- [x] `PDD.md` criado (não existia documento equivalente no repositório antes
  desta etapa) — cobre o fluxo completo: validação → indicadores → relatório →
  resumo executivo.
- [ ] `CHANGELOG.md` com uma entrada de versão desta etapa.
  ⚠️ Não criado nesta rodada — meu escopo autorizado para esta entrega não incluiu
  o CHANGELOG (revisar com o time se é necessário antes de qualquer PR).

## G. Segurança e Git

- [x] Nenhum `.venv`, `.env`, log ou diretório `output/`/`logs/` commitado
  (`git ls-files` conferido).
- [x] Nenhum caminho absoluto de máquina local commitado — o script de evidências
  (`docs/evidencias/aula24/gerar_evidencias.py`) resolve a raiz do projeto a
  partir do próprio `__file__`, não de um caminho fixo.

## H. Pull Request

- [ ] PR aberta contra `develop` reunindo processamento, indicadores, relatórios,
  testes e documentação.
  ⚠️ Não aberta nesta etapa, por decisão explícita: o repositório não tem
  `develop` (só `main`), e a decisão de qual branch de integração usar (ou de
  criar `develop`) é do time, não desta rodada de trabalho. Código, testes,
  evidências e documentação estão prontos para quando essa decisão for tomada.
- [ ] Descrição do PR / reviewers / checks de CI.
  ⚠️ Depende do item anterior.
