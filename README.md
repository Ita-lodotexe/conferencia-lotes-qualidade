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

## RN03 — Existência do lote

**Regra:** o `lote_id` do relatório deve existir na aba `Base_Referencia` da planilha de referência.

**Implementação:** `validacao_lotes.py`

- Ao importar o módulo, a base de referência é carregada de `data/processed/base_lotes_referencia.csv`. Se o arquivo não existir ou não puder ser lido, o programa encerra com `sys.exit()`.
- `verificar_existencia_lote(lote)` → `True`/`False`, implementa a RN03 diretamente.
- `verificar_status_lote(lote)` → `True` (existe e está ativo), `False` (existe mas não está ativo) ou `None` (não existe — RN03 falhou antes de chegar no status).

`tests/test_validacao_lotes.py` cobre 100% do módulo, incluindo falha de leitura do CSV e casos de borda (lote duplicado, entrada `None`, coluna ausente).

> ⚠️ Duplicidade de `lote_id` na base de referência quebra `verificar_status_lote` (`.item()` exige valor único). A RN03 garante existência, não unicidade — vale revisar se isso é aceitável para os dados de origem.