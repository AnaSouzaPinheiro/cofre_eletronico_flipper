"""
Diagnóstico da comunicação PC/SC <-> Flipper Zero (app CCID).

Não depende da interface gráfica nem do critério de autenticação. Não envia
nenhuma APDU por conta própria: só o que você digitar. Gera um log de
evidências (texto) em tools/evidencias/.

Uso:
  python tools/flipper_diag.py                    # modo interativo
  python tools/flipper_diag.py --list             # só lista os leitores
  python tools/flipper_diag.py -r 0 --atr         # conecta no leitor 0 e mostra o ATR
  python tools/flipper_diag.py -r flipper -a "00 A4 04 00" --follow-up
  python tools/flipper_diag.py --self-test        # testa o parser sem hardware
"""
import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.apdu import (APDUFormatError, describe_sw, format_hex, parse_hex,  # noqa: E402
                       validate_apdu)
from core.smartcard_reader import PCSCReader, ReaderError  # noqa: E402

EVID_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidencias")


class Evidence:
    """Espelha tudo que é impresso num arquivo .txt com horário."""

    def __init__(self, enabled=True):
        self.f = None
        if enabled:
            os.makedirs(EVID_DIR, exist_ok=True)
            self.path = os.path.join(EVID_DIR, datetime.now().strftime("diag_%Y%m%d_%H%M%S.txt"))
            self.f = open(self.path, "w", encoding="utf-8")

    def out(self, msg=""):
        print(msg)
        if self.f:
            self.f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
            self.f.flush()

    def close(self):
        if self.f:
            self.f.close()


def choose_reader(names, sel):
    """sel: None -> auto (Flipper se achar), índice numérico ou trecho do nome."""
    if not names:
        raise ReaderError("Nenhum leitor PC/SC encontrado.")
    if sel is None:
        fl = PCSCReader.find_flipper(names)
        if fl:
            return fl
        if len(names) == 1:
            return names[0]
        raise ReaderError("Vários leitores e nenhum parece o Flipper; use -r <índice|nome>.")
    if sel.isdigit():
        i = int(sel)
        if i >= len(names):
            raise ReaderError(f"Índice {i} inválido (há {len(names)} leitor(es)).")
        return names[i]
    m = [n for n in names if sel.lower() in n.lower()]
    if len(m) != 1:
        raise ReaderError(f"'{sel}' corresponde a {len(m)} leitores; seja mais específico.")
    return m[0]


def do_list(ev):
    names = PCSCReader.list_readers()
    ev.out(f"{len(names)} leitor(es) PC/SC:")
    for i, n in enumerate(names):
        mark = "  <- parece ser o Flipper (heurística)" if n == PCSCReader.find_flipper(names) else ""
        ev.out(f"  [{i}] {n}{mark}")
    return names


def send(ev, reader, text, follow_up):
    try:
        apdu = parse_hex(text)
    except APDUFormatError as e:
        ev.out(f"  APDU inválida: {e}")
        return
    warn = validate_apdu(apdu)
    if warn:
        ev.out(f"  Aviso: {warn}")
    ev.out(f"  TX ({len(apdu)} B): {format_hex(apdu)}")
    try:
        r = reader.transmit(apdu, follow_up=follow_up)
    except ReaderError as e:
        ev.out(f"  ERRO: {e}")
        ev.out("  (conexão marcada como perdida; reconecte com 'c')")
        return
    ev.out(f"  RX bruto  : {format_hex(r.data + bytes([r.sw1, r.sw2]))}")
    ev.out(f"  Dados     : {format_hex(r.data)}  ({len(r.data)} bytes)")
    ev.out(f"  SW1       : {r.sw1:02X}")
    ev.out(f"  SW2       : {r.sw2:02X}")
    ev.out(f"  Significado SW (ISO 7816-4, genérico): {describe_sw(r.sw1, r.sw2)}")
    if r.data:
        ascii_ = "".join(chr(b) if 32 <= b < 127 else "." for b in r.data)
        ev.out(f"  Dados ASCII: {ascii_}")


def connect(ev, name):
    rd = PCSCReader(name)
    rd.connect()
    ev.out(f"Conectado a: {name}")
    ev.out(f"ATR ({len(rd.atr)} B): {format_hex(rd.atr)}")
    return rd


