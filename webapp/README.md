# Interface web do Bot de Conferência de Lotes

Módulo independente que expõe uma página única para operar o bot pelo
navegador: enviar o relatório original, ver um resumo das divergências
encontradas e baixar o relatório de divergências em `.xlsx` (gerado por
`gerar_relatorio()`, em [src/relatorio.py](../src/relatorio.py)).

- Backend: [FastAPI](https://fastapi.tiangolo.com/) (`webapp/main.py`), reaproveita os módulos de
  validação de `src/modules/` e `src/relatorio.py` sem duplicar regra de negócio.
- Frontend: HTML/CSS/JS puro em `webapp/static/` (sem framework, sem build step).

> **Sobre o visual:** a paleta e o estilo são inspirados na identidade
> visual **pública** da LG Electronics (vermelho de marca `#A50034`,
> branco, cinzas neutros, tipografia sans-serif limpa). Este projeto não
> teve acesso ao design system interno oficial da LG (tokens, componentes,
> fontes proprietárias) — se esse material existir e puder ser
> compartilhado, o CSS em `webapp/static/styles.css` deve ser ajustado
> para segui-lo.

## Pré-requisitos

- Python 3.12+
- Dependências do projeto (inclui `fastapi`, `uvicorn`, `python-multipart`):

  ```bash
  pip install -r requirements.txt
  ```

- A base de referência de lotes precisa existir em
  `data/processed/base_lotes_referencia.csv` (versionada via DVC — ver
  README raiz). **Atenção:** `src/modules/verificacao_lotes.py` chama
  `sys.exit()` na importação se esse arquivo não existir, o que impede o
  servidor de subir. Rode `dvc pull` antes de iniciar a aplicação.

## Como executar

A partir da **raiz do repositório** (para que os imports `src.*`/`webapp.*`
resolvam corretamente):

```bash
python -m uvicorn webapp.main:app --reload
```

Depois abra [http://127.0.0.1:8000](http://127.0.0.1:8000) no navegador.

## Como usar

1. Na página, escolha (ou arraste) o arquivo do relatório original —
   `.xlsx` ou `.csv`, com as colunas `lote_id, produto, linha, turno,
   status, responsavel, data, observacao` — e clique em **Enviar relatório**.
2. O resumo (total de lotes, lotes conformes, lotes com divergência e a
   lista de divergências por regra RN01–RN07) aparece na própria página.
3. Clique em **Baixar relatório de divergências (.xlsx)** para obter o
   arquivo completo, com as abas `Resumo` e `Divergencias`.

## API

| Método | Rota                                | Descrição                                                   |
|--------|--------------------------------------|--------------------------------------------------------------|
| POST   | `/api/relatorios`                    | Recebe o arquivo (`multipart/form-data`, campo `arquivo`), roda `gerar_relatorio()` e devolve `{id, resumo, divergencias}`. |
| GET    | `/api/relatorios/{id}/download`      | Baixa o `.xlsx` de divergências gerado para aquele `id`.     |

Os arquivos `.xlsx` gerados ficam em um diretório temporário do sistema e
o mapeamento `id -> arquivo` vive em memória (válido enquanto o processo
do servidor estiver de pé) — suficiente para o uso local/demonstração
deste módulo.

## Testes

Os testes de `gerar_relatorio()` (que esta interface consome) estão em
[tests/test_relatorio.py](../tests/test_relatorio.py):

```bash
python -m pytest tests/test_relatorio.py -v
```
