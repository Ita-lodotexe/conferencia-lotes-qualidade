# conferencia-lotes-qualidade

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
