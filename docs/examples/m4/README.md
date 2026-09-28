# Примеры согласованного контракта M4 v1

- [ranged-v1.request.json](ranged-v1.request.json) — numeric ranged Minion 1×1, seed 20260928, 3 trials, budget 5, sequential mode.
- [ranged-v1.result.json](ranged-v1.result.json) — полный proposed output с исходным запросом, runtime, seed scheme, compact records и summary.

Это примеры [ADR-0016](../../decisions/ADR-0016-ranged-simulation-json-v1.md). Production JSON adapters, Schema, application service и CLI simulate реализованы. Integration tests читают request, исполняют service/CLI через sequential/spawn и сравнивают encoded result с примером.

2026-09-28 выполнена одноразовая проверка отображения всех полей запроса в существующие public constructors по разделу «Преобразование и семантические проверки» ADR. NpcRangedScenario admission успешен. Настоящие run_npc_ranged_simulation и run_npc_ranged_simulation_parallel(workers=2, batch_size=1) дали равные typed results. Сохранённый result сформирован из sequential result и проверен JSON round-trip: три side_defeated, 10 Attack, 5 посещённых раундов. Эти значения иллюстрируют конкретный seed, а не оценку вероятности или порог статистического теста.

Runtime примера: CPython 3.14.5, package 0.1.0. Для полного replay нужны те же правила/код и RNG/runtime. Parser проверяет весь вход; unit tests покрывают unknown/duplicate keys, types, cross-reference/facts/GM guards. Runtime metadata encoder берётся из текущего интерпретатора.

Числовой источник непосредственно перечитан: BOOK-GM-GUIDE 1.1, Allies and Antagonists / Brigands & Footpads / Brigand, стр. 97. Используется только Warbow excerpt; факт отсутствия применимых дополнительных правил указан caller явно. Полный каталог или автоматическое наследование PC weapon rules не предполагаются.

Композиция Python API (в importable `.py` файле; guard нужен для process mode):

```python
from pathlib import Path

from towr.adapters.ranged_json_errors import RangedSimulationInputError
from towr.adapters.ranged_simulation_json import (
    parse_ranged_simulation_request, encode_ranged_simulation_result,
    encode_ranged_simulation_error,
)
from towr.application.ranged_simulation_errors import RangedSimulationExecutionError
from towr.application.ranged_simulation_service import execute_ranged_simulation


def main():
    raw = Path("docs/examples/m4/ranged-v1.request.json").read_bytes()
    try:
        command = parse_ranged_simulation_request(raw)
        result = execute_ranged_simulation(command)
    except (RangedSimulationInputError, RangedSimulationExecutionError) as error:
        output = encode_ranged_simulation_error(error)
    else:
        output = encode_ranged_simulation_result(command, result)
    print(output, end="")


if __name__ == "__main__":
    main()
```

Для process заменить execution в запросе на `{"mode": "process", "workers": 2, "batch_size": 1}`. Service не подбирает параметры и не делает fallback. Python-фрагмент выше демонстрирует API; готовая политика файлового I/O/stdout encoding/exit codes предоставляется CLI.

## Запуск CLI

Из корня проекта после установки зависимостей:

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m towr simulate docs/examples/m4/ranged-v1.request.json
```

После установки текущей версии проекта (`.venv/Scripts/python.exe -m pip install .`) доступна также команда `.venv/Scripts/towr.exe simulate INPUT`. Для stdin используйте `simulate -` и передайте полный UTF-8 документ до EOF. Режим, workers/batch_size, seed и trials задаются только JSON-входом; command-line override отсутствует.

Stdout — один result/error JSON; stderr — диагностика. Коды 0/2/3/4 означают success, input/usage error, execution failure и I/O failure. Help — текст и code 0. Ошибка чтения файла или аргументов не выдаёт JSON. При сбое доставки stdout документ может быть неполным; caller должен проверить exit code. [Полный контракт](../../decisions/ADR-0016-ranged-simulation-json-v1.md#cli-simulate).

Пример передачи stdin без перекодирования оболочкой (из Python в установленном окружении):

```python
from pathlib import Path
import subprocess
import sys

completed = subprocess.run(
    [sys.executable, "-m", "towr", "simulate", "-"],
    input=Path("docs/examples/m4/ranged-v1.request.json").read_bytes(),
    capture_output=True,
)
sys.stdout.buffer.write(completed.stdout)
sys.stderr.buffer.write(completed.stderr)
raise SystemExit(completed.returncode)
```
