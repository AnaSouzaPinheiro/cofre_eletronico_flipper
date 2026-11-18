"""Executor simples: roda a suíte e grava resumo CSV em logs/security_test_summary.csv."""
import csv
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402

# Os testes não devem misturar tentativas simuladas no registro real do cofre.
config.LOG_FILE = "logs/security_test_access_log.csv"

class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = []
    def addSuccess(self, test):
        super().addSuccess(test)
        self.rows.append((test.id(), "APROVADO", "Comportamento conforme a expectativa do teste"))
    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.rows.append((test.id(), "FALHOU", self._exc_info_to_string(err, test).splitlines()[-1]))
    def addError(self, test, err):
        super().addError(test, err)
        self.rows.append((test.id(), "ERRO", self._exc_info_to_string(err, test).splitlines()[-1]))

class Runner(unittest.TextTestRunner):
    resultclass = Result

suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern="test_*.py")
runner = Runner(verbosity=2)
result = runner.run(suite)
log_dir = ROOT / "logs"
log_dir.mkdir(exist_ok=True)
out = log_dir / "security_test_summary.csv"
with out.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow(["data_hora", "teste", "resultado", "observacao"])
    stamp = datetime.now().isoformat(timespec="seconds")
    for test, status, note in result.rows:
        writer.writerow([stamp, test, status, note])
print(f"\nResumo CSV salvo em: {out}")
print(f"Total: {result.testsRun} | Falhas: {len(result.failures)} | Erros: {len(result.errors)}")
sys.exit(0 if result.wasSuccessful() else 1)
