import asyncio
import json
import time
from playwright.async_api import async_playwright

ARTIFACTS_DIR = "C:/Users/Vini/.gemini/antigravity/brain/5eb108eb-e384-4b8d-92be-79be5c417116/drawer_validation"

DRAWER_MAPPING = [
    {
        "drawerId": "drawer-06",
        "employeeId": "employee-06",
        "deskId": "desk-06",
        "char": "Cientista Voxel",
        "cam": "mesa6_closeup",
        "targetZ": -4.65,
        "approachPos": {"x": -0.17, "z": -4.65}
    },
    {
        "drawerId": "drawer-01",
        "employeeId": "employee-01",
        "deskId": "desk-01",
        "char": "Desenvolvedor",
        "cam": "mesa1_closeup",
        "targetZ": -4.65,
        "approachPos": {"x": -1.43, "z": -4.65}
    },
    {
        "drawerId": "drawer-02",
        "employeeId": "employee-02",
        "deskId": "desk-02",
        "char": "Lutador Voxel",
        "cam": "mesa2_closeup",
        "targetZ": -4.65,
        "approachPos": {"x": -0.17, "z": -4.65}
    },
    {
        "drawerId": "drawer-03",
        "employeeId": "employee-03",
        "deskId": "desk-03",
        "char": "Cavaleiro Voxel",
        "cam": "mesa3_closeup",
        "targetZ": -4.65,
        "approachPos": {"x": -1.43, "z": -4.65}
    },
    {
        "drawerId": "drawer-04",
        "employeeId": "employee-04",
        "deskId": "desk-04",
        "char": "Pato Elegante",
        "cam": "mesa4_closeup",
        "targetZ": -4.65,
        "approachPos": {"x": -0.17, "z": -4.65}
    },
    {
        "drawerId": "drawer-05",
        "employeeId": "employee-05",
        "deskId": "desk-05",
        "char": "Jogador Bulls #23",
        "cam": "mesa5_closeup",
        "targetZ": -4.65,
        "approachPos": {"x": -1.43, "z": -4.65}
    }
]

