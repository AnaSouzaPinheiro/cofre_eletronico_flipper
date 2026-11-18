# Fundamentação Teórica — Cofre Eletrônico com Flipper Zero (CCID, PC/SC, ISO 7816, APDU)

**Parte 5 — Pesquisa e fundamentação (Lucas)**

Base conceitual do experimento descrito no `README.md` e no `PLANO_DE_DESENVOLVIMENTO.md`. Onde o texto fala do projeto, cita o arquivo do repositório correspondente. O comportamento do Flipper físico foi verificado em 18/11/2026 (seção 7); o que não tem evidência está marcado como tal, seguindo a regra do plano ("só afirmar o que há evidência").

> Uso educacional: os testes devem ser feitos apenas neste protótipo acadêmico e em dispositivos próprios.

---

## 1. O projeto e onde cada tecnologia entra

O experimento é um cofre eletrônico que só libera quando a resposta do dispositivo bate exatamente com um critério configurado (`config.py`). Qualquer outra situação mantém o cofre **bloqueado** (fail-closed).

```
 Flipper Zero (app CCID)
        │  USB (CCID)                      ← classe USB de leitor de cartão
        ▼
 Windows: driver CCID ─► serviço PC/SC (SCardSvr / winscard)   ← API padrão de cartões
        │
        ▼
 PySCard ─► core/smartcard_reader.py       ← transmite APDUs (ISO 7816-4)
                 ▼
          core/authenticator.py            ← decide (compara com o critério)
                 ▼
          core/vault_state.py ─► ui/ + logs/access_log.csv
```

| Camada | Tecnologia | Onde aparece no projeto |
|---|---|---|
| Rádio (contexto) | RFID / NFC | Origem do modelo de cartão sem contato; **não é o canal usado aqui** (o canal é USB) |
| Cartão | ISO/IEC 7816 (ATR, T=0/T=1) | ATR lido em `PCSCReader.connect` e comparado em `Authenticator` |
| Comandos | APDU (ISO/IEC 7816-4) | `core/apdu.py`, `PCSCReader.transmit`, `tools/flipper_diag.py` |
| Transporte PC–dispositivo | USB CCID | Flipper se apresenta como leitor de cartão |
| API no PC | PC/SC (`winscard`, PySCard) | `core/smartcard_reader.py` |

**Mensagem central:** o cofre trata o Flipper como se fosse um cartão inteligente falando APDU por um leitor CCID; todas as fragilidades do experimento vêm de como esse "cartão" é verificado.

---

## 2. RFID

Identificação por radiofrequência: um leitor gera um campo e uma etiqueta responde com um identificador ou dados. Tags passivas são alimentadas pelo campo (acoplamento indutivo em LF/HF) e respondem por modulação de carga.

| Faixa | Frequência | Alcance típico | Exemplos | Segurança |
|---|---|---|---|---|
| LF | 125–134 kHz | até ~10 cm | EM4100, HID Prox | Só ID fixo, **sem autenticação** |
| HF | 13,56 MHz | até ~10 cm | MIFARE, DESFire, FeliCa, NFC | Varia de nenhuma a forte |
| UHF | 860–960 MHz | metros | Logística | Fora do foco |

Conceito útil: o **UID** é um identificador de fábrica, não um segredo.
Relação com o projeto: o cofre usa a mesma lógica de "apresentar credencial e ser verificado", mas por USB; o estudo de RFID serve de contexto para entender por que credenciais estáticas são frágeis.

---

## 3. NFC

Conjunto de padrões sobre RFID de 13,56 MHz, alcance de poucos centímetros: ISO/IEC 14443 (A/B), FeliCa, ISO/IEC 18092, certificado pelo NFC Forum.

- **Modos:** leitor/gravador, emulação de cartão, ponto a ponto.
- **Camada de aplicação:** em cartões ISO 14443-4 (ISO-DEP) trafegam **APDUs de ISO 7816-4**. Ou seja, o mesmo formato de comando vale por contato, por NFC e, no projeto, dentro de mensagens CCID sobre USB.

---

## 4. ISO/IEC 7816

