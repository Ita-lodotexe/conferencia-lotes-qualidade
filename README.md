# conferencia-lotes-qualidade

## Preparando o dado real (issue #26)

A planilha oficial do exercício fica em
`dados_referencia/inspecao_lotes_dia.xlsx`. Ela tem formato humano (3 abas,
títulos, rodapé, legenda de cores, nota do revisor) e por isso não é
consumida diretamente pelo bot: um preprocessor traduz o formato humano
para os CSVs que o restante do fluxo já sabe ler.

```bash
python -m scripts.planilha_para_csv
```

Isso gera dois arquivos:

| Saída | Origem | Conteúdo | Consumido por |
|---|---|---|---|
| `dados_entrada/lotes_auditoria.csv` | aba `Inspecao_14_06_2026` | 25 lotes | Dispatcher (fila) e Performer (dry-run) |
| `data/processed/base_lotes_referencia.csv` | aba `Base_Referencia` | 23 lotes cadastrados | Performer (RN03) |

O preprocessor corta as linhas de lixo (rodapé `Total de registros`,
legenda de cores, nota do revisor) por limite de posição, e normaliza
células vazias do Excel para string vazia — evitando que `NaN` do pandas
chegue ao DataPool do Maestro, onde não é JSON válido.

**Fluxo operacional completo:**

```bash
python -m scripts.planilha_para_csv   # 1. planilha oficial -> CSVs
python -m scripts.dispatcher          # 2. CSV -> fila no Maestro
python -m src.bot.performer           # 3. fila -> validação RN01-RN07
```

> ⚠️ **Divergência conhecida entre a planilha e o resultado do bot.** A
> planilha marca visualmente 8 lotes como divergentes entre os 25; o bot
> detecta 7. A diferença é a linha 18 (`LG-2026-00115`), cuja coluna
> `data` traz `15-06-2026` em vez de `14/06/2026` — separador e dia
> diferentes do resto. Validar *formato* e *coerência* de data não é
> nenhuma das regras RN01–RN07 do PDD: a `data` só é verificada quanto a
> estar preenchida (RN02), e `15-06-2026` está preenchida. Portanto o bot
> classificar esse lote como conforme é o resultado **correto dado o
> escopo do PDD** — não um bug. Cobrir esse caso exigiria uma regra nova,
> fora do escopo desta issue.

## Camada BotCity (v0.2.1)

Fundação de execução do bot como robô BotCity: configuração via `.env`,
logging em arquivo e validação fail-fast de pré-requisitos, em `src/bot/`.

> **v0.2.1:** o bot passou a operar sobre o dado real do exercício (a
> planilha oficial da LG), via o preprocessor descrito na seção acima. Até
> a v0.2.0 o fluxo rodava sobre um CSV fictício escrito à mão.

**Configuração:**

```bash
cp .env.example .env
# preencha BOTCITY_WORKSPACE, BOTCITY_SERVER, BOTCITY_LOGIN e BOTCITY_KEY
# com os valores do painel do BotCity Maestro
# (https://developers.botcity.dev/app/ → Ambiente do desenvolvedor)
```

**Rodando o bot localmente:**

```bash
python -m src.bot.main
```

Os logs de execução são gravados em `logs/execucao.log` (e também exibidos
no terminal).

> **Nota:** esta versão entrega a fundação (config, logs, validação
> fail-fast da pasta de entrada), o cofre de credenciais e o Dispatcher
> da fila (seções abaixo).

## Cofre de credenciais

`src/bot/vault_client.py` expõe `obter_credencial_erp() -> (usuario, senha)`,
usada para autenticar no ERP sem nenhuma senha hardcoded no código.

A flag `VAULT_ENABLED` (no `.env`) alterna o comportamento:

- **`VAULT_ENABLED=false`** (padrão, modo local/desenvolvimento): retorna
  uma credencial fictícia (`"bot_local"` / `"senha_dev"`) sem tocar no SDK
  do BotCity — não precisa nem de rede nem de credenciais reais para
  desenvolver.
- **`VAULT_ENABLED=true`**: faz login no BotCity Maestro
  (`BOTCITY_SERVER` + `BOTCITY_LOGIN` + `BOTCITY_KEY`, configurados no
  `.env`, nunca commitados) e busca a credencial real
  `credencial_erp_eqp04` (chaves `usuario`/`senha`) no Credentials Vault
  do workspace.

**A senha nunca é logada em nenhum modo**, incluindo o caminho de erro: se
o Vault ou o SDK falharem, o `vault_client` loga só o *tipo* da exceção
(nunca `str(exception)`, que poderia ecoar conteúdo sensível do servidor)
e relança uma `VaultError` genérica — quem chama a função nunca vê a
exceção original do SDK, só uma mensagem apontando para checar
`BOTCITY_SERVER`/`BOTCITY_LOGIN`/`BOTCITY_KEY`.

