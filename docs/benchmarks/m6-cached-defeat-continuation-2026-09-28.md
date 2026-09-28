# M6 sequential benchmark baseline

UTC: 2026-09-28T16:21:52+00:00

Runtime: CPython 3.14.5; Windows-11-10.0.26200-SP0
Processor: Intel64 Family 6 Model 140 Stepping 1, GenuineIntel; GC enabled: True
Source revision: `da10b4cdff6b98fdf74fc57996874106afdbc9c6 (src has uncommitted changes)`
Source/harness SHA-256: `806b3b68cf5f4bb7d2c7c07ad8852c4aae872e42a5c2543ce7f1d2ada1a826f3`
Seed scheme: `towr:npc-melee-trial:v1`

```powershell
$env:PYTHONPATH = "src"
py -3.14 tools/profile_m6.py --trials 100 --master-seed 20260928 --round-budget 5 --repeats 3 --top 20 --output "docs/benchmarks/m6-cached-defeat-continuation-2026-09-28.md"
```

Warm-up: min(3, trials) per case. Fixture/imports and gc.collect are outside timing. Wall repeats, tracemalloc and cProfile are separate runs; all trial records and aggregate summaries are compared for equality. Timed batch includes summary projection. Peak is incremental traced Python allocation during one batch, not process RSS; pre-existing fixture/reference result are excluded. cProfile cumulative rows overlap and must not be summed.

| Case | Trials | Seed | Round budget | Wall seconds (repeats) | Median s | Peak Python KiB | Outcomes (achieved/defeated/limit/unsupported) | Attacks | Visited rounds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1x1 | 100 | 20260928 | 5 | 0.317592, 0.272819, 0.256521 | 0.272819 | 87.6 | 52/48/0/0 | 312 | 182 |
| 2x2 | 100 | 20260928 | 5 | 0.532522, 0.760313, 0.602216 | 0.602216 | 125.0 | 58/42/0/0 | 606 | 227 |
| 3x2 | 100 | 20260928 | 5 | 0.618442, 0.622719, 0.704014 | 0.622719 | 148.4 | 96/4/0/0 | 616 | 209 |

## Profile: 2 actors

Trial-record SHA-256: `c6cc84bfb21a94bc79866272fd703e37e46a7fc63237dbe0e1c9e16db61dcb3d`

Cumulative time:

```text
952492 function calls (952128 primitive calls) in 0.647 seconds

   Ordered by: cumulative time
   List reduced from 405 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    0.741    0.741 profile_m6.py:105(run_batch)
        1    0.000    0.000    0.741    0.741 npc_melee_simulation.py:32(run_npc_melee_simulation)
      101    0.003    0.000    0.740    0.007 npc_melee_simulation.py:42(<genexpr>)
      100    0.002    0.000    0.738    0.007 npc_melee_simulation.py:14(run_npc_melee_trial)
      100    0.005    0.000    0.724    0.007 npc_melee_scenario_runner.py:61(run_npc_melee_scenario)
      182    0.002    0.000    0.611    0.003 npc_rounds_runner.py:42(run_npc_rounds)
      182    0.008    0.000    0.593    0.003 npc_round_coordinator.py:27(run_npc_round)
    10316    0.013    0.000    0.273    0.000 dataclasses.py:1762(replace)
    10316    0.043    0.000    0.254    0.000 dataclasses.py:1781(_replace)
      312    0.001    0.000    0.186    0.001 npc_roster_attack_execution.py:12(execute_npc_roster_attack)
      312    0.005    0.000    0.185    0.001 npc_attack_controller.py:22(select_npc_attack)
      312    0.004    0.000    0.140    0.000 attack_action_execution.py:20(execute_attack_action)
      182    0.001    0.000    0.086    0.000 npc_round_models.py:39(__post_init__)
      182    0.009    0.000    0.083    0.000 npc_round_models.py:91(_validate_steps)
      312    0.002    0.000    0.078    0.000 kernel.py:86(resolve_kernel_attack)
     2698    0.033    0.000    0.063    0.000 turn_models.py:261(__post_init__)
     1248    0.012    0.000    0.059    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
      312    0.003    0.000    0.057    0.000 attack_resolution.py:25(resolve_attack)
      624    0.007    0.000    0.056    0.000 npc_melee_scenario_result_models.py:30(melee_scenario_candidates)
      624    0.003    0.000    0.056    0.000 npc_attack_selection_models.py:92(attack_preparation_request)
```

