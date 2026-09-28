# M3 sequential benchmark baseline

UTC: 2026-09-28T10:42:57+00:00

Runtime: CPython 3.14.5; Windows-11-10.0.26200-SP0
Processor: Intel64 Family 6 Model 140 Stepping 1, GenuineIntel; GC enabled: True
Source revision: `b1eeecd4985e006400c2733c0b91090b73ab3cf0 (src has uncommitted changes)`
Seed scheme: `towr:npc-ranged-trial:v1`

```powershell
$env:PYTHONPATH = "src"
py -3.14 tools/profile_m3.py --trials 100 --master-seed 20260928 --round-budget 5 --repeats 3 --top 12 --output "docs/benchmarks/m3-cached-attack-state-2026-09-28.md"
```

Warm-up: min(3, trials) per case. Fixture/imports and gc.collect are outside timing. Wall repeats, tracemalloc and cProfile are separate runs; all trial records are compared for equality. Peak is incremental traced Python allocation during one batch, not process RSS; pre-existing fixture/reference result are excluded. cProfile cumulative rows overlap and must not be summed.

| Case | Trials | Seed | Round budget | Wall seconds (repeats) | Median s | Peak Python KiB | Outcomes (achieved/defeated/limit/unsupported) | Attacks | Visited rounds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1x1 | 100 | 20260928 | 5 | 0.236101, 0.301168, 0.273343 | 0.273343 | 96.6 | 56/43/1/0 | 368 | 212 |
| 2x2 | 100 | 20260928 | 5 | 0.584341, 0.664305, 0.566432 | 0.584341 | 144.7 | 67/30/3/0 | 810 | 307 |
| 3x2 | 100 | 20260928 | 5 | 0.644116, 0.588850, 0.643556 | 0.643556 | 149.0 | 95/5/0/0 | 735 | 232 |

## Profile: 2 actors

Trial-record SHA-256: `55f0e0354cd51d2e014d34062966c3cb570b7093bf627d2917a3143448eaf1a0`

Cumulative time:

```text
1192562 function calls (1192138 primitive calls) in 0.646 seconds

   Ordered by: cumulative time
   List reduced from 388 to 12 due to restriction <12>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    0.735    0.735 npc_ranged_simulation.py:30(run_npc_ranged_simulation)
      101    0.002    0.000    0.734    0.007 npc_ranged_simulation.py:40(<genexpr>)
      100    0.001    0.000    0.732    0.007 npc_ranged_simulation.py:14(run_npc_ranged_trial)
      100    0.003    0.000    0.713    0.007 npc_ranged_scenario_runner.py:61(run_npc_ranged_scenario)
      212    0.001    0.000    0.587    0.003 npc_rounds_runner.py:42(run_npc_rounds)
      212    0.007    0.000    0.570    0.003 npc_round_coordinator.py:27(run_npc_round)
    12330    0.013    0.000    0.284    0.000 dataclasses.py:1762(replace)
    12330    0.042    0.000    0.264    0.000 dataclasses.py:1781(_replace)
      368    0.004    0.000    0.194    0.001 npc_attack_controller.py:22(select_npc_attack)
      368    0.001    0.000    0.171    0.000 npc_roster_attack_execution.py:12(execute_npc_roster_attack)
      368    0.004    0.000    0.130    0.000 attack_action_execution.py:20(execute_attack_action)
      212    0.001    0.000    0.084    0.000 npc_round_models.py:39(__post_init__)
```

Self time:

```text
1192562 function calls (1192138 primitive calls) in 0.646 seconds

   Ordered by: internal time
   List reduced from 388 to 12 due to restriction <12>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    12330    0.042    0.000    0.264    0.000 dataclasses.py:1781(_replace)
     3250    0.032    0.000    0.063    0.000 turn_models.py:261(__post_init__)
     2840    0.027    0.000    0.065    0.000 npc_round_request_models.py:24(__post_init__)
   246791    0.025    0.000    0.025    0.000 {built-in method builtins.isinstance}
     2208    0.018    0.000    0.023    0.000 test_models.py:216(__post_init__)
     2208    0.015    0.000    0.023    0.000 turn_models.py:202(__post_init__)
     8096    0.015    0.000    0.025    0.000 npc_attack_preparation_models.py:216(_rank)
   124799    0.014    0.000    0.014    0.000 {built-in method builtins.len}
     1018    0.013    0.000    0.019    0.000 npc_roster_attack_models.py:49(__post_init__)
     1472    0.013    0.000    0.075    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
    12330    0.013    0.000    0.284    0.000 dataclasses.py:1762(replace)
     2944    0.013    0.000    0.018    0.000 attack_models.py:298(__post_init__)
```

