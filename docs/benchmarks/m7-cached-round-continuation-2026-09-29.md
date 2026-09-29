# M7 sequential benchmark baseline

UTC: 2026-09-29T10:47:27+00:00

Runtime: CPython 3.14.5; Windows-11-10.0.26200-SP0
Processor: Intel64 Family 6 Model 140 Stepping 1, GenuineIntel; GC enabled: True
Source revision: `4db7a22879671cbb1de4ec4581b20f8641a60557 (src has uncommitted changes)`
Source/harness SHA-256: `7ec759973c51dea9f4ff1c06758f5fd07486636a1c6348e8c627a074f7576519`
Seed scheme: `towr:npc-mixed-trial:v1`

```powershell
$env:PYTHONPATH = "src"
& "D:\git\tow-encounter-balancer\.venv\Scripts\python.exe" tools/profile_m7.py --trials 100 --master-seed 20260929 --round-budget 5 --repeats 5 --top 20 --output "docs/benchmarks/m7-cached-round-continuation-2026-09-29.md"
```

Warm-up: min(3, trials) per case. Fixture/imports and gc.collect are outside timing. Wall repeats, tracemalloc and cProfile are separate runs; all trial records and aggregate summaries are compared for equality. Timed batch includes summary projection. Peak is incremental traced Python allocation during one batch, not process RSS; pre-existing fixture/reference result are excluded. cProfile cumulative rows overlap and must not be summed.

Fixtures: 2x1 = Pbow@rear, P1/E1@arena; 3x2 = Pbow@rear, P1/P2/E1/E2@arena; 2x2 = Pbow@rear, P1/E1@arena, E2bow@far. Side/actor order as listed (allies first); target priority is opposing roster order. All enemy pairs involving a bow are explicitly Medium, all other enemy pairs explicitly Close; rear/arena/far are mutually adjacent. Numeric profiles: Footpad Dagger 3d/3 Dam2 RES3 Athletics 3d/3; Brigand Warbow 3d/3 Dam3 RES4 Athletics 3d/2. GM1.1 Allies and Antagonists pp91,93,97; PG1.4 Equipment p94; Rules pp114,118-119. GM-approved KO/outnumbering, can_leave_zone=False, repeated Staggered chooses Wound. Aware, clear sight, stationary, unmounted, complete zone roster, no higher ground/other modifiers/additional rules, sufficient ammunition, no reload action. All four outcomes count; unsupported is a technical stop, not a defeat. These are fixed numeric projections, not full NPC catalogue support.

| Case | Trials | Seed | Round budget | Wall seconds (repeats) | Median s | Peak Python KiB | Outcomes (achieved/defeated/limit/unsupported) | Attacks | Visited rounds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2x1 | 100 | 20260929 | 5 | 0.258576, 0.239004, 0.241099, 0.257461, 0.252417 | 0.252417 | 86.6 | 84/0/0/16 | 298 | 158 |
| 3x2 | 100 | 20260929 | 5 | 0.446887, 0.563118, 0.572916, 0.612043, 0.618008 | 0.572916 | 152.8 | 86/0/0/14 | 643 | 212 |
| 2x2 | 100 | 20260929 | 5 | 0.354759, 0.363014, 0.367780, 0.371561, 0.322723 | 0.363014 | 120.9 | 3/8/0/89 | 420 | 190 |

## Profile: 3 actors

Trial-record SHA-256: `50083eb5e44c0abcf260b97e68a146b056c5ca1ae7405d43688f00753a623fe5`

Cumulative time:

