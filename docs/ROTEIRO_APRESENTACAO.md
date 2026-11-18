# Roteiro da apresentação

Slides: 12, na ordem abaixo. As falas detalhadas estão nas notas de cada slide.

| # | Slide | Quem apresenta | Pontos principais |
|---|---|---|---|
| 1 | Capa | [nome] | Grupo e tema; experimento acadêmico |
| 2 | Problema | [nome] | Credencial fixa, cifra fraca, relay |
| 3 | Objetivo | [nome] | Simular, analisar, propor |
| 4 | Conceitos | [nome] | Cartão inteligente, ATR, CCID, APDU |
| 5 | Arquitetura | [nome] | Flipper → PC/SC → Python → cofre; fail-closed |
| 6 | Ferramentas | [nome] | Python, PySide6, PySCard, diagnóstico, testes |
| 7 | Demonstração | [nome] | **Demo ao vivo** (abaixo) |
| 8 | Resultados com o Flipper | [nome] | Tabela de APDUs; `01 01 00 00` → `90 00` |
| 9 | Testes | [nome] | 30 testes: 23 defesas, 7 vulnerabilidades |
| 10 | Riscos | [nome] | Replay, tentativas sem limite, mitigações |
| 11 | Conclusão | [nome] | O que mostramos e limitações |
| 12 | Referências | [nome] | Perguntas |

## Antes de começar (checklist)

- [ ] Flipper carregado, app CCID instalado; cabo USB **de dados** testado.
- [ ] Computador com `pcscd` ativo (Linux) ou serviço Cartão Inteligente (Windows).
- [ ] `.venv` criado e `.venv/bin/python main.py` abrindo a janela.
- [ ] Abrir o app CCID e conferir com `pcsc_scan` (ou `.venv/bin/python tools/flipper_diag.py --list`) que o leitor aparece.
- [ ] Capturas de `docs/evidencias/` abertas numa aba, para o plano B.

## Demo ao vivo (slide 7, ~2 min)

1. Mostrar o cofre **BLOQUEADO** e o modo de simulação desmarcado.
2. **Detectar leitores** → aparece `Generic USB Smart Card Reader`. **Conectar** → ATR `3B00`.
3. **Iniciar autenticação** → AGUARDANDO → **ACESSO LIBERADO**. Mostrar o registro "Autenticação ACEITO / REAL".
4. **Bloquear cofre**. No Flipper, fechar o app CCID. **Iniciar autenticação** de novo → **BLOQUEADO** (falha de comunicação, fail-closed).
5. Frase de transição para o slide 8: "Funcionou, mas a resposta que abre o cofre é sempre a mesma. Vamos ver o porquê."

## Plano B

- **Flipper não aparece como leitor:** reabrir o app CCID; trocar cabo/porta. Se não resolver em 30 s, seguir sem ele.
- **Sem hardware:** marcar **Modo de simulação**, Conectar, Iniciar autenticação (cenários válido, inválido e falha de comunicação) e mostrar as capturas reais de `docs/evidencias/` (`tela_2_liberado.png`, `tela_negativo_sem_dispositivo.png`).
- **Aplicação não abre:** mostrar só as capturas e rodar `.venv/bin/python tests/run_tests.py` no terminal (30/30).

## Perguntas prováveis

- **Por que o critério é tão fraco?** O app CCID não guarda chave nem dados próprios; a única coisa verificável é o `90 00`. Isso é o próprio achado do trabalho.
- **Como corrigir?** Challenge-response: o cofre manda um número aleatório e o cartão responde com um HMAC usando uma chave secreta; exige um cartão ou app com chave.
- **Vocês clonaram algum cartão?** Não. Todos os testes foram no protótipo e em dispositivos próprios; os testes de segurança usam leitores simulados.