HELP = """Comandos:
  l            listar leitores
  s <n|nome>   selecionar leitor e conectar
  c            (re)conectar ao leitor atual
  a            mostrar ATR
  t <hex>      transmitir APDU (ex.: t 00 A4 04 00)
  f            alternar tratamento de SW 61xx/6Cxx (atualmente: {fu})
  d            desconectar
  q            sair"""


def interactive(ev, follow_up):
    names, name, rd = [], None, None
    ev.out("Diagnóstico Flipper Zero / PC-SC. 'h' = ajuda.")
    try:
        names = do_list(ev)
    except ReaderError as e:
        ev.out(f"ERRO: {e}")
    while True:
        try:
            line = input("diag> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        cmd, _, arg = line.partition(" ")
        cmd = cmd.lower()
        try:
            if cmd == "q":
                break
            elif cmd == "h":
                ev.out(HELP.format(fu="ligado" if follow_up else "desligado"))
            elif cmd == "l":
                names = do_list(ev)
            elif cmd == "s":
                names = PCSCReader.list_readers()
                name = choose_reader(names, arg.strip() or None)
                if rd:
                    rd.disconnect()
                rd = connect(ev, name)
            elif cmd == "c":
                if not name:
                    ev.out("Selecione um leitor primeiro (s).")
                else:
                    if rd:
                        rd.disconnect()
                    rd = connect(ev, name)
            elif cmd == "a":
                if rd and rd.is_connected:
                    ev.out(f"ATR ({len(rd.atr)} B): {format_hex(rd.atr)}")
                else:
                    ev.out("Não conectado.")
            elif cmd == "t":
                if rd and rd.is_connected:
                    send(ev, rd, arg, follow_up)
                else:
                    ev.out("Não conectado (use s/c).")
            elif cmd == "f":
                follow_up = not follow_up
                ev.out(f"Tratamento 61xx/6Cxx: {'ligado' if follow_up else 'desligado'}")
            elif cmd == "d":
                if rd:
                    rd.disconnect()
                    ev.out("Desconectado.")
                rd = None
            else:
                ev.out("Comando desconhecido. 'h' para ajuda.")
        except ReaderError as e:
            ev.out(f"ERRO: {e}")
    if rd:
        rd.disconnect()
        ev.out("Desconectado.")


def self_test():
    assert parse_hex("ff ca 00 00") == b"\xff\xca\x00\x00"
    assert parse_hex("0xFF,0xCA") == b"\xff\xca"
    for bad in ("", "abc", "zz", "0"):
        try:
            parse_hex(bad)
        except APDUFormatError:
            continue
        raise AssertionError(f"deveria rejeitar {bad!r}")
    assert format_hex(b"\x90\x00") == "90 00" and format_hex(b"") == "(vazio)"
    assert validate_apdu(b"\x00\xA4") is not None
    assert validate_apdu(bytes.fromhex("00A40400")) is None
    assert "não encontrado" in describe_sw(0x6A, 0x82) and "GET RESPONSE" in describe_sw(0x61, 0x10)
    print("self-test OK (parser/formatador/SW; não toca em hardware)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="lista leitores e sai")
    ap.add_argument("-r", "--reader", help="índice ou parte do nome do leitor")
    ap.add_argument("--atr", action="store_true", help="conecta e mostra o ATR")
    ap.add_argument("-a", "--apdu", action="append", help="APDU em hex (pode repetir)")
    ap.add_argument("--follow-up", action="store_true", help="trata SW 61xx (GET RESPONSE) e 6Cxx")
    ap.add_argument("--no-log", action="store_true", help="não grava arquivo de evidências")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return self_test()

    ev = Evidence(enabled=not a.no_log)
    rd = None
    try:
        if ev.f:
            ev.out(f"Evidências em: {ev.path}")
        if a.list:
            do_list(ev)
        elif a.atr or a.apdu:
            name = choose_reader(PCSCReader.list_readers(), a.reader)
            rd = connect(ev, name)
            for text in a.apdu or []:
                send(ev, rd, text, a.follow_up)
        else:
            interactive(ev, a.follow_up)
    except ReaderError as e:
        ev.out(f"ERRO: {e}")
        return 1
    finally:
        if rd:
            rd.disconnect()
            ev.out("Desconectado.")
        ev.close()


if __name__ == "__main__":
    sys.exit(main())