Família de normas para cartões com chip.

| Parte | Assunto |
|---|---|
| 1 e 2 | Características físicas e contatos |
| **3** | Sinais elétricos e protocolos de transmissão (T=0 por byte, T=1 por bloco); **ATR** |
| **4** | Organização, segurança e comandos de intercâmbio: **APDU**, sistema de arquivos, secure messaging |

Edições consultadas: **7816-3, 3ª ed. (2006)** e **7816-4, 4ª ed. (2020)**.

**ATR (Answer To Reset):** primeira resposta do cartão ao ser energizado/reiniciado; informa protocolo(s) e parâmetros. No projeto, `PCSCReader.connect()` guarda o ATR e o `Authenticator` pode compará-lo com `expected_atr`.

**Protocolo T=0 / T=1:** o `connect()` usa o padrão do PySCard (T=0|T=1). Se os testes exigirem, o plano prevê fixar o protocolo (`TODO(equipe-flipper)`).

Outros conceitos: MF/DF/EF (sistema de arquivos), AID (identificador de aplicação, usado no SELECT), secure messaging (APDU autenticada/cifrada).

---

## 5. APDU

**Application Protocol Data Unit** (ISO/IEC 7816-4): unidade de mensagem terminal ↔ cartão, em modo mestre/escravo.

**Comando (C-APDU):** `CLA INS P1 P2 [Lc dados] [Le]`

| Campo | Tamanho | Função |
|---|---|---|
| CLA | 1 B | Classe |
| INS | 1 B | Instrução (ex.: `A4` SELECT, `B0` READ BINARY, `C0` GET RESPONSE) |
| P1, P2 | 1 B cada | Parâmetros |
| Lc / Data | 0–1(3) B / Lc B | Tamanho e dados enviados |
| Le | 0–1(3) B | Tamanho máximo esperado |

**Resposta (R-APDU):** `dados + SW1 SW2`.

| SW1 SW2 | Significado (conforme `core/apdu.py`) |
|---|---|
| `90 00` | Sucesso |
| `61 XX` | XX bytes adicionais: usar GET RESPONSE |
| `6C XX` | Le incorreto: reenviar com Le = XX |
| `63 CX` | Verificação falhou, X tentativas restantes |
| `69 82` | Condição de segurança não satisfeita |
| `6A 82` | Arquivo/aplicação não encontrado |
| `6D 00` / `6E 00` | INS / CLA não suportado |

**Como o projeto trata isso**
- `parse_hex` / `format_hex` convertem texto ↔ bytes; `validate_apdu` só **avisa** sobre estrutura (curto/longo, Lc incoerente), sem bloquear, porque comandos proprietários podem fugir do padrão.
- `split_response` separa dados e SW1/SW2.
- `PCSCReader.transmit(follow_up=True)` trata `61xx` (GET RESPONSE) e `6Cxx` (reenvio com Le correto), **opcional e desligado por padrão**, com limite de 16 iterações para evitar laço infinito.

**Exemplo de formato** (ilustração, **não** sabemos se o Flipper aceita): `00 A4 04 00` = SELECT por nome de aplicação (CLA=00, INS=A4, P1=04, P2=00). O próprio `flipper_diag.py` e o README avisam que é só exemplo de formato.

Observação: a simulação usa APDU fictícia (`b"SIM-REQ"`), que não segue o formato ISO 7816-4. Isso é aceitável porque o leitor simulado é falso, e `validate_apdu` emitiria apenas um aviso.

---

## 6. CCID e PC/SC

**CCID (Chip Card Interface Device):** classe USB (`0x0B`) definida pelo USB-IF que padroniza leitores de cartão com chip, permitindo um driver genérico no sistema operacional.

- Endpoints: Bulk-OUT (comandos), Bulk-IN (respostas), Interrupt-IN opcional (inserção/remoção).
- Mensagens principais: `PC_to_RDR_IccPowerOn` (devolve o ATR), `PC_to_RDR_XfrBlock` (**transporta o APDU**), `PC_to_RDR_IccPowerOff`, `RDR_to_PC_DataBlock`, `RDR_to_PC_SlotStatus`.

