"""Testes de segurança da autenticação do cofre (ambiente local/simulado).

Estes testes não comunicam com cartões, leitores PC/SC ou Flipper Zero.
Eles verificam a lógica Authenticator usando leitores controlados em memória.
"""
import unittest

from core.authenticator import Authenticator, AuthReason
from core.criterion import Criterion
from core.smartcard_reader import BaseReader, APDUResponse, ReaderError, SimulatedReader
from core.access_log import AccessLog, OK, DENIED


class ControlledReader(BaseReader):
    """Leitor de teste que permite controlar a resposta recebida pelo autenticador."""
    def __init__(self, *, data=b"SIM-OK", sw=(0x90, 0x00), atr=b"TEST-ATR",
                 error=None, simulated=True):
        super().__init__("Leitor controlado de teste")
        self._data = data
        self._sw = sw
        self._atr = atr
        self._error = error
        self.is_simulated = simulated
        self.received_apdus = []

    def connect(self):
        self.atr = self._atr
        self.is_connected = True

    def transmit(self, apdu):
        if not self.is_connected:
            raise ReaderError("Dispositivo não conectado")
        self.received_apdus.append(bytes(apdu))
        if self._error:
            raise self._error
        return APDUResponse(self._data, self._sw[0], self._sw[1])


def make_criterion(**kwargs):
    values = dict(apdu=b"TEST", expected_data=b"SIM-OK", expected_sw=(0x90, 0x00))
    values.update(kwargs)
    return Criterion(**values)


