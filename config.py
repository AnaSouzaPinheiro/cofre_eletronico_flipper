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
    apdu=None,              # TODO(equipe-flipper): APDU real
    expected_data=None,     # TODO(equipe-flipper): dados de resposta esperados
    expected_sw=(0x90, 0x00),
    expected_atr=None,      # TODO(equipe-flipper): ATR esperado (opcional)
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
