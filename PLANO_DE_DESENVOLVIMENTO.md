# Plano de Desenvolvimento e Acompanhamento

Última atualização: 17/11/2026. Mantenha este arquivo atualizado a cada entrega (um commit por atualização de status).

**Legenda:** `[x]` concluído e validado · `[~]` parcialmente concluído · `[ ]` pendente.
Para cada item distinguimos três níveis de evidência, e **só o último conta como "concluído" para o que depende do Flipper**:

| Nível | Significado |
|---|---|
| **IMPL** | Código/documento existe no repositório |
| **MOCK** | Testado sem hardware (parser, mocks, interface em simulação) |
| **HW** | Validado com o Flipper Zero físico |

> Regra: este documento registra apenas o que há evidência para afirmar. Onde não encontramos evidência no repositório, está marcado como pendente — isso significa "sem evidência", não necessariamente "não feito".

## Visão geral
| # | Parte | Responsável | Status | IMPL | MOCK | HW |
|---|---|---|---|---|---|---|
| 1 | Flipper Zero e CCID | Ulisses | `[ ]` sem evidências | — | — | não |
| 2 | Interface e lógica do cofre | Fernanda | `[~]` | sim | sim (simulação) | não |
| 3 | Comunicação APDU/PC/SC | Ana | `[~]` | sim | sim | **não** |
| 4 | Testes de vulnerabilidade | a definir | `[ ]` | não | — | não |
| 5 | Fundamentação teórica | a definir | `[ ]` | não | — | — |
| 6 | Integração e apresentação | Andrigo | `[ ]` | só instruções de execução (README) | — | não |

---

## Parte 1 — Flipper Zero e CCID (Ulisses) — `[ ]`
**Escopo:** instalar/configurar o app CCID, conexão USB, reconhecimento do leitor, testes de APDU no dispositivo.

**Já produzido:** nenhum artefato no repositório (sem logs de teste, ATR registrado, nem lista de APDUs).

**Testado:** nada registrado.

**Pendente:**
- [ ] Instalar/abrir o app CCID e conectar por USB; registrar versão do app e do firmware.
- [ ] Confirmar que o Windows enxerga o leitor (`Get-PnpDevice -Class SmartCardReader`, `certutil -scinfo`); anotar VID/PID e nome do leitor.
- [ ] Registrar o **ATR** (em ≥3 conexões) e se há "cartão presente".
- [ ] Descobrir, **por teste**, quais APDUs o app aceita e o que responde (listar também as recusadas).
- [ ] Entregar a Ana/Fernanda os valores para o `REAL_CRITERION`.

**Dependências:** é pré-requisito das Partes 3 (validação), 4 e 6.

---

## Parte 2 — Interface e lógica do cofre (Fernanda) — `[~]`
**IMPL (`main.py`, `ui/`, `core/vault_state.py`, `core/access_log.py`, `core/authenticator.py`, `core/criterion.py`, `config.py`):**
- janela PySide6 com cofre animado, estados BLOQUEADO / AGUARDANDO / LIBERADO e bloqueio automático;
- Authenticator fail-closed (negado por padrão; critério real não configurado = negado);
- modo simulação com faixa de aviso e critério próprio; registro na tela e em CSV.

**MOCK (executados na revisão de integração, offscreen):** simulação (válido/inválido/falha de comunicação), seleção do critério pelo leitor, perda de conexão, exceção no worker, rótulo de modo no log, fechamento da janela.
Ressalva: esses scripts ainda **não estão versionados** (ver pendências da Parte 3).

**HW:** a janela **não** foi exercitada com o Flipper.

**Pendente:**
- [ ] Preencher `REAL_CRITERION` só com evidências da Parte 1 (**não fazer antes**).
- [ ] Decidir sobre critério só de ATR (ver "Riscos em aberto", item 1).
- [ ] Capturas de tela em modo real (aceito/rejeitado) para o relatório.

**Dependências:** Parte 1 (valores reais), Parte 3 (transporte).

---

## Parte 3 — Comunicação APDU/PC/SC (Ana) — `[~]`

### Estado atual
| Item | IMPL | MOCK | HW |
|---|---|---|---|
| Listar leitores (`PCSCReader.list_readers`) | sim | não* | não |
| Selecionar Flipper (`find_flipper`, heurística pelo nome "flipper") | sim | não | não |
| Conectar + ATR | sim | simulado | não |
| Erro "sem cartão" (`NoCardException`) | sim | não | não |
| Transmitir APDU, separar dados e SW1/SW2 | sim | sim | não |
| `follow_up` (61xx GET RESPONSE / 6Cxx), opcional, desligado por padrão | sim | sim | não |
| Falha de transmissão ⇒ `is_connected=False` ⇒ acesso negado | sim | sim | não |
| Parser/formatador hex, validação, descrição de SW (`core/apdu.py`) | sim | sim (`--self-test`) | n/a |
| Diagnóstico `tools/flipper_diag.py` (listar, conectar, ATR, APDU, log de evidências) | sim | parcial (só `--self-test`) | não |
| Integração na UI (critério pelo leitor, perda de conexão, worker, fechamento) | sim | sim | não |