class AuthenticationSecurityTests(unittest.TestCase):
    def setUp(self):
        # Usa o mesmo CSV da interface, mas identifica claramente os eventos de teste.
        self.access_log = AccessLog()
        self.attempt_number = 0

    def authenticate(self, authenticator):
        """Executa e registra cada tentativa automatizada no access_log.csv."""
        result = authenticator.authenticate()
        self.attempt_number += 1
        test_name = self.id().split(".")[-1]
        detail = result.reason.value
        if result.detail:
            detail += f" | {result.detail}"
        detail += f" | tentativa {self.attempt_number}"
        self.access_log.add(
            event=f"Teste automatizado - {test_name}",
            result=OK if result.success else DENIED,
            mode="TESTE AUTOMATIZADO",
            device=getattr(authenticator.reader, "name", "-"),
            detail=detail,
        )
        return result

    def connected_reader(self, **kwargs):
        reader = ControlledReader(**kwargs)
        reader.connect()
        return reader

    def test_01_valid_static_response_is_accepted(self):
        reader = self.connected_reader()
        result = self.authenticate(Authenticator(reader, make_criterion()))
        self.assertTrue(result.success)
        self.assertEqual(result.reason, AuthReason.OK)

    def test_02_invalid_credential_response_is_denied(self):
        reader = self.connected_reader(data=b"SIM-FAKE")
        result = self.authenticate(Authenticator(reader, make_criterion()))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.BAD_RESPONSE)

    def test_03_unexpected_apdu_status_is_denied(self):
        reader = self.connected_reader(sw=(0x69, 0x82))
        result = self.authenticate(Authenticator(reader, make_criterion()))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.BAD_STATUS)

    def test_04_empty_response_is_denied(self):
        reader = self.connected_reader(data=b"")
        result = self.authenticate(Authenticator(reader, make_criterion()))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.BAD_RESPONSE)

    def test_05_communication_error_is_denied(self):
        reader = self.connected_reader(error=ReaderError("Timeout de teste"))
        result = self.authenticate(Authenticator(reader, make_criterion()))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.COMM_ERROR)

    def test_06_disconnected_reader_is_denied(self):
        reader = ControlledReader()  # não chama connect()
        result = self.authenticate(Authenticator(reader, make_criterion()))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.NO_DEVICE)

    def test_07_unconfigured_criterion_is_denied(self):
        reader = self.connected_reader()
        result = self.authenticate(Authenticator(reader, Criterion()))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.NOT_CONFIGURED)

    def test_08_same_static_response_can_be_reused(self):
        """Demonstra ausência de desafio/nonce na lógica atual: não é replay RF real."""
        reader = SimulatedReader(SimulatedReader.VALID)
        reader.connect()
        auth = Authenticator(reader, make_criterion(apdu=b"SIM-REQ", expected_data=b"SIM-OK"))
        first = self.authenticate(auth)
        second = self.authenticate(auth)  # mesma resposta fixa, sem estado anti-replay
        self.assertTrue(first.success)
        self.assertTrue(second.success)

    def test_09_atr_only_criterion_accepts_matching_atr_without_secret_challenge(self):
        """Demonstra que ATR configurado sozinho basta para retornar sucesso."""
        reader = self.connected_reader(atr=b"KNOWN-ATR")
        criterion = Criterion(expected_atr=b"KNOWN-ATR")
        result = self.authenticate(Authenticator(reader, criterion))
        self.assertTrue(result.success)
        self.assertEqual(reader.received_apdus, [])

    def test_10_mismatched_atr_is_denied(self):
        reader = self.connected_reader(atr=b"OTHER-ATR")
        criterion = Criterion(expected_atr=b"KNOWN-ATR")
        result = self.authenticate(Authenticator(reader, criterion))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.ATR_MISMATCH)

    def test_11_repeated_invalid_attempts_are_not_rate_limited(self):
        """A camada Authenticator não aplica bloqueio progressivo nem limite de tentativas."""
        reader = self.connected_reader(data=b"SIM-FAKE")
        auth = Authenticator(reader, make_criterion())

        results = [self.authenticate(auth) for _ in range(20)]

        self.assertEqual(len(reader.received_apdus), 20)
        self.assertTrue(all(not result.success for result in results))
        self.assertTrue(all(result.reason == AuthReason.BAD_RESPONSE for result in results))


    def test_12_response_with_valid_prefix_and_extra_bytes_is_denied(self):
        """A comparação deve exigir igualdade exata, não apenas prefixo válido."""
        reader = self.connected_reader(data=b"SIM-OK-EXTRA")
        result = self.authenticate(Authenticator(reader, make_criterion()))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.BAD_RESPONSE)

    def test_13_missing_response_object_is_denied(self):
        """Resposta ausente/None deve falhar fechada, sem liberar acesso."""
        class NoResponseReader(ControlledReader):
            def transmit(self, apdu):
                self.received_apdus.append(bytes(apdu))
                return None
        reader = NoResponseReader()
        reader.connect()
        result = self.authenticate(Authenticator(reader, make_criterion()))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.COMM_ERROR)

    def test_14_unexpected_internal_exception_is_denied(self):
        """Exceção inesperada do leitor não pode resultar em autenticação aceita."""
        reader = self.connected_reader(error=RuntimeError("Falha interna simulada"))
        result = self.authenticate(Authenticator(reader, make_criterion()))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.COMM_ERROR)

    def test_15_atr_mismatch_prevents_apdu_transmission(self):
        """Se o ATR não corresponde, o comando APDU não deve ser enviado."""
        reader = self.connected_reader(atr=b"ATR-DIFERENTE")
        criterion = make_criterion(expected_atr=b"ATR-ESPERADO")
        result = self.authenticate(Authenticator(reader, criterion))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.ATR_MISMATCH)
        self.assertEqual(reader.received_apdus, [])

    def test_16_configured_apdu_is_transmitted_exactly(self):
        """Confirma que o autenticador envia exatamente os bytes configurados."""
        reader = self.connected_reader()
        command = bytes.fromhex("00 A4 04 00 07")
        result = self.authenticate(Authenticator(reader, make_criterion(apdu=command)))
        self.assertTrue(result.success)
        self.assertEqual(reader.received_apdus, [command])

    def test_17_reader_disconnect_during_transmission_is_denied(self):
        """Desconexão no meio da troca APDU deve resultar em negação."""
        class DisconnectingReader(ControlledReader):
            def transmit(self, apdu):
                self.received_apdus.append(bytes(apdu))
                self.is_connected = False
                raise ReaderError("Cartão removido durante a comunicação")
        reader = DisconnectingReader()
        reader.connect()
        result = self.authenticate(Authenticator(reader, make_criterion()))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, AuthReason.COMM_ERROR)



if __name__ == "__main__":
    unittest.main(verbosity=2)
