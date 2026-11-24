# TKS ENGINE 3.0 — RELATÓRIO DE PRÉ-VALIDAÇÃO OPERACIONAL LOCAL-FIRST
## TESTE DE AGENDAMENTO COM ARQUIVOS LOCAIS (E:\ORLA1200\) — 6 DEPARTAMENTOS — 6 CONTAS TIKTOK

**Data:** 23/11/2026  
**Horário Local da Análise:** 15:35 (America/Sao_Paulo)  
**Horário Alvo de Agendamento:** 17:00:00 (America/Sao_Paulo)  
**Legenda Exata:** `bizarro`  
**Concorrência Máxima:** 2 contas simultâneas (`MAX_CONCURRENT_ACCOUNT_JOBS = 2`, `MAX_JOBS_PER_ACCOUNT = 1`)  
**Modo Real:** **DESATIVADO (Aguardando autorização explícita do operador)**

---

### 1. RESUMO EXECUTIVO DA PRÉ-VALIDAÇÃO

O pipeline de processamento **Local-First** foi configurado com sucesso. Os seis vídeos foram escaneados diretamente no disco local `E:\ORLA1200\`, eliminando completamente downloads do Google Drive, cópias intermediárias e buffering em memória RAM.

- **Total de Pastas Verificadas:** 6 (Pastas `1` a `6`)
- **Total de Vídeos Encontrados:** 6 (Exatamente 1 vídeo por pasta)
- **Integridade dos Arquivos:** 100% íntegros (todos válidos, legíveis e com SHA-256 e ffprobe computados)
- **Contas Vinculadas:** 6 contas TikTok independentes autenticadas no `AccountManager`
- **Reconciliação no SQLite (`storage/tks_jobs.db`):** 6 jobs em estado `READY_FOR_UPLOAD`, jobs legados arquivados com status `SUPERSEDED` para evitar duplicidade
- **Uploader Playwright:** Configurado para receber diretamente o caminho absoluto via `locator.set_input_files()`

---

### 2. TABELA DE PRÉ-VALIDAÇÃO DOS 6 DEPARTAMENTOS

| Pasta | Arquivo Local | Conta TikTok | Legenda | Data Agendamento | Horário | Estado | Detalhes Técnicos |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---|
| **1** | `rmn.ftbl1_009_7689492826450660630.mp4` | **Conta 01 — Instagram** (`@unamyti`) | `bizarro` | 23/11/2026 | 17:00 | **READY_FOR_UPLOAD** | 18.92 MB (19.834.979 B) \| 94.02s \| 1080x1440 \| hevc |
| **2** | `rmn.ftbl1_012_7689210188892654851.mp4` | **Conta 02 — Mercado Livre** (`@valueini`) | `bizarro` | 23/11/2026 | 17:00 | **READY_FOR_UPLOAD** | 15.35 MB (16.093.329 B) \| 77.72s \| 1080x1440 \| hevc |
| **3** | `rmn.ftbl1_013_7699867073010502934.mp4` | **Conta 03 — Shorts** (`@vinihack537`) | `bizarro` | 23/11/2026 | 17:00 | **READY_FOR_UPLOAD** | 9.58 MB (10.046.150 B) \| 65.43s \| 1080x1440 \| hevc |
| **4** | `rmn.ftbl1_011_7686592084618349846.mp4` | **Conta 04 — TikTok** (`@vinihack979`) | `bizarro` | 23/11/2026 | 17:00 | **READY_FOR_UPLOAD** | 12.03 MB (12.609.244 B) \| 87.50s \| 1080x1440 \| hevc |
| **5** | `rmn.ftbl1_014_7674994821555031318.mp4` | **Conta 05 — TikTok Shop** (`@vinihack120`) | `bizarro` | 23/11/2026 | 17:00 | **READY_FOR_UPLOAD** | 12.33 MB (12.929.343 B) \| 62.97s \| 1080x1440 \| hevc |
| **6** | `rmn.ftbl1_027_7691404197928979734.mp4` | **Conta 06 — YouTube** (`@viniciusferraz218`) | `bizarro` | 23/11/2026 | 17:00 | **READY_FOR_UPLOAD** | 10.18 MB (10.671.672 B) \| 71.40s \| 1080x1440 \| hevc |

---

### 3. AUDITORIA DETALHADA DE CADA DEPARTAMENTO

#### DEPARTAMENTO 01 — INSTAGRAM
- **Pasta Local:** `E:\ORLA1200\1\`
- **Caminho Absoluto:** `E:\ORLA1200\1\rmn.ftbl1_009_7689492826450660630.mp4`
- **Tamanho:** 19.834.979 bytes (18.92 MB)
- **SHA-256:** `005cc202552cd7d593fa90f96089a0e61e0aa839e73b0e9f33a917dd9be13dba`
- **Funcionário:** `employee-01` | **Gaveta:** `drawer-01` (`top_left`)
- **Conta Vinculada:** Conta 01 — Instagram (`@unamyti`)
- **ID da Conta:** `10d617eb-e1a7-4ed7-b8b3-acda804f3f98`
- **Status da Sessão:** `AUTHENTICATED` (20 cookies isolados)
- **ID do Job (SQLite):** `0d013377-89bb-4180-a948-ed831d2d21e0`
- **Status:** `READY_FOR_UPLOAD`

#### DEPARTAMENTO 02 — MERCADO LIVRE
- **Pasta Local:** `E:\ORLA1200\2\`
- **Caminho Absoluto:** `E:\ORLA1200\2\rmn.ftbl1_012_7689210188892654851.mp4`
- **Tamanho:** 16.093.329 bytes (15.35 MB)
- **SHA-256:** `78e1b0a93163fa617edb7ec5f4856edeb42be64439faa5650937196dc21f3100`
- **Funcionário:** `employee-02` | **Gaveta:** `drawer-02` (`top_right`)
- **Conta Vinculada:** Conta 02 — Mercado Livre (`@valueini`)
- **ID da Conta:** `37bc39cd-077f-4920-95d1-b11746f0399f`
- **Status da Sessão:** `AUTHENTICATED` (20 cookies isolados)
- **ID do Job (SQLite):** `b244cc03-34df-4ae4-8173-86cf81a1ba41`
- **Status:** `READY_FOR_UPLOAD`

#### DEPARTAMENTO 03 — SHORTS
- **Pasta Local:** `E:\ORLA1200\3\`
- **Caminho Absoluto:** `E:\ORLA1200\3\rmn.ftbl1_013_7699867073010502934.mp4`
- **Tamanho:** 10.046.150 bytes (9.58 MB)
- **SHA-256:** `2c37c0bc8bd6ca0ad3a8e30201d873bb49a123e656abeb957566ada124f2e274`
- **Funcionário:** `employee-03` | **Gaveta:** `drawer-03` (`center_left`)
- **Conta Vinculada:** Conta 03 — Shorts (`@vinihack537`)
- **ID da Conta:** `669df47e-4abf-4efd-a870-934295fa7a58`
- **Status da Sessão:** `AUTHENTICATED` (20 cookies isolados)
- **ID do Job (SQLite):** `909ac3e4-b66a-4e1e-a9ba-4a18ca73fc38`
- **Status:** `READY_FOR_UPLOAD`

#### DEPARTAMENTO 04 — TIKTOK
- **Pasta Local:** `E:\ORLA1200\4\`
- **Caminho Absoluto:** `E:\ORLA1200\4\rmn.ftbl1_011_7686592084618349846.mp4`
- **Tamanho:** 12.609.244 bytes (12.03 MB)
- **SHA-256:** `73a1a35b882614ab4019805ab3e857e3fd3af8383d7e0a4791ba9732060df10b`
- **Funcionário:** `employee-04` | **Gaveta:** `drawer-04` (`center_right`)
- **Conta Vinculada:** Conta 04 — TikTok (`@vinihack979`)
- **ID da Conta:** `a874cfb3-700c-4b6f-aa3c-ba1e2856894e`
- **Status da Sessão:** `AUTHENTICATED` (20 cookies isolados)
- **ID do Job (SQLite):** `60fc3b74-4416-43e0-9db6-e15dd23c5d15`
- **Status:** `READY_FOR_UPLOAD`

#### DEPARTAMENTO 05 — TIKTOK SHOP
- **Pasta Local:** `E:\ORLA1200\5\`
- **Caminho Absoluto:** `E:\ORLA1200\5\rmn.ftbl1_014_7674994821555031318.mp4`
- **Tamanho:** 12.929.343 bytes (12.33 MB)
- **SHA-256:** `900156db27015728f8fd5eed4a6dabfae04dab35c60e42c47effa87ba3bc5b55`
- **Funcionário:** `employee-05` | **Gaveta:** `drawer-05` (`bottom_left`)
- **Conta Vinculada:** Conta 05 — TikTok Shop (`@vinihack120`)
- **ID da Conta:** `e7e6bd57-59de-4272-82b8-f20ce2487e83`
- **Status da Sessão:** `AUTHENTICATED` (20 cookies isolados)
- **ID do Job (SQLite):** `e4d8de04-1973-47d5-bf4d-3360d9b598dc`
- **Status:** `READY_FOR_UPLOAD`

#### DEPARTAMENTO 06 — YOUTUBE
- **Pasta Local:** `E:\ORLA1200\6\`
- **Caminho Absoluto:** `E:\ORLA1200\6\rmn.ftbl1_027_7691404197928979734.mp4`
- **Tamanho:** 10.671.672 bytes (10.18 MB)
- **SHA-256:** `5b7985fa1a181971ee3de9c2a5aada1b7e049510c38af7fae1e5b9c3d26abf68`
- **Funcionário:** `employee-06` | **Gaveta:** `drawer-06` (`bottom_right`)
- **Conta Vinculada:** Conta 06 — YouTube (`@viniciusferraz218`)
- **ID da Conta:** `4baf0564-985f-4273-b559-9787cdd86c0d`
- **Status da Sessão:** `AUTHENTICATED` (29 cookies isolados)
- **ID do Job (SQLite):** `b1ff5b1a-00c3-4298-aa78-544c65570e74`
- **Status:** `READY_FOR_UPLOAD`

---

### 4. COMPROVAÇÃO DE REGRAS E SEGURANÇA

1. **Zero Download do Google Drive:** O pipeline opera exclusivamente sobre arquivos locais existentes em `E:\ORLA1200\`. Nenhuma chamada ao Google Drive é feita para obtenção do vídeo.
2. **Concorrência Estrita:** `ExecutionCoordinator` trava em `MAX_CONCURRENT_ACCOUNT_JOBS = 2`. No máximo duas contas processarão uploads simultaneamente.
3. **Exclusividade de Conta:** Cada conta tem lock próprio (`MAX_JOBS_PER_ACCOUNT = 1`), impedindo múltiplos uploads concorrentes no mesmo perfil.
4. **Legenda Padronizada:** A legenda é estritamente `bizarro`, sem tags ou pontuações extras.
5. **Horário Futuro Válido:** Data `23/11/2026 às 17:00:00` (~1h25min à frente do horário local atual), atendendo à exigência do TikTok Studio (mínimo de 15 minutos até 10 dias).
6. **Modo Real Bloqueado:** Permanece desativado até confirmação explícita do usuário.
