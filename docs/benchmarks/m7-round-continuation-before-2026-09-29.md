# M7 sequential benchmark baseline

UTC: 2026-09-29T10:45:05+00:00

Runtime: CPython 3.14.5; Windows-11-10.0.26200-SP0
Processor: Intel64 Family 6 Model 140 Stepping 1, GenuineIntel; GC enabled: True
Source revision: `4db7a22879671cbb1de4ec4581b20f8641a60557`
Source/harness SHA-256: `529d908bbfa1885419038f94845dfcf3718db6d663e807d8252e669ed6f5ff43`
Seed scheme: `towr:npc-mixed-trial:v1`

```powershell
$env:PYTHONPATH = "src"
& "D:\git\tow-encounter-balancer\.venv\Scripts\python.exe" tools/profile_m7.py --trials 100 --master-seed 20260929 --round-budget 5 --repeats 5 --top 20 --output "docs/benchmarks/m7-round-continuation-before-2026-09-29.md"
```

Warm-up: min(3, trials) per case. Fixture/imports and gc.collect are outside timing. Wall repeats, tracemalloc and cProfile are separate runs; all trial records and aggregate summaries are compared for equality. Timed batch includes summary projection. Peak is incremental traced Python allocation during one batch, not process RSS; pre-existing fixture/reference result are excluded. cProfile cumulative rows overlap and must not be summed.

Fixtures: 2x1 = Pbow@rear, P1/E1@arena; 3x2 = Pbow@rear, P1/P2/E1/E2@arena; 2x2 = Pbow@rear, P1/E1@arena, E2bow@far. Side/actor order as listed (allies first); target priority is opposing roster order. All enemy pairs involving a bow are explicitly Medium, all other enemy pairs explicitly Close; rear/arena/far are mutually adjacent. Numeric profiles: Footpad Dagger 3d/3 Dam2 RES3 Athletics 3d/3; Brigand Warbow 3d/3 Dam3 RES4 Athletics 3d/2. GM1.1 Allies and Antagonists pp91,93,97; PG1.4 Equipment p94; Rules pp114,118-119. GM-approved KO/outnumbering, can_leave_zone=False, repeated Staggered chooses Wound. Aware, clear sight, stationary, unmounted, complete zone roster, no higher ground/other modifiers/additional rules, sufficient ammunition, no reload action. All four outcomes count; unsupported is a technical stop, not a defeat. These are fixed numeric projections, not full NPC catalogue support.

| Case | Trials | Seed | Round budget | Wall seconds (repeats) | Median s | Peak Python KiB | Outcomes (achieved/defeated/limit/unsupported) | Attacks | Visited rounds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2x1 | 100 | 20260929 | 5 | 0.333231, 0.267733, 0.266529, 0.250126, 0.261822 | 0.266529 | 86.6 | 84/0/0/16 | 298 | 158 |
| 3x2 | 100 | 20260929 | 5 | 0.519429, 0.551138, 0.569703, 0.701596, 0.579698 | 0.569703 | 152.7 | 86/0/0/14 | 643 | 212 |
| 2x2 | 100 | 20260929 | 5 | 0.400679, 0.403749, 0.341511, 0.397388, 0.405495 | 0.400679 | 120.9 | 3/8/0/89 | 420 | 190 |

## Profile: 3 actors

Trial-record SHA-256: `50083eb5e44c0abcf260b97e68a146b056c5ca1ae7405d43688f00753a623fe5`

Cumulative time:

