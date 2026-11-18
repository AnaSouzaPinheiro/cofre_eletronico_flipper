"""
Lógica de autenticação. Regra única e fail-closed:
só retorna sucesso se TODAS as verificações configuradas baterem exatamente.
Qualquer outra situação (sem dispositivo, erro, resposta diferente) = negado.
"""
import hmac
from dataclasses import dataclass
from enum import Enum

from core.criterion import Criterion
from core.smartcard_reader import BaseReader, ReaderError


class AuthReason(Enum):
    OK = "Autenticação aceita"
    NO_DEVICE = "Nenhum dispositivo conectado"
    NOT_CONFIGURED = "Critério de autenticação real não configurado (config.py)"
    ATR_MISMATCH = "ATR diferente do esperado"
    BAD_STATUS = "Status APDU (SW) diferente do esperado"
    BAD_RESPONSE = "Resposta diferente do esperado"
    COMM_ERROR = "Falha de comunicação com o dispositivo"


@dataclass(frozen=True)
class AuthResult:
    success: bool
    reason: AuthReason
    detail: str = ""
    simulated: bool = False


class Authenticator:
    def __init__(self, reader: BaseReader, criterion: Criterion):
        self.reader = reader
        self.criterion = criterion

    def _fail(self, reason, detail=""):
        sim = bool(self.reader and self.reader.is_simulated)
        return AuthResult(False, reason, detail, sim)

    def authenticate(self) -> AuthResult:
        r, c = self.reader, self.criterion
        if r is None or not r.is_connected:
            return self._fail(AuthReason.NO_DEVICE)
        if not c.is_configured:
            return self._fail(AuthReason.NOT_CONFIGURED)
        try:
            if c.expected_atr is not None:
                if not hmac.compare_digest(bytes(r.atr), c.expected_atr):
                    return self._fail(AuthReason.ATR_MISMATCH, f"ATR={r.atr.hex().upper()}")
            if c.apdu is not None:
                resp = r.transmit(c.apdu)
                if tuple(resp.sw) != tuple(c.expected_sw):
                    return self._fail(AuthReason.BAD_STATUS, f"SW={resp.sw1:02X}{resp.sw2:02X}")
                if c.expected_data is not None and not hmac.compare_digest(
                    resp.data, c.expected_data
                ):
                    return self._fail(
                        AuthReason.BAD_RESPONSE,
                        f"SW={resp.sw1:02X}{resp.sw2:02X} rx={resp.data[:16].hex().upper()}"
                        f" ({len(resp.data)} bytes)",
                    )
            return AuthResult(True, AuthReason.OK, "", r.is_simulated)
        except ReaderError as e:
            return self._fail(AuthReason.COMM_ERROR, str(e))
        except Exception as e:  # nunca liberar por erro inesperado
            return self._fail(AuthReason.COMM_ERROR, f"Erro inesperado: {e}")
