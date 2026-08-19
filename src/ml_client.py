"""Cliente HTTP para a API de ML (api_ml/), com circuit breaker (Seção 3.3).

MLClient é deliberadamente burro: não conhece RegistroValidado, não sabe
o que é "Ambíguo" nem nenhuma regra de negócio — só fala HTTP com
{base_url}/predict e nunca deixa uma exceção escapar. Quem decide o que
fazer com o resultado (ou com a ausência dele) é src/item_processor.py,
mantendo a separação de responsabilidades do critério de aceite da
Seção 7.
"""
from __future__ import annotations

import time

import httpx


class MLClient:
    """Cliente HTTP para POST {base_url}/predict, com circuit breaker.

    O circuit breaker existe para não empilhar timeouts de 3s por
    registro quando a API de ML está fora do ar: depois de
    `max_falhas_consecutivas` falhas em sequência, o cliente para de
    tentar a rede e devolve None imediatamente. Não há half-open
    automático por tempo — o enunciado aceita reset manual
    (`resetar_circuito()`) ou reinício do processo.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 3.0,
        max_falhas_consecutivas: int = 5,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_falhas_consecutivas = max_falhas_consecutivas
        self._falhas_consecutivas = 0
        self.circuito_aberto = False

    def resetar_circuito(self) -> None:
        """Fecha o circuito manualmente e zera o contador de falhas."""
        self._falhas_consecutivas = 0
        self.circuito_aberto = False

    def classificar(
        self, lote_id: str, status: str, turno: str, tem_observacao: bool
    ) -> dict | None:
        """POST {base_url}/predict. Nunca lança — falha vira None.

        Em sucesso, devolve o JSON de PredictionOutput acrescido de
        `latencia_ms` (medida com time.monotonic() ao redor da chamada).
        """
        if self.circuito_aberto:
            return None

        payload = {
            "lote_id": lote_id,
            "status": status,
            "turno": turno,
            "tem_observacao": tem_observacao,
        }

        inicio = time.monotonic()
        try:
            resposta = httpx.post(f"{self.base_url}/predict", json=payload, timeout=self.timeout)
            resposta.raise_for_status()
        except httpx.HTTPError:
            # Cobre httpx.TimeoutException, erro de conexão (subclasses de
            # httpx.RequestError) e raise_for_status() em 4xx/5xx
            # (httpx.HTTPStatusError) — todas subclasses de httpx.HTTPError.
            self._registrar_falha()
            return None

        latencia_ms = (time.monotonic() - inicio) * 1000
        self._registrar_sucesso()

        resultado = resposta.json()
        resultado["latencia_ms"] = latencia_ms
        return resultado

    def _registrar_falha(self) -> None:
        self._falhas_consecutivas += 1
        if self._falhas_consecutivas >= self.max_falhas_consecutivas:
            self.circuito_aberto = True

    def _registrar_sucesso(self) -> None:
        self._falhas_consecutivas = 0
