# Cofre Eletrônico Experimental (PySide6 + PC/SC + Flipper Zero)

Protótipo para experimento acadêmico de Segurança da Informação. O cofre só libera
quando a resposta do dispositivo bate **exatamente** com o critério definido em `config.py`.
Qualquer outra situação (sem dispositivo, erro, resposta diferente, critério não configurado) mantém o cofre **bloqueado**.

> **Status resumido:** aplicação, simulação e camada PC/SC/APDU implementadas e testadas **sem hardware**
> (parser, mocks e interface em modo simulado). **Nada foi validado ainda com o Flipper Zero físico** e o
> critério de autenticação real (`REAL_CRITERION`) está **vazio de propósito**: autenticação em modo real é recusada.
> Acompanhamento detalhado por integrante: [`PLANO_DE_DESENVOLVIMENTO.md`](PLANO_DE_DESENVOLVIMENTO.md).

> **Apresentação (slides):** [abrir e editar](https://claude.ai/artifact/EoGnfAVoMB5m536WKWSWSy) ·
> **Fundamentação teórica:** [`fundamentacao_teorica_integrante5.md`](fundamentacao_teorica_integrante5.md)
> (o link dos slides é privado: precisa ser compartilhado pelo menu Share para o grupo editar).

## 1. Objetivo e funcionamento esperado
Simular um cofre eletrônico controlado por um "cartão inteligente" e estudar suas fragilidades:
- o **Flipper Zero**, rodando o aplicativo comunitário **CCID**, é apresentado ao computador como um leitor/cartão USB de cartão inteligente;
- a aplicação Python consulta o dispositivo por **PC/SC** usando **APDUs**;
- se a resposta atender ao critério configurado, o cofre é liberado; caso contrário, permanece bloqueado;
- o projeto também serve para **analisar vulnerabilidades** do esquema (por exemplo, um critério estático é reproduzível por qualquer dispositivo que emule a mesma resposta — ver "Observação para o relatório").

Há dois modos: **simulação** (sem hardware, critério fictício próprio, sempre sinalizado na tela e nos registros) e **real** (dispositivo via PC/SC).

## 2. Arquitetura
```
 Flipper Zero (app CCID)
        │  USB (CCID)
        ▼
 Windows: driver CCID ─► serviço PC/SC (SCardSvr / winscard)      ← a confirmar com o dispositivo
        │
        ▼
 PySCard ──► core/smartcard_reader.py  (PCSCReader: detectar, conectar, ATR, transmitir APDU)
                       │  bytes: dados + SW1/SW2  (a camada NÃO decide nada)
                       ▼
             core/authenticator.py  (compara com core/criterion.py / config.py; fail-closed)
                       │  AuthResult (aceito/negado + motivo)
                       ▼
             core/vault_state.py  (BLOQUEADO → AGUARDANDO → LIBERADO)  ──►  ui/ (PySide6) + core/access_log.py (CSV)
```
Princípio de projeto: a **comunicação apenas transmite e recebe**; quem decide liberar o cofre é o `Authenticator`.
A chamada APDU roda em *worker* (QThreadPool) para não travar a interface.

### Papéis
| Componente | Papel |
|---|---|
| **Flipper Zero + app CCID** | Apresenta-se ao PC como leitor de cartão inteligente USB. Quais APDUs ele aceita e responde **ainda não foi confirmado** — depende dos testes com o dispositivo. |
| **PC/SC (Windows)** | Camada padrão de acesso a leitores/cartões; o serviço "Cartão Inteligente" (SCardSvr) é configurado para iniciar por gatilho (chegada de leitor/chamada RPC). |
| **PySCard (Python)** | Biblioteca que expõe o PC/SC ao Python. |
| **APDU** | Unidade de comando/resposta (ISO 7816-4): comando `CLA INS P1 P2 [Lc dados] [Le]`; resposta `dados + SW1 SW2`. |
| **Authenticator** | Única regra de liberação do cofre. Negado por padrão. |

## 3. Fluxo de autenticação
1. **Detectar leitores** → escolher o dispositivo → **Conectar** (obtém o ATR).
2. **Iniciar autenticação**: o cofre vai a *AGUARDANDO AUTENTICAÇÃO*.
3. Em *worker*, o `Authenticator` aplica o critério configurado: verifica o ATR (se definido), envia a APDU (se definida) e compara SW1/SW2 e dados **exatamente**.
4. Tudo certo → *ACESSO LIBERADO* (com bloqueio automático após `AUTO_LOCK_SECONDS`, padrão 60 s).
   Qualquer outra coisa → *BLOQUEADO*: sem dispositivo, critério não configurado, ATR/SW/dados diferentes, erro de comunicação ou exceção inesperada.
5. Se a conexão cair durante a transmissão, a interface desconecta, registra o evento e mantém o cofre bloqueado.
6. Todas as tentativas são registradas na tela e em `logs/access_log.csv` (marcadas `SIMULAÇÃO` ou `REAL`).

## 4. Etapas previstas
| Etapa | Conteúdo | Situação (ver plano) |
|---|---|---|
| Desenvolvimento | Aplicação/cofre, camada PC/SC/APDU, diagnóstico | Implementado; sem hardware |
| Integração | Aplicação ↔ Flipper via PC/SC, definição do critério real | Pendente (depende do dispositivo) |
| Testes | APDUs suportadas, ATR, falhas, respostas inesperadas, replay | Pendente |
| Demonstração | Roteiro, integração final, slides | Pendente |

## 5. Estrutura
```
cofre_eletronico/
├── main.py                  # ponto de entrada
├── config.py                # >>> CRITÉRIO DE AUTENTICAÇÃO / APDU (adaptar aqui)
├── requirements.txt
├── PLANO_DE_DESENVOLVIMENTO.md  # status por parte/integrante
├── core/
│   ├── apdu.py              # hex <-> bytes, validação e descrição de SW (funções puras)
│   ├── criterion.py         # o que é uma autenticação válida
│   ├── smartcard_reader.py  # PC/SC (PySCard) + leitor SIMULADO
│   ├── authenticator.py     # decisão (fail-closed)
│   ├── vault_state.py       # máquina de estados BLOQUEADO/AGUARDANDO/LIBERADO
│   └── access_log.py        # registros (tela + logs/access_log.csv)
├── ui/
│   ├── styles.py            # tema escuro
│   ├── vault_widget.py      # cofre animado (QPainter)
│   └── main_window.py       # janela principal
├── tools/
│   └── flipper_diag.py      # diagnóstico PC/SC independente da interface
└── logs/                    # CSV gerado automaticamente (não versionado)
```

## 6. Instalação no Windows
1. Instale Python 3.10–3.12 (marque "Add Python to PATH").
2. No terminal, dentro da pasta do projeto:
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
3. O serviço "Cartão Inteligente" (SCardSvr) precisa estar disponível. Se o PC/SC falhar com `0x8010001D`
   (`SCARD_E_NO_SERVICE`), significa que o **Gerenciador de Recursos do Cartão Inteligente não está em execução**.
   É um problema do ambiente Windows, não de APDU. A relação com a ausência do Flipper/leitor ainda é uma
   **hipótese** a confirmar; ver a seção de ambiente da Parte 3 em `PLANO_DE_DESENVOLVIMENTO.md`.

Sem hardware: marque **Modo de simulação**, clique em **Conectar** e depois **Iniciar autenticação**.
O modo simulado exibe uma faixa laranja, marca os registros como `SIMULAÇÃO` e usa um critério fictício próprio.

## 7. Conectando o Flipper Zero
1. No Flipper, abra o app CCID e conecte o USB ao PC.
2. Verifique o que o Windows enxerga: `certutil -scinfo` (lista leitores/cartões PC/SC).
3. Teste primeiro com o diagnóstico (abaixo), depois na aplicação: desmarque a simulação, **Detectar leitores**, escolha o dispositivo e **Conectar**.
   Anote o ATR exibido e o nome do leitor.
4. Descubra, **por teste**, os comandos APDU reais e as respostas (não presumimos nenhum comando;
   o app CCID pode não oferecer credencial personalizada).
5. Preencha `REAL_CRITERION` em `config.py` **somente com valores observados**. Até lá a autenticação REAL é recusada com
   "Critério de autenticação real não configurado".

## 8. Ferramenta de diagnóstico (`tools/flipper_diag.py`)
Independente da interface e do critério; **não envia nada sozinha**. Grava evidências em `tools/evidencias/`.
```
python tools/flipper_diag.py --self-test            # sem hardware (parser/formatador/SW)
python tools/flipper_diag.py --list                 # lista leitores
python tools/flipper_diag.py                        # interativo (h = ajuda)
python tools/flipper_diag.py -r flipper --atr
python tools/flipper_diag.py -r 0 -a "00 A4 04 00" --follow-up
```
A saída separa TX, RX bruto, dados, SW1 e SW2 (com descrição genérica ISO 7816-4 — não confirma o que o Flipper implementa).
O exemplo `00 A4 04 00` é apenas ilustração de formato: **não** sabemos se o Flipper o suporta.

## 9. Pontos a adaptar
| Onde | O que |
|---|---|
| `config.py → REAL_CRITERION` | `apdu`, `expected_data`, `expected_sw`, `expected_atr` (só com evidências) |
| `core/smartcard_reader.py → PCSCReader.connect` | fixar protocolo T=0/T=1, se os testes exigirem |
| `core/smartcard_reader.py → PCSCReader.transmit(follow_up=True)` | `61xx` (GET RESPONSE) / `6Cxx` já implementado e **opcional**; ligar só se o dispositivo precisar |
| `core/authenticator.py → authenticate` | lógica extra (ex.: várias APDUs, challenge-response) |

## 10. Observação para o relatório
Um critério estático (mesma resposta sempre) é, por definição, reproduzível por qualquer
dispositivo que emule essa resposta. Isso é um bom ponto de análise do experimento;
`authenticator.py` é o lugar para testar variantes mais fortes.
Os testes devem ser feitos exclusivamente neste protótipo acadêmico.
