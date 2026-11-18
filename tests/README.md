# Testes automatizados de segurança (Parte 4)

Execute a partir da pasta raiz do projeto (com o ambiente virtual):

```
.venv/bin/python tests/run_tests.py
```

No Windows: `.venv\Scripts\python tests\run_tests.py`.

O executor descobre automaticamente todos os arquivos `test_*.py` e gera:

- `logs/security_test_summary.csv`: uma linha por teste, com situação e observação.
- `logs/security_test_access_log.csv`: uma linha por tentativa de autenticação executada pelos testes
  (separado de `logs/access_log.csv`, que é o registro real do cofre).

Os testes T01–T17 cobrem autenticação básica, repetição, ATR, respostas APDU e falhas de comunicação. Os testes T18–T30 ampliam os casos de borda: resposta sem validação de dados, ATR vazio, repetição em novas sessões, desconexão após sucesso, tamanhos de resposta, bytes extras, SW1/SW2, dados malformados e APDU vazio.

**Importante:** `APROVADO` significa que o comportamento observado correspondeu à expectativa codificada no teste. Alguns testes são diagnósticos e passam justamente quando confirmam um comportamento vulnerável. Consulte a descrição de cada teste e o campo `observacao`.

Todos os testes usam leitores simulados/controlados em memória. Eles não capturam tráfego RF, não clonam cartões e não testam um dispositivo físico.

Análise e recomendações: [`docs/TESTES_DE_SEGURANCA.md`](../docs/TESTES_DE_SEGURANCA.md).