async def run_single_test(page, item, test_idx):
    d_id = item["drawerId"]
    emp = item["employeeId"]
    char_name = item["char"]
    print(f"\n=======================================================")
    print(f"--- TESTE {test_idx}: {char_name} ({emp} <-> {d_id}) ---")
    print(f"=======================================================")

    # 1. Ajustar câmera
    await page.evaluate(f"window.__tksSetCameraPreset && window.__tksSetCameraPreset('{item['cam']}')")
    await page.wait_for_timeout(1000)
    
    # Capturar estado inicial
    await page.screenshot(path=f"{ARTIFACTS_DIR}/{test_idx:02d}_{d_id}_01_initial_seated.png")

    # 2. Disparar coleta
    triggered = await page.evaluate(f"""() => {{
        return window.__tksDrawerSystem.triggerVideoTask('{d_id}', {{
            driveFileId: 'file_{d_id}_test',
            filename: 'video_{d_id}.mp4',
            jobId: 'job_{d_id}_val'
        }});
    }}""")
    print(f"[{d_id}] Coleta disparada: {triggered}")
    assert triggered == True, f"Falha ao disparar coleta para {d_id}"

    # Focar câmera no armário para ver a gaveta abrindo e o funcionário chegando
    await page.evaluate("window.__tksSetCameraPreset && window.__tksSetCameraPreset('mezzanine_meeting')")

    history = []
    start_time = time.time()
    seen_states = set()

    captured_opening = False
    captured_collecting = False
    captured_waiting_closed = False
    captured_returned = False

    while time.time() - start_time < 75: # Timeout de 75s para garantir que os 6 retornem e sentem com folga # Timeout seguro de 50s por teste individual
        state_info = await page.evaluate(f"""() => {{
            const store = window.__tksDrawerSystem.getState();
            const drawer = store.drawers['{d_id}'];
            return {{
                routineState: drawer.routineState,
                physicalState: drawer.physicalState,
                currentZ: drawer.currentZ,
                targetZ: drawer.targetZ,
                hasItemInHand: drawer.hasItemInHand,
                hasItemOnDesk: drawer.hasItemOnDesk,
            }};
        }}""")

        r_st = state_info["routineState"]
        p_st = state_info["physicalState"]
        cur_z = state_info["currentZ"]

        if r_st not in seen_states:
            seen_states.add(r_st)
            print(f"[{d_id}] Estado: {r_st} | Gaveta física: {p_st} (z={cur_z:.3f}m) | Mão: {state_info['hasItemInHand']} | Mesa: {state_info['hasItemOnDesk']}")
            history.append({
                "time": round(time.time() - start_time, 2),
                "state": r_st,
                "physicalState": p_st,
                "z": round(cur_z, 3),
                "inHand": state_info["hasItemInHand"],
                "onDesk": state_info["hasItemOnDesk"]
            })

        # Captura: Gaveta aberta
        if r_st in ("DRAWER_OPEN", "WALKING_TO_DRAWER") and not captured_opening and cur_z > 0.40:
            await page.screenshot(path=f"{ARTIFACTS_DIR}/{test_idx:02d}_{d_id}_02_drawer_open.png")
            captured_opening = True

        # Captura: Coletando o vídeo na gaveta
        if r_st in ("COLLECTING_VIDEO", "VIDEO_COLLECTED") and not captured_collecting:
            await page.screenshot(path=f"{ARTIFACTS_DIR}/{test_idx:02d}_{d_id}_03_collecting_video.png")
            captured_collecting = True

        # Captura: Aguardando a gaveta fechar 100% de pé em frente
        if r_st == "DRAWER_CLOSING" and not captured_waiting_closed:
            await page.screenshot(path=f"{ARTIFACTS_DIR}/{test_idx:02d}_{d_id}_04_standing_waiting_drawer_close.png")
            captured_waiting_closed = True

        # Captura: Retornando à mesa
        if r_st == "SITTING_DOWN" and not captured_returned:
            await page.evaluate(f"window.__tksSetCameraPreset && window.__tksSetCameraPreset('{item['cam']}')")
            await page.wait_for_timeout(600)
            await page.screenshot(path=f"{ARTIFACTS_DIR}/{test_idx:02d}_{d_id}_05_returning_seated.png")
            captured_returned = True

        if r_st == "IDLE" and "DRAWER_CLOSED" in seen_states:
            print(f"[{d_id}] Ciclo completo concluído com sucesso e retornado a IDLE!")
            break

        await asyncio.sleep(0.3)

    # Validar se a gaveta terminou 100% fechada
    final_info = await page.evaluate(f"""() => {{
        const store = window.__tksDrawerSystem.getState();
        return store.drawers['{d_id}'];
    }}""")

    assert final_info["physicalState"] == "CLOSED", f"Gaveta {d_id} não terminou fechada! Estado: {final_info['physicalState']}"
    assert final_info["currentZ"] <= 0.01, f"Gaveta {d_id} Z final não é 0.0! Z: {final_info['currentZ']}"
    print(f"[{d_id}] CONFIRMAÇÃO FÍSICA: Gaveta 100% FECHADA (z = {final_info['currentZ']:.3f}m, state = {final_info['physicalState']})")
    
    return {
        "drawerId": d_id,
        "employeeId": emp,
        "character": char_name,
        "history": history,
        "finalState": final_info["routineState"],
        "finalPhysical": final_info["physicalState"],
        "finalZ": final_info["currentZ"]
    }

async def run_deduplication_test(page):
    print("\n=======================================================")
    print("--- TESTE DE DEDUPLICAÇÃO DE DISPARO ---")
    print("=======================================================")
    # Disparar coleta para drawer-06
    first_trigger = await page.evaluate("""() => {
        return window.__tksDrawerSystem.triggerVideoTask('drawer-06', {
            driveFileId: 'dup_test_1',
            filename: 'dup_1.mp4'
        });
    }""")
    print("Primeiro disparo (deve aceitar):", first_trigger)
    assert first_trigger == True, "Primeiro disparo deveria ser aceito"

    await page.wait_for_timeout(1000)

    # Disparar segundo evento idêntico enquanto a rotina está em andamento
    second_trigger = await page.evaluate("""() => {
        return window.__tksDrawerSystem.triggerVideoTask('drawer-06', {
            driveFileId: 'dup_test_1',
            filename: 'dup_1.mp4'
        });
    }""")
    print("Segundo disparo duplicado durante execução (deve ser rejeitado):", second_trigger)
    assert second_trigger == False, "Segundo disparo duplicado deveria ter sido rejeitado!"

    # Esperar o ciclo terminar
    while True:
        st = await page.evaluate("window.__tksDrawerSystem.getState().drawers['drawer-06'].routineState")
        if st == "IDLE":
            break
        await asyncio.sleep(0.5)
    print("Deduplicação validada com sucesso!")

