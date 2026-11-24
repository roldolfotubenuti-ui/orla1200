# RELATÓRIO TÉCNICO OFICIAL — TKS ENGINE 3.0 | FASE 3
## INTEGRAÇÃO DO MOTOR MULTIACCOUNT COM O UPLOADER REAL DO TIKTOK STUDIO

**Projeto:** TKS Engine 3.0 + TKS Virtual Office  
**Ambiente:** Windows 10/11 x64  
**Tecnologias:** Python 3.15, Playwright Async API, Chromium, SQLite (WAL Mode), PyQt6  
**Status da Implementação:** 100% CONCLUÍDO E HOMOLOGADO  
**Data:** 23 de Novembro de 2026  

---

## 1. RESUMO EXECUTIVO

A **Fase 3 do TKS Engine 3.0** foi concluída com êxito absoluto. O objetivo central desta etapa foi estabelecer a conexão operacional e direta entre a infraestrutura multi-sessão (criada na Fase 2 com `BrowserRuntime`, `ContextRegistry`, `QueueManager` e `RoundRobinRouter`) e o pipeline real de automação e preparação de vídeos do TikTok Studio (`Uploader` e `DOMHandler`).

A integração foi realizada segundo o princípio fundamental de **preservação do código testado**: o pipeline existente não foi reescrito; foi adaptado cirurgicamente para operar sobre instâncias de `Page` injetadas pertencentes a contextos isolados de cada conta, sem gerar múltiplos processos de Chromium na máquina host.

Além disso, foi implementado o **Modo Homologação (Simulation Mode)** com trava de segurança rígida: em nenhuma circunstância os testes automatizados ou execuções padrão acionam o clique definitivo de postagem no TikTok Studio. Apenas mediante ação voluntária, explícita e confirmada do usuário na interface gráfica o Modo Real de Publicação pode ser ativado para a sessão em memória.

---

## 2. ARQUIVOS MODIFICADOS E CRIADOS

| Arquivo | Natureza | Descrição das Modificações |
| :--- | :--- | :--- |
| `core/uploader.py` | Modificado | Adicionado suporte a `from_page()`, aceitação de `homologation_mode` e interceptor de segurança no Passo 6 (impede `click_post()` em homologação, retornando `simulation_success`). |
| `core/dom_handler.py` | Modificado | Adicionados métodos `get_logged_in_username()` para validação da identidade da conta ativa no DOM e `cancel_or_dismiss_upload()` para limpeza segura do modal de rascunho. |
| `core/account_executor.py` | Modificado | Substituído o placeholder de dry-run pela orquestração do `Uploader.from_page()` com validação de identidade da conta, injeção de tarefas e telemetria completa via `OfficeEventBridge`. |
| `core/execution_coordinator.py` | Modificado | Implementada a trava de segurança `allow_real_publishing` (padrão `False`), classificação estrita de status `UNKNOWN` (sem retry automático) e emissão de eventos operacionais para o Virtual Office. |
| `gui/dialogs/multiaccount_central_dialog.py` | Modificado | Adicionado seletor visual de modos operacionais: **Modo 1 (Homologação Segura)** vs. **Modo 2 (Operação Real)** com diálogo modal de advertência e confirmação mandatória. |
| `tests/test_multiaccount_phase3.py` | Criado | Suíte oficial de validação da Fase 3 cobrindo os 11 testes obrigatórios (Testes A ao K), aprovados com 100% de sucesso. |
| `tks_multiaccount_phase3_relatorio.md` | Criado | Relatório de entrega técnica e auditoria de segurança da Fase 3. |

---

## 3. ARQUITETURA DE INTEGRAÇÃO DO PIPELINE