```text
964075 function calls (963711 primitive calls) in 0.570 seconds

   Ordered by: cumulative time
   List reduced from 413 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    0.651    0.651 profile_m7.py:135(run_batch)
        1    0.000    0.000    0.651    0.651 npc_mixed_simulation.py:32(run_npc_mixed_simulation)
      101    0.002    0.000    0.650    0.006 npc_mixed_simulation.py:42(<genexpr>)
      100    0.001    0.000    0.648    0.006 npc_mixed_simulation.py:14(run_npc_mixed_trial)
      100    0.003    0.000    0.633    0.006 npc_mixed_scenario_runner.py:61(run_npc_mixed_scenario)
      182    0.001    0.000    0.542    0.003 npc_rounds_runner.py:42(run_npc_rounds)
      182    0.006    0.000    0.538    0.003 npc_round_coordinator.py:27(run_npc_round)
     9540    0.011    0.000    0.240    0.000 dataclasses.py:1762(replace)
     9540    0.036    0.000    0.224    0.000 dataclasses.py:1781(_replace)
      314    0.003    0.000    0.166    0.001 npc_attack_controller.py:22(select_npc_attack)
      298    0.001    0.000    0.154    0.001 npc_roster_attack_execution.py:12(execute_npc_roster_attack)
      298    0.003    0.000    0.116    0.000 attack_action_execution.py:20(execute_attack_action)
      182    0.001    0.000    0.088    0.000 npc_round_models.py:40(__post_init__)
      182    0.008    0.000    0.078    0.000 npc_round_models.py:97(_validate_steps)
      298    0.001    0.000    0.064    0.000 kernel.py:86(resolve_kernel_attack)
      628    0.008    0.000    0.062    0.000 npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
     2706    0.030    0.000    0.060    0.000 turn_models.py:261(__post_init__)
     1192    0.011    0.000    0.059    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
      596    0.003    0.000    0.052    0.000 npc_attack_selection_models.py:92(attack_preparation_request)
      298    0.003    0.000    0.048    0.000 attack_resolution.py:25(resolve_attack)
```

Self time:

```text
964075 function calls (963711 primitive calls) in 0.570 seconds

   Ordered by: internal time
   List reduced from 413 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
     9540    0.036    0.000    0.224    0.000 dataclasses.py:1781(_replace)
     2706    0.030    0.000    0.060    0.000 turn_models.py:261(__post_init__)
   204520    0.021    0.000    0.021    0.000 {built-in method builtins.isinstance}
     1344    0.016    0.000    0.041    0.000 npc_round_request_models.py:24(__post_init__)
     1788    0.016    0.000    0.020    0.000 test_models.py:216(__post_init__)
     1852    0.013    0.000    0.021    0.000 turn_models.py:202(__post_init__)
    94967    0.012    0.000    0.012    0.000 {built-in method builtins.len}
     2384    0.011    0.000    0.016    0.000 attack_models.py:298(__post_init__)
     1192    0.011    0.000    0.059    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
     9540    0.011    0.000    0.240    0.000 dataclasses.py:1762(replace)
     1570    0.010    0.000    0.022    0.000 npc_attack_selection_models.py:128(__post_init__)
     4876    0.010    0.000    0.017    0.000 npc_attack_preparation_models.py:216(_rank)
    63538    0.009    0.000    0.009    0.000 {method 'strip' of 'str' objects}
     2764    0.009    0.000    0.014    0.000 turn_models.py:445(_normalize_participants)
    54160    0.009    0.000    0.009    0.000 {built-in method builtins.getattr}
      628    0.008    0.000    0.062    0.000 npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
      596    0.008    0.000    0.015    0.000 test_resolution.py:106(complete_test)
      182    0.008    0.000    0.078    0.000 npc_round_models.py:97(_validate_steps)
      744    0.007    0.000    0.011    0.000 spatial_models.py:99(__post_init__)
    14178    0.007    0.000    0.017    0.000 npc_roster_models.py:175(participant)
```

dataclasses.replace callers:

```text
Ordered by: cumulative time
   List reduced from 413 to 1 due to restriction <'dataclasses.py:.*\\(replace\\)'>

Function                      was called by...
                                  ncalls  tottime  cumtime
dataclasses.py:1762(replace)  <-     894    0.001    0.018  action_execution_models.py:422(_validate_execution_transition)
                                     894    0.001    0.020  attack_action_execution.py:20(execute_attack_action)
                                     216    0.000    0.008  minion_defeat_models.py:95(_build_continuation)
                                     628    0.001    0.015  npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
                                     100    0.000    0.002  npc_mixed_scenario_result_models.py:97(__post_init__)
                                     168    0.000    0.007  npc_mixed_scenario_result_models.py:187(current)
                                     314    0.000    0.010  npc_mixed_scenario_runner.py:35(get_candidates)
                                     758    0.001    0.015  npc_roster_attack_models.py:228(_build_state)
                                      58    0.000    0.002  npc_round_advance_models.py:18(__post_init__)
                                      58    0.000    0.001  npc_round_advance_models.py:57(__post_init__)
                                     116    0.000    0.004  npc_round_advance_models.py:71(continuation)
                                     628    0.001    0.020  npc_round_coordinator.py:27(run_npc_round)
                                      84    0.000    0.003  npc_round_exclusion.py:14(apply_npc_round_exclusion)
                                     252    0.000    0.008  npc_round_exclusion_models.py:47(round_state)
                                     182    0.000    0.007  npc_round_models.py:65(_build_continuation)
                                    1784    0.002    0.049  npc_round_models.py:97(_validate_steps)
                                    1192    0.001    0.019  protection_models.py:114(_expected_protection)
                                      58    0.000    0.002  spatial_resolution.py:141(start_next_spatial_round)
                                     314    0.000    0.010  turn_resolution.py:31(start_combat_turn)
                                     628    0.001    0.015  turn_resolution.py:62(reserve_combat_action_slot)
                                     214    0.000    0.006  turn_resolution.py:149(end_combat_turn)
```

