# conferencia-lotes-qualidade

Bot de conferência de lotes de qualidade — Convênio N.º 005/2025 (INOVA |
IFAM | LG Electronics do Brasil Ltda.), Polo Industrial de Manaus.

## O problema que este projeto resolve

Todos os dias, uma planilha de inspeção registra o resultado da
conferência de lotes de produção (aprovado, reprovado, pendente...).
Alguém precisa olhar essa planilha e decidir três coisas:

1. **O que está errado na própria planilha?** (campo vazio, data
   malformada — "Erro de Entrada")
2. **O que não bate com o cadastro da empresa?** (lote que não existe
   na base de referência, ou duplicado no mesmo dia — "Divergência")
3. **O que precisa de uma pessoa decidir?** (um status que o sistema
   não reconhece — "Ambíguo")

Fazer isso manualmente, todo dia, é lento e sujeito a erro. Este
projeto lê a planilha, aplica um conjunto de regras (RN01 a RN12) e
classifica **cada linha** em uma de quatro categorias — **Válido**,
**Divergência**, **Ambíguo** ou **Erro de Entrada** — produzindo um
relatório em `.xlsx` com um dashboard (indicadores, gráfico de rosca e
gráfico de evolução por dia) para quem só quer abrir o Excel e entender
a situação em 30 segundos, sem olhar código nenhum.

## Pré-requisitos e instalação

Você precisa de Python 3.11 ou superior.

```bash
git clone <url-do-repositorio>
cd conferencia-lotes-qualidade
python -m venv .venv
source .venv/bin/activate          # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Isso instala `pandas` e `openpyxl` (leitura/escrita de planilhas e
gráficos nativos do Excel), `fastapi`/`uvicorn`/`python-multipart`/`httpx`
(interface web, em construção), `pytest` (testes) e `dvc` (versionamento
de dados, opcional).

## Testes

A suíte de testes segue a pirâmide de testes da Aula 23, organizada em
camadas:

```
tests/
├── conftest.py              # fixtures compartilhadas (Base_Referencia mockada)
├── unit/                    # testes rápidos e isolados
│   ├── test_normalizacao_status.py
│   ├── test_observacao.py
│   ├── test_validacao.py
│   ├── test_validacao_lotes.py
│   ├── test_aula22_classificacao.py
│   ├── test_validacao_testcase.py        # unittest.TestCase com setUp/subTest
│   ├── test_classificacao_parametrize.py # parametrize com IDs descritivos
│   ├── test_operational_indicators.py    # os 10 indicadores operacionais (Aula 24)
│   └── test_resumo_executivo.py          # texto do resumo_executivo.md (Aula 24)
├── integration/             # colaboração entre módulos
│   ├── test_aula22_relatorio.py          # gera .xlsx em tmp_path
│   └── test_webapp_aula22.py             # API via TestClient
└── e2e/                     # fluxo completo (requer dataset real)
    └── test_contra_gabarito.py