## Dispatcher (Issue #19)

`scripts/dispatcher.py` lê `dados_entrada/lotes_auditoria.csv` e envia cada
linha como um item (`DataPoolEntry`) para o DataPool
`FilaAuditoriaLotes-Eqp04` no BotCity Maestro, usando o `BotMaestroSDK`.

**Como rodar:**

```bash
python -m scripts.dispatcher
```

**Requisitos:** `.env` com `MAESTRO_ENABLED=true` e credenciais válidas
(`BOTCITY_SERVER`, `BOTCITY_LOGIN`, `BOTCITY_KEY`). Com
`MAESTRO_ENABLED=false` (padrão), o Dispatcher roda em modo dry-run: lê o
CSV, loga cada item que seria enviado, mas não contata o Maestro.

O CSV de entrada fica em `dados_entrada/lotes_auditoria.csv` e é **gerado
pelo preprocessor** a partir da planilha oficial — veja
[Preparando o dado real](#preparando-o-dado-real-issue-26). Ele traz os 25
lotes do exercício, incluindo os erros propositais (lote_id vazio,
`responsavel` vazio, status ambíguo, reprovado sem observação, lote fora da
base de referência).

> ⚠️ **O envio não é idempotente**: rodar o Dispatcher duas vezes acumula
> itens duplicados na fila — o script não verifica se um lote já foi
> enviado antes. O log de início de execução avisa sobre isso.
> Falha ao enviar um item individual não aborta o restante do lote (o
> Dispatcher segue para o próximo e reporta o total de falhas no fim).

Logs de execução em `logs/execucao.log` (mesmo arquivo usado pelo restante
do bot). Testes em [tests/test_dispatcher.py](tests/test_dispatcher.py).

## Performer (Issue #21)

`src/bot/performer.py` é o outro lado do Dispatcher: consome os itens do
DataPool `FilaAuditoriaLotes-Eqp04`, aplica RN01–RN07 em cada lote e
publica o resultado no Maestro.

**Como rodar:**

```bash
python -m src.bot.performer
```

**O que ele faz, em ordem:** autentica no Maestro → cria uma
`AutomationTask` real → puxa item por item da fila
(`report_done` quando o lote está conforme, `report_error` quando não) →
escreve o resumo em JSON e o anexa à task via `post_artifact` →
encerra a task com `finish_task`.

**Requisitos:** `.env` com credenciais válidas, `BOTCITY_ACTIVITY_LABEL`
apontando para uma **Automation já cadastrada no painel** do Maestro, e a
fila previamente populada pelo [Dispatcher](#dispatcher-issue-19).
A `activity_label` não é opcional: artefatos e alertas só podem ser
anexados a uma task existente — o servidor rejeita identificadores
inventados com `404`.

**Modo dry-run:** com `MAESTRO_ENABLED=false`, o Performer lê
`dados_entrada/lotes_auditoria.csv` direto do disco e aplica as mesmas
regras, sem criar task, consumir fila ou postar artefato. É o modo
recomendado para desenvolvimento.

**Classificação de erros na fila:** divergências de regra de negócio
(RN02–RN07) marcam o item com `ErrorType.BUSINESS`; exceções inesperadas
marcam com `ErrorType.SYSTEM`. Em nenhum dos casos o loop é interrompido —
um item problemático nunca impede o processamento dos seguintes.

**Base de referência (RN03):** usa exclusivamente
`data/processed/base_lotes_referencia.csv`, gerado pelo preprocessor. Não
há mais fallback: se o arquivo não existir, o Performer falha com uma
mensagem instruindo a rodar `python -m scripts.planilha_para_csv` primeiro.
A ordem preprocessor → performer é explícita, em vez de resolvida por um
fallback silencioso.

**Onde ver o resultado:** no painel do Maestro, na task finalizada pela
execução — o resumo em JSON fica na aba de artefatos dessa task, e o
status final (`SUCCESS` ou `PARTIALLY_COMPLETED`) reflete se houve
divergências. Os logs locais ficam em `logs/execucao.log`.

Testes em [tests/test_performer.py](tests/test_performer.py) e
[tests/test_avaliar_lote.py](tests/test_avaliar_lote.py).

## Interface web

O bot pode ser operado por uma página única no navegador: upload do
relatório original, resumo das divergências direto na tela e download do
relatório de divergências em `.xlsx`. É um módulo independente, em
[webapp/](webapp/) — instruções de execução completas em
[webapp/README.md](webapp/README.md).

## Relatório de divergências (Issue #5)

`gerar_relatorio()`, em [src/relatorio.py](src/relatorio.py), aplica as
regras RN01–RN07 sobre a planilha de lotes e monta o `.xlsx` de
divergências (abas `Resumo` e `Divergencias`). É a função consumida pela
interface web acima.

```python
import pandas as pd
from src.relatorio import gerar_relatorio

df = pd.read_csv("data/processed/dados_relatorio.csv")
resultado = gerar_relatorio(df, "relatorio_divergencias.xlsx")
print(resultado["resumo"])
```

Testes em [tests/test_relatorio.py](tests/test_relatorio.py).

## RN07 - Observação obrigatória em lote reprovado

Um lote com status `REPROVADO` (ou `NOK`) obrigatoriamente precisa ter o
campo de observação preenchido. Se o lote estiver reprovado e a observação
estiver vazia (ou só com espaços em branco), isso é uma divergência que o
bot deve sinalizar. A validação trata variações de caixa no status (ex.:
`"reprovado"`, `"REPROVADO"`, `"NOK"`).

A regra está implementada em [src/observacao.py](src/observacao.py), na
função `lote_conforme_rn07`.

### Como validar um lote

```python
from src.observacao import lote_conforme_rn07

lote = {"status": "REPROVADO", "observacao": ""}

if not lote_conforme_rn07(lote):
    print("Divergência RN07: lote reprovado sem observação preenchida.")
```

### Como rodar os testes

```bash
pip install pytest
python3 -m pytest tests/ -v
```

## RN03 — Existência do lote

**Regra:** o `lote_id` do relatório deve existir na aba `Base_Referencia` da planilha de referência.

**Implementação:** `validacao_lotes.py`

- Ao importar o módulo, a base de referência é carregada de `data/processed/base_lotes_referencia.csv`. Se o arquivo não existir ou não puder ser lido, o programa encerra com `sys.exit()`.
- `verificar_existencia_lote(lote)` → `True`/`False`, implementa a RN03 diretamente.
- `verificar_status_lote(lote)` → `True` (existe e está ativo), `False` (existe mas não está ativo) ou `None` (não existe — RN03 falhou antes de chegar no status).

`tests/test_validacao_lotes.py` cobre 100% do módulo, incluindo falha de leitura do CSV e casos de borda (lote duplicado, entrada `None`, coluna ausente).

> ⚠️ Duplicidade de `lote_id` na base de referência quebra `verificar_status_lote` (`.item()` exige valor único). A RN03 garante existência, não unicidade — vale revisar se isso é aceitável para os dados de origem.

# Módulo de geração de relatório

## O que esse módulo faz

O módulo [src/relatorio.py](src/relatorio.py) é responsável por gerar o relatório de divergências a partir dos dados de entrada, aplicando as regras de negócio definidas nos demais módulos do projeto.

Ele atua como orquestrador do processo de validação, chamando funções específicas para verificar:

- a estrutura do relatório e a presença de campos obrigatórios;
- a existência e o status dos lotes;
- a normalização e a consistência do campo de status;
- a obrigatoriedade de observação para lotes reprovados.

## Funções principais

### encontrar_divergencias(relatorio)

Essa função recebe um DataFrame com os dados do relatório e executa o fluxo completo de validação.

O fluxo é o seguinte:

1. Valida a estrutura do relatório com as funções de [src/modules/validacao.py](src/modules/validacao.py).
2. Verifica campos obrigatórios e identifica linhas com valores vazios.
3. Para cada lote, chama as validações de:
   - [src/modules/verificacao_lotes.py](src/modules/verificacao_lotes.py) para a RN03;
   - [src/modules/normalizacao_status.py](src/modules/normalizacao_status.py) para as regras de status;
   - [src/modules/observacao.py](src/modules/observacao.py) para a RN07.
4. Consolida as divergências encontradas e gera um arquivo Excel com os lotes problemáticos.

### gerar_relatorio_excel(df_original, rn02, rn03, rn06, rn07, caminho_saida)

Essa função organiza as divergências recebidas e exporta um relatório em formato Excel contendo apenas os registros que apresentaram alguma inconsistência.

O resultado inclui uma coluna chamada `Motivo_Divergencia`, com os motivos associados a cada lote.

## Regras que o módulo consulta

O módulo utiliza as seguintes validações:

- RN01 e RN02: estrutura do relatório e campos obrigatórios;
- RN03: existência do lote na base de referência;
- RN04 e RN05: validação e normalização do status;
- RN07: observação obrigatória para lote reprovado.

## Como executar

A partir da raiz do projeto, o módulo pode ser executado diretamente com:

```bash
python src/relatorio.py
```

Isso lê o arquivo CSV em `data/processed/dados_relatorio.csv` e gera um relatório Excel em `data/processed/`.

## Exemplo de uso

```python
import pandas as pd
from src.relatorio import encontrar_divergencias

relatorio = pd.read_csv('data/processed/dados_relatorio.csv')
encontrar_divergencias(relatorio)
```

## Saída gerada

O módulo produz:

- logs detalhados em `logs/relatorio.log`;
- um arquivo Excel com os lotes divergentes em `data/processed/`;
- uma consolidação dos motivos de divergência para cada linha do relatório.