```text
ExecutionCoordinator (Fair Round-Robin & Concorrência <= 2)
        │
        ▼
QueueManager (SQLite WAL)
        │
        ▼
AccountExecutor (Isolamento por Conta)
        │
        ▼
ContextRegistry (BrowserContext Isolado + DPAPI)
        │
        ▼
Page Exclusiva no Chromium Persistente
        │
        ▼
Uploader (from_page)
        │
        ▼
DOMHandler (Interações de DOM)
        │
        ├── Se Modo Homologação (Padrão) ──> Valida Botão Habilitado + Limpa Rascunho (simulation_success)
        └── Se Modo Operação Real (Confirmado) ──> click_post() + Modais de Confirmação (published / scheduled)
        │
        ▼
OfficeEventBridge (Telemetria Sanitizada para o Virtual Office 3D)
```

### 3.1. Injeção de Sessão (`Page Injection`)
Ao invés de instanciar o `BrowserManager` legado que abriria um novo processo Chromium avulso com flags redundantes, o `AccountExecutor` consulta o `BrowserRuntime` persistente e obtém uma tupla `(BrowserContext, Page)` autenticada com os cookies protegidos via Windows DPAPI da conta atribuída. O `Uploader.from_page(page, logger, homologation_mode)` recebe essa página diretamente, garantindo que toda a navegação ocorra no contexto isolado daquele usuário.

### 3.2. Verificação de Identidade no DOM
Antes e durante a submissão, o método `DOMHandler.get_logged_in_username()` inspeciona os seletores estruturais do cabeçalho do TikTok Studio (`a[href*='/@']`, `[data-tt='header-user-info']`, `.user-info-name`). Se o usuário detectado na página divergir do `AccountRecord.username` cadastrado para a gaveta/departamento, um alerta crítico de divergência de identidade é emitido.

---

## 4. MODOS OPERACIONAIS E DIRETRIZES DE SEGURANÇA

### Modo 1: Homologação (Padrão — Ativo)
* **Comportamento:** O pipeline executa todas as etapas preparatórias do TikTok Studio:
  1. Carregamento e injeção do arquivo MP4 via input de arquivo oculto.
  2. Aguardo da conclusão do upload e parsing do arquivo.
  3. Preenchimento humanizado da legenda e hashtags.
  4. Ativação do toggle de agendamento e preenchimento de data e horário (quando aplicável).
  5. Seleção do modo de privacidade/visibilidade.
  6. Checagem de direitos autorais de áudio e verificação de integridade de conteúdo.
  7. **Inspeção de liberação do botão Post:** Verifica se o botão final está visível, habilitado e sem atributos de bloqueio.
  8. **Trava de Interceptação:** **O botão de postagem NUNCA é clicado.** O modal é descartado com segurança (`cancel_or_dismiss_upload`), o vídeo físico é preservado e o resultado é gravado como `simulation_success`.

### Modo 2: Operação Real (Publicação Efetiva)
* **Comportamento:** Desabilitado por padrão. A ativação requer ação voluntária do usuário no seletor de modos da Central Multiaccount, seguida da confirmação explícita no diálogo modal do sistema:
  > *"ATENÇÃO: No MODO DE OPERAÇÃO REAL, o TKS Engine acionará o botão final de publicação e agendamento no TikTok Studio. Deseja prosseguir?"*
* **Persistência em Memória:** Esta permissão é estritamente volátil; **nunca é persistida em arquivos de configuração ou disco**. Caso o sistema seja reiniciado, o TKS Engine reverte compulsoriamente para o Modo 1 (Homologação).

---

## 5. INTEGRAÇÃO COM TKS VIRTUAL OFFICE 3D

Todas as transições de estado geradas pelo `ExecutionCoordinator`, `AccountExecutor` e `Uploader` são convertidas em eventos limpos e sanitizados através do `OfficeEventBridge`:

```text
employee.fetch_started    --> Funcionário 3D levanta da mesa e coleta na gaveta
account.execution_started --> Contexto Chromium da conta ativado
video.upload_started      --> Upload do arquivo iniciado no TikTok Studio
video.processing          --> Análise de qualidade de vídeo e legenda
video.submitting          --> Submissão final / verificação de botão
video.scheduled           --> Agendamento concluído com sucesso
video.published           --> Publicação imediata concluída com sucesso
video.failed              --> Falha reportada com log sanitizado
employee.returned         --> Funcionário retorna para a estação de trabalho
employee.idle             --> Estação de trabalho entra em espera quando a fila esvazia
```

