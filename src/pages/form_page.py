from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver


class FormPage:
    LOTE_INPUT = "#lote"
    PRODUTO_INPUT = "#produto"
    OBSERVACAO_TEXTAREA = "#observacao"
    STATUS_RADIO = "input[name='status']"
    SUBMIT_BUTTON = "button[type='submit']"
    SUCCESS_BOX = "#mensagemSucesso"
    ERROR_BOX = "#mensagemErro"
    ERROR_MESSAGE = "#erroMensagem"
    SUCCESS_LOTE = "#sucessoLote"
    SUCCESS_PRODUTO = "#sucessoProduto"
    SUCCESS_MESSAGE = "#sucessoMensagem"
    STATUS_MAP = {
        "OK": "APROVADO",
        "NOK": "REPROVADO",
        "REPROV.": "REPROVADO",
    }

    def __init__(self, page: Page):
        self.page = page

    def goto(self, url: str) -> None:
        self.page.goto(url)
        self.page.wait_for_load_state("domcontentloaded")

    def preencher_formulario(self, dados_lote: dict[str, str]) -> None:
        self.fill_lote(dados_lote.get("lote") or dados_lote.get("lote_id", ""))
        self.fill_produto(dados_lote.get("produto", ""))
        self.select_status(dados_lote.get("status", ""))
        self.fill_observacao(dados_lote.get("observacao", ""))

    def fill_lote(self, lote: str) -> None:
        if lote is None:
            return
        self.page.fill(self.LOTE_INPUT, str(lote))

    def fill_produto(self, produto: str) -> None:
        if produto is None:
            return
        self.page.fill(self.PRODUTO_INPUT, str(produto))

    def preencher_lote(self, lote: str) -> None:
        self.fill_lote(lote)

    def preencher_produto(self, produto: str) -> None:
        self.fill_produto(produto)

    def selecionar_status(self, status: str) -> None:
        self.select_status(status)

    def select_status(self, status: str) -> None:
        if not status:
            return

        normalized = str(status).strip().upper()
        candidates = [normalized]
        alias = self.STATUS_MAP.get(normalized)
        if alias and alias != normalized:
            candidates.append(alias)

        for target in candidates:
            try:
                self.page.locator(f"{self.STATUS_RADIO}[value=\"{target}\"]").check(timeout=0)
                return
            except Exception:
                continue

        # Caso o status não exista como opção visível, injetamos um rádio oculto
        # para manter o valor original e permitir validação no front-end.
        self._inject_hidden_status(normalized)

    def _inject_hidden_status(self, status: str) -> None:
        self.page.evaluate(
            "(status) => {\n"
            "  const form = document.getElementById('formCadastro');\n"
            "  if (!form) return;\n"
            "  const radios = Array.from(document.querySelectorAll(\"input[name='status']\"));\n"
            "  const existing = radios.find((radio) => radio.value === status);\n"
            "  if (existing) { existing.checked = true; return; }\n"
            "  const hidden = document.createElement('input');\n"
            "  hidden.type = 'radio';\n"
            "  hidden.name = 'status';\n"
            "  hidden.value = status;\n"
            "  hidden.checked = true;\n"
            "  hidden.style.display = 'none';\n"
            "  form.appendChild(hidden);\n"
            "}",
            status,
        )

    def fill_observacao(self, observacao: str) -> None:
        if observacao is None:
            return
        self.page.fill(self.OBSERVACAO_TEXTAREA, str(observacao))

    def submit(self) -> None:
        self.page.locator(self.SUBMIT_BUTTON).click()

    def wait_for_result(self, timeout: int = 10_000) -> None:
        self.page.wait_for_selector(
            f"{self.SUCCESS_BOX}.show, {self.ERROR_BOX}.show",
            timeout=timeout,
        )

    def is_sucesso(self) -> bool:
        return self.page.locator(self.SUCCESS_BOX).is_visible()

    def is_erro(self) -> bool:
        return self.page.locator(self.ERROR_BOX).is_visible()

    def get_error_message(self) -> str:
        return self.page.locator(self.ERROR_MESSAGE).inner_text()

    def get_success_details(self) -> dict[str, str]:
        return {
            "lote": self.page.locator(self.SUCCESS_LOTE).inner_text(),
            "produto": self.page.locator(self.SUCCESS_PRODUTO).inner_text(),
            "mensagem": self.page.locator(self.SUCCESS_MESSAGE).inner_text(),
        }

    def get_title(self) -> str:
        return self.page.title()

    def get_lote_value(self) -> str:
        return self.page.locator(self.LOTE_INPUT).input_value()

    def get_produto_value(self) -> str:
        return self.page.locator(self.PRODUTO_INPUT).input_value()

    def get_selected_status(self) -> str:
        return self.page.evaluate("document.querySelector('input[name=\\'status\\']:checked').value")

    def screenshot(self, path: Path) -> Path:
        self.page.screenshot(path=str(path), full_page=True)
        return path