```text
1014899 function calls (1014535 primitive calls) in 0.584 seconds

   Ordered by: cumulative time
   List reduced from 412 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    0.666    0.666 profile_m7.py:135(run_batch)
        1    0.000    0.000    0.665    0.665 npc_mixed_simulation.py:32(run_npc_mixed_simulation)
      101    0.002    0.000    0.665    0.007 npc_mixed_simulation.py:42(<genexpr>)
      100    0.001    0.000    0.663    0.007 npc_mixed_simulation.py:14(run_npc_mixed_trial)
      100    0.003    0.000    0.647    0.006 npc_mixed_scenario_runner.py:61(run_npc_mixed_scenario)
      182    0.001    0.000    0.538    0.003 npc_rounds_runner.py:42(run_npc_rounds)
      182    0.006    0.000    0.520    0.003 npc_round_coordinator.py:27(run_npc_round)
    10218    0.011    0.000    0.259    0.000 dataclasses.py:1762(replace)
    10218    0.037    0.000    0.241    0.000 dataclasses.py:1781(_replace)
      314    0.003    0.000    0.163    0.001 npc_attack_controller.py:22(select_npc_attack)
      298    0.001    0.000    0.153    0.001 npc_roster_attack_execution.py:12(execute_npc_roster_attack)
      298    0.003    0.000    0.115    0.000 attack_action_execution.py:20(execute_attack_action)
      182    0.001    0.000    0.077    0.000 npc_round_models.py:39(__post_init__)
      182    0.008    0.000    0.075    0.000 npc_round_models.py:91(_validate_steps)
      298    0.001    0.000    0.064    0.000 kernel.py:86(resolve_kernel_attack)
      628    0.008    0.000    0.061    0.000 npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
     2706    0.030    0.000    0.059    0.000 turn_models.py:261(__post_init__)
     2022    0.023    0.000    0.059    0.000 npc_round_request_models.py:24(__post_init__)
     1192    0.011    0.000    0.058    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
      100    0.003    0.000    0.051    0.001 npc_mixed_scenario_result_models.py:97(__post_init__)
```

Self time:

```text
1014899 function calls (1014535 primitive calls) in 0.584 seconds

   Ordered by: internal time
   List reduced from 412 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    10218    0.037    0.000    0.241    0.000 dataclasses.py:1781(_replace)
     2706    0.030    0.000    0.059    0.000 turn_models.py:261(__post_init__)
     2022    0.023    0.000    0.059    0.000 npc_round_request_models.py:24(__post_init__)
   215594    0.022    0.000    0.022    0.000 {built-in method builtins.isinstance}
     1788    0.016    0.000    0.020    0.000 test_models.py:216(__post_init__)
     1852    0.013    0.000    0.021    0.000 turn_models.py:202(__post_init__)
    99539    0.012    0.000    0.012    0.000 {built-in method builtins.len}
    10218    0.011    0.000    0.259    0.000 dataclasses.py:1762(replace)
     2384    0.011    0.000    0.015    0.000 attack_models.py:298(__post_init__)
     1192    0.011    0.000    0.058    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
     1570    0.010    0.000    0.021    0.000 npc_attack_selection_models.py:128(__post_init__)
    69934    0.010    0.000    0.010    0.000 {method 'strip' of 'str' objects}
     4876    0.009    0.000    0.016    0.000 npc_attack_preparation_models.py:216(_rank)
    56194    0.009    0.000    0.009    0.000 {built-in method builtins.getattr}
     2764    0.009    0.000    0.014    0.000 turn_models.py:445(_normalize_participants)
    16084    0.008    0.000    0.019    0.000 npc_roster_models.py:175(participant)
      628    0.008    0.000    0.061    0.000 npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
      596    0.008    0.000    0.015    0.000 test_resolution.py:106(complete_test)
    17316    0.008    0.000    0.012    0.000 npc_roster_models.py:189(_identifier)
      182    0.008    0.000    0.075    0.000 npc_round_models.py:91(_validate_steps)
```

dataclasses.replace callers:

```text
Ordered by: cumulative time
   List reduced from 412 to 1 due to restriction <'dataclasses.py:.*\\(replace\\)'>

Function                      was called by...
                                  ncalls  tottime  cumtime
dataclasses.py:1762(replace)  <-     894    0.001    0.017  action_execution_models.py:422(_validate_execution_transition)
                                     894    0.001    0.020  attack_action_execution.py:20(execute_attack_action)
                                     216    0.000    0.007  minion_defeat_models.py:95(_build_continuation)
                                     628    0.001    0.015  npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
                                     100    0.000    0.001  npc_mixed_scenario_result_models.py:97(__post_init__)
                                     168    0.000    0.007  npc_mixed_scenario_result_models.py:187(current)
                                     314    0.000    0.009  npc_mixed_scenario_runner.py:35(get_candidates)
                                     758    0.001    0.015  npc_roster_attack_models.py:228(_build_state)
                                      58    0.000    0.002  npc_round_advance_models.py:18(__post_init__)
                                      58    0.000    0.001  npc_round_advance_models.py:57(__post_init__)
                                     116    0.000    0.004  npc_round_advance_models.py:71(continuation)
                                     628    0.001    0.019  npc_round_coordinator.py:27(run_npc_round)
                                      84    0.000    0.003  npc_round_exclusion.py:14(apply_npc_round_exclusion)
                                     252    0.000    0.008  npc_round_exclusion_models.py:47(round_state)
                                     860    0.001    0.032  npc_round_models.py:59(continuation)
                                    1784    0.002    0.047  npc_round_models.py:91(_validate_steps)
                                    1192    0.001    0.019  protection_models.py:114(_expected_protection)
                                      58    0.000    0.001  spatial_resolution.py:141(start_next_spatial_round)
                                     314    0.000    0.010  turn_resolution.py:31(start_combat_turn)
                                     628    0.001    0.015  turn_resolution.py:62(reserve_combat_action_slot)
                                     214    0.000    0.006  turn_resolution.py:149(end_combat_turn)
```