Self time:

```text
952492 function calls (952128 primitive calls) in 0.647 seconds

   Ordered by: internal time
   List reduced from 405 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    10316    0.043    0.000    0.254    0.000 dataclasses.py:1781(_replace)
     2698    0.033    0.000    0.063    0.000 turn_models.py:261(__post_init__)
     1954    0.023    0.000    0.052    0.000 npc_round_request_models.py:24(__post_init__)
   201507    0.022    0.000    0.022    0.000 {built-in method builtins.isinstance}
     1872    0.018    0.000    0.022    0.000 test_models.py:216(__post_init__)
     1872    0.015    0.000    0.023    0.000 turn_models.py:202(__post_init__)
   101300    0.013    0.000    0.013    0.000 {built-in method builtins.len}
     2496    0.013    0.000    0.017    0.000 attack_models.py:298(__post_init__)
    10316    0.013    0.000    0.273    0.000 dataclasses.py:1762(replace)
     1248    0.012    0.000    0.059    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
     1560    0.011    0.000    0.024    0.000 npc_attack_selection_models.py:128(__post_init__)
    56646    0.010    0.000    0.010    0.000 {built-in method builtins.getattr}
      624    0.010    0.000    0.018    0.000 test_resolution.py:106(complete_test)
      182    0.009    0.000    0.083    0.000 npc_round_models.py:91(_validate_steps)
    59819    0.009    0.000    0.009    0.000 {method 'strip' of 'str' objects}
     2780    0.009    0.000    0.013    0.000 turn_models.py:445(_normalize_participants)
     3388    0.009    0.000    0.012    0.000 turn_models.py:471(_next_side)
      182    0.008    0.000    0.593    0.003 npc_round_coordinator.py:27(run_npc_round)
      788    0.008    0.000    0.012    0.000 spatial_models.py:99(__post_init__)
      624    0.008    0.000    0.033    0.000 npc_roster_attack_models.py:131(validate_npc_roster_attack)
```

dataclasses.replace callers:

```text
Ordered by: cumulative time
   List reduced from 405 to 1 due to restriction <'dataclasses.py:.*\\(replace\\)'>

Function                      was called by...
                                  ncalls  tottime  cumtime
dataclasses.py:1762(replace)  <-     936    0.001    0.020  action_execution_models.py:422(_validate_execution_transition)
                                     936    0.001    0.024  attack_action_execution.py:20(execute_attack_action)
                                     200    0.000    0.007  minion_defeat_models.py:95(_build_continuation)
                                     624    0.001    0.015  npc_melee_scenario_result_models.py:30(melee_scenario_candidates)
                                     100    0.000    0.001  npc_melee_scenario_result_models.py:88(__post_init__)
                                     104    0.000    0.004  npc_melee_scenario_result_models.py:179(current)
                                     312    0.000    0.010  npc_melee_scenario_runner.py:35(get_candidates)
                                     866    0.001    0.019  npc_roster_attack_models.py:228(_build_state)
                                      82    0.000    0.002  npc_round_advance_models.py:18(__post_init__)
                                      82    0.000    0.002  npc_round_advance_models.py:57(__post_init__)
                                     164    0.000    0.005  npc_round_advance_models.py:71(continuation)
                                     624    0.001    0.020  npc_round_coordinator.py:27(run_npc_round)
                                      52    0.000    0.002  npc_round_exclusion.py:14(apply_npc_round_exclusion)
                                     156    0.000    0.006  npc_round_exclusion_models.py:47(round_state)
                                     828    0.001    0.028  npc_round_models.py:59(continuation)
                                    1772    0.002    0.051  npc_round_models.py:91(_validate_steps)
                                    1248    0.002    0.022  protection_models.py:114(_expected_protection)
                                      82    0.000    0.002  spatial_resolution.py:141(start_next_spatial_round)
                                     312    0.000    0.011  turn_resolution.py:31(start_combat_turn)
                                     624    0.001    0.016  turn_resolution.py:62(reserve_combat_action_slot)
                                     212    0.000    0.006  turn_resolution.py:149(end_combat_turn)
```

## Profile: 4 actors

Trial-record SHA-256: `ea0c128e33e2207394cb08e0221566cdd23070344913b0de331349c3493f6d2d`