## Profile: 5 actors

Trial-record SHA-256: `6dec914d829a246977a683c6fae3ffe524da555495dd1272cd1c475573b5b165`

Cumulative time:

```text
2264707 function calls (2263987 primitive calls) in 1.284 seconds

   Ordered by: cumulative time
   List reduced from 413 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    1.462    1.462 profile_m7.py:135(run_batch)
        1    0.000    0.000    1.462    1.462 npc_mixed_simulation.py:32(run_npc_mixed_simulation)
      101    0.004    0.000    1.462    0.014 npc_mixed_simulation.py:42(<genexpr>)
      100    0.002    0.000    1.457    0.015 npc_mixed_simulation.py:14(run_npc_mixed_trial)
      100    0.006    0.000    1.438    0.014 npc_mixed_scenario_runner.py:61(run_npc_mixed_scenario)
      360    0.003    0.000    1.221    0.003 npc_rounds_runner.py:42(run_npc_rounds)
      360    0.013    0.000    1.214    0.003 npc_round_coordinator.py:27(run_npc_round)
    20207    0.023    0.000    0.550    0.000 dataclasses.py:1762(replace)
    20207    0.076    0.000    0.516    0.000 dataclasses.py:1781(_replace)
      657    0.007    0.000    0.351    0.001 npc_attack_controller.py:22(select_npc_attack)
      643    0.002    0.000    0.342    0.001 npc_roster_attack_execution.py:12(execute_npc_roster_attack)
      643    0.007    0.000    0.253    0.000 attack_action_execution.py:20(execute_attack_action)
      360    0.003    0.000    0.201    0.001 npc_round_models.py:40(__post_init__)
     1314    0.021    0.000    0.179    0.000 npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
      360    0.017    0.000    0.178    0.000 npc_round_models.py:97(_validate_steps)
     5806    0.068    0.000    0.143    0.000 turn_models.py:261(__post_init__)
      643    0.003    0.000    0.140    0.000 kernel.py:86(resolve_kernel_attack)
     2572    0.023    0.000    0.122    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
      657    0.000    0.000    0.119    0.000 npc_rounds_runner.py:38(get_candidates)
      657    0.001    0.000    0.119    0.000 npc_mixed_scenario_runner.py:35(get_candidates)
```

Self time:

```text
2264707 function calls (2263987 primitive calls) in 1.284 seconds

   Ordered by: internal time
   List reduced from 413 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    20207    0.076    0.000    0.516    0.000 dataclasses.py:1781(_replace)
     5806    0.068    0.000    0.143    0.000 turn_models.py:261(__post_init__)
   495572    0.050    0.000    0.050    0.000 {built-in method builtins.isinstance}
     4624    0.041    0.000    0.052    0.000 test_models.py:216(__post_init__)
     2686    0.038    0.000    0.105    0.000 npc_round_request_models.py:24(__post_init__)
     3914    0.028    0.000    0.044    0.000 turn_models.py:202(__post_init__)
   210454    0.025    0.000    0.025    0.000 {built-in method builtins.len}
     5144    0.024    0.000    0.034    0.000 attack_models.py:298(__post_init__)
     2572    0.023    0.000    0.122    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
   164738    0.023    0.000    0.023    0.000 {method 'strip' of 'str' objects}
     3285    0.023    0.000    0.049    0.000 npc_attack_selection_models.py:128(__post_init__)
    20207    0.023    0.000    0.550    0.000 dataclasses.py:1762(replace)
     5918    0.022    0.000    0.037    0.000 turn_models.py:445(_normalize_participants)
     1314    0.021    0.000    0.179    0.000 npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
    36539    0.020    0.000    0.045    0.000 npc_roster_models.py:175(participant)
   114976    0.018    0.000    0.018    0.000 {built-in method builtins.getattr}
     8974    0.018    0.000    0.031    0.000 npc_attack_preparation_models.py:216(_rank)
    40198    0.018    0.000    0.027    0.000 turn_models.py:487(_validate_non_empty_string)
    40070    0.018    0.000    0.027    0.000 npc_roster_models.py:189(_identifier)
     1286    0.018    0.000    0.034    0.000 test_resolution.py:106(complete_test)
```