```

A suíte inteira roda com dados **sintéticos** (inventados só para o
teste) — você não precisa de nenhum arquivo externo para ver os testes
passando. Os 3 testes em `tests/e2e/test_contra_gabarito.py` são
pulados automaticamente se o dataset real de avaliação não estiver
presente — veja ["O dataset real e o gabarito"](#o-dataset-real-e-o-gabarito)
abaixo.

### Rodar a suíte completa

```bash
python -m pytest tests/ -v
```

### Rodar por camada

```bash
python -m pytest tests/ -m unit -v           # só unitários
python -m pytest tests/ -m integration -v    # só integração
python -m pytest tests/ -m e2e -v            # só E2E (precisa do dataset real)
python -m pytest tests/ -m regression -v     # só proteção contra regressões
```

### Combinar markers

```bash
python -m pytest tests/ -m "unit or integration" -v   # tudo exceto E2E
python -m pytest tests/ -m "not e2e" -v               # equivalente ao acima
```

### Cobertura

```bash
python -m pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=80
```

O relatório de cobertura da última execução está em
[`docs/evidencias/cobertura_aula24.txt`](docs/evidencias/cobertura_aula24.txt)
— 99% de cobertura em `src/` (limiar exigido: 80%). O snapshot da Aula 23
fica preservado em
[`docs/evidencias/cobertura_aula23.txt`](docs/evidencias/cobertura_aula23.txt).

### Markers disponíveis

| Marker | Significado |
|--------|-------------|
| `unit` | Testes rápidos e isolados de funções individuais |
| `integration` | Testes de colaboração entre módulos (leitura + validação + relatório) |
| `e2e` | Fluxo completo das 10 abas ao relatório final |
| `regression` | Protege bugs já corrigidos contra reintrodução silenciosa |

### Convenções

- **Falhas conhecidas** são documentadas com `@pytest.mark.xfail(reason="...")`,
  nunca comentadas ou apagadas.
- **Funcionalidades futuras** sem implementação usam
  `@pytest.mark.skip(reason="...")`.
- Testes E2E (`test_contra_gabarito.py`) são pulados automaticamente se o
  dataset real não estiver em `dados_referencia/`.
- Testes que geram arquivos usam `tmp_path` — nada é escrito no repo.
- Dependências externas (Base_Referencia, datetime) são mockadas com
  `unittest.mock.patch`.

## Como rodar o pipeline com uma planilha de verdade

Hoje (antes da interface web ficar pronta — ver
["Interface web"](#interface-web-em-construção) no fim deste documento)
o jeito de processar uma planilha é chamar as três funções em sequência
num script Python. Crie um arquivo, por exemplo `executar.py`, na raiz
do projeto:

```python
from src.aula22_preprocessador import carregar_planilha_10dias
from src.aula22_classificacao import classificar_lotes
from src.operational_indicators import calcular_indicadores
from src.aula22_relatorio import gerar_relatorio_aula22
from src.resumo_executivo import gerar_resumo_executivo

# 1. Lê as 10 abas diárias + a aba Base_Referencia do arquivo de entrada
registros_por_dia, base_referencia = carregar_planilha_10dias(
    "dados_referencia/inspecao_lotes_10dias.xlsx"
)

# 2. Aplica as regras RN01-RN12 em cada registro, linha por linha
registros = classificar_lotes(registros_por_dia, base_referencia)

# 3. Calcula os 10 indicadores operacionais uma única vez — o mesmo
#    objeto alimenta o Excel e o resumo executivo, para os dois nunca
#    divergirem entre si.
indicadores = calcular_indicadores(registros)

# 4. Gera o relatório final: 8 abas + dashboard nativo do Excel
resultado = gerar_relatorio_aula22(
    registros, "relatorio_conferencia_lotes.xlsx", indicadores=indicadores
)

# 5. Gera o resumo executivo em Markdown, em linguagem de negócio
texto_resumo_executivo = gerar_resumo_executivo(indicadores)
with open("resumo_executivo.md", "w", encoding="utf-8") as arquivo:
    arquivo.write(texto_resumo_executivo)

print(resultado["resumo"])   # totais e percentuais por classificação
print(resultado["log"])      # log de execução (data/hora, totais, dias processados)
```

E execute:

```bash
python executar.py
```

Ao final, `relatorio_conferencia_lotes.xlsx` e `resumo_executivo.md`
estarão na raiz do projeto, prontos para abrir no Excel/editor de texto.

## Estrutura do projeto

```
src/
  modules/                    # regras de base (RN01-RN07), reaproveitadas pela Aula 22
    validacao.py              # RN01 (estrutura) e RN02 (campos obrigatórios)
    verificacao_lotes.py      # RN03 (existência/status do lote na base de referência)
    normalizacao_status.py    # RN04/RN05 (status permitido e normalização OK/NOK)
    observacao.py             # RN07 (observação obrigatória em lote reprovado)
  aula22_preprocessador.py    # lê a planilha de 10 dias e organiza os registros por dia
  aula22_classificacao.py     # motor de classificação: aplica RN01-RN12 e decide a categoria
  operational_indicators.py   # calcula os 10 indicadores operacionais (Aula 24) a partir dos registros
  aula22_relatorio.py         # gera o .xlsx de 8 abas + dashboard nativo, a partir dos indicadores
  resumo_executivo.py         # formata os mesmos indicadores como resumo_executivo.md

