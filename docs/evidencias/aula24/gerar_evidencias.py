"""Gera um dataset sintético de 10 dias e roda o pipeline real de ponta a
ponta, para produzir o pacote de evidências da Aula 24 (Seção 5.7).

Não é um teste automatizado — é um script único, executado manualmente,
cujo resultado (xlsx + md + json + log) é anexado em docs/evidencias/aula24/.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))

from src.aula22_preprocessador import carregar_planilha_10dias
from src.aula22_classificacao import classificar_lotes
from src.operational_indicators import calcular_indicadores
from src.aula22_relatorio import gerar_relatorio_aula22
from src.resumo_executivo import gerar_resumo_executivo

DESTINO = RAIZ / "docs" / "evidencias" / "aula24"
DESTINO.mkdir(parents=True, exist_ok=True)

PRODUTOS = [("TV55", "Televisão 55pol"), ("TV65", "Televisão 65pol"), ("GEL01", "Geladeira Frost Free")]

LOTES_BASE = [f"LOTE-{n:03d}" for n in range(1, 41)]
LOTES_INATIVOS_OU_INEXISTENTES = {"LOTE-901", "LOTE-902"}

wb = openpyxl.Workbook()
wb.remove(wb.active)

base = wb.create_sheet("Base_Referencia")
base.append(["Base de Referência — Cadastro de Lotes"])
base.append(["lote_id", "codigo_produto", "descricao_produto", "status_cadastro"])
for i, lote in enumerate(LOTES_BASE):
    produto, descricao = PRODUTOS[i % len(PRODUTOS)]
    status_cadastro = "Ativo" if i % 9 != 0 else "Inativo"
    base.append([lote, produto, descricao, status_cadastro])

data_inicial = date(2026, 6, 15)
linha_id_global = 1
for dia_idx in range(10):
    dia = data_inicial + timedelta(days=dia_idx)
    nome_aba = f"Insp_{dia.strftime('%d_%m_%Y')}"
    ws = wb.create_sheet(nome_aba)
    ws.append([f"Inspeção diária — {dia.strftime('%d/%m/%Y')}"])
    ws.append(["gerado automaticamente para fins de evidência (Aula 24)"])
    ws.append(["lote_id", "produto", "linha", "turno", "status", "responsavel", "data", "observacao"])

    data_str = dia.strftime("%d/%m/%Y")
    linhas_do_dia = []

    # 4 válidos
    for k in range(4):
        lote = LOTES_BASE[(dia_idx * 4 + k) % len(LOTES_BASE)]
        produto, _ = PRODUTOS[k % len(PRODUTOS)]
        linhas_do_dia.append([lote, produto, "L1", "A", "OK", "Ana", data_str, None])

    # 1 divergência: lote não cadastrado (RN05)
    linhas_do_dia.append(["LOTE-901", "TV55", "L1", "A", "OK", "Ana", data_str, None])

    # 1 divergência: REPROVADO sem observação (RN10) — só nos dias pares
    if dia_idx % 2 == 0:
        lote = LOTES_BASE[(dia_idx * 4 + 5) % len(LOTES_BASE)]
        linhas_do_dia.append([lote, "GEL01", "L2", "B", "NOK", "Bruno", data_str, None])

    # 1 ambíguo: status não reconhecido (RN09) — só a cada 3 dias
    if dia_idx % 3 == 0:
        lote = LOTES_BASE[(dia_idx * 4 + 6) % len(LOTES_BASE)]
        linhas_do_dia.append([lote, "TV65", "L1", "A", "EM AJUSTE", "Carla", data_str, None])

    # 1 erro de entrada: campo obrigatório vazio (RN01-RN04) — só a cada 4 dias
    if dia_idx % 4 == 0:
        linhas_do_dia.append(["", "TV55", "L1", "A", "OK", "Ana", data_str, None])

    for linha in linhas_do_dia:
        ws.append(linha)
    ws.append([f"Total de registros: {len(linhas_do_dia)}"])

buffer_path = DESTINO / "_dataset_sintetico_10dias.xlsx"
wb.save(buffer_path)

registros_por_dia, base_referencia = carregar_planilha_10dias(str(buffer_path))
registros = classificar_lotes(registros_por_dia, base_referencia)

indicadores = calcular_indicadores(registros)

caminho_xlsx = DESTINO / "relatorio_conferencia_lotes.xlsx"
resultado = gerar_relatorio_aula22(registros, str(caminho_xlsx), indicadores=indicadores)

caminho_md = DESTINO / "resumo_executivo.md"
caminho_md.write_text(gerar_resumo_executivo(indicadores), encoding="utf-8")

execucao_json = {
    "dataset": "sintético (10 dias, gerado para fins de evidência — o dataset real "
               "inspecao_lotes_10dias.xlsx não é distribuído no repositório)",
    "total_registros": indicadores.total_registros,
    "por_classificacao": {
        "Válido": indicadores.qtd_validos,
        "Divergência": indicadores.qtd_divergencias,
        "Ambíguo": indicadores.qtd_ambiguos,
        "Erro de Entrada": indicadores.qtd_erros_entrada,
    },
    "percentual": {
        "Válido": round(indicadores.pct_validos, 1),
        "Divergência": round(indicadores.pct_divergencias, 1),
        "Ambíguo": round(indicadores.pct_ambiguos, 1),
        "Erro de Entrada": round(indicadores.pct_erros_entrada, 1),
    },
    "regra_mais_acionada": indicadores.regra_mais_acionada,
    "regra_mais_acionada_nome": indicadores.regra_mais_acionada_nome,
    "regra_mais_acionada_qtd": indicadores.regra_mais_acionada_qtd,
    "taxa_qualidade_entrada": round(indicadores.taxa_qualidade_entrada, 1),
    "taxa_revisao_humana": round(indicadores.taxa_revisao_humana, 1),
    "taxa_retrabalho": round(indicadores.taxa_retrabalho, 1),
    "ganho_estimado_minutos": round(indicadores.ganho_estimado_minutos, 1),
    "tempo_manual_min_por_registro": indicadores.tempo_manual_min_por_registro,
    "tempo_automatizado_min_por_registro": indicadores.tempo_automatizado_min_por_registro,
    "ranking_regras": indicadores.ranking_regras,
    "arquivo_excel": str(caminho_xlsx.relative_to(RAIZ)),
    "arquivo_resumo_executivo": str(caminho_md.relative_to(RAIZ)),
}
caminho_json = DESTINO / "execucao.json"
caminho_json.write_text(json.dumps(execucao_json, ensure_ascii=False, indent=2), encoding="utf-8")

buffer_path.unlink()

print("OK - artefatos gerados em", DESTINO)
print(json.dumps(execucao_json, ensure_ascii=False, indent=2))