**PC/SC:** API padronizada (PC/SC Workgroup). No Windows, `winscard.dll` e o serviço **Cartão Inteligente (SCardSvr)**; no Linux, `pcsc-lite`. Em Python, **PySCard** expõe `readers()`, `createConnection()`, `connect()`, `getATR()`, `transmit()`.

```
Aplicação -> PySCard -> winscard/SCardSvr -> driver CCID -> USB -> Flipper (app CCID)
            transmit(APDU)
```

**Erro observado no repositório (máquina sem Flipper):** `0x8010001D` = `SCARD_E_NO_SERVICE` (Gerenciador de Recursos do Cartão Inteligente não está em execução). O plano registra que `SCardSvr` está configurado com início por gatilho (chegada de dispositivo) e levanta a hipótese de que sem leitor visível o serviço não sobe. No Linux o comportamento é análogo: o `pcscd` é ativado por socket e só lista o leitor quando o app CCID está aberto no Flipper (sem o app, o Flipper aparece apenas como porta serial).

---

## 7. Flipper Zero

**Hardware geral (documentação oficial):** microcontrolador STM32WB55 (Cortex-M4 + M0+ para BLE); NFC 13,56 MHz (ST25R3916); RFID 125 kHz; Sub-GHz (CC1101); infravermelho; iButton; GPIO; USB; microSD. O firmware é de código aberto e permite aplicativos externos.

**Papel no projeto (o que importa aqui):** o README define que o Flipper roda o **aplicativo comunitário CCID** e é apresentado ao computador como **leitor/cartão USB de cartão inteligente**. Ou seja, o caminho usado é **USB/CCID**, não o rádio NFC/RFID.

**Verificação com o Flipper físico (18/11/2026, Linux com `pcscd`):** com o app CCID aberto, o computador vê o leitor `Generic USB Smart Card Reader` com ATR `3B 00` (ATR mínimo, sem bytes históricos). Os comandos ISO comuns (classes `00`, `80`, `FF`) recebem `6E 00` (classe não suportada); a classe `01` é aceita, e `01 01 00 00` recebe `90 00` sem dados. Esses valores formam o critério real em `config.py`. Como a resposta é fixa e não depende de segredo, o app CCID ilustra exatamente a **credencial estática** discutida na seção de vulnerabilidades. Evidências em `docs/evidencias/` e detalhes em `PLANO_DE_DESENVOLVIMENTO.md` (Parte 3, "Validação com hardware").

**Capacidades gerais do Flipper em RFID/NFC (para contexto da discussão, fora do canal USB):** lê e emula tags LF (EM4100, HID Prox), lê MIFARE Classic/Ultralight/NTAG e tenta chaves conhecidas, **não clona** cartões com criptografia forte (ex.: DESFire, EMV) por não ter acesso à chave secreta. Limitações: alcance de poucos cm e fidelidade de emulação variável.

---

## 8. Modelo de autenticação do cofre

Resumo do que `core/authenticator.py` e `core/criterion.py` implementam:

1. **Fail-closed:** sem dispositivo, critério não configurado, ATR/SW/dados diferentes, erro de comunicação ou exceção inesperada → **negado**.
2. **Critério** (`Criterion`): `apdu`, `expected_data`, `expected_sw` (padrão `90 00`) e `expected_atr`. É "configurado" se há ATR esperado **ou** (APDU e dados esperados).
3. **Comparação** de ATR e dados com `hmac.compare_digest` (tempo constante), evitando vazar informação por tempo de comparação.
4. **Falha de transmissão** marca `is_connected=False`, exigindo reconexão.
5. **Máquina de estados** BLOQUEADO → AGUARDANDO → LIBERADO, com bloqueio automático (`AUTO_LOCK_SECONDS`) e log CSV de todas as tentativas.

O modelo é de **verificação estática**: o terminal envia sempre a mesma APDU e espera sempre a mesma resposta. É isso que o experimento quer analisar.

---

## 9. Vulnerabilidades