tests/                        # unit/, integration/, e2e/ + conftest.py — ver seção "Testes"

webapp/                       # interface web (FastAPI + frontend), ver seção "Interface web"

data/processed/               # base de referência em CSV, usada por alguns testes
dados_referencia/              # (crie esta pasta) coloque aqui o dataset real de 10 dias
docs/evidencias/               # evidências versionadas (ex.: relatório de cobertura)
```

### Por que `src/modules/` e `src/aula22_*.py` são coisas separadas

`src/modules/` já existia antes desta atividade e implementa as regras
que **não mudam** de uma planilha de 1 dia para uma de 10 dias:
existência do lote na base de referência, normalização de status
(`OK`→`APROVADO`, `NOK`→`REPROVADO`) e observação obrigatória em
reprovado. Os módulos `aula22_*.py` **reaproveitam essas funções sem
alterá-las** e só implementam o que é novo desta atividade: a dataclass
`RegistroValidado`, a deduplicação por dia (RN11) e a validação de
formato de data (RN12). Isso evita duplicar lógica e mantém as duas
frentes de trabalho isoladas uma da outra.

## As regras de negócio — RN01 a RN12

Cada linha da planilha passa pelas regras **nesta ordem exata**. A
primeira regra que "pegar" decide a classificação final da linha — por
isso a ordem importa (ex.: um lote com campo vazio *e* status ambíguo
é classificado pelo campo vazio, não pelo status).

| # | Regra | Verifica | Se falhar, classificação |
|---|-------|----------|---------------------------|
| 1 | **RN01–RN04** | `lote_id`, `produto`, `linha`, `status` ou `responsavel` vazio | **Erro de Entrada** |
| 2 | **RN12** | `data` ausente ou fora do formato `DD/MM/AAAA` | **Erro de Entrada** |
| 3 | **RN11** | `lote_id` repetido no mesmo dia (a partir da 2ª vez) | **Divergência** |
| 4 | **RN05** | `lote_id` não existe (ou está inativo) na `Base_Referencia` | **Divergência** |
| 5 | **RN06/RN07** | normaliza o status (`OK`→`APROVADO`, `NOK`→`REPROVADO`) — não gera divergência, só prepara o valor pra próxima regra | — |
| 6 | **RN09** | status, já normalizado, não é `APROVADO`/`REPROVADO`/`PENDENTE` (ex.: `"EM AJUSTE"`) | **Ambíguo** |
| 7 | **RN10** | status normalizado é `REPROVADO` e a `observacao` está vazia | **Divergência** |
| 8 | (nenhuma das anteriores) | — | **Válido** (RN08) |

Dois detalhes importantes, confirmados no código e nos testes
(`tests/test_aula22_classificacao.py`):

- **RN11 é por dia, nunca entre dias diferentes.** O mesmo `lote_id`
  aparecendo em duas abas diárias diferentes não é duplicidade — é
  esperado que o mesmo lote passe por inspeções em dias distintos.
- **`lote_id` vazio nunca conta como duplicidade.** Se a linha já não
  tem `lote_id`, ela já cai em Erro de Entrada (regra 1) antes de a
  RN11 ser avaliada.

### Onde cada regra está implementada

```python
from src.aula22_classificacao import classificar_registro