Cumulative time:

```text
2085899 function calls (2085187 primitive calls) in 1.450 seconds

   Ordered by: cumulative time
   List reduced from 407 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    1.666    1.666 profile_m6.py:105(run_batch)
        1    0.000    0.000    1.666    1.666 npc_melee_simulation.py:32(run_npc_melee_simulation)
      101    0.005    0.000    1.665    0.016 npc_melee_simulation.py:42(<genexpr>)
      100    0.002    0.000    1.660    0.017 npc_melee_simulation.py:14(run_npc_melee_trial)
      100    0.009    0.000    1.641    0.016 npc_melee_scenario_runner.py:61(run_npc_melee_scenario)
      356    0.004    0.000    1.375    0.004 npc_rounds_runner.py:42(run_npc_rounds)
      356    0.018    0.000    1.330    0.004 npc_round_coordinator.py:27(run_npc_round)
    20109    0.026    0.000    0.632    0.000 dataclasses.py:1762(replace)
    20109    0.092    0.000    0.591    0.000 dataclasses.py:1781(_replace)
      606    0.003    0.000    0.411    0.001 npc_roster_attack_execution.py:12(execute_npc_roster_attack)
      606    0.009    0.000    0.383    0.001 npc_attack_controller.py:22(select_npc_attack)
      606    0.009    0.000    0.304    0.001 attack_action_execution.py:20(execute_attack_action)
      356    0.003    0.000    0.204    0.001 npc_round_models.py:39(__post_init__)
      356    0.021    0.000    0.200    0.001 npc_round_models.py:91(_validate_steps)
      606    0.005    0.000    0.172    0.000 kernel.py:86(resolve_kernel_attack)
     1212    0.018    0.000    0.165    0.000 npc_melee_scenario_result_models.py:30(melee_scenario_candidates)
     5345    0.070    0.000    0.145    0.000 turn_models.py:261(__post_init__)
     3662    0.055    0.000    0.140    0.000 npc_round_request_models.py:24(__post_init__)
     2424    0.028    0.000    0.126    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
      606    0.008    0.000    0.122    0.000 attack_resolution.py:25(resolve_attack)
```

Self time:

```text
2085899 function calls (2085187 primitive calls) in 1.450 seconds

   Ordered by: internal time
   List reduced from 407 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    20109    0.092    0.000    0.591    0.000 dataclasses.py:1781(_replace)
     5345    0.070    0.000    0.145    0.000 turn_models.py:261(__post_init__)
     3662    0.055    0.000    0.140    0.000 npc_round_request_models.py:24(__post_init__)
   454398    0.052    0.000    0.052    0.000 {built-in method builtins.isinstance}
     4464    0.045    0.000    0.056    0.000 test_models.py:216(__post_init__)
     3636    0.032    0.000    0.049    0.000 turn_models.py:202(__post_init__)
     2424    0.028    0.000    0.126    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
     3030    0.028    0.000    0.055    0.000 npc_attack_selection_models.py:128(__post_init__)
   206349    0.028    0.000    0.028    0.000 {built-in method builtins.len}
    20109    0.026    0.000    0.632    0.000 dataclasses.py:1762(replace)
     4848    0.026    0.000    0.036    0.000 attack_models.py:298(__post_init__)
   145300    0.023    0.000    0.023    0.000 {method 'strip' of 'str' objects}
   110958    0.021    0.000    0.021    0.000 {built-in method builtins.getattr}
      356    0.021    0.000    0.200    0.001 npc_round_models.py:91(_validate_steps)
     5472    0.021    0.000    0.034    0.000 turn_models.py:445(_normalize_participants)
     1212    0.021    0.000    0.039    0.000 test_resolution.py:106(complete_test)
    34022    0.020    0.000    0.046    0.000 npc_roster_models.py:175(participant)
     6782    0.019    0.000    0.027    0.000 turn_models.py:471(_next_side)
     2040    0.018    0.000    0.028    0.000 npc_attack_selection_models.py:64(__post_init__)
    37619    0.018    0.000    0.028    0.000 npc_roster_models.py:189(_identifier)
```

dataclasses.replace callers:

