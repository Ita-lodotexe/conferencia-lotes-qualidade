from __future__ import annotations

from playwright.sync_api import Page
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver


class LoginPage:
    USUARIO_INPUT = "#usuario"
    SENHA_INPUT = "#senha"
    LOGIN_BUTTON = "#btn-login"

    def __init__(self, page: Page):
        self.page = page

    def goto(self, url: str) -> None:
        self.page.goto(url)
        self.page.wait_for_load_state("domcontentloaded")

    def preencher_usuario(self, usuario: str) -> None:
        self.page.fill(self.USUARIO_INPUT, usuario or "")

    def preencher_senha(self, senha: str) -> None:
        self.page.fill(self.SENHA_INPUT, senha or "")

    def fazer_login(self, usuario: str, senha: str) -> None:
        self.preencher_usuario(usuario)
        self.preencher_senha(senha)
        self.page.click(self.LOGIN_BUTTON)
        self.page.wait_for_load_state("networkidle")


class LoginPageSelenium:
    USUARIO_INPUT = "#usuario"
    SENHA_INPUT = "#senha"
    LOGIN_BUTTON = "#btn-login"

    def __init__(self, driver: WebDriver):
        self.driver = driver

    def goto(self, url: str) -> None:
        self.driver.get(url)

    def preencher_usuario(self, usuario: str) -> None:
        elemento = self.driver.find_element(By.CSS_SELECTOR, self.USUARIO_INPUT)
        elemento.clear()
        elemento.send_keys(usuario or "")

    def preencher_senha(self, senha: str) -> None:
        elemento = self.driver.find_element(By.CSS_SELECTOR, self.SENHA_INPUT)
        elemento.clear()
        elemento.send_keys(senha or "")

    def fazer_login(self, usuario: str, senha: str) -> None:
        self.preencher_usuario(usuario)
        self.preencher_senha(senha)
        self.driver.find_element(By.CSS_SELECTOR, self.LOGIN_BUTTON).click()
