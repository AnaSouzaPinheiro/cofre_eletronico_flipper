"""
Configuração central do cofre.

>>> ESTE É O PRINCIPAL PONTO DE ADAPTAÇÃO PARA O FLIPPER ZERO <<<

Nenhum comando APDU real foi inventado aqui. Enquanto REAL_CRITERION não for
preenchido com valores obtidos nos testes da equipe, a autenticação em modo
REAL é recusada (falha fechada: o cofre permanece bloqueado).
"""
from core.criterion import Criterion

# ----------------------------------------------------------------------------
# CRITÉRIO REAL (hardware) -- PREENCHER APÓS OS TESTES COM O FLIPPER
# ----------------------------------------------------------------------------
# apdu          : comando enviado ao dispositivo (bytes), ex.: bytes.fromhex("...")
#                 None = não envia nada (só verifica o ATR, se configurado)
# expected_data : dados EXATOS esperados na resposta (b"" = resposta sem dados)
# expected_sw   : (SW1, SW2) esperado
# expected_atr  : ATR exato esperado (None = não verifica)
#
# O critério é considerado "configurado" se expected_atr estiver definido OU
# se apdu e expected_data estiverem definidos.
REAL_CRITERION = Criterion(
    # Valores obtidos com tools/flipper_diag.py em 18/11/2026 (app CCID):
    # CLA 00/80/FF -> 6E 00; "01 02 03 04" -> 6A 00; "01 01 00 00" -> 90 00.
    apdu=bytes.fromhex("01010000"),
    expected_data=b"",
    expected_sw=(0x90, 0x00),
    expected_atr=bytes.fromhex("3B00"),
)

# ----------------------------------------------------------------------------
# CRITÉRIO DA SIMULAÇÃO -- valores fictícios, só existem no modo simulado
# ----------------------------------------------------------------------------
SIMULATION_CRITERION = Criterion(
    apdu=b"SIM-REQ",
    expected_data=b"SIM-OK",
    expected_sw=(0x90, 0x00),
    expected_atr=None,
)

# Respostas que o leitor SIMULADO devolve em cada cenário
SIM_VALID_DATA = b"SIM-OK"
SIM_INVALID_DATA = b"SIM-FAKE"
SIM_ATR = b"SIMULATED-ATR"

# Bloqueio automático após liberar (segundos). 0 = desativado.
AUTO_LOCK_SECONDS = 60

# Arquivo de registros (CSV)
LOG_FILE = "logs/access_log.csv"
