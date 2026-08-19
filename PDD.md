# PDD — Process Design Document

## Conferência de Lotes de Qualidade

Convênio N.º 005/2025 (INOVA | IFAM | LG Electronics do Brasil Ltda.),
Polo Industrial de Manaus.

> Este documento não existia no repositório antes da Aula 24. Foi criado
> nesta etapa para descrever o processo automatizado como ele está hoje —
> motor de validação (Aula 22), suíte de testes (Aula 23) e camada de
> indicadores/resumo executivo (Aula 24). Se a equipe já mantém um PDD em
> outro lugar (Notion, Google Docs, etc.), este arquivo deve ser tratado
> como um espelho técnico, não como a fonte oficial.

## 1. Objetivo do processo

Substituir a conferência manual, diária, de lotes de produção por um
pipeline automatizado que lê a planilha de inspeção, classifica cada
registro em uma de quatro categorias de negócio, e produz duas saídas —
um relatório Excel operacional e um resumo executivo em linguagem de
gestão — a partir da mesma fonte de verdade.

## 2. Entrada do processo

| Item | Descrição |
|---|---|
| Arquivo | `inspecao_lotes_10dias.xlsx` |
| Estrutura | 10 abas diárias (`Insp_DD_MM_AAAA`) + 1 aba `Base_Referencia` |
| Campos por lote | `lote_id`, `produto`, `linha`, `turno`, `status`, `responsavel`, `data`, `observacao` |
| Volume de referência | 250 registros, 100 divergências propositais (dataset de avaliação, não distribuído no repositório) |

## 3. Visão geral do pipeline

```
inspecao_lotes_10dias.xlsx
        │
        ▼
carregar_planilha_10dias()          [src/aula22_preprocessador.py]
  lê as 10 abas diárias + Base_Referencia
        │
        ▼
classificar_lotes()                  [src/aula22_classificacao.py]
  aplica RN01–RN12 linha a linha, na ordem definida na Seção 4
  → lista de RegistroValidado
        │
        ▼
calcular_indicadores()                [src/operational_indicators.py]
  consolida a lista em UM objeto OperationalIndicators (os 10 indicadores)
  → calculado UMA ÚNICA VEZ por execução
        │
        ├──────────────────────────┐
        ▼                          ▼
gerar_relatorio_aula22()     gerar_resumo_executivo()
[aula22_relatorio.py]        [resumo_executivo.py]
  .xlsx de 8 abas               .md em linguagem de negócio
        │                          │
        ▼                          ▼
relatorio_conferencia_lotes.xlsx   resumo_executivo.md
```

O ponto crítico do desenho: **os dois arquivos de saída nascem do mesmo
objeto `OperationalIndicators`**, calculado uma única vez. Nenhuma das
duas funções de saída recalcula contagens ou percentuais — ambas só
formatam o que já veio pronto. Isso existe para eliminar a classe de bug
"duas fontes de verdade": se o Excel e o resumo executivo calculassem os
números cada um por conta própria, uma mudança de regra de negócio
poderia atualizar um e não o outro, e os dois arquivos divergiriam
silenciosamente.

## 4. Regras de negócio (RN01–RN12)

Aplicadas nesta ordem exata — a primeira regra que "pegar" decide a
classificação final da linha:

| Ordem | Regra | Verifica | Classificação se falhar |
|---|---|---|---|
| 1 | RN01–RN04 | Campo obrigatório vazio (`lote_id`, `produto`, `linha`, `status`, `responsavel`) | Erro de Entrada |
| 2 | RN12 | Data ausente ou fora do formato `DD/MM/AAAA` | Erro de Entrada |
| 3 | RN11 | `lote_id` repetido no mesmo dia (2ª ocorrência em diante) | Divergência |
| 4 | RN05 | `lote_id` não existe ou está inativo na `Base_Referencia` | Divergência |
| 5 | RN06/RN07 | Normalização de status (`OK`→`APROVADO`, `NOK`→`REPROVADO`) | — (prepara o valor, não classifica) |
| 6 | RN09 | Status normalizado não é `APROVADO`/`REPROVADO`/`PENDENTE` | Ambíguo |
| 7 | RN10 | Status `REPROVADO` sem `observacao` preenchida | Divergência |
| 8 | (nenhuma das anteriores) | — | Válido (RN08) |

