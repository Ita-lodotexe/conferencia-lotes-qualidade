# Issue #3 — RN04 e RN05 (status e normalização OK/NOK)

## O que este módulo faz
Implementa as regras RN04 (status permitido) e RN05 (normalização OK/NOK) do
PDD, seção 12.

- `normalizar_status(status)` → aplica a RN05
- `validar_status(status)` → aplica RN04 sobre o valor já normalizado, e
  sinaliza `ambiguo=True` para os casos que devem ir para revisão humana (RN06)

## Como executar os testes

```bash
pip install pytest
pytest tests/test_issue_03.py -v
```

## Como usar na Main do projeto

```python
from src.issue_03 import validar_status

resultado = validar_status(linha["status"])

if resultado["ambiguo"]:
    # encaminhar para a lista de casos ambíguos (RN06)
    ...
else:
    status_final = resultado["status_normalizado"]
```

## Referência
PDD, seção 12 — Regras de negócio (RN04, RN05). Exemplos reais de status
ambíguos usados nos testes: `REPROV.` e `APROVADO PARCIAL` (ver EX05 do PDD).