### 9.1 Do esquema do cofre (ligadas à Parte 4 do plano; são hipóteses a testar, não resultados)

| Vulnerabilidade | Por que ocorre no projeto | Mitigação |
|---|---|---|
| **Replay / emulação** | Critério estático: qualquer dispositivo que devolva os mesmos bytes (mesma APDU → mesma resposta) é aceito | **Challenge-response**: cartão responde a um desafio aleatório com uma chave; resposta nunca se repete. Não implementado; `authenticator.py` é o ponto de extensão |
| **Critério só de ATR** | O ATR é guardado na conexão; não prova presença do dispositivo no momento da autenticação, e é público | Exigir APDU no critério real ou reconsultar o ATR (decisão em aberto no plano) |
| **Sem segredo no dispositivo** | A "credencial" é um valor fixo, equivalente a um ID | Chave secreta no cartão + autenticação mútua |
| **Sem timeout em `transmit`** | PC/SC não oferece timeout; dispositivo travado prende o worker | Limitar espera no lado da aplicação |
| **Respostas inesperadas** | SW de erro, dados diferentes, vazio, muito longo | Já tratadas como negado (comprovado em mock; falta hardware) |
| **Conexão/detecção na thread da UI** | `SCardConnect` com dispositivo que não responde pode congelar a janela | Mover para worker |

Defesa já presente: fail-closed e comparação em tempo constante.

### 9.2 Em autenticação por cartões em geral (contexto)

| Vulnerabilidade | Exemplo | Relação com o projeto |
|---|---|---|
| ID estático sem autenticação | EM4100, HID Prox | Mesmo problema do critério estático |
| Cifra proprietária fraca | CRYPTO1 (MIFARE Classic) | Mostra o risco de segurança por obscuridade |
| Chaves padrão/compartilhadas | `FFFFFFFFFFFF` em instalações | Critério único para todos os usuários |
| **Relay** | Pagamento por aproximação, chaves veiculares | Um dispositivo intermediário repassa as APDUs; o cofre não detecta distância |
| Replay | Protocolos sem aleatório fresco | Idem 9.1 |
| Canal lateral | DESFire original (MF3ICD40) | Fora do escopo, mas ilustra ataque ao hardware |
| Skimming | Leitura não autorizada de cartões HF | Fora do escopo (canal USB) |

**Linha do tempo:** 2008 engenharia reversa do CRYPTO1 (Nohl et al.) e ataque prático (Garcia et al.); 2011 canal lateral no DESFire (Oswald & Paar); 2015 ataques ciphertext-only a MIFARE Classic endurecido (Meijer & Verdult); relay em chaves veiculares (Francillon et al., 2011).

**Princípio de Kerckhoffs:** a segurança deve estar na chave e na criptografia aberta, não no sigilo do protocolo.

---

## 10. Roteiro sugerido de slides (sincronizar com a Parte 6)

1. Objetivo e arquitetura do cofre (diagrama da seção 1)
2. RFID e NFC (contexto)
3. ISO 7816: ATR e protocolos
4. APDU: estrutura, SW, exemplo
5. CCID e PC/SC: o caminho PC → Flipper
6. Flipper Zero e o app CCID (o que sabemos / o que testamos)
7. Modelo de autenticação e fail-closed
8. Demonstração (simulação e real)
9. Vulnerabilidades: critério estático, replay, relay, ATR-only
10. Mitigações: challenge-response e chaves por dispositivo
11. Conclusão e referências

---

## 11. Glossário

- **ATR / ATS:** resposta inicial do cartão (contato / ISO 14443-4).
- **APDU, SW1/SW2:** comando/resposta e status de ISO 7816-4.
- **CCID:** classe USB de leitores de cartão com chip.
- **PC/SC:** API de acesso a leitores e cartões.
- **Fail-closed:** em caso de dúvida ou erro, nega.
- **Replay:** reapresentar uma resposta já observada.
- **Challenge-response:** autenticação por desafio aleatório.
- **Relay:** retransmissão da comunicação entre cartão e leitor distantes.
- **Distance bounding:** medir o tempo de ida e volta para limitar a distância.