async def run_simultaneous_test(page):
    print("\n=======================================================")
    print("--- TESTE SIMULTÂNEO: TODAS AS 6 GAVETAS ---")
    print("=======================================================")
    
    # Vista zenital top-down para registrar o tráfego global no diorama
    await page.evaluate("window.__tksSetCameraPreset && window.__tksSetCameraPreset('top_down')")
    await page.wait_for_timeout(1500)
    await page.screenshot(path=f"{ARTIFACTS_DIR}/simultaneous_01_all_idle.png")

    # Disparar simultaneamente as 6 gavetas
    results = await page.evaluate("""() => {
        const res = {};
        for (let i = 1; i <= 6; i++) {
            const dId = `drawer-0${i}`;
            res[dId] = window.__tksDrawerSystem.triggerVideoTask(dId, {
                driveFileId: `file_sim_${dId}`,
                filename: `video_${dId}.mp4`,
                jobId: `job_sim_${dId}`
            });
        }
        return res;
    }""")
    print("Disparos simultâneos:", results)
    for k, v in results.items():
        assert v == True, f"Falha ao disparar {k} simultâneo"

    start_time = time.time()
    t10_shot = False
    t20_shot = False

    while time.time() - start_time < 75: # Timeout de 75s para garantir que os 6 retornem e sentem com folga
        elapsed = time.time() - start_time
        all_drawers = await page.evaluate("window.__tksDrawerSystem.getState().drawers")
        
        active_count = sum(1 for d in all_drawers.values() if d["routineState"] != "IDLE")
        open_drawers = [k for k, d in all_drawers.items() if d["physicalState"] in ("OPEN", "OPENING")]
        closing_drawers = [k for k, d in all_drawers.items() if d["physicalState"] in ("CLOSING")]
        closed_drawers = [k for k, d in all_drawers.items() if d["physicalState"] == "CLOSED"]

        if elapsed > 6 and not t10_shot:
            await page.screenshot(path=f"{ARTIFACTS_DIR}/simultaneous_02_all_walking_to_drawers.png")
            t10_shot = True

        if elapsed > 15 and not t20_shot:
            await page.screenshot(path=f"{ARTIFACTS_DIR}/simultaneous_03_all_returning_to_desks.png")
            t20_shot = True

        if active_count == 0:
            print(f"Todos os 6 funcionários concluíram em {elapsed:.1f}s!")
            break

        await asyncio.sleep(0.5)

    await page.wait_for_timeout(2000)
    await page.screenshot(path=f"{ARTIFACTS_DIR}/simultaneous_04_all_finished_closed.png")

    # Validar que as 6 gavetas estão 100% fechadas
    final_drawers = await page.evaluate("window.__tksDrawerSystem.getState().drawers")
    all_closed = True
    for k, d in final_drawers.items():
        print(f"[{k}] Estado Final: {d['routineState']} | Físico: {d['physicalState']} | Z: {d['currentZ']:.3f}m")
        if d["physicalState"] != "CLOSED" or d["currentZ"] > 0.01:
            all_closed = False

    assert all_closed == True, "Nem todas as gavetas fecharam 100% no teste simultâneo!"
    print("Teste simultâneo concluído com 100% de sucesso!")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1600, "height": 900})
        await page.goto("http://localhost:3005")
        await page.wait_for_timeout(3500)

        report = {
            "individual_tests": [],
            "simultaneous_test": None
        }

        # 1. Executar os 6 testes individuais
        for idx, item in enumerate(DRAWER_MAPPING, 1):
            res = await run_single_test(page, item, idx)
            report["individual_tests"].append(res)
            await page.wait_for_timeout(1000)

        # 2. Executar teste de deduplicação
        await run_deduplication_test(page)
        await page.wait_for_timeout(3000)

        # 3. Executar teste simultâneo dos 6 funcionários
        await run_simultaneous_test(page)
        report["simultaneous_test"] = "PASS"

        with open(f"{ARTIFACTS_DIR}/validation_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        await browser.close()
        print("\n>>> TODOS OS TESTES FORAM CONCLUÍDOS COM SUCESSO! <<<")

if __name__ == "__main__":
    asyncio.run(main())