```text
Ordered by: cumulative time
   List reduced from 407 to 1 due to restriction <'dataclasses.py:.*\\(replace\\)'>

Function                      was called by...
                                  ncalls  tottime  cumtime
dataclasses.py:1762(replace)  <-    1818    0.002    0.042  action_execution_models.py:422(_validate_execution_transition)
                                    1818    0.002    0.053  attack_action_execution.py:20(execute_attack_action)
                                     458    0.001    0.023  minion_defeat_models.py:95(_build_continuation)
                                    1212    0.002    0.036  npc_melee_scenario_result_models.py:30(melee_scenario_candidates)
                                     100    0.000    0.002  npc_melee_scenario_result_models.py:88(__post_init__)
                                     116    0.000    0.005  npc_melee_scenario_result_models.py:179(current)
                                     606    0.001    0.025  npc_melee_scenario_runner.py:35(get_candidates)
                                    1810    0.002    0.048  npc_roster_attack_models.py:228(_build_state)
                                     127    0.000    0.004  npc_round_advance_models.py:18(__post_init__)
                                     127    0.000    0.003  npc_round_advance_models.py:57(__post_init__)
                                     254    0.000    0.009  npc_round_advance_models.py:71(continuation)
                                    1212    0.002    0.047  npc_round_coordinator.py:27(run_npc_round)
                                     129    0.000    0.006  npc_round_exclusion.py:14(apply_npc_round_exclusion)
                                     316    0.000    0.012  npc_round_exclusion_models.py:47(round_state)
                                    1524    0.002    0.069  npc_round_models.py:59(continuation)
                                    3536    0.005    0.122  npc_round_models.py:91(_validate_steps)
                                      71    0.000    0.003  npc_rounds_chain_summary_models.py:43(__post_init__)
                                    2424    0.003    0.044  protection_models.py:114(_expected_protection)
                                     127    0.000    0.004  spatial_resolution.py:141(start_next_spatial_round)
                                     606    0.001    0.022  turn_resolution.py:31(start_combat_turn)
                                    1212    0.001    0.034  turn_resolution.py:62(reserve_combat_action_slot)
                                     506    0.001    0.016  turn_resolution.py:149(end_combat_turn)
```

## Profile: 5 actors

Trial-record SHA-256: `78e6654e992b4c8d09ba180fb07245da650b12638acdc8c35f3841ec31fda92b`

Cumulative time:

```text
2245073 function calls (2244397 primitive calls) in 2.218 seconds

   Ordered by: cumulative time
   List reduced from 407 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    2.550    2.550 profile_m6.py:105(run_batch)
        1    0.000    0.000    2.549    2.549 npc_melee_simulation.py:32(run_npc_melee_simulation)
      101    0.007    0.000    2.549    0.025 npc_melee_simulation.py:42(<genexpr>)
      100    0.003    0.000    2.542    0.025 npc_melee_simulation.py:14(run_npc_melee_trial)
      100    0.016    0.000    2.504    0.025 npc_melee_scenario_runner.py:61(run_npc_melee_scenario)
      338    0.006    0.000    2.069    0.006 npc_rounds_runner.py:42(run_npc_rounds)
      338    0.028    0.000    2.000    0.006 npc_round_coordinator.py:27(run_npc_round)
    20571    0.047    0.000    0.971    0.000 dataclasses.py:1762(replace)
    20571    0.136    0.000    0.899    0.000 dataclasses.py:1781(_replace)
      616    0.004    0.000    0.618    0.001 npc_roster_attack_execution.py:12(execute_npc_roster_attack)
      616    0.016    0.000    0.575    0.001 npc_attack_controller.py:22(select_npc_attack)
      616    0.014    0.000    0.448    0.001 attack_action_execution.py:20(execute_attack_action)
      338    0.004    0.000    0.286    0.001 npc_round_models.py:39(__post_init__)
      338    0.031    0.000    0.279    0.001 npc_round_models.py:91(_validate_steps)
     1232    0.033    0.000    0.271    0.000 npc_melee_scenario_result_models.py:30(melee_scenario_candidates)
      616    0.006    0.000    0.250    0.000 kernel.py:86(resolve_kernel_attack)
     3724    0.087    0.000    0.229    0.000 npc_round_request_models.py:24(__post_init__)
     5539    0.102    0.000    0.216    0.000 turn_models.py:261(__post_init__)
      100    0.013    0.000    0.190    0.002 npc_melee_scenario_result_models.py:88(__post_init__)
      616    0.001    0.000    0.185    0.000 npc_rounds_runner.py:38(get_candidates)
```

