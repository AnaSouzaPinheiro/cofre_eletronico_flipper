# Plano de testes de segurança — cofre eletrônico

## 1. Execução

Na pasta raiz do projeto, execute `.venv/bin/python tests/run_tests.py` (detalhes em [`tests/README.md`](../tests/README.md)).

## 2. Cobertura automatizada

- T01–T07: credencial válida/inválida, status APDU, resposta vazia, falhas, leitor desconectado e critério não configurado.
- T08–T11: repetição de resposta estática, autenticação baseada somente em ATR e tentativas inválidas repetidas.
- T12–T17: bytes extras, resposta ausente, exceção inesperada, divergência de ATR, transmissão APDU e remoção do cartão.
- T18–T30: validação opcional de dados, ATR vazio, repetição entre sessões, desconexão após sucesso, comprimentos de resposta, bytes adicionais, SW1/SW2 inválidos, dados malformados, APDU vazio e resposta vazia explicitamente configurada.

### Arquivos de evidência

- `logs/security_test_access_log.csv`: registro de cada chamada de autenticação dos testes.
- `logs/security_test_summary.csv`: resultado por caso de teste.

Resultado da execução final (30 testes, 30 `APROVADO`): [`docs/evidencias/testes_seguranca/`](evidencias/testes_seguranca/).
Reexecutada em 18/11/2026 contra o código com o `REAL_CRITERION` do Flipper: 30/30 `APROVADO`.

## 3. Vulnerabilidades

A análise dos testes permitiu identificar diferentes fragilidades na lógica de autenticação e no tratamento das comunicações APDU.

| Testes | Vulnerabilidade identificada | Prioridade |
|---|---|---|
| T08 e T20 | Reutilização de respostas estáticas entre autenticações e sessões | Crítica |
| T09 e T19 | Autenticação baseada exclusivamente no ATR | Crítica |
| T11 | Ausência de limitação de tentativas inválidas | Crítica |
| T18 | Ausência de validação dos dados recebidos quando `expected_data=None` | Crítica |
| T28 | Aceitação e transmissão de comandos APDU vazios | Alta |
| T30 | Aceitação de respostas vazias quando configuradas como esperadas | Alta |
| T21 | Necessidade de garantir a invalidação da sessão após desconexão | Alta |
| T13, T14 e T27 | Tratamento de respostas ausentes, exceções e dados inválidos | Média |
| T22 a T26 | Respostas com tamanho ou status APDU inesperados | Média |

### 3.1. Relação com o critério real do Flipper Zero

O critério validado com o hardware em 18/11/2026 (`config.py`) é: ATR `3B 00` + APDU `01 01 00 00` → `90 00`, **sem dados**. Com isso:

- **T08/T20 se aplicam diretamente:** a resposta é sempre a mesma e não depende de nenhum segredo. Qualquer dispositivo que se apresente como leitor CCID e responda `90 00` a esse comando libera o cofre.
- **T30 se aplica diretamente:** o critério real espera resposta vazia (`expected_data=b""`), então a prova de identidade se resume ao status `90 00`.
- **T09/T19 não se aplicam como critério único** (o critério real exige também a APDU), mas o ATR `3B 00` é genérico e não identifica o dispositivo.
- **T18 e T28 não se aplicam** à configuração atual (`expected_data` definido e APDU não vazia); continuam sendo riscos de configuração.

Os testes usam leitores simulados; a vulnerabilidade de T08/T20 foi confirmada também no comportamento real do Flipper (mesma resposta em todas as execuções do diagnóstico).

As vulnerabilidades demonstram que, embora o sistema já possua mecanismos de rejeição para diversas situações inválidas, ainda existem configurações e condições específicas capazes de permitir autenticações sem comprovação criptográfica suficiente.

---

## 4. Mecanismos de Segurança Recomendados

### 4.1. Autenticação por Desafio e Resposta (Challenge-Response)

**Vulnerabilidades relacionadas:** T08 e T20.

**Prioridade:** Crítica.

**Mecanismo proposto:**

Implementar autenticação baseada em desafio e resposta, utilizando valores aleatórios e imprevisíveis (Nonce).

O processo deverá seguir as seguintes etapas:

1. O cofre gera um desafio aleatório e exclusivo para a autenticação.
2. O desafio é enviado ao cartão inteligente.
3. O cartão utiliza uma chave criptográfica secreta para produzir uma resposta vinculada ao desafio.
4. O cofre verifica a validade da resposta utilizando o mecanismo criptográfico correspondente.
5. O desafio é invalidado após a tentativa, independentemente do resultado.

Pode-se utilizar HMAC-SHA-256 ou outro mecanismo criptográfico compatível com as capacidades do cartão.

**Benefícios esperados:**

- Impedir a reutilização de respostas capturadas anteriormente.
- Tornar cada autenticação única.
- Dificultar ataques de repetição.
- Aumentar a confiabilidade do processo de autenticação.

### 4.2. Bloqueio Progressivo de Tentativas de Autenticação

**Vulnerabilidade relacionada:** T11.

**Prioridade:** Crítica.

