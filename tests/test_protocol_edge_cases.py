"""Testes complementares de borda do protocolo APDU e ATR.

Todos os testes usam leitores em memória; nenhum cartão real é acessado.
Resultados diagnósticos podem confirmar comportamentos vulneráveis existentes.
"""
import unittest

from core.authenticator import Authenticator, AuthReason
from core.criterion import Criterion
from core.smartcard_reader import BaseReader, APDUResponse, ReaderError
from core.access_log import AccessLog, OK, DENIED


class EdgeReader(BaseReader):
    def __init__(self, *, atr=b"EDGE-ATR", data=b"TOKEN", sw=(0x90, 0x00), error=None):
        super().__init__("Leitor de borda automatizado")
        self._atr = atr
        self.data = data
        self.sw = sw
        self.error = error
        self.apdus = []
        self.is_simulated = True

    def connect(self):
        self.atr = self._atr
        self.is_connected = True

    def transmit(self, apdu):
        if not self.is_connected:
            raise ReaderError("Leitor desconectado")
        self.apdus.append(bytes(apdu))
        if self.error:
            raise self.error
        return APDUResponse(self.data, self.sw[0], self.sw[1])


class ProtocolEdgeCaseTests(unittest.TestCase):
    def setUp(self):
        self.log = AccessLog()
        self.counter = 0

    def run_auth(self, reader, criterion):
        result = Authenticator(reader, criterion).authenticate()
        self.counter += 1
        name = self.id().split(".")[-1]
        detail = result.reason.value + (f" | {result.detail}" if result.detail else "")
        detail += f" | tentativa {self.counter}"
        self.log.add(
            event=f"Teste automatizado - {name}",
            result=OK if result.success else DENIED,
            mode="TESTE AUTOMATIZADO",
            device=reader.name,
            detail=detail,
        )
        return result

    def connected(self, **kwargs):
        reader = EdgeReader(**kwargs)
        reader.connect()
        return reader

    def test_18_response_data_is_not_checked_when_expected_data_is_none(self):
        """Confirma que ATR + APDU + expected_data=None não valida os dados recebidos."""
        reader = self.connected(atr=b"ATR-CERTO", data=b"QUALQUER-CONTEUDO")
        criterion = Criterion(apdu=b"CHALLENGE", expected_data=None, expected_atr=b"ATR-CERTO")
        result = self.run_auth(reader, criterion)
        self.assertTrue(result.success)
        self.assertEqual(reader.apdus, [b"CHALLENGE"])

    def test_19_empty_atr_can_be_used_as_the_only_criterion(self):
        """Registra o comportamento atual: ATR vazio esperado e recebido é aceito."""
        reader = self.connected(atr=b"")
        result = self.run_auth(reader, Criterion(expected_atr=b""))
        self.assertTrue(result.success)

    def test_20_static_response_is_reusable_across_reader_instances(self):
        """Demonstra repetição da resposta fixa em sessões/leitores novos simulados."""
        criterion = Criterion(apdu=b"REQ", expected_data=b"TOKEN")
        first_reader = self.connected(data=b"TOKEN")
        second_reader = self.connected(data=b"TOKEN")
        first = self.run_auth(first_reader, criterion)
        second = self.run_auth(second_reader, criterion)
        self.assertTrue(first.success)
        self.assertTrue(second.success)

    def test_21_disconnected_reader_after_previous_success_is_denied(self):
        reader = self.connected()
        first = self.run_auth(reader, Criterion(apdu=b"REQ", expected_data=b"TOKEN"))
        reader.disconnect()
        second = self.run_auth(reader, Criterion(apdu=b"REQ", expected_data=b"TOKEN"))
        self.assertTrue(first.success)
        self.assertFalse(second.success)
        self.assertEqual(second.reason, AuthReason.NO_DEVICE)

    def test_22_short_response_is_denied(self):
        reader = self.connected(data=b"TOKE")
        result = self.run_auth(reader, Criterion(apdu=b"REQ", expected_data=b"TOKEN"))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.BAD_RESPONSE)

    def test_23_trailing_zero_byte_is_denied(self):
        reader = self.connected(data=b"TOKEN\\x00")
        result = self.run_auth(reader, Criterion(apdu=b"REQ", expected_data=b"TOKEN"))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.BAD_RESPONSE)

    def test_24_wrong_sw1_is_denied(self):
        reader = self.connected(sw=(0x91, 0x00))
        result = self.run_auth(reader, Criterion(apdu=b"REQ", expected_data=b"TOKEN"))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.BAD_STATUS)

    def test_25_wrong_sw2_is_denied(self):
        reader = self.connected(sw=(0x90, 0x01))
        result = self.run_auth(reader, Criterion(apdu=b"REQ", expected_data=b"TOKEN"))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.BAD_STATUS)

    def test_26_malformed_expected_sw_is_denied(self):
        reader = self.connected()
        result = self.run_auth(reader, Criterion(apdu=b"REQ", expected_data=b"TOKEN", expected_sw=(0x90,)))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.BAD_STATUS)

    def test_27_none_response_data_is_denied(self):
        class NoneDataReader(EdgeReader):
            def transmit(self, apdu):
                self.apdus.append(bytes(apdu))
                return APDUResponse(None, 0x90, 0x00)
        reader = NoneDataReader()
        reader.connect()
        result = self.run_auth(reader, Criterion(apdu=b"REQ", expected_data=b"TOKEN"))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.COMM_ERROR)

    def test_28_empty_apdu_is_transmitted_as_configured(self):
        reader = self.connected()
        result = self.run_auth(reader, Criterion(apdu=b"", expected_data=b"TOKEN"))
        self.assertTrue(result.success)
        self.assertEqual(reader.apdus, [b""])

    def test_29_case_changed_response_is_denied(self):
        reader = self.connected(data=b"token")
        result = self.run_auth(reader, Criterion(apdu=b"REQ", expected_data=b"TOKEN"))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.BAD_RESPONSE)

    def test_30_empty_response_is_accepted_when_explicitly_configured(self):
        reader = self.connected(data=b"")
        result = self.run_auth(reader, Criterion(apdu=b"REQ", expected_data=b""))
        self.assertTrue(result.success)
        self.assertEqual(result.reason, AuthReason.OK)


if __name__ == "__main__":
    unittest.main(verbosity=2)
