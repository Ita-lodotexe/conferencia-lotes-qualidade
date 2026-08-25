# Checklist final — Exercício 24-A (ML + RPA)

Preenchido em 2026-08-19, sobre a branch `feature/ml-classificador`.
Cada item tem uma evidência concreta (teste ou commit), não só um "☑" —
e os itens não automatizáveis por código (Seção 8.5) ficam
explicitamente pendentes, não marcados por engano.

## 8.1 Modelo e dataset

- [x] Dataset sintético com ≥ 200 amostras, 3 features e 3 classes.
  **Evidência**: `train_model.py` (Commit 1) gera 300 amostras
  (`N_AMOSTRAS = 300`), features `status_raw`/`turno`/`tem_obs`, classes
  `valido_automatico`/`revisar`/`recusar_automatico`.
- [x] Modelo serializado via joblib.
  **Evidência**: `models/classificador_lotes.pkl`, gerado por
  `RandomForestClassifier` + `joblib.dump()` (Commit 1). Não versionado
  em git (`.gitignore: models/*.pkl`) — é binário e 100% regenerável com
  `python train_model.py`; só `models/.gitkeep` é versionado.
- [x] Accuracy razoável (>70%), com premissas documentadas.
  **Evidência**: 73,33% medido no split de teste 80/20 (`seed=42`),
  documentado em `train_model.py` e no README (seção "Exercício 24-A"),
  junto com o cálculo do teto teórico (~74%) que justifica o número.

## 8.2 API

- [x] `/predict` valida com Pydantic e rejeita turno inválido com 422.
  **Evidência**: `LoteInput.turno_deve_ser_valido` (Commit 2) +
  `tests/integration/test_api_ml.py::test_predict_com_turno_invalido_retorna_422`.
- [x] `/health` reflete o estado real do carregamento do modelo,
  inclusive quando o `.pkl` está ausente/corrompido.
  **Evidência**: `lifespan()` em `api_ml/main.py` (Commit 2) +
  `tests/integration/test_api_ml.py::test_health_com_modelo_ausente_nao_derruba_o_processo`
  e `test_predict_com_modelo_ausente_retorna_503_em_vez_de_500` (Commit 6)
  — o cenário que o Formulário de Revisão por Pares pede para testar
  manualmente ("renomear o .pkl"), aqui automatizado.
- [x] `api_ml/` container próprio, com `docker-compose.yml` e
  healthcheck.
  **Evidência**: `docker-compose.yml` + `api_ml/Dockerfile` (Commit 3).
  Testado de verdade nesta máquina: `docker compose up -d --build` →
  `docker compose ps` mostrou `Up ... (healthy)`; `/predict` e `/health`
  responderam pela porta mapeada (8001); `docker compose down` limpo.

## 8.3 Integração e resiliência

- [x] `MLClient` nunca lança exceção (timeout, erro de conexão, 4xx/5xx).
  **Evidência**: `src/ml_client.py::classificar` (Commit 4) +
  `tests/unit/test_ml_client.py::TestClassificarFalha` (3 testes: erro
  de conexão, timeout, status 5xx — todos retornam `None`, nenhum lança).
- [x] Circuit breaker abre após 5 falhas consecutivas e bloqueia a 6ª
  chamada (não bate na rede de novo).
  **Evidência**: `tests/unit/test_ml_client.py::TestCircuitBreaker::
  test_circuito_abre_apos_falhas_consecutivas_e_bloqueia_a_sexta_chamada`
  — prova explícita via `mock_post.call_count` (5 chamadas reais, 6ª
  bloqueada antes de chegar em `httpx.post`). Reset manual
  (`resetar_circuito()`) e reset por sucesso intercalado também testados.
- [x] `item_processor.py` aplica o fallback `REVISAO_ML_OFFLINE` quando a
  API não responde, sem interromper o processamento do lote.
  **Evidência**: `src/item_processor.py::processar_item_ambiguo` (Commit 4)
  + `tests/unit/test_item_processor.py::test_ml_client_retorna_none_cai_no_fallback_revisao_ml_offline`,
  e a prova ponta a ponta via API HTTP real (webapp completo) em
  `tests/integration/test_resiliencia_api_ml_offline.py` (Commit 6):
  `POST /api/aula22/dashboard` continua **200** com a API de ML
  totalmente fora do ar.

## 8.4 Auditoria e testes

- [x] Log estruturado com os 5 campos (`lote_id`, `classe_ml`,
  `probabilidade_ml`, `decisao_ml`, `latencia_ms`).
  **Evidência**: `src/logging_estruturado.py::FormatterJSON` +
  instrumentação em `src/item_processor.py::_resultado` (Commit 5);
  linha real de exemplo no README, seção "Exercício 24-A".
- [x] Aba "Decisões de ML" sem perda de registro (paridade com
  "Ambíguos").
  **Evidência**: `tests/integration/test_relatorio_decisoes_ml.py`
  (Commit 5, chamando a função direto) e
  `tests/integration/test_resiliencia_api_ml_offline.py` (Commit 6, via
  API HTTP real) — as duas abas com o mesmo número de linhas nos dois
  caminhos.
- [x] Mínimo de 5 testes novos para a camada de ML, todos passando.
  **Evidência**: muito além do mínimo — **31 testes novos** no total
  (182 no fim do Exercício 24-A menos 151 antes do Commit 1), cobrindo
  `train_model.py` (indiretamente, via accuracy medida), `api_ml/main.py`
  (100% de cobertura), `src/ml_client.py`, `src/item_processor.py`,
  `src/logging_estruturado.py`, a 9ª aba do Excel e a resiliência ponta
  a ponta. `pytest --cov=src --cov=api_ml`: 99,39% de cobertura total.

## 8.5 Torneio e entrega

- [ ] Grupo ensaiou a API de ML sendo derrubada durante uma apresentação
  (ex.: parar o container ao vivo e mostrar o dashboard continuando).
  **Pendente** — ação humana de ensaio para o Torneio, fora do escopo de
  um commit de código. O teste automatizado equivalente
  (`test_resiliencia_api_ml_offline.py`) já prova que o comportamento
  técnico é correto; falta o ensaio da apresentação em si.
- [ ] Repositório configurado como privado, com instrutor/mentor
  adicionados como colaboradores.
  **Pendente** — ação de configuração do repositório no GitHub, fora do
  escopo de um commit de código; depende de quem administra o
  repositório remoto.
