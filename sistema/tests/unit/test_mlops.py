# ============================================================================
# Testes: featurizacao da manutencao preditiva (funcao pura montar_dataset).
# ============================================================================
from ai.mlops.train_score import montar_dataset


def _linha(km, vmax, bruscos, consumo):
    return {"km_rodados": km, "velocidade_media": 60, "velocidade_maxima": vmax,
            "bruscos": bruscos, "consumo": consumo, "score_conducao": 70}


def test_dataset_mapeia_features_na_ordem_esperada():
    linhas = [_linha(100, 90, 2, 20)]
    X, y = montar_dataset(linhas, horas_desde_manut=1000)
    assert X[0] == [100.0, 90.0, 2.0, 20.0]
    assert y[0] in (0, 1)


def test_alto_desgaste_gera_rotulo_de_risco():
    # Uso intenso + muito tempo desde manutencao -> risco alto (label 1).
    linhas = [_linha(2000, 160, 40, 80)]
    _X, y = montar_dataset(linhas, horas_desde_manut=9000)
    assert y[0] == 1


def test_baixo_desgaste_gera_rotulo_baixo():
    linhas = [_linha(20, 60, 0, 5)]
    _X, y = montar_dataset(linhas, horas_desde_manut=100)
    assert y[0] == 0