## Profile: 5 actors

Trial-record SHA-256: `6dec914d829a246977a683c6fae3ffe524da555495dd1272cd1c475573b5b165`

Cumulative time:

```text
2384475 function calls (2383755 primitive calls) in 1.344 seconds

   Ordered by: cumulative time
   List reduced from 412 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    1.531    1.531 profile_m7.py:135(run_batch)
        1    0.000    0.000    1.531    1.531 npc_mixed_simulation.py:32(run_npc_mixed_simulation)
      101    0.004    0.000    1.530    0.015 npc_mixed_simulation.py:42(<genexpr>)
      100    0.002    0.000    1.526    0.015 npc_mixed_simulation.py:14(run_npc_mixed_trial)
      100    0.006    0.000    1.506    0.015 npc_mixed_scenario_runner.py:61(run_npc_mixed_scenario)
      360    0.003    0.000    1.246    0.003 npc_rounds_runner.py:42(run_npc_rounds)
      360    0.013    0.000    1.204    0.003 npc_round_coordinator.py:27(run_npc_round)
    21415    0.024    0.000    0.603    0.000 dataclasses.py:1762(replace)
    21415    0.080    0.000    0.566    0.000 dataclasses.py:1781(_replace)
      657    0.007    0.000    0.357    0.001 npc_attack_controller.py:22(select_npc_attack)
      643    0.002    0.000    0.346    0.001 npc_roster_attack_execution.py:12(execute_npc_roster_attack)
      643    0.007    0.000    0.258    0.000 attack_action_execution.py:20(execute_attack_action)
      360    0.002    0.000    0.183    0.001 npc_round_models.py:39(__post_init__)
     1314    0.021    0.000    0.180    0.000 npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
      360    0.017    0.000    0.179    0.000 npc_round_models.py:91(_validate_steps)
     3894    0.053    0.000    0.149    0.000 npc_round_request_models.py:24(__post_init__)
     5806    0.067    0.000    0.143    0.000 turn_models.py:261(__post_init__)
      643    0.004    0.000    0.143    0.000 kernel.py:86(resolve_kernel_attack)
     2572    0.024    0.000    0.123    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
      100    0.006    0.000    0.118    0.001 npc_mixed_scenario_result_models.py:97(__post_init__)
```

Self time:

```text
2384475 function calls (2383755 primitive calls) in 1.344 seconds

   Ordered by: internal time
   List reduced from 412 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    21415    0.080    0.000    0.566    0.000 dataclasses.py:1781(_replace)
     5806    0.067    0.000    0.143    0.000 turn_models.py:261(__post_init__)
   522916    0.053    0.000    0.053    0.000 {built-in method builtins.isinstance}
     3894    0.053    0.000    0.149    0.000 npc_round_request_models.py:24(__post_init__)
     4624    0.041    0.000    0.052    0.000 test_models.py:216(__post_init__)
     3914    0.028    0.000    0.044    0.000 turn_models.py:202(__post_init__)
   218574    0.027    0.000    0.027    0.000 {built-in method builtins.len}
   181837    0.025    0.000    0.025    0.000 {method 'strip' of 'str' objects}
     5144    0.025    0.000    0.034    0.000 attack_models.py:298(__post_init__)
    21415    0.024    0.000    0.603    0.000 dataclasses.py:1762(replace)
     2572    0.024    0.000    0.123    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
     3285    0.023    0.000    0.049    0.000 npc_attack_selection_models.py:128(__post_init__)
    41836    0.023    0.000    0.051    0.000 npc_roster_models.py:175(participant)
     5918    0.022    0.000    0.037    0.000 turn_models.py:445(_normalize_participants)
     1314    0.021    0.000    0.180    0.000 npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
    45495    0.020    0.000    0.031    0.000 turn_models.py:487(_validate_non_empty_string)
    45367    0.020    0.000    0.031    0.000 npc_roster_models.py:189(_identifier)
   118600    0.019    0.000    0.019    0.000 {built-in method builtins.getattr}
     8974    0.018    0.000    0.032    0.000 npc_attack_preparation_models.py:216(_rank)
      360    0.017    0.000    0.179    0.000 npc_round_models.py:91(_validate_steps)
```