\* `list_readers` não tem teste automatizado, mas foi executado de verdade pelo diagnóstico num Windows sem leitor: devolveu `ReaderError` com o erro `0x8010001D` (ver "Dependem do hardware"). Isso **não** valida a listagem com leitor presente.

O que **foi** testado: `--self-test` do parser/formatador/SW; `PCSCReader` com conexão simulada (mock) cobrindo resposta normal, 61xx com e sem `follow_up`, 6Cxx e erro de transmissão; Authenticator fail-closed (erro de comunicação, critério vazio); simulação; interface offscreen (cenários acima).
**Mocks não comprovam funcionamento com hardware.** O comportamento real do pyscard/driver/Flipper permanece desconhecido.

### Revisão — bugs, lacunas e riscos (não corrigidos nesta etapa)
**Dependem do código (corrigíveis sem o Flipper):**
1. **Mensagem de erro de `list_readers` pode ser mais informativa:** em erro de contexto PC/SC sugere apenas "verifique o serviço Cartão Inteligente". `0x8010001D` (`SCARD_E_NO_SERVICE`) significa que o Gerenciador de Recursos não está em execução; a mensagem poderia citar o código e orientar o diagnóstico (ver "Ambiente Windows"), sem afirmar a causa.
2. **Diagnóstico não escolhe protocolo:** `connect()` usa o padrão (T=0|T=1). Falta opção `--protocol T0|T1|raw` para o caso de a conexão falhar ou o ATR variar.
3. **Evidências incompletas no log:** o arquivo não registra versão do pyscard/Python/Windows, lista completa de leitores nem tempo de resposta; a estabilidade do ATR exige repetir a conexão manualmente (falta `--repeat N`).
4. **Sem testes versionados:** os testes de mock e de UI foram executados fora do repositório; criar `tests/` (parser, `PCSCReader` com mock, Authenticator, UI offscreen).
5. **Conexão e detecção na thread da UI:** `SCardConnect` com dispositivo que não responde pode congelar a janela (conhecido, adiado).
6. **Sem timeout de transmissão:** o PC/SC não oferece timeout em `transmit`; um dispositivo travado pode prender o worker (a UI fica em AGUARDANDO). Precisa ser observado em teste real; mitigação possível é limitar a espera no lado da aplicação.
7. **`.gitignore` não cobria `logs/*.csv`** (registro de tentativas); ajustado nesta entrega.
8. **Comentários `TODO` em `smartcard_reader.py`** ainda mencionam tratamento de 61xx/6C que já existe de forma opcional.

**Dependem do hardware (não resolvíveis sem o Flipper):**
- Nome real do leitor e se `find_flipper` o seleciona; protocolo (T=0/T=1) e ATR (valor e estabilidade);
- se existe "cartão presente" quando o app CCID está aberto;
- quais APDUs são aceitas e se há 61xx/6Cxx; se o driver do Windows já trata GET RESPONSE;
- comportamento ao remover o USB no meio de uma operação; fechamento da janela durante autenticação;
- **o que o `readers()` faz com leitor conectado e serviço ativo** (listagem real). Já observado (4 execuções de `flipper_diag.py --list` em 17/11/2026, sem Flipper): o pyscard levanta `Failed to establish context: O Gerenciador de Recursos do Cartão Inteligente não está em execução. (0x8010001D)`. Ou seja, nessa condição o `list_readers` devolve `ReaderError` (não lista vazia) — o tratamento de erro funcionou como previsto; falta ver o caso com leitor e serviço ativos.

### Para considerar a Parte 3 concluída
- [ ] Itens de código acima tratados (1–4 no mínimo) e `tests/` versionado.
- [ ] `flipper_diag.py` executado com o Flipper: `--list`, ATR (≥3 conexões), APDUs reais testadas, log guardado em `tools/evidencias/`.
- [ ] Aplicação em modo real: conectar, ATR exibido, autenticação rejeitada (critério vazio) e depois aceita/rejeitada com `REAL_CRITERION` baseado em evidências.
- [ ] Cenários de falha reais: USB removido, app CCID fechado, serviço PC/SC indisponível — todos resultando em acesso **negado**.
- [ ] Evidências organizadas para o relatório (ver lista no fim).

### Ambiente Windows (máquina da Ana, 17/11/2026, **sem o Flipper conectado**)
Consultas somente de leitura. Esta é observação de ambiente da Parte 3, **não** evidência da Parte 1.

**Fatos observados:**
- `SCardEstablishContext` retornou `0x8010001D` (`SCARD_E_NO_SERVICE`: o Gerenciador de Recursos do Cartão Inteligente não está em execução), nos escopos USER e SYSTEM; `certutil -scinfo` falhou com o mesmo código; `SCardAccessStartedEvent` não sinalizou em 10 s.
- Nas consultas de 17/11: `SCardSvr` e `ScDeviceEnum` parados (tipo Manual); `SCardSvr` com gatilhos de início (chegada de interface de dispositivo e eventos RPC); `PlugPlay` e `RpcSs` em execução.
- Não havia dispositivo da classe SmartCardReader, nem registro de VID_0483, nessa instalação do Windows.
- Logs `Microsoft-Windows-SmartCard-*` vazios; sem eventos de falha do serviço no System consultado.
- O estado "Running" de `SCardSvr` relatado em outras verificações **não** foi reproduzido nas consultas de 17/11.