# campos obrigatórios que a Aula 22 exige (5, não os 7 do fluxo antigo):
from src.aula22_classificacao import CAMPOS_OBRIGATORIOS_LOTE
print(CAMPOS_OBRIGATORIOS_LOTE)
# ['lote_id', 'produto', 'linha', 'status', 'responsavel']
```

- RN01–RN04 (campos obrigatórios): `validar_campos_obrigatorios_lote()`
  em `src/aula22_classificacao.py`.
- RN05 (existência/status na base): `verificar_existencia_lote()` e
  `verificar_status_lote()`, reaproveitadas de
  `src/modules/verificacao_lotes.py`.
- RN06/RN07 (normalização) e RN09 (ambíguo): `validar_status()`,
  reaproveitada de `src/modules/normalizacao_status.py`.
- RN10 (observação em reprovado): `lote_conforme_rn07()`, reaproveitada
  de `src/modules/observacao.py` — sim, o nome da função ainda diz
  "rn07" porque é a mesma lógica da regra RN07 do fluxo antigo, só que
  na Aula 22 essa regra passou a se chamar RN10.
- RN11 (duplicidade por dia): `_contar_ocorrencias_por_dia()`, nova.
- RN12 (formato de data): `validar_data_referencia()`, nova.
- A orquestração de tudo isso, na ordem certa, é a função
  `classificar_registro()` — é ela que você chamaria se quisesse
  classificar uma única linha manualmente, mas o uso normal é via
  `classificar_lotes()`, que já processa todos os dias de uma vez.

## Os indicadores operacionais (Aula 24)

`calcular_indicadores()` (em `src/operational_indicators.py`) consolida
a lista de registros classificados nos dez indicadores de negócio do
dashboard executivo — total, válidos, divergências, ambíguos, erros de
entrada (quantidade e %), a regra mais acionada, taxa de qualidade da
entrada, taxa de revisão humana, taxa de retrabalho e o ganho estimado
de tempo (uma **estimativa didática**, não uma medição real de
produção — as premissas de tempo manual/automatizado usadas ficam
explícitas no próprio objeto retornado).

Esse objeto (`OperationalIndicators`) é calculado **uma única vez** e
repassado tanto para `gerar_relatorio_aula22()` quanto para
`gerar_resumo_executivo()` — garantindo que o Excel e o
`resumo_executivo.md` nunca divirjam entre si por terem sido calculados
separadamente.

## O relatório gerado

`gerar_relatorio_aula22()` (em `src/aula22_relatorio.py`) produz um
`.xlsx` com exatamente 8 abas, nesta ordem:

1. **Resumo** — a única aba que quem for usar o relatório no dia a dia
   realmente precisa olhar. Tem os indicadores numéricos (total e % de
   cada categoria), um **gráfico de rosca** com a distribuição
   percentual e um **gráfico de linha** com a evolução de
   Divergência+Ambíguo por dia (mais o total do dia, como referência).
   Ambos os gráficos são objetos **nativos do Excel**
   (`openpyxl.chart.DoughnutChart`/`LineChart`), não imagens coladas —
   dá pra clicar e editar dentro do próprio Excel.
2. **Todos** — todos os registros processados, sem filtro.
3. **Válidos**, **Divergências**, **Ambíguos**, **Erros de Entrada** —
   uma aba por categoria, cada uma contendo **só** a sua classificação
   (isso é verificado por teste: nenhuma aba pode misturar categorias
   diferentes).
4. **Ranking de Regras** — as regras de divergência/ambiguidade/erro que
   apareceram no período, da mais para a menos frequente (RN08/Válido
   não entra aqui — ela não representa um problema).
5. **Dicionário** — o significado de cada código de regra (RN01–RN12),
   para quem lê o relatório sem o enunciado das RNs em mãos.

## O resumo executivo (`resumo_executivo.md`)

`gerar_resumo_executivo()` (em `src/resumo_executivo.py`) recebe o mesmo
`OperationalIndicators` do Excel e devolve um texto em Markdown, em
linguagem de negócio (sem nomes de função, classe, coluna ou código de
regra "solto"), com cinco seções: **Visão Geral**, **Indicadores
Principais**, **Destaque** (a regra mais acionada, pelo nome legível —
ou uma nota explícita de que nenhum problema ocorreu no período),
**Ganho Estimado de Tempo** (com as premissas usadas) e **Observação**
(deixando claro que o ganho é uma estimativa didática). A função só
devolve a string — quem chama decide se grava em disco, devolve pela
API, ou os dois.

## O dataset real e o gabarito

O arquivo `inspecao_lotes_10dias.xlsx` (10 abas diárias
`Insp_DD_MM_AAAA` + uma aba `Base_Referencia`) é o dado de avaliação
desta atividade e **não é distribuído neste repositório**. Se você tiver
esse arquivo (com a aba extra `Gabarito_Instrutor` do instrutor), coloque-o em:

```
dados_referencia/inspecao_lotes_10dias.xlsx
```

Com o arquivo nesse caminho, `python -m pytest tests/ -v` deixa de pular
os 3 testes de `tests/e2e/test_contra_gabarito.py` e passa a validar de
ponta a ponta: 250 registros totais, 100 divergências propositais, e a
distribuição exata por dia (5 Divergência + 2 Ambíguo + 3 Erro de
Entrada, todos os dias). Sem o arquivo, esses 3 testes continuam
aparecendo como `SKIPPED` — isso é esperado, não é falha.

## Interface web

`webapp/main.py` expõe a API (FastAPI) e serve o frontend
(`webapp/static/`) — upload, preview do resumo com gráfico de rosca e
evolução por dia, e botão de download do `.xlsx`.

Para subir o servidor:

```bash
python -m uvicorn webapp.main:app --reload
```

Com o servidor no ar, abra `http://127.0.0.1:8000/docs` para testar os
endpoints direto no navegador (Swagger UI gerado automaticamente pelo
FastAPI), ou use `curl`:

```bash
# 1. Envia a planilha, recebe o resumo (e o id do relatório gerado)
curl -F "arquivo=@dados_referencia/inspecao_lotes_10dias.xlsx" \
     http://127.0.0.1:8000/api/aula22/dashboard

# 2. Baixa o .xlsx com o dashboard (troque <id> pelo valor devolvido acima)
curl -o relatorio_conferencia_lotes.xlsx \
     http://127.0.0.1:8000/api/aula22/dashboard/<id>/download

# 3. (opcional) consulta o log de execução em texto puro
curl http://127.0.0.1:8000/api/aula22/dashboard/<id>/log

# 4. (opcional) consulta o resumo executivo em Markdown
curl http://127.0.0.1:8000/api/aula22/dashboard/<id>/resumo-executivo
```

| Método | Rota | Faz o quê |
|--------|------|-----------|
| `POST` | `/api/aula22/dashboard` | Recebe o upload (`.xlsx`/`.xls`), classifica e já gera o relatório. Devolve `id`, `total`, `por_classificacao`, `percentual` e `evolucao_por_dia`. |
| `GET` | `/api/aula22/dashboard/{id}/download` | Devolve o `.xlsx` de 8 abas + dashboard, pelo `id` retornado no passo anterior. |
| `GET` | `/api/aula22/dashboard/{id}/log` | Devolve o log de execução (texto puro): data/hora, totais por classificação, dias processados. |
| `GET` | `/api/aula22/dashboard/{id}/resumo-executivo` | Devolve o `resumo_executivo.md` (texto puro, Markdown), calculado a partir do mesmo `OperationalIndicators` do Excel. |

O arquivo gerado fica num diretório temporário do sistema, associado ao
`id` num dicionário em memória — válido enquanto o processo do servidor
estiver de pé. Suficiente para uso local; não é pensado para produção
com múltiplas instâncias.

O frontend em `webapp/static/` (HTML/CSS/JS puro, sem framework, sem
build step) chama esses três endpoints pelo navegador — abra
`http://127.0.0.1:8000/` com o servidor no ar. Visual inspirado na
identidade da LG (vermelho `#A50034`), com blobs suaves e cantos bem
arredondados.

Testes em [tests/integration/test_webapp_aula22.py](tests/integration/test_webapp_aula22.py).