class FormPageSelenium:
    LOTE_INPUT = "#lote"
    PRODUTO_INPUT = "#produto"
    OBSERVACAO_TEXTAREA = "#observacao"
    STATUS_RADIO = "input[name='status']"
    SUBMIT_BUTTON = "button[type='submit']"
    SUCCESS_BOX = "#mensagemSucesso"
    ERROR_BOX = "#mensagemErro"
    ERROR_MESSAGE = "#erroMensagem"
    SUCCESS_LOTE = "#sucessoLote"
    SUCCESS_PRODUTO = "#sucessoProduto"
    SUCCESS_MESSAGE = "#sucessoMensagem"

    def __init__(self, driver: WebDriver):
        self.driver = driver

    def goto(self, url: str) -> None:
        self.driver.get(url)

    def preencher_formulario(self, dados_lote: dict[str, str]) -> None:
        self.preencher_lote(dados_lote.get("lote") or dados_lote.get("lote_id", ""))
        self.preencher_produto(dados_lote.get("produto", ""))
        self.selecionar_status(dados_lote.get("status", ""))
        self.preencher_observacao(dados_lote.get("observacao", ""))

    def preencher_lote(self, lote: str) -> None:
        elemento = self.driver.find_element(By.CSS_SELECTOR, self.LOTE_INPUT)
        elemento.clear()
        elemento.send_keys(str(lote or ""))

    def preencher_produto(self, produto: str) -> None:
        elemento = self.driver.find_element(By.CSS_SELECTOR, self.PRODUTO_INPUT)
        elemento.clear()
        elemento.send_keys(str(produto or ""))

    def selecionar_status(self, status: str) -> None:
        if not status:
            return

        normalized = str(status).strip().upper()
        if normalized not in {"APROVADO", "REPROVADO", "PENDENTE"}:
            return

        radios = self.driver.find_elements(By.CSS_SELECTOR, self.STATUS_RADIO)
        for radio in radios:
            if radio.get_attribute("value") == normalized:
                radio.click()
                return

    def preencher_observacao(self, observacao: str) -> None:
        elemento = self.driver.find_element(By.CSS_SELECTOR, self.OBSERVACAO_TEXTAREA)
        elemento.clear()
        elemento.send_keys(str(observacao or ""))

    def submit(self) -> None:
        self.driver.find_element(By.CSS_SELECTOR, self.SUBMIT_BUTTON).click()

    def is_sucesso(self) -> bool:
        return self._is_visible(self.SUCCESS_BOX)

    def is_erro(self) -> bool:
        return self._is_visible(self.ERROR_BOX)

    def get_error_message(self) -> str:
        return self.driver.find_element(By.CSS_SELECTOR, self.ERROR_MESSAGE).text

    def get_success_details(self) -> dict[str, str]:
        return {
            "lote": self.driver.find_element(By.CSS_SELECTOR, self.SUCCESS_LOTE).text,
            "produto": self.driver.find_element(By.CSS_SELECTOR, self.SUCCESS_PRODUTO).text,
            "mensagem": self.driver.find_element(By.CSS_SELECTOR, self.SUCCESS_MESSAGE).text,
        }

    def screenshot(self, path: Path) -> Path:
        self.driver.save_screenshot(str(path))
        return path

    def _is_visible(self, selector: str) -> bool:
        try:
            elemento = self.driver.find_element(By.CSS_SELECTOR, selector)
            return elemento.is_displayed()
        except Exception:
            return False