**Hipóteses (não comprovadas):**
1. Sem leitor CCID visível, o serviço não é iniciado (ou para sozinho) e o `0x8010001D` é consequência.
2. O Flipper conectado não expõe a interface CCID (app fechado, cabo só de carga, driver não associado).
3. Política ou configuração do Windows bloqueando o serviço (sem indício até agora).

**Como confirmar (antes de qualquer reparo):** repetir as consultas com o Flipper conectado e o app CCID aberto — `Get-PnpDevice -Class SmartCardReader`, `sc query SCardSvr`, o teste de `SCardAccessStartedEvent`, `certutil -scinfo`. Resultado esperado só como critério de decisão: se o leitor aparecer e o serviço subir, a hipótese 1 fica sustentada.

**Dependências:** Parte 1 (dispositivo), Parte 2 (UI/Authenticator).

---

## Parte 4 — Testes de vulnerabilidade — `[ ]`
**IMPL/MOCK/HW:** nenhum teste ou relatório no repositório.

**Hipóteses de análise já levantadas na revisão (a testar, não são resultados):**
- critério estático ⇒ **replay** / emulação por outro dispositivo que devolva a mesma resposta;
- critério só com ATR (sem APDU) usa o ATR guardado na conexão: não comprova presença do dispositivo no momento da autenticação (decisão em aberto);
- respostas inesperadas (SW de erro, dados diferentes, resposta vazia, tamanho longo) e falhas de comunicação — a aplicação deve sempre negar (comprovado em mock; falta hardware);
- ausência de timeout em `transmit`.

**Pendente:**
- [ ] Definir plano de testes (casos, método, critério de sucesso) e executar **somente no protótipo acadêmico**.
- [ ] Documentar riscos e mitigações (ex.: challenge-response — não implementado).

**Dependências:** Partes 1, 2 e 3 funcionando com o Flipper.

---

## Parte 5 — Fundamentação teórica — `[ ]`
**Produzido:** nada no repositório.
**Pendente:**
- [ ] RFID e NFC, CCID, ISO 7816 (APDU, ATR, SW) — o README e `core/apdu.py` mencionam ISO 7816-4 apenas como referência, não como fundamentação.
- [ ] Referências bibliográficas.

**Dependências:** serve de base para o relatório e os slides (Parte 6).

---

## Parte 6 — Integração e apresentação (Andrigo) — `[ ]`
**Produzido:** instruções de instalação/execução no README e o rascunho dos slides (11 slides): [abrir e editar](https://claude.ai/artifact/EoGnfAVoMB5m536WKWSWSy). Os resultados de hardware nos slides ainda estão como "A testar".
**Pendente:**
- [ ] Roteiro da demonstração (simulação e real) e plano B caso o Flipper/PC/SC falhe.
- [ ] Integração final e ensaio; slides.
- [ ] Verificar instalação limpa no Windows (venv, `pip install -r requirements.txt`).

**Dependências:** todas as partes; demonstração real exige a Parte 1 concluída.

---

## Riscos em aberto
1. **Critério só de ATR** não prova presença no momento da autenticação. Exigir APDU no critério real, ou reconsultar o ATR, é decisão da equipe (não alterado).
2. **Ambiente Windows:** o PC/SC respondeu `0x8010001D` (`SCARD_E_NO_SERVICE`) na máquina da Ana, sem o Flipper conectado. Se a ausência do Flipper é a causa é **hipótese**; confirmar com o Flipper conectado antes de qualquer reparo no sistema.
3. **Respostas reais desconhecidas:** nenhum comando APDU foi confirmado no Flipper; não preencher `REAL_CRITERION` sem evidência.

## Evidências a coletar para o relatório
- `Get-PnpDevice -Class SmartCardReader` e `certutil -scinfo` com o Flipper conectado; nome do leitor, VID/PID.
- ATR em ≥3 conexões; comportamento sem "cartão".
- Para cada APDU testada: TX, RX bruto, dados, SW1, SW2 (arquivos de `tools/evidencias/`), inclusive as recusadas.
- Capturas da aplicação em modo real (aceito e rejeitado) e linhas de `logs/access_log.csv`.
- Cenários de falha (USB removido, app fechado, serviço parado) e confirmação de que o cofre permaneceu bloqueado.
- Justificativa do critério real escolhido (dados, SW, ATR) e resultados dos testes de vulnerabilidade.

## Registro de atualizações
| Data | Alteração |
|---|---|
| 17/11/2026 | Criação do plano; revisão da Parte 3; README ampliado; `.gitignore` cobre `logs/*.csv`. |
