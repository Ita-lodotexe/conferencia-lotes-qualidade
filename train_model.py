"""Geração do dataset sintético + treinamento do classificador (Exercício 24-A).

Não existe (ainda) um histórico real de decisões de conferência de lotes
rotulado por humano — este script fabrica um substituto plausível para
poder treinar e validar o pipeline de ML de ponta a ponta, até que um
dataset real de produção esteja disponível.

Domínio do dataset sintético
-----------------------------
3 features, todas já numéricas (o objetivo aqui é o pipeline de ML, não
o encoding de categorias):

    status_raw : 0=APROVADO, 1=REPROVADO, 2=PENDENTE, 3=EM_AJUSTE, 4=CANCELADO
    turno      : 0=A, 1=B, 2=C
    tem_obs    : 0 ou 1 (observação preenchida ou não)

3 classes alvo: valido_automatico, revisar, recusar_automatico.

A classe de cada amostra é sorteada (não é uma regra determinística) a
partir de uma distribuição de probabilidade que depende de status_raw e
tem_obs, pensada para refletir o domínio de negócio:

    - APROVADO (status_raw=0): tende fortemente a valido_automatico,
      pouco sensível a tem_obs (um lote aprovado raramente precisa de
      observação para ser confiável).
    - REPROVADO (status_raw=1): tende fortemente a recusar_automatico;
      a ausência de observação (tem_obs=0) empurra ainda mais para
      recusar_automatico e reduz um pouco a chance de valido_automatico
      — reprovado sem justificativa é o cenário mais arriscado de
      liberar automaticamente (ver RN10 do motor de validação).
    - PENDENTE / EM_AJUSTE / CANCELADO (status_raw>=2): nenhum desses
      status representa uma decisão fechada, então a maioria das
      amostras cai em revisar.

O ruído é proposital: um classificador que acertasse 100% estaria só
decorando a regra de geração, não aprendendo um padrão estatístico —
o que seria inútil como exercício de ML.

Reprodutibilidade: numpy.random.seed(42) fixa tanto a geração do
dataset quanto o split treino/teste e o RandomForestClassifier.

Uso:
    python train_model.py

Saída:
    models/classificador_lotes.pkl (RandomForestClassifier serializado via joblib)
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

RAIZ = Path(__file__).resolve().parent
CAMINHO_MODELO = RAIZ / "models" / "classificador_lotes.pkl"

SEED = 42
N_AMOSTRAS = 300

FEATURES = ["status_raw", "turno", "tem_obs"]
CLASSES = ["valido_automatico", "revisar", "recusar_automatico"]

STATUS_APROVADO = 0
STATUS_REPROVADO = 1
STATUS_PENDENTE = 2
# 3 = EM_AJUSTE, 4 = CANCELADO — tratados junto com PENDENTE (status_raw >= 2)


def _probabilidades_para(status_raw: int, tem_obs: int) -> list[float]:
    """Distribuição de probabilidade das 3 classes, dado o status e a observação.

    Ordem das probabilidades: [valido_automatico, revisar, recusar_automatico].
    """
    if status_raw == STATUS_APROVADO:
        return [0.85, 0.10, 0.05]
    if status_raw == STATUS_REPROVADO and tem_obs == 1:
        return [0.10, 0.20, 0.70]
    if status_raw == STATUS_REPROVADO and tem_obs == 0:
        return [0.05, 0.25, 0.70]
    # status_raw >= 2 (PENDENTE, EM_AJUSTE, CANCELADO)
    return [0.15, 0.60, 0.25]


def gerar_dataset(n_amostras: int = N_AMOSTRAS) -> pd.DataFrame:
    """Gera `n_amostras` linhas sintéticas de (status_raw, turno, tem_obs, classe)."""
    linhas = []
    for _ in range(n_amostras):
        status_raw = np.random.randint(0, 5)  # 0..4
        turno = np.random.randint(0, 3)       # 0..2
        tem_obs = np.random.randint(0, 2)     # 0 ou 1

        probabilidades = _probabilidades_para(status_raw, tem_obs)
        classe = np.random.choice(CLASSES, p=probabilidades)

        linhas.append(
            {"status_raw": status_raw, "turno": turno, "tem_obs": tem_obs, "classe": classe}
        )

    return pd.DataFrame(linhas)


def treinar_modelo(dataset: pd.DataFrame) -> tuple[RandomForestClassifier, dict]:
    """Treina o RandomForestClassifier e devolve (modelo, métricas de avaliação)."""
    X = dataset[FEATURES]
    y = dataset["classe"]

    X_treino, X_teste, y_treino, y_teste = train_test_split(
        X, y, test_size=0.2, random_state=SEED, stratify=y
    )

    modelo = RandomForestClassifier(random_state=SEED)
    modelo.fit(X_treino, y_treino)

    y_previsto = modelo.predict(X_teste)
    metricas = {
        "accuracy": accuracy_score(y_teste, y_previsto),
        "classification_report": classification_report(y_teste, y_previsto),
    }
    return modelo, metricas


def main() -> int:
    np.random.seed(SEED)

    dataset = gerar_dataset()
    print(f"Dataset sintético gerado: {len(dataset)} amostras")
    print(dataset["classe"].value_counts())
    print()

    modelo, metricas = treinar_modelo(dataset)

    print(f"Accuracy: {metricas['accuracy']:.4f}")
    print()
    print("Classification report:")
    print(metricas["classification_report"])

    CAMINHO_MODELO.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelo, CAMINHO_MODELO)
    print(f"Modelo salvo em: {CAMINHO_MODELO}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
