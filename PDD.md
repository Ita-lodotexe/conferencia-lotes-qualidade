# PDD - Refatoração Page Objects

## Objetivo

Refatorar o fluxo de automação para aplicar Page Object Model (POM) em Playwright e Selenium, separando:

- locators e ações da interface
- lógica de negócio e validação
- orquestração do fluxo

## Escopo

- Criar a pasta `src/pages/`
- Implementar `LoginPage` e `FormPage` para Playwright
- Implementar `LoginPageSelenium` e `FormPageSelenium` para Selenium
- Refatorar `playwright_fill.py` para usar `FormPage`
- Refatorar `web_automation.py` para usar `UploadPage`
- Adicionar suporte a Selenium local em `selenium_automation.py`
- Manter logs, screenshots e evidências funcionando
- Atualizar README com o novo POM

## Critérios de aceitação

- `feature/page-objects` criada
- `src/pages/` criada
- Page Objects Playwright e Selenium conectados
- Locators centralizados em classes de página
- Regras de negócio fora dos Page Objects
- Bot e automações executam sem regressão de fluxo
- Screenshots e logs mantidos
- README e PDD atualizados
