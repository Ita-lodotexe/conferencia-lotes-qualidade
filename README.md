# conferencia-lotes-qualidade

## Camada BotCity (v0.2.0)

Fundação de execução do bot como robô BotCity: configuração via `.env`,
logging em arquivo e validação fail-fast de pré-requisitos, em `src/bot/`.

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

O CSV de entrada fica em `dados_entrada/lotes_auditoria.csv`. Este arquivo
é versionado no repositório (não está no `.gitignore`) porque também serve
de massa de teste para a Issue #21 (Performer): traz linhas válidas e
linhas com erros propositais (lote_id vazio, status ambíguo, reprovado sem
observação, turno vazio).

> ⚠️ **O envio não é idempotente**: rodar o Dispatcher duas vezes acumula
> itens duplicados na fila — o script não verifica se um lote já foi
> enviado antes. O log de início de execução avisa sobre isso.
> Falha ao enviar um item individual não aborta o restante do lote (o
> Dispatcher segue para o próximo e reporta o total de falhas no fim).

Logs de execução em `logs/execucao.log` (mesmo arquivo usado pelo restante
do bot). Testes em [tests/test_dispatcher.py](tests/test_dispatcher.py).

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