dataclasses.replace callers:

```text
Ordered by: cumulative time
   List reduced from 388 to 1 due to restriction <'dataclasses.py:.*\\(replace\\)'>

Function                      was called by...
                                  ncalls  tottime  cumtime
dataclasses.py:1762(replace)  <-    1104    0.001    0.020  action_execution_models.py:422(_validate_execution_transition)
                                    1104    0.001    0.022  attack_action_execution.py:20(execute_attack_action)
                                    1300    0.001    0.038  minion_defeat_models.py:89(continuation)
                                     100    0.000    0.001  npc_ranged_scenario_result_models.py:60(__post_init__)
                                     112    0.000    0.004  npc_ranged_scenario_result_models.py:150(current)
                                     368    0.000    0.010  npc_ranged_scenario_runner.py:35(get_candidates)
                                     818    0.001    0.015  npc_roster_attack_models.py:228(_build_state)
                                     112    0.000    0.003  npc_round_advance_models.py:18(__post_init__)
                                     112    0.000    0.002  npc_round_advance_models.py:57(__post_init__)
                                     224    0.000    0.006  npc_round_advance_models.py:71(continuation)
                                     736    0.001    0.020  npc_round_coordinator.py:27(run_npc_round)
                                      56    0.000    0.002  npc_round_exclusion.py:14(apply_npc_round_exclusion)
                                     168    0.000    0.005  npc_round_exclusion_models.py:47(round_state)
                                     950    0.001    0.028  npc_round_models.py:59(continuation)
                                    2109    0.002    0.050  npc_round_models.py:91(_validate_steps)
                                    1472    0.002    0.022  protection_models.py:114(_expected_protection)
                                     112    0.000    0.003  spatial_resolution.py:141(start_next_spatial_round)
                                     368    0.000    0.011  turn_resolution.py:31(start_combat_turn)
                                     736    0.001    0.016  turn_resolution.py:62(reserve_combat_action_slot)
                                     269    0.000    0.007  turn_resolution.py:149(end_combat_turn)
```

## Profile: 4 actors

Trial-record SHA-256: `b2416792286dce9f28d5f2d03864aceedb4241135e141ecf807e994481bc5cc4`

Cumulative time:

```text
2830633 function calls (2829721 primitive calls) in 1.713 seconds

   Ordered by: cumulative time
   List reduced from 388 to 12 due to restriction <12>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    1.954    1.954 npc_ranged_simulation.py:30(run_npc_ranged_simulation)
      101    0.005    0.000    1.953    0.019 npc_ranged_simulation.py:40(<genexpr>)
      100    0.002    0.000    1.948    0.019 npc_ranged_simulation.py:14(run_npc_ranged_trial)
      100    0.008    0.000    1.921    0.019 npc_ranged_scenario_runner.py:61(run_npc_ranged_scenario)
      456    0.004    0.000    1.597    0.004 npc_rounds_runner.py:42(run_npc_rounds)
      456    0.019    0.000    1.547    0.003 npc_round_coordinator.py:27(run_npc_round)
    25951    0.031    0.000    0.752    0.000 dataclasses.py:1762(replace)
    25951    0.104    0.000    0.704    0.000 dataclasses.py:1781(_replace)
      810    0.010    0.000    0.499    0.001 npc_attack_controller.py:22(select_npc_attack)
      810    0.003    0.000    0.457    0.001 npc_roster_attack_execution.py:12(execute_npc_roster_attack)
      810    0.009    0.000    0.343    0.000 attack_action_execution.py:20(execute_attack_action)
      456    0.003    0.000    0.232    0.001 npc_round_models.py:39(__post_init__)
```

Self time:

```text
2830633 function calls (2829721 primitive calls) in 1.713 seconds

   Ordered by: internal time
   List reduced from 388 to 12 due to restriction <12>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    25951    0.104    0.000    0.704    0.000 dataclasses.py:1781(_replace)
     7286    0.086    0.000    0.177    0.000 turn_models.py:261(__post_init__)
     5497    0.070    0.000    0.183    0.000 npc_round_request_models.py:24(__post_init__)
   607954    0.067    0.000    0.067    0.000 {built-in method builtins.isinstance}
     5866    0.055    0.000    0.070    0.000 test_models.py:216(__post_init__)
     4860    0.038    0.000    0.059    0.000 turn_models.py:202(__post_init__)
    17820    0.036    0.000    0.063    0.000 npc_attack_preparation_models.py:216(_rank)
   274408    0.036    0.000    0.036    0.000 {built-in method builtins.len}
     3240    0.034    0.000    0.188    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
     6480    0.033    0.000    0.046    0.000 attack_models.py:298(__post_init__)
    25951    0.031    0.000    0.752    0.000 dataclasses.py:1762(replace)
   206358    0.031    0.000    0.031    0.000 {method 'strip' of 'str' objects}
```

dataclasses.replace callers:

```text
Ordered by: cumulative time
   List reduced from 388 to 1 due to restriction <'dataclasses.py:.*\\(replace\\)'>

Function                      was called by...
                                  ncalls  tottime  cumtime
dataclasses.py:1762(replace)  <-    2430    0.003    0.053  action_execution_models.py:422(_validate_execution_transition)
                                    2430    0.003    0.060  attack_action_execution.py:20(execute_attack_action)
                                    1894    0.002    0.073  minion_defeat_models.py:89(continuation)
                                     100    0.000    0.002  npc_ranged_scenario_result_models.py:60(__post_init__)
                                     134    0.000    0.005  npc_ranged_scenario_result_models.py:150(current)
                                     810    0.001    0.029  npc_ranged_scenario_runner.py:35(get_candidates)
                                    1798    0.002    0.044  npc_roster_attack_models.py:228(_build_state)
                                     207    0.000    0.007  npc_round_advance_models.py:18(__post_init__)
                                     207    0.000    0.005  npc_round_advance_models.py:57(__post_init__)
                                     414    0.000    0.014  npc_round_advance_models.py:71(continuation)
                                    1620    0.002    0.057  npc_round_coordinator.py:27(run_npc_round)
                                     156    0.000    0.007  npc_round_exclusion.py:14(apply_npc_round_exclusion)
                                     379    0.000    0.014  npc_round_exclusion_models.py:47(round_state)
                                    1930    0.003    0.079  npc_round_models.py:59(continuation)
                                    4763    0.006    0.144  npc_round_models.py:91(_validate_steps)
                                      89    0.000    0.004  npc_rounds_chain_summary_models.py:43(__post_init__)
                                    3240    0.004    0.057  protection_models.py:114(_expected_protection)
                                     207    0.000    0.007  spatial_resolution.py:141(start_next_spatial_round)
                                     810    0.001    0.028  turn_resolution.py:31(start_combat_turn)
                                    1620    0.002    0.042  turn_resolution.py:62(reserve_combat_action_slot)
                                     713    0.001    0.021  turn_resolution.py:149(end_combat_turn)
```

## Profile: 5 actors

Trial-record SHA-256: `ff2343bf24fe833ea98c5c5f45b8719de6671cf0d0cf54db10a78ede447c901c`

Cumulative time:

```text
2698915 function calls (2698183 primitive calls) in 1.455 seconds

   Ordered by: cumulative time
   List reduced from 386 to 12 due to restriction <12>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    1.654    1.654 npc_ranged_simulation.py:30(run_npc_ranged_simulation)
      101    0.004    0.000    1.653    0.016 npc_ranged_simulation.py:40(<genexpr>)
      100    0.002    0.000    1.649    0.016 npc_ranged_simulation.py:14(run_npc_ranged_trial)
      100    0.006    0.000    1.621    0.016 npc_ranged_scenario_runner.py:61(run_npc_ranged_scenario)
      366    0.003    0.000    1.330    0.004 npc_rounds_runner.py:42(run_npc_rounds)
      366    0.014    0.000    1.289    0.004 npc_round_coordinator.py:27(run_npc_round)
    23552    0.026    0.000    0.667    0.000 dataclasses.py:1762(replace)
    23552    0.085    0.000    0.627    0.000 dataclasses.py:1781(_replace)
      735    0.008    0.000    0.407    0.001 npc_attack_controller.py:22(select_npc_attack)
      735    0.002    0.000    0.376    0.001 npc_roster_attack_execution.py:12(execute_npc_roster_attack)
      735    0.008    0.000    0.282    0.000 attack_action_execution.py:20(execute_attack_action)
      366    0.002    0.000    0.200    0.001 npc_round_models.py:39(__post_init__)
```

Self time:

```text
2698915 function calls (2698183 primitive calls) in 1.455 seconds

   Ordered by: internal time
   List reduced from 386 to 12 due to restriction <12>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    23552    0.085    0.000    0.627    0.000 dataclasses.py:1781(_replace)
     6557    0.074    0.000    0.158    0.000 turn_models.py:261(__post_init__)
     4874    0.065    0.000    0.182    0.000 npc_round_request_models.py:24(__post_init__)
   587931    0.058    0.000    0.058    0.000 {built-in method builtins.isinstance}
     5616    0.048    0.000    0.061    0.000 test_models.py:216(__post_init__)
     4410    0.031    0.000    0.049    0.000 turn_models.py:202(__post_init__)
    16170    0.031    0.000    0.053    0.000 npc_attack_preparation_models.py:216(_rank)
   250770    0.030    0.000    0.030    0.000 {built-in method builtins.len}
   208143    0.028    0.000    0.028    0.000 {method 'strip' of 'str' objects}
     2940    0.028    0.000    0.156    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
     5880    0.027    0.000    0.038    0.000 attack_models.py:298(__post_init__)
    50437    0.026    0.000    0.059    0.000 npc_roster_models.py:175(participant)
```

dataclasses.replace callers:

```text
Ordered by: cumulative time
   List reduced from 386 to 1 due to restriction <'dataclasses.py:.*\\(replace\\)'>

Function                      was called by...
                                  ncalls  tottime  cumtime
dataclasses.py:1762(replace)  <-    2205    0.002    0.045  action_execution_models.py:422(_validate_execution_transition)
                                    2205    0.002    0.050  attack_action_execution.py:20(execute_attack_action)
                                    1926    0.002    0.074  minion_defeat_models.py:89(continuation)
                                     100    0.000    0.002  npc_ranged_scenario_result_models.py:60(__post_init__)
                                     190    0.000    0.008  npc_ranged_scenario_result_models.py:150(current)
                                     735    0.001    0.025  npc_ranged_scenario_runner.py:35(get_candidates)
                                    1635    0.002    0.035  npc_roster_attack_models.py:228(_build_state)
                                     132    0.000    0.005  npc_round_advance_models.py:18(__post_init__)
                                     132    0.000    0.003  npc_round_advance_models.py:57(__post_init__)
                                     264    0.000    0.010  npc_round_advance_models.py:71(continuation)
                                    1470    0.002    0.052  npc_round_coordinator.py:27(run_npc_round)
                                     193    0.000    0.009  npc_round_exclusion.py:14(apply_npc_round_exclusion)
                                     481    0.001    0.017  npc_round_exclusion_models.py:47(round_state)
                                    1564    0.002    0.069  npc_round_models.py:59(continuation)
                                    4310    0.005    0.128  npc_round_models.py:91(_validate_steps)
                                      98    0.000    0.005  npc_rounds_chain_summary_models.py:43(__post_init__)
                                    2940    0.003    0.047  protection_models.py:114(_expected_protection)
                                     132    0.000    0.004  spatial_resolution.py:141(start_next_spatial_round)
                                     735    0.001    0.024  turn_resolution.py:31(start_combat_turn)
                                    1470    0.002    0.036  turn_resolution.py:62(reserve_combat_action_slot)
                                     635    0.001    0.018  turn_resolution.py:149(end_combat_turn)
```
