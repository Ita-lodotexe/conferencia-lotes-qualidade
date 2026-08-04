from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class UploadPage:
    INPUT_FILE = "#arquivo"
    SUBMIT_BUTTON = "#btn-enviar"
    RESULT_SECTION = "#resultado-section:not([hidden])"
    ERROR_MESSAGE = "#mensagem-erro"
    NO_DIVERGENCIAS = "#sem-divergencias"
    METRICAS = "#metricas"

    def __init__(self, page: Page):
        self.page = page

    def goto(self, url: str) -> None:
        self.page.goto(url)
        self.page.wait_for_load_state("domcontentloaded")

    def upload_file(self, arquivo_path: str) -> None:
        self.page.set_input_files(self.INPUT_FILE, arquivo_path)

    def submit(self) -> None:
        self.page.locator(self.SUBMIT_BUTTON).click()

    def wait_for_result(self, timeout: int = 10_000) -> None:
        self.page.wait_for_selector(self.RESULT_SECTION, timeout=timeout)

    def has_error(self) -> bool:
        return self.page.locator(self.ERROR_MESSAGE).is_visible()

    def has_no_divergencias(self) -> bool:
        return self.page.locator(self.NO_DIVERGENCIAS).is_visible()

    def get_metricas(self) -> str:
        return self.page.locator(self.METRICAS).inner_text()

    def screenshot(self, path: Path) -> Path:
        self.page.screenshot(path=str(path), full_page=True)
        return path


class UploadPageSelenium:
    INPUT_FILE = "#arquivo"
    SUBMIT_BUTTON = "#btn-enviar"
    RESULT_SECTION = "#resultado-section:not([hidden])"
    ERROR_MESSAGE = "#mensagem-erro"
    NO_DIVERGENCIAS = "#sem-divergencias"
    METRICAS = "#metricas"

    def __init__(self, driver: WebDriver):
        self.driver = driver

    def goto(self, url: str) -> None:
        self.driver.get(url)

    def upload_file(self, arquivo_path: str) -> None:
        self.driver.find_element(By.CSS_SELECTOR, self.INPUT_FILE).send_keys(arquivo_path)

    def submit(self) -> None:
        self.driver.find_element(By.CSS_SELECTOR, self.SUBMIT_BUTTON).click()

    def wait_for_result(self, timeout: int = 10_000) -> None:
        WebDriverWait(self.driver, timeout / 1000).until(
            lambda d: self._is_element_visible(self.RESULT_SECTION)
        )

    def has_error(self) -> bool:
        return self._is_element_visible(self.ERROR_MESSAGE)

    def has_no_divergencias(self) -> bool:
        return self._is_element_visible(self.NO_DIVERGENCIAS)

    def get_metricas(self) -> str:
        element = self.driver.find_element(By.CSS_SELECTOR, self.METRICAS)
        return element.text

    def screenshot(self, path: Path) -> Path:
        self.driver.save_screenshot(str(path))
        return path

    def _is_element_visible(self, selector: str) -> bool:
        try:
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            return element.is_displayed()
        except Exception:
            return False
