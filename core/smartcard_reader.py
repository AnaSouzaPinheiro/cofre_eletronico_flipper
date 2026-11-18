"""
Camada de comunicação (PC/SC). Nada aqui decide se o acesso é liberado:
esta camada apenas entrega bytes. A decisão fica em core/authenticator.py.
"""
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

import config

try:
    from smartcard.System import readers as _pcsc_readers
    PYSCARD_AVAILABLE = True
except Exception:  # pyscard ausente ou sem PC/SC
    PYSCARD_AVAILABLE = False

try:
    from smartcard.Exceptions import NoCardException as _NoCardException
except Exception:
    class _NoCardException(Exception):  # placeholder para o except abaixo
        pass

# Heurística (NÃO confirmada): o nome do leitor do Flipper deve conter "flipper".
# A equipe deve confirmar o nome real em --list e ajustar aqui se necessário.
FLIPPER_NAME_HINTS = ("flipper",)


class ReaderError(Exception):
    """Falha de comunicação/conexão com o leitor ou cartão."""


@dataclass(frozen=True)
class APDUResponse:
    data: bytes
    sw1: int
    sw2: int

    @property
    def sw(self):
        return (self.sw1, self.sw2)


class BaseReader(ABC):
    is_simulated = False

    def __init__(self, name: str):
        self.name = name
        self.atr = b""
        self.is_connected = False

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def transmit(self, apdu: bytes) -> APDUResponse: ...

    def disconnect(self) -> None:
        self.is_connected = False
        self.atr = b""


class PCSCReader(BaseReader):
    """Leitor/cartão real via PC/SC (PySCard)."""

    @staticmethod
    def list_readers() -> List[str]:
        if not PYSCARD_AVAILABLE:
            raise ReaderError("PySCard não está instalado ou PC/SC indisponível.")
        try:
            return [str(r) for r in _pcsc_readers()]
        except Exception as e:
            raise ReaderError(
                f"Serviço PC/SC indisponível (verifique o serviço 'Cartão Inteligente' no Windows): {e}"
            )

    @staticmethod
    def find_flipper(names: List[str]) -> Optional[str]:
        """Primeiro leitor cujo nome sugere ser o Flipper (heurística), ou None."""
        for n in names:
            if any(h in n.lower() for h in FLIPPER_NAME_HINTS):
                return n
        return None

    def __init__(self, name: str):
        super().__init__(name)
        self._conn = None
        # transmit() roda em thread de worker; disconnect() na UI.
        self._lock = threading.RLock()

    def connect(self) -> None:
        with self._lock:
            self._connect_locked()

    def _connect_locked(self) -> None:
        if not PYSCARD_AVAILABLE:
            raise ReaderError("PySCard não está disponível.")
        if self._conn is not None:  # reconexão: libera a anterior
            self.disconnect()
        try:
            target = next((r for r in _pcsc_readers() if str(r) == self.name), None)
            if target is None:
                raise ReaderError("Leitor não encontrado (foi desconectado?).")
            self._conn = target.createConnection()
            # TODO(equipe-flipper): se necessário, fixar o protocolo:
            #   self._conn.connect(protocol=CardConnection.T1_protocol)
            self._conn.connect()
            self.atr = bytes(self._conn.getATR())
            self.is_connected = True
        except ReaderError:
            raise
        except _NoCardException:
            self._conn = None
            raise ReaderError(
                "Leitor encontrado, mas sem cartão presente. No Flipper, abra o app CCID "
                "e confirme que o cartão/dispositivo está ativo."
            )
        except Exception as e:  # CardConnectionException...
            self._conn = None
            raise ReaderError(f"Não foi possível conectar ao cartão: {e}")

    def transmit(self, apdu: bytes, follow_up: bool = False) -> APDUResponse:
        """Envia a APDU e devolve dados + SW1/SW2 separados.

        follow_up=False (padrão): resposta devolvida exatamente como veio.
        follow_up=True: trata SW1=61 (GET RESPONSE, ISO 7816-4) e SW1=6C
        (reenvio com Le correto). Só use após confirmar nos testes que o
        dispositivo precisa disso.
        """
        with self._lock:
            if not self.is_connected or self._conn is None:
                raise ReaderError("Dispositivo não conectado.")
            try:
                data, sw1, sw2 = self._conn.transmit(list(apdu))
                data = bytes(data)
                if follow_up:
                    data, sw1, sw2 = self._follow_up(bytes(apdu), data, sw1, sw2)
                return APDUResponse(data, sw1, sw2)
            except Exception as e:
                self.is_connected = False  # fail-closed: exige reconexão
                raise ReaderError(f"Falha na comunicação APDU: {e}")

    def _follow_up(self, apdu: bytes, data: bytes, sw1: int, sw2: int):
        if sw1 == 0x6C and len(apdu) in (4, 5):  # reenvia com Le = SW2
            retry = apdu[:4] + bytes([sw2])
            d, sw1, sw2 = self._conn.transmit(list(retry))
            data = bytes(d)
        for _ in range(16):  # limite para não ficar em laço infinito
            if sw1 != 0x61:
                break
            d, sw1, sw2 = self._conn.transmit([0x00, 0xC0, 0x00, 0x00, sw2])
            data += bytes(d)
        return data, sw1, sw2

    def disconnect(self) -> None:
        with self._lock:
            try:
                if self._conn is not None:
                    self._conn.disconnect()
            except Exception:
                pass
            self._conn = None
            super().disconnect()


class SimulatedReader(BaseReader):
    """Leitor FICTÍCIO para demonstração. Nunca representa autenticação real."""
    is_simulated = True

    VALID, INVALID, COMM_FAIL = "valid", "invalid", "comm_fail"
    SCENARIOS = {
        VALID: "Credencial válida (simulada)",
        INVALID: "Credencial inválida (simulada)",
        COMM_FAIL: "Falha de comunicação (simulada)",
    }

    def __init__(self, scenario: str = VALID):
        super().__init__("Leitor Simulado [SIMULAÇÃO]")
        self.scenario = scenario

    def connect(self) -> None:
        self.atr = config.SIM_ATR
        self.is_connected = True

    def transmit(self, apdu: bytes) -> APDUResponse:
        if not self.is_connected:
            raise ReaderError("Dispositivo não conectado.")
        if self.scenario == self.COMM_FAIL:
            raise ReaderError("Timeout simulado na comunicação.")
        if self.scenario == self.INVALID:
            return APDUResponse(config.SIM_INVALID_DATA, 0x90, 0x00)
        return APDUResponse(config.SIM_VALID_DATA, 0x90, 0x00)