dataclasses.replace callers:

```text
Ordered by: cumulative time
   List reduced from 413 to 1 due to restriction <'dataclasses.py:.*\\(replace\\)'>

Function                      was called by...
                                  ncalls  tottime  cumtime
dataclasses.py:1762(replace)  <-    1929    0.002    0.040  action_execution_models.py:422(_validate_execution_transition)
                                    1929    0.002    0.045  attack_action_execution.py:20(execute_attack_action)
                                     468    0.001    0.019  minion_defeat_models.py:95(_build_continuation)
                                    1314    0.001    0.035  npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
                                     100    0.000    0.002  npc_mixed_scenario_result_models.py:97(__post_init__)
                                     172    0.000    0.008  npc_mixed_scenario_result_models.py:187(current)
                                     657    0.001    0.023  npc_mixed_scenario_runner.py:35(get_candidates)
                                    1750    0.002    0.035  npc_roster_attack_models.py:228(_build_state)
                                     112    0.000    0.004  npc_round_advance_models.py:18(__post_init__)
                                     112    0.000    0.003  npc_round_advance_models.py:57(__post_init__)
                                     224    0.000    0.008  npc_round_advance_models.py:71(continuation)
                                    1314    0.002    0.048  npc_round_coordinator.py:27(run_npc_round)
                                     178    0.000    0.009  npc_round_exclusion.py:14(apply_npc_round_exclusion)
                                     442    0.001    0.016  npc_round_exclusion_models.py:47(round_state)
                                     360    0.001    0.017  npc_round_models.py:65(_build_continuation)
                                    3842    0.004    0.116  npc_round_models.py:97(_validate_steps)
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
1530499 function calls (1529891 primitive calls) in 0.884 seconds

   Ordered by: cumulative time
   List reduced from 413 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    1.007    1.007 profile_m7.py:135(run_batch)
        1    0.000    0.000    1.007    1.007 npc_mixed_simulation.py:32(run_npc_mixed_simulation)
      101    0.003    0.000    1.006    0.010 npc_mixed_simulation.py:42(<genexpr>)
      100    0.001    0.000    1.003    0.010 npc_mixed_simulation.py:14(run_npc_mixed_trial)
      100    0.004    0.000    0.992    0.010 npc_mixed_scenario_runner.py:61(run_npc_mixed_scenario)
      304    0.002    0.000    0.848    0.003 npc_rounds_runner.py:42(run_npc_rounds)
      304    0.010    0.000    0.842    0.003 npc_round_coordinator.py:27(run_npc_round)
    14113    0.016    0.000    0.376    0.000 dataclasses.py:1762(replace)
    14113    0.054    0.000    0.351    0.000 dataclasses.py:1781(_replace)
      509    0.005    0.000    0.236    0.000 npc_attack_controller.py:22(select_npc_attack)
      420    0.001    0.000    0.222    0.001 npc_roster_attack_execution.py:12(execute_npc_roster_attack)
      420    0.004    0.000    0.167    0.000 attack_action_execution.py:20(execute_attack_action)
      304    0.002    0.000    0.154    0.001 npc_round_models.py:40(__post_init__)
      304    0.013    0.000    0.137    0.000 npc_round_models.py:97(_validate_steps)
     1018    0.015    0.000    0.119    0.000 npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
     4143    0.047    0.000    0.098    0.000 turn_models.py:261(__post_init__)
      420    0.002    0.000    0.092    0.000 kernel.py:86(resolve_kernel_attack)
     1680    0.016    0.000    0.085    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
      509    0.000    0.000    0.079    0.000 npc_rounds_runner.py:38(get_candidates)
      509    0.001    0.000    0.078    0.000 npc_mixed_scenario_runner.py:35(get_candidates)
```