**Descrição do problema:** o T11 mostrou que tentativas inválidas repetidas são todas processadas, sem espera nem bloqueio, o que permite tentativas automatizadas ilimitadas.

**Mecanismo proposto:**

Implementar um mecanismo de controle de tentativas, com bloqueio progressivo após sucessivas falhas de autenticação.

Exemplo de política:

| Tentativas inválidas | Ação recomendada |
|---|---|
| 1 a 3 | Registrar as falhas normalmente |
| 4 a 5 | Aplicar intervalo de espera |
| 6 a 9 | Bloqueio temporário de 1 minuto |
| 10 ou mais | Bloqueio temporário de 5 minutos e geração de alerta |

Os valores apresentados são parâmetros iniciais e poderão ser ajustados conforme os requisitos operacionais.

**Medidas complementares:**

- Armazenar persistentemente o histórico de tentativas.
- Registrar horários e quantidade de falhas.
- Implementar procedimento administrativo de desbloqueio.
- Evitar que a reinicialização da aplicação elimine o histórico.
- Gerar alertas para sequências anormais de tentativas.

**Benefícios esperados:**

- Dificultar ataques de força bruta.
- Reduzir a possibilidade de tentativas automatizadas.
- Facilitar a identificação de comportamentos suspeitos.

### 4.3. Autenticação Multifator (MFA)

**Vulnerabilidades relacionadas:** T09 e T19.

**Prioridade:** Alta.

**Mecanismo proposto:**

Implementar autenticação multifator, combinando diferentes elementos de verificação:

- **Fator de posse:** cartão inteligente com chave criptográfica individual.
- **Fator de conhecimento:** senha ou PIN pessoal.

A liberação do cofre deverá ocorrer somente após a validação dos fatores exigidos.

**Benefícios esperados:**

- Acrescentar uma camada adicional de proteção.
- Reduzir o risco de acesso por cartões substituídos ou comprometidos.
- Associar a autenticação a uma credencial individual.

O PIN deverá ser validado por um mecanismo seguro, preferencialmente no próprio cartão, evitando seu armazenamento em texto puro na aplicação.

### 4.4. Validação Rigorosa de Comandos e Respostas APDU

**Vulnerabilidades relacionadas:** T18, T22, T23, T26, T27, T28 e T30.

**Prioridade:** Crítica.

**Descrição do problema:**

Os testes demonstraram situações em que comandos e respostas APDU podem apresentar características inadequadas, como ausência de dados esperados, comandos vazios, respostas incompletas e parâmetros de validação inválidos.

Também foi identificado que a configuração `expected_data=None` permite que os dados recebidos não sejam comparados com um valor esperado.

**Mecanismo proposto:**

Implementar validação obrigatória dos parâmetros de comunicação antes do envio dos comandos e após o recebimento das respostas.

| Elemento | Validação recomendada |
|---|---|
| APDU | Rejeitar comandos vazios ou fora do formato permitido |
| ATR | Rejeitar valores vazios ou inválidos quando exigidos pelo protocolo |
| SW1/SW2 | Validar os códigos de status esperados |
| Dados recebidos | Exigir comparação exata ou validação criptográfica |
| Comprimento | Verificar os tamanhos mínimo e máximo permitidos |
| Resposta | Rejeitar objetos ausentes, nulos ou malformados |

**Medidas complementares:**

- Impedir que `expected_data=None` seja utilizado como critério suficiente de autenticação.
- Validar a estrutura do critério antes de iniciar a comunicação.
- Não permitir que uma resposta vazia seja considerada válida apenas por configuração acidental.
- Manter a comparação segura dos dados recebidos utilizando `hmac.compare_digest()`.

É importante observar que a comparação segura já está presente no módulo `authenticator.py` e deve ser preservada.

**Benefícios esperados:**

- Reduzir a possibilidade de autenticações indevidas.
- Impedir que respostas incompletas sejam aceitas.
- Evitar configurações inseguras.
- Fortalecer a comunicação entre o cofre e o cartão inteligente.

### 4.5. Proteção Contra Clonagem e Substituição de Cartões

**Vulnerabilidades relacionadas:** T09, T19 e T20.

**Prioridade:** Alta.

**Descrição do problema:**

A utilização do ATR como identificador suficiente não garante que o cartão apresentado seja legítimo.

Um dispositivo capaz de reproduzir características de identificação ou respostas estáticas pode simular determinados comportamentos esperados pelo sistema.

**Mecanismo proposto:**

Implementar autenticação criptográfica individualizada para cada cartão autorizado.

Cada credencial deverá possuir:

- Identificador individual.
- Chave criptográfica exclusiva.
- Cadastro de cartões autorizados.
- Estado de validade ou revogação.

Durante a autenticação, o sistema deverá verificar uma prova criptográfica produzida pelo cartão, em vez de depender exclusivamente de características de identificação.

Também deverá existir uma lista de revogação para cartões perdidos, substituídos ou comprometidos.

**Benefícios esperados:**

- Dificultar a utilização de cartões clonados.
- Permitir a revogação de credenciais comprometidas.
- Evitar que a simples correspondência do ATR autorize o acesso.

A implementação depende dos recursos criptográficos disponíveis no modelo de cartão utilizado.