Detalhes de implementação e reaproveitamento de módulos anteriores estão
documentados no [README](README.md#as-regras-de-negócio--rn01-a-rn12).

## 5. Camada de indicadores (`OperationalIndicators`)

Dataclass com os dez indicadores de negócio (Seção 4 do enunciado da
Aula 24), calculada por `calcular_indicadores()`:

1. Total de registros
2–5. Válidos, Divergências, Ambíguos, Erros de Entrada — quantidade e %
6. Regra mais acionada (código + nome legível + quantidade)
7. Taxa de qualidade da entrada — `(total − erros_de_entrada) / total × 100`
8. Taxa de revisão humana — `ambíguos / total × 100`
9. Taxa de retrabalho — `divergências / total × 100`
10. Ganho estimado de tempo — `total × (tempo_manual − tempo_automatizado)`,
    com as premissas (`tempo_manual_min_por_registro`,
    `tempo_automatizado_min_por_registro`) explícitas no próprio objeto

Toda proporção passa por uma única função, `_percentual(parte, total)`,
que retorna 0 (em vez de lançar `ZeroDivisionError`) quando `total == 0`
— condição coberta em teste, junto com um cenário parametrizado cobrindo
os 10 indicadores.

O indicador 6 (regra mais acionada) exclui deliberadamente RN08 (Válido)
do ranking: ela representa "nenhum problema", não uma regra de negócio
violada — se fosse contada, dominaria o indicador sempre que a maioria
dos registros estivesse correta, que é o caso normal, mascarando o
gargalo real.

## 6. Saídas do processo

### 6.1 Relatório Excel (`relatorio_conferencia_lotes.xlsx`) — 8 abas

| # | Aba | Conteúdo |
|---|---|---|
| 1 | Resumo | Os 10 indicadores, gráfico de rosca (distribuição por classificação) e gráfico de linha (evolução por dia) — ambos nativos do Excel (`openpyxl.chart`) |
| 2 | Todos | Todos os registros processados, sem filtro |
| 3–6 | Válidos / Divergências / Ambíguos / Erros de Entrada | Uma aba por categoria, sem mistura de classificações |
| 7 | Ranking de Regras | Regras de divergência/ambiguidade/erro, da mais para a menos acionada (mesma contagem do indicador 6 — não recalculada) |
| 8 | Dicionário | Significado de cada código RN01–RN12, em linguagem acessível |

### 6.2 Resumo executivo (`resumo_executivo.md`)

Markdown em linguagem de negócio, sem jargão técnico nem código de regra
"solto" (sempre acompanhado do nome legível), com cinco seções fixas:
Visão Geral, Indicadores Principais, Destaque, Ganho Estimado de Tempo e
Observação (deixando explícito que o ganho é uma estimativa didática,
não uma medição real de produção).

## 7. Integração e orquestração

`webapp/main.py` (FastAPI) é o ponto único de orquestração em produção —
não existe um `main.py` na raiz do projeto (desvio mapeado desde a Aula
22/23: o pipeline roda como serviço web, não como script solto).

No endpoint `POST /api/aula22/dashboard`, a função `criar_dashboard()`:

1. Classifica o upload (`_classificar_upload` → `classificar_lotes`).
2. Chama `calcular_indicadores(registros)` **uma única vez**.
3. Passa o mesmo objeto para `gerar_relatorio_aula22(..., indicadores=indicadores)`
   e para `gerar_resumo_executivo(indicadores)`.
4. Grava os dois arquivos de saída em disco (diretório temporário do
   sistema) e guarda os caminhos associados ao `dashboard_id`.

Endpoints de leitura expõem os artefatos gerados:

| Método | Rota | Retorno |
|---|---|---|
| `GET` | `/api/aula22/dashboard/{id}/download` | `.xlsx` de 8 abas |
| `GET` | `/api/aula22/dashboard/{id}/log` | Log de execução (texto puro) |
| `GET` | `/api/aula22/dashboard/{id}/resumo-executivo` | `resumo_executivo.md` (texto puro) |

## 8. Testes e qualidade

Suíte organizada em camadas (`tests/unit`, `tests/integration`,
`tests/e2e`), com markers `unit`/`integration`/`regression`/`e2e`
(`pytest.ini` via `pyproject.toml`). Cobertura mínima exigida: 80%;
cobertura atual: 99% (ver `docs/evidencias/cobertura_aula24.txt`).

Testes específicos da camada de indicadores:

- `tests/unit/test_operational_indicators.py` — `_percentual()` e os 10
  indicadores, incluindo cenário parametrizado.
- `tests/unit/test_resumo_executivo.py` — as 5 seções obrigatórias,
  ausência de código de regra solto, sensibilidade aos números de
  entrada, e o caso `regra_mais_acionada is None`.
- `tests/integration/test_relatorio_consolidado.py` — criação física do
  `.xlsx` em `tmp_path` e presença das 8 abas.
- `tests/integration/test_webapp_aula22.py` — inclui o teste de
  consistência entre o Excel e o resumo executivo (mesmo total, mesma
  regra mais acionada).

## 9. Limitações conhecidas

- O **ganho estimado de tempo** (indicador 10) é uma estimativa
  didática, não uma medição real de produção. Para virar uma métrica de
  produção seria necessário medir o tempo manual e automatizado
  observados de fato (ex.: cronometragem amostral ou telemetria do
  próprio pipeline), em vez de premissas fixas configuráveis por
  parâmetro.
- O armazenamento dos relatórios gerados por `webapp/main.py` é em
  memória de processo + diretório temporário do sistema — válido
  enquanto o processo do servidor estiver de pé; não pensado para
  produção com múltiplas instâncias.
- O dataset real de avaliação (`inspecao_lotes_10dias.xlsx`) não é
  distribuído neste repositório; as evidências em
  `docs/evidencias/aula24/` foram geradas com um dataset sintético.