Self time:

```text
2245073 function calls (2244397 primitive calls) in 2.218 seconds

   Ordered by: internal time
   List reduced from 407 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    20571    0.136    0.000    0.899    0.000 dataclasses.py:1781(_replace)
     5539    0.102    0.000    0.216    0.000 turn_models.py:261(__post_init__)
     3724    0.087    0.000    0.229    0.000 npc_round_request_models.py:24(__post_init__)
   495328    0.081    0.000    0.081    0.000 {built-in method builtins.isinstance}
     4648    0.065    0.000    0.086    0.000 test_models.py:216(__post_init__)
     3696    0.047    0.000    0.076    0.000 turn_models.py:202(__post_init__)
    20571    0.047    0.000    0.971    0.000 dataclasses.py:1762(replace)
   211026    0.040    0.000    0.040    0.000 {built-in method builtins.len}
     4928    0.040    0.000    0.053    0.000 attack_models.py:298(__post_init__)
     2464    0.038    0.000    0.179    0.000 npc_attack_preparation_models.py:177(_expected_npc_attack)
     1232    0.038    0.000    0.120    0.000 npc_roster_attack_models.py:131(validate_npc_roster_attack)
     3080    0.036    0.000    0.078    0.000 npc_attack_selection_models.py:128(__post_init__)
   163021    0.036    0.000    0.036    0.000 {method 'strip' of 'str' objects}
   113884    0.033    0.000    0.033    0.000 {built-in method builtins.getattr}
     1232    0.033    0.000    0.271    0.000 npc_melee_scenario_result_models.py:30(melee_scenario_candidates)
     5648    0.033    0.000    0.053    0.000 turn_models.py:445(_normalize_participants)
    38707    0.031    0.000    0.069    0.000 npc_roster_models.py:175(participant)
      338    0.031    0.000    0.279    0.001 npc_round_models.py:91(_validate_steps)
     2184    0.029    0.000    0.044    0.000 npc_attack_selection_models.py:64(__post_init__)
     1232    0.028    0.000    0.055    0.000 test_resolution.py:106(complete_test)
```

dataclasses.replace callers:

```text
Ordered by: cumulative time
   List reduced from 407 to 1 due to restriction <'dataclasses.py:.*\\(replace\\)'>

Function                      was called by...
                                  ncalls  tottime  cumtime
dataclasses.py:1762(replace)  <-    1848    0.003    0.065  action_execution_models.py:422(_validate_execution_transition)
                                    1848    0.006    0.080  attack_action_execution.py:20(execute_attack_action)
                                     458    0.001    0.032  minion_defeat_models.py:95(_build_continuation)
                                    1232    0.003    0.059  npc_melee_scenario_result_models.py:30(melee_scenario_candidates)
                                     100    0.000    0.003  npc_melee_scenario_result_models.py:88(__post_init__)
                                     192    0.000    0.016  npc_melee_scenario_result_models.py:179(current)
                                     616    0.001    0.036  npc_melee_scenario_runner.py:35(get_candidates)
                                    1848    0.003    0.065  npc_roster_attack_models.py:228(_build_state)
                                     109    0.000    0.006  npc_round_advance_models.py:18(__post_init__)
                                     109    0.000    0.004  npc_round_advance_models.py:57(__post_init__)
                                     218    0.000    0.012  npc_round_advance_models.py:71(continuation)
                                    1232    0.002    0.069  npc_round_coordinator.py:27(run_npc_round)
                                     194    0.000    0.016  npc_round_exclusion.py:14(apply_npc_round_exclusion)
                                     484    0.003    0.033  npc_round_exclusion_models.py:47(round_state)
                                    1452    0.006    0.112  npc_round_models.py:59(continuation)
                                    3596    0.006    0.177  npc_round_models.py:91(_validate_steps)
                                      98    0.000    0.008  npc_rounds_chain_summary_models.py:43(__post_init__)
                                    2464    0.005    0.063  protection_models.py:114(_expected_protection)
                                     109    0.000    0.005  spatial_resolution.py:141(start_next_spatial_round)
                                     616    0.001    0.033  turn_resolution.py:31(start_combat_turn)
                                    1232    0.002    0.050  turn_resolution.py:62(reserve_combat_action_slot)
                                     516    0.002    0.027  turn_resolution.py:149(end_combat_turn)
```