---

## 12. Referências

**Normas e especificações**

INTERNATIONAL ORGANIZATION FOR STANDARDIZATION. **ISO/IEC 7816-3:** Identification cards — Integrated circuit cards — Part 3: Cards with contacts — Electrical interface and transmission protocols. 3. ed. Geneva: ISO/IEC, 2006.

INTERNATIONAL ORGANIZATION FOR STANDARDIZATION. **ISO/IEC 7816-4:** Identification cards — Integrated circuit cards — Part 4: Organization, security and commands for interchange. 4. ed. Geneva: ISO/IEC, 2020.

INTERNATIONAL ORGANIZATION FOR STANDARDIZATION. **ISO/IEC 14443:** Cards and security devices for personal identification — Contactless proximity objects (Partes 1 a 4). Geneva: ISO/IEC.

INTERNATIONAL ORGANIZATION FOR STANDARDIZATION. **ISO/IEC 18092:** Near Field Communication — Interface and Protocol (NFCIP-1). Geneva: ISO/IEC.

USB IMPLEMENTERS FORUM. **Universal Serial Bus Device Class: Smart Card CCID — Specification for Integrated Circuit(s) Cards Interface Devices.** Rev. 1.1. USB-IF. Disponível em: usb.org. Acesso em: 17 nov. 2026.

PC/SC WORKGROUP. **PC/SC Specifications** (Interoperability Specification for ICCs and Personal Computer Systems). Disponível em: pcscworkgroup.com. Acesso em: 17 nov. 2026.

NFC FORUM. **NFC Forum Technical Specifications.** Disponível em: nfc-forum.org. Acesso em: 17 nov. 2026.

**Livros**

FINKENZELLER, K. **RFID Handbook:** Fundamentals and Applications in Contactless Smart Cards, Radio Frequency Identification and Near-Field Communication. 3. ed. Chichester: Wiley, 2010.

RANKL, W.; EFFING, W. **Smart Card Handbook.** 4. ed. Chichester: Wiley, 2010.

**Artigos**

GARCIA, F. D. *et al.* Dismantling MIFARE Classic. In: ESORICS, 13., 2008. **Proceedings…** Berlin: Springer, 2008.

NOHL, K. *et al.* Reverse-Engineering a Cryptographic RFID Tag. In: USENIX SECURITY SYMPOSIUM, 17., 2008. **Proceedings…** San Jose: USENIX, 2008.

GARCIA, F. D. *et al.* Wirelessly Pickpocketing a Mifare Classic Card. In: IEEE SYMPOSIUM ON SECURITY AND PRIVACY, 2009. **Proceedings…** Oakland: IEEE, 2009.

OSWALD, D.; PAAR, C. Breaking Mifare DESFire MF3ICD40: Power Analysis and Templates in the Real World. In: CHES, 2011. **Proceedings…** Berlin: Springer, 2011.

MEIJER, C.; VERDULT, R. Ciphertext-only Cryptanalysis on Hardened Mifare Classic Cards. In: ACM CCS, 22., 2015. **Proceedings…** New York: ACM, 2015.

HANCKE, G. P. A Practical Relay Attack on ISO 14443 Proximity Cards. Cambridge: University of Cambridge, Computer Laboratory, 2005. Relatório técnico.

DRIMER, S.; MURDOCH, S. J. Keep Your Enemies Close: Distance Bounding Against Smartcard Relay Attacks. In: USENIX SECURITY SYMPOSIUM, 16., 2007. **Proceedings…** Boston: USENIX, 2007.

FRANCILLON, A. *et al.* Relay Attacks on Passive Keyless Entry and Start Systems in Modern Cars. In: NDSS, 2011. **Proceedings…** San Diego: ISOC, 2011.

**Documentação e software**

FLIPPER DEVICES. **Flipper Zero Documentation.** Disponível em: docs.flipper.net. Acesso em: 17 nov. 2026.

FLIPPER DEVICES. **flipperzero-firmware.** Disponível em: github.com/flipperdevices/flipperzero-firmware. Acesso em: 17 nov. 2026.
