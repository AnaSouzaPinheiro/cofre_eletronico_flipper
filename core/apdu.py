"""
Utilitários APDU puros (sem PC/SC, sem estado): conversão hex <-> bytes,
validação estrutural e descrição de status words.

Nada aqui inventa comandos: apenas interpreta o que o usuário digita e
descreve códigos SW definidos na ISO/IEC 7816-4 (referência genérica; o que o
Flipper realmente devolve só se sabe testando).
"""
import re
from typing import Optional

MAX_SHORT_APDU = 261  # CLA INS P1 P2 Lc(1) + 255 dados + Le(1)


class APDUFormatError(ValueError):
    """APDU/hexadecimal informado é inválido."""


def parse_hex(text: str) -> bytes:
    """Aceita 'FF CA 00 00', 'ffca0000', '0xFF,0xCA' etc. Levanta APDUFormatError."""
    if text is None:
        raise APDUFormatError("Entrada vazia.")
    cleaned = re.sub(r"0x|[\s,:;-]", "", text.strip(), flags=re.IGNORECASE)
    if not cleaned:
        raise APDUFormatError("Entrada vazia.")
    if not re.fullmatch(r"[0-9A-Fa-f]+", cleaned):
        raise APDUFormatError("Contém caracteres que não são hexadecimais.")
    if len(cleaned) % 2:
        raise APDUFormatError("Número ímpar de dígitos hexadecimais (cada byte tem 2).")
    return bytes.fromhex(cleaned)


def format_hex(data: bytes, group: bool = True) -> str:
    """b'\\x90\\x00' -> '90 00' (ou '9000' com group=False). Vazio -> '(vazio)'."""
    if not data:
        return "(vazio)"
    h = bytes(data).hex().upper()
    return " ".join(h[i:i + 2] for i in range(0, len(h), 2)) if group else h


def validate_apdu(apdu: bytes) -> Optional[str]:
    """Verificação estrutural mínima. Retorna aviso (str) ou None se plausível.

    É só um aviso: o dispositivo decide o que aceita; a ferramenta não bloqueia
    por isso, pois comandos proprietários podem fugir da ISO 7816-4.
    """
    n = len(apdu)
    if n < 4:
        return "APDU com menos de 4 bytes (CLA INS P1 P2 são obrigatórios)."
    if n > MAX_SHORT_APDU:
        return f"APDU com {n} bytes excede o formato curto ({MAX_SHORT_APDU})."
    if n == 4 or n == 5:
        return None  # caso 1 / caso 2
    lc = apdu[4]
    if lc != 0 and n not in (5 + lc, 6 + lc):
        return (f"Lc={lc:02X} sugere {5 + lc} ou {6 + lc} bytes, mas a APDU tem {n}. "
                "(Pode ser intencional em comandos fora do padrão.)")
    return None


_SW_EXACT = {
    (0x90, 0x00): "Sucesso (comando executado)",
    (0x62, 0x00): "Aviso: sem informação adicional",
    (0x62, 0x82): "Aviso: fim de arquivo/registro antes de Le bytes",
    (0x63, 0x00): "Aviso: sem informação / falha de verificação",
    (0x65, 0x81): "Erro de memória",
    (0x67, 0x00): "Erro: tamanho (Lc/Le) incorreto",
    (0x68, 0x00): "Erro: função de CLA não suportada",
    (0x69, 0x82): "Erro: condição de segurança não satisfeita",
    (0x69, 0x83): "Erro: método de autenticação bloqueado",
    (0x69, 0x85): "Erro: condições de uso não satisfeitas",
    (0x69, 0x86): "Erro: comando não permitido (sem EF corrente)",
    (0x6A, 0x80): "Erro: dados incorretos no comando",
    (0x6A, 0x81): "Erro: função não suportada",
    (0x6A, 0x82): "Erro: arquivo/aplicação não encontrado",
    (0x6A, 0x86): "Erro: P1-P2 incorretos",
    (0x6A, 0x88): "Erro: dado referenciado não encontrado",
    (0x6B, 0x00): "Erro: parâmetros P1-P2 incorretos",
    (0x6D, 0x00): "Erro: INS não suportado/inválido",
    (0x6E, 0x00): "Erro: CLA não suportado",
    (0x6F, 0x00): "Erro: diagnóstico não especificado",
}


def describe_sw(sw1: int, sw2: int) -> str:
    """Descrição legível (ISO 7816-4) de SW1/SW2."""
    if (sw1, sw2) in _SW_EXACT:
        return _SW_EXACT[(sw1, sw2)]
    if sw1 == 0x61:
        return f"{sw2} byte(s) adicionais disponíveis (use GET RESPONSE)"
    if sw1 == 0x6C:
        return f"Le incorreto; reenviar com Le={sw2:02X}"
    if sw1 == 0x63 and (sw2 & 0xF0) == 0xC0:
        return f"Aviso: verificação falhou, {sw2 & 0x0F} tentativa(s) restante(s)"
    if sw1 == 0x62:
        return "Aviso: memória não alterada"
    if sw1 == 0x63:
        return "Aviso: memória alterada"
    if sw1 == 0x64:
        return "Erro de execução: memória não alterada"
    if sw1 == 0x67:
        return "Erro: tamanho incorreto"
    if sw1 == 0x69:
        return "Erro: comando não permitido"
    if sw1 == 0x6A:
        return "Erro: parâmetros incorretos"
    return "Código não catalogado (consulte a documentação do dispositivo)"


def split_response(raw: bytes):
    """Separa resposta bruta (dados || SW1 SW2) em (dados, sw1, sw2)."""
    if len(raw) < 2:
        raise APDUFormatError("Resposta com menos de 2 bytes: sem SW1/SW2.")
    return bytes(raw[:-2]), raw[-2], raw[-1]