dataclasses.replace callers:

```text
Ordered by: cumulative time
   List reduced from 412 to 1 due to restriction <'dataclasses.py:.*\\(replace\\)'>

Function                      was called by...
                                  ncalls  tottime  cumtime
dataclasses.py:1762(replace)  <-    1929    0.002    0.040  action_execution_models.py:422(_validate_execution_transition)
                                    1929    0.002    0.046  attack_action_execution.py:20(execute_attack_action)
                                     468    0.001    0.019  minion_defeat_models.py:95(_build_continuation)
                                    1314    0.002    0.036  npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
                                     100    0.000    0.002  npc_mixed_scenario_result_models.py:97(__post_init__)
                                     172    0.000    0.008  npc_mixed_scenario_result_models.py:187(current)
                                     657    0.001    0.022  npc_mixed_scenario_runner.py:35(get_candidates)
                                    1750    0.002    0.035  npc_roster_attack_models.py:228(_build_state)
                                     112    0.000    0.004  npc_round_advance_models.py:18(__post_init__)
                                     112    0.000    0.003  npc_round_advance_models.py:57(__post_init__)
                                     224    0.000    0.008  npc_round_advance_models.py:71(continuation)
                                    1314    0.002    0.047  npc_round_coordinator.py:27(run_npc_round)
                                     178    0.000    0.009  npc_round_exclusion.py:14(apply_npc_round_exclusion)
                                     442    0.001    0.016  npc_round_exclusion_models.py:47(round_state)
                                    1568    0.002    0.070  npc_round_models.py:59(continuation)
                                    3842    0.004    0.116  npc_round_models.py:91(_validate_steps)
                                      92    0.000    0.005  npc_rounds_chain_summary_models.py:43(__post_init__)
                                    2572    0.003    0.042  protection_models.py:114(_expected_protection)
                                     112    0.000    0.003  spatial_resolution.py:141(start_next_spatial_round)
                                     657    0.001    0.022  turn_resolution.py:31(start_combat_turn)
                                    1314    0.001    0.033  turn_resolution.py:62(reserve_combat_action_slot)
                                     557    0.001    0.017  turn_resolution.py:149(end_combat_turn)
```

## Profile: 4 actors

Trial-record SHA-256: `26d865a03c89535439672065f65278082135d8f70bfeaf4fdfb4a46c4034ed8c`

Cumulative time:

```text
1633634 function calls (1633026 primitive calls) in 1.019 seconds

   Ordered by: cumulative time
   List reduced from 412 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    1.162    1.162 profile_m7.py:135(run_batch)
        1    0.000    0.000    1.162    1.162 npc_mixed_simulation.py:32(run_npc_mixed_simulation)
      101    0.003    0.000    1.161    0.011 npc_mixed_simulation.py:42(<genexpr>)
      100    0.001    0.000    1.157    0.012 npc_mixed_simulation.py:14(run_npc_mixed_trial)
      100    0.005    0.000    1.141    0.011 npc_mixed_scenario_runner.py:61(run_npc_mixed_scenario)
      304    0.003    0.000    0.943    0.003 npc_rounds_runner.py:42(run_npc_rounds)
      304    0.012    0.000    0.907    0.003 npc_round_coordinator.py:27(run_npc_round)
    15303    0.019    0.000    0.459    0.000 dataclasses.py:1762(replace)
    15303    0.063    0.000    0.430    0.000 dataclasses.py:1781(_replace)
      509    0.006    0.000    0.260    0.001 npc_attack_controller.py:22(select_npc_attack)
      420    0.002    0.000    0.242    0.001 npc_roster_attack_execution.py:12(execute_npc_roster_attack)
      420    0.005    0.000    0.182    0.000 attack_action_execution.py:20(execute_attack_action)
      304    0.002    0.000    0.152    0.001 npc_round_models.py:39(__post_init__)
      304    0.014    0.000    0.149    0.000 npc_round_models.py:91(_validate_steps)
     1018    0.017    0.000    0.132    0.000 npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
     3086    0.043    0.000    0.115    0.000 npc_round_request_models.py:24(__post_init__)
     4143    0.051    0.000    0.106    0.000 turn_models.py:261(__post_init__)
      420    0.002    0.000    0.100    0.000 kernel.py:86(resolve_kernel_attack)
     1680    0.018    0.000    0.093    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
      100    0.005    0.000    0.090    0.001 npc_mixed_scenario_result_models.py:97(__post_init__)
```

