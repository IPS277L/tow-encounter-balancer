# Примеры согласованного контракта M4 v1

- [ranged-v1.request.json](ranged-v1.request.json) — numeric ranged Minion 1×1, seed 20260928, 3 trials, budget 5, sequential mode.
- [ranged-v1.result.json](ranged-v1.result.json) — полный proposed output с исходным запросом, runtime, seed scheme, compact records и summary.

Это примеры [ADR-0016](../../decisions/ADR-0016-ranged-simulation-json-v1.md). Production JSON adapters и Schema реализованы; application service/CLI simulate ещё отсутствуют. Integration tests читают request, исполняют existing typed APIs и сравнивают encoded result с примером.

2026-09-28 выполнена одноразовая проверка отображения всех полей запроса в существующие public constructors по разделу «Преобразование и семантические проверки» ADR. NpcRangedScenario admission успешен. Настоящие run_npc_ranged_simulation и run_npc_ranged_simulation_parallel(workers=2, batch_size=1) дали равные typed results. Сохранённый result сформирован из sequential result и проверен JSON round-trip: три side_defeated, 10 Attack, 5 посещённых раундов. Эти значения иллюстрируют конкретный seed, а не оценку вероятности или порог статистического теста.

Runtime примера: CPython 3.14.5, package 0.1.0. Для полного replay нужны те же правила/код и RNG/runtime. Parser проверяет весь вход; unit tests покрывают unknown/duplicate keys, types, cross-reference/facts/GM guards. Runtime metadata encoder берётся из текущего интерпретатора.

Числовой источник непосредственно перечитан: BOOK-GM-GUIDE 1.1, Allies and Antagonists / Brigands & Footpads / Brigand, стр. 97. Используется только Warbow excerpt; факт отсутствия применимых дополнительных правил указан caller явно. Полный каталог или автоматическое наследование PC weapon rules не предполагаются.