---

## 6. RESULTADOS DA BATERIA DE TESTES OBRIGATÓRIOS (FASE 3)

A suíte executável `tests/test_multiaccount_phase3.py` cobriu integralmente os 11 testes obrigatórios da Fase 3:

```text
======================================================================
TESTES OBRIGATÓRIOS DA FASE 3 (test_multiaccount_phase3.py)
----------------------------------------------------------------------
[OK] Teste A — Integração: AccountExecutor entrega a página correta ao Uploader sem novo processo.
[OK] Teste B — Identidade: Uploader e Executor operam e validam a conta selecionada.
[OK] Teste C — Isolamento: Duas contas paralelas com cookies e contextos estritamente isolados.
[OK] Teste D — Round-Robin: Alternância sequencial perfeita entre contas do mesmo departamento.
[OK] Teste E — Concorrência: Limite estrito de no máximo 2 contas simultâneas e 1 por conta.
[OK] Teste F — Falha independente: Falha em uma conta não compromete a continuidade da outra.
[OK] Teste G — Agendamento: Classificação precisa entre SCHEDULED e PUBLISHED.
[OK] Teste H — Idempotência: Detecção e bloqueio de submissões duplicadas para o mesmo vídeo/conta.
[OK] Teste I — Reinicialização: Recuperação consistente de tarefas interrompidas (RUNNING -> ASSIGNED).
[OK] Teste J — Regressão: Integridade das 6 contas e 6 departamentos no banco SQLite.
[OK] Teste K — Modo Homologação: Botão final verificado como habilitado e preservado sem clique.
----------------------------------------------------------------------
Resultado: 11/11 APROVADOS (100% de sucesso) em 19.28 segundos.
======================================================================
```

### Resultados das Suítes de Regressão:
- **`tests/test_multiaccount_phase1.py`:** 8/8 testes aprovados (100%).
- **`tests/test_multiaccount_phase2.py`:** 10/10 testes aprovados (100%).
- **`tests/test_regressions.py`:** 20/20 testes aprovados (100%).
- **Total Geral de Testes Automatizados:** **49/49 testes aprovados.**

---

## 7. TRATAMENTO DE INCERTEZA E IDEMPOTÊNCIA

1. **Classificação `UNKNOWN`:** Caso ocorra qualquer timeout após a validação do formulário ou durante o aguardo do Toast final no Modo Real, o resultado é classificado como `UNKNOWN`. **Nenhum retry automático é disparado**, evitando a criação de vídeos duplicados no canal do usuário.
2. **Chave de Idempotência:** Cada vídeo enfileirado recebe a chave única estruturada `{drive_file_id}:{platform}:{account_id}:publish`. Se um arquivo idêntico for reenfileirado para a mesma conta, o `QueueManager` reutiliza a tarefa existente sem criar registros duplicados na tabela `jobs`.

---

## 8. PROCEDIMENTO PARA O PRIMEIRO TESTE REAL ACOMPANHADO

Quando o usuário desejar realizar a primeira publicação/agendamento real no TikTok Studio, o procedimento operacional recomendado é:

1. **Iniciar a aplicação:** `python main.py`.
2. **Acessar a Central Multiaccount:** Na aba *Contas*, clicar no botão *Central Multiaccount*.
3. **Confirmar Contas Conectadas:** Verificar se as contas dos departamentos desejados constam como *Autenticadas*.
4. **Executar em Modo Homologação:** Deixar selecionado o *Modo 1 (Homologação)* e clicar em *Iniciar Execução*. Verificar nos logs do console que os campos são preenchidos e o botão é validado com sucesso sem postagem real.
5. **Habilitar Modo Real de Forma Controlada:**
   - Selecionar a opção *Modo 2: Operação Real*.
   - Ler atentamente a mensagem de confirmação e clicar em *Sim*.
   - Apenas uma conta e um vídeo devem ser processados na primeira execução.
   - Confirmar o Toast e o agendamento no painel oficial do TikTok Studio.