Self time:

```text
1633634 function calls (1633026 primitive calls) in 1.019 seconds

   Ordered by: internal time
   List reduced from 412 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    15303    0.063    0.000    0.430    0.000 dataclasses.py:1781(_replace)
     4143    0.051    0.000    0.106    0.000 turn_models.py:261(__post_init__)
     3086    0.043    0.000    0.115    0.000 npc_round_request_models.py:24(__post_init__)
   352963    0.040    0.000    0.040    0.000 {built-in method builtins.isinstance}
     2940    0.028    0.000    0.036    0.000 test_models.py:216(__post_init__)
     2876    0.023    0.000    0.035    0.000 turn_models.py:202(__post_init__)
   154273    0.020    0.000    0.020    0.000 {built-in method builtins.len}
    15303    0.019    0.000    0.459    0.000 dataclasses.py:1762(replace)
   121426    0.018    0.000    0.018    0.000 {method 'strip' of 'str' objects}
     2545    0.018    0.000    0.039    0.000 npc_attack_selection_models.py:128(__post_init__)
     1680    0.018    0.000    0.093    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
     3360    0.017    0.000    0.024    0.000 attack_models.py:298(__post_init__)
     1018    0.017    0.000    0.132    0.000 npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
    28824    0.016    0.000    0.038    0.000 npc_roster_models.py:175(participant)
     4233    0.016    0.000    0.026    0.000 turn_models.py:445(_normalize_participants)
     7524    0.016    0.000    0.028    0.000 npc_attack_preparation_models.py:216(_rank)
    30924    0.015    0.000    0.023    0.000 npc_roster_models.py:189(_identifier)
    83615    0.015    0.000    0.015    0.000 {built-in method builtins.getattr}
      304    0.014    0.000    0.149    0.000 npc_round_models.py:91(_validate_steps)
    29915    0.014    0.000    0.022    0.000 turn_models.py:487(_validate_non_empty_string)
```

dataclasses.replace callers:

```text
Ordered by: cumulative time
   List reduced from 412 to 1 due to restriction <'dataclasses.py:.*\\(replace\\)'>

Function                      was called by...
                                  ncalls  tottime  cumtime
dataclasses.py:1762(replace)  <-    1260    0.001    0.028  action_execution_models.py:422(_validate_execution_transition)
                                    1260    0.002    0.032  attack_action_execution.py:20(execute_attack_action)
                                     250    0.000    0.011  minion_defeat_models.py:95(_build_continuation)
                                    1018    0.001    0.029  npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
                                     100    0.000    0.002  npc_mixed_scenario_result_models.py:97(__post_init__)
                                       6    0.000    0.000  npc_mixed_scenario_result_models.py:187(current)
                                     509    0.001    0.017  npc_mixed_scenario_runner.py:35(get_candidates)
                                    1016    0.001    0.023  npc_roster_attack_models.py:228(_build_state)
                                      90    0.000    0.004  npc_round_advance_models.py:18(__post_init__)
                                      90    0.000    0.002  npc_round_advance_models.py:57(__post_init__)
                                     180    0.000    0.007  npc_round_advance_models.py:71(continuation)
                                    1018    0.001    0.037  npc_round_coordinator.py:27(run_npc_round)
                                      88    0.000    0.004  npc_round_exclusion.py:14(apply_npc_round_exclusion)
                                     179    0.000    0.007  npc_round_exclusion_models.py:47(round_state)
                                    1494    0.002    0.067  npc_round_models.py:59(continuation)
                                    2954    0.004    0.094  npc_round_models.py:91(_validate_steps)
                                      85    0.000    0.004  npc_rounds_chain_summary_models.py:43(__post_init__)
                                    1680    0.002    0.030  protection_models.py:114(_expected_protection)
                                      90    0.000    0.003  spatial_resolution.py:141(start_next_spatial_round)
                                     509    0.001    0.018  turn_resolution.py:31(start_combat_turn)
                                    1018    0.001    0.027  turn_resolution.py:62(reserve_combat_action_slot)
                                     409    0.001    0.013  turn_resolution.py:149(end_combat_turn)
```