Self time:

```text
1530499 function calls (1529891 primitive calls) in 0.884 seconds

   Ordered by: internal time
   List reduced from 413 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    14113    0.054    0.000    0.351    0.000 dataclasses.py:1781(_replace)
     4143    0.047    0.000    0.098    0.000 turn_models.py:261(__post_init__)
   329703    0.034    0.000    0.034    0.000 {built-in method builtins.isinstance}
     2940    0.026    0.000    0.033    0.000 test_models.py:216(__post_init__)
     1896    0.025    0.000    0.067    0.000 npc_round_request_models.py:24(__post_init__)
     2876    0.021    0.000    0.033    0.000 turn_models.py:202(__post_init__)
   146213    0.018    0.000    0.018    0.000 {built-in method builtins.len}
     2545    0.017    0.000    0.037    0.000 npc_attack_selection_models.py:128(__post_init__)
    14113    0.016    0.000    0.376    0.000 dataclasses.py:1762(replace)
     3360    0.016    0.000    0.022    0.000 attack_models.py:298(__post_init__)
     1680    0.016    0.000    0.085    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
   107138    0.015    0.000    0.015    0.000 {method 'strip' of 'str' objects}
     1018    0.015    0.000    0.119    0.000 npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
     7524    0.015    0.000    0.026    0.000 npc_attack_preparation_models.py:216(_rank)
     4233    0.014    0.000    0.024    0.000 turn_models.py:445(_normalize_participants)
      304    0.013    0.000    0.137    0.000 npc_round_models.py:97(_validate_steps)
    24458    0.013    0.000    0.030    0.000 npc_roster_models.py:175(participant)
    80045    0.013    0.000    0.013    0.000 {built-in method builtins.getattr}
     1198    0.013    0.000    0.020    0.000 spatial_models.py:99(__post_init__)
     5400    0.012    0.000    0.018    0.000 turn_models.py:471(_next_side)
```

dataclasses.replace callers:

```text
Ordered by: cumulative time
   List reduced from 413 to 1 due to restriction <'dataclasses.py:.*\\(replace\\)'>

Function                      was called by...
                                  ncalls  tottime  cumtime
dataclasses.py:1762(replace)  <-    1260    0.001    0.026  action_execution_models.py:422(_validate_execution_transition)
                                    1260    0.001    0.029  attack_action_execution.py:20(execute_attack_action)
                                     250    0.000    0.010  minion_defeat_models.py:95(_build_continuation)
                                    1018    0.001    0.026  npc_mixed_scenario_result_models.py:30(mixed_scenario_candidates)
                                     100    0.000    0.002  npc_mixed_scenario_result_models.py:97(__post_init__)
                                       6    0.000    0.000  npc_mixed_scenario_result_models.py:187(current)
                                     509    0.001    0.016  npc_mixed_scenario_runner.py:35(get_candidates)
                                    1016    0.001    0.022  npc_roster_attack_models.py:228(_build_state)
                                      90    0.000    0.003  npc_round_advance_models.py:18(__post_init__)
                                      90    0.000    0.002  npc_round_advance_models.py:57(__post_init__)
                                     180    0.000    0.006  npc_round_advance_models.py:71(continuation)
                                    1018    0.001    0.035  npc_round_coordinator.py:27(run_npc_round)
                                      88    0.000    0.004  npc_round_exclusion.py:14(apply_npc_round_exclusion)
                                     179    0.000    0.006  npc_round_exclusion_models.py:47(round_state)
                                     304    0.000    0.013  npc_round_models.py:65(_build_continuation)
                                    2954    0.003    0.088  npc_round_models.py:97(_validate_steps)
                                      85    0.000    0.004  npc_rounds_chain_summary_models.py:43(__post_init__)
                                    1680    0.002    0.027  protection_models.py:114(_expected_protection)
                                      90    0.000    0.002  spatial_resolution.py:141(start_next_spatial_round)
                                     509    0.001    0.017  turn_resolution.py:31(start_combat_turn)
                                    1018    0.001    0.025  turn_resolution.py:62(reserve_combat_action_slot)
                                     409    0.000    0.012  turn_resolution.py:149(end_combat_turn)
```
