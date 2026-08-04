# conferencia-lotes-qualidade

![CI](https://github.com/SEU_USUARIO/SEU_REPO/actions/workflows/ci.yml/badge.svg)

## Vis�o geral

Este repositório implementa um fluxo de auditoria de lotes com três camadas:

1. **Pr�-processamento de dados**: converte a planilha oficial
   `dados_referencia/inspecao_lotes_dia.xlsx` em CSVs consumiveis.
2. **BotCity Maestro**: Dispatcher envia lotes para fila e Performer consome
   a fila aplicando as regras RN02�RN07.
3. **Automa��o de UI local**: Playwright e Selenium validam o formul�rio de
   lote em `webapp/static/`.

Tamb�m h� uma interface web local em `webapp/` baseada em FastAPI.

---

## Estrutura do projeto

- `scripts/planilha_para_csv.py`
  - pr�-processa a planilha oficial e gera os arquivos de entrada.
- `scripts/dispatcher.py`
  - envia lotes para a fila `FilaAuditoriaLotes-Eqp04` do Maestro.
- `src/bot/`
  - `config.py`: l� configura��es do `.env`.
  - `vault_client.py`: busca credenciais do Vault ou usa credenciais locais.
  - `performer.py`: consome a fila e aplica as regras do exerc�cio.
  - `bot.py`: configura logging e startup do bot.
- `src/pages/`
  - page objects Playwright e Selenium para login, formul�rio e upload.
- `webapp/`
  - FastAPI e frontend est�tico para interface local.
- `tests/`
  - testes unit�rios, de integra��o e E2E.
- `playwright_fill.py`, `selenium_automation.py`, `web_automation.py`
  - automa��es locais de UI.

---

## Requisitos e instala��o

### 1. Criar e ativar o ambiente virtual

Para Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 2. Instalar depend�ncias

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

### 3. Instalar Chromium para Playwright

```bash
python -m playwright install chromium
```

> **Passo obrigatório:** execute `python -m playwright install chromium` antes de rodar qualquer teste Playwright ou automação Playwright. Sem este comando, o Chromium não estará instalado e os testes/automação vão falhar.

### 4. Configurar `.env`

Copie o exemplo e preencha as vari�veis necess�rias:

```bash
copy .env.example .env
```

Defina no `.env`:

- `BOTCITY_SERVER`
- `BOTCITY_LOGIN`
- `BOTCITY_KEY`
- `BOTCITY_WORKSPACE`
- `BOTCITY_ACTIVITY_LABEL`
- `MAESTRO_ENABLED` (`false` para desenvolvimento)
- `VAULT_ENABLED` (`false` para modo local)
- `PASTA_ENTRADA` (opcional, padr�o `dados_entrada`)

---

## Prepara��o dos dados

### Planilha oficial

Coloque a planilha de entrada em:

```text
dados_referencia/inspecao_lotes_dia.xlsx
```

### Gerar CSVs consum�veis

```bash
python -m scripts.planilha_para_csv
```

### Sa�da esperada

O comando gera:

- `dados_entrada/lotes_auditoria.csv`
- `data/processed/base_lotes_referencia.csv`

### O que o preprocessor faz

- limpa linhas de rodap�, notas e legendas n�o estruturadas.
- normaliza valores vazios do Excel para strings vazias.
- produz CSVs prontos para o Dispatcher e o Performer.

---

## Fluxo BotCity Maestro

### Dispatcher

O Dispatcher l� `dados_entrada/lotes_auditoria.csv` e envia cada lote para
a fila `FilaAuditoriaLotes-Eqp04`.

```bash
python -m scripts.dispatcher
```

#### Modo dry-run

Defina `MAESTRO_ENABLED=false` no `.env` para n�o enviar dados ao Maestro.
Nesse modo, o script apenas simula o envio e escreve logs.

#### Requisitos

- `.env` com `BOTCITY_SERVER`, `BOTCITY_LOGIN`, `BOTCITY_KEY`
- `dados_entrada/lotes_auditoria.csv` gerado pelo preprocessor

#### Observa��es

- O envio n�o � idempotente: rodar duas vezes pode criar itens duplicados.
- Falha em um item n�o aborta o envio dos demais.

### Performer

O Performer consome a fila e valida cada lote segundo RN02�RN07.

```bash
python -m src.bot.performer
```

#### O que acontece

1. autentica no BotCity Maestro.
2. cria uma `AutomationTask`.
3. l� itens da fila.
4. aplica valida��es de lote.
5. reporta `report_done` ou `report_error`.
6. anexa artefatos JSON.
7. finaliza a task.

#### Requisitos

- `.env` com credenciais v�lidas.
- `BOTCITY_ACTIVITY_LABEL` configurado para uma Automation existente.
- fila previamente populada pelo Dispatcher.
- `data/processed/base_lotes_referencia.csv` presente.

#### Modo dry-run

Com `MAESTRO_ENABLED=false`, o Performer processa os dados localmente sem
criar task, fila ou artefato.

#### Base de refer�ncia (RN03)

O Performer usa apenas `data/processed/base_lotes_referencia.csv` para
comparar lotes contra a base de refer�ncia.
Se o arquivo n�o existir, ele falha e solicita rodar o preprocessor.

#### Resultados

- o resumo de execu��o � gravado em `logs/execucao.log`.
- o servidor Maestro guarda o artefato JSON e o status final da task.

---

## Cofre de credenciais

`src/bot/vault_client.py` fornece credenciais do ERP utilizadas pelo bot.

- `VAULT_ENABLED=false`
  - retorna credenciais fict�cias `bot_local` / `senha_dev`.
  - �til para desenvolvimento sem rede ou credenciais reais.
- `VAULT_ENABLED=true`
  - usa o BotCity Vault real via SDK.

A senha nunca � impressa em logs.

---

## Interface web local

A interface FastAPI e frontend est�o em `webapp/`.

### Executar a interface local

```bash
python -m uvicorn webapp.main:app --reload
```

A interface permite:

- upload da planilha original.
- gera��o de relat�rios de diverg�ncia.
- download do resultado em Excel.

Consulte `webapp/README.md` para mais detalhes.

---

## Execução com Docker e CI/CD

Este projeto agora suporta execução em container Docker e validação no GitHub Actions.

### Build e execução em container

```bash
docker compose build

docker compose run --rm bot-conferencia
```

### Pastas de evidências geradas

Após a execução em container, verifique:

- `logs/`
- `data/output/`
- `screenshots/`
- `reports/`

### Pipeline GitHub Actions

O workflow `.github/workflows/ci.yml` agora inclui:

- `test`: instala dependências e executa `pytest -q`
- `build-docker`: constrói a imagem, inicia `webapp`, executa `bot-conferencia`, verifica evidências e publica artifacts

### Badges

Adicione o badge do workflow no topo do README após o título:

```md
![CI](https://github.com/SEU_USUARIO/SEU_REPO/actions/workflows/ci.yml/badge.svg)
```

---

## Automa��o local de UI

### Playwright

- `playwright_fill.py`: exemplo de automa��o completa de login e envio.
- `tests/e2e/test_formulario_lotes.py`: valida o formul�rio real do site.
- `tests/test_playwright_login.py`, `tests/test_playwright_form.py`,
  `tests/test_playwright_upload.py`: testes adicionais de UI.

### Selenium

- `selenium_automation.py`: exemplo de execu��o com WebDriver.
- page objects Selenium em `src/pages/`.

---

## Testes

### Executar todos os testes

```bash
python -m pytest tests/ -v
```

### Executar testes E2E Playwright

```bash
python -m pytest tests/e2e -q
```

### O que os testes E2E cobrem

- carregamento da p�gina de lote local.
- preenchimento do campo de produto.
- status padr�o `PENDENTE`.
- cadastro de lote com sucesso.
- valida��es RN02, RN06 e RN07.
- captura de screenshot de evid�ncia.

---

## Arquivos importantes

- `dados_referencia/inspecao_lotes_dia.xlsx`: planilha oficial.
- `dados_entrada/lotes_auditoria.csv`: CSV de lotes para Dispatcher/Performer.
- `data/processed/base_lotes_referencia.csv`: base de refer�ncia RN03.
- `webapp/static/login.html`: tela de login local.
- `webapp/static/lote-teste.html`: formul�rio de lote local.
- `src/pages/`: page objects Playwright e Selenium.
- `tests/e2e/`: testes de ponta a ponta.

---

## Fluxo completo de execu��o

1. ativar o ambiente virtual.
2. instalar depend�ncias.
3. instalar Chromium com Playwright.
4. configurar `.env`.
5. colocar a planilha em `dados_referencia/`.
6. rodar `python -m scripts.planilha_para_csv`.
7. rodar `python -m scripts.dispatcher`.
8. rodar `python -m src.bot.performer`.
9. rodar `python -m uvicorn webapp.main:app --reload` (opcional).
10. executar testes com `python -m pytest tests/ -v`.

---

## Observa��es importantes

- Alguns fluxos dependem de vari�veis de ambiente e arquivo externo n�o
  versionado (`.env`, planilha oficial).
- `python -m playwright install chromium` � obrigat�rio para os testes
  Playwright.
- O README agora documenta o estado atual do projeto e cada etapa de
  execu��o.
