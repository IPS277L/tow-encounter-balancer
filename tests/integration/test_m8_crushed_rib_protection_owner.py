"""Full-owner iff/foreign-source boundaries around actual Protection55."""
from copy import deepcopy
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from towr.domain.npc_crushed_rib_models import NpcCrushedRibContext as Context, NpcCrushedRibConsumptionWitness as Witness
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_champion_attack_resolution import apply_npc_roster_champion_attack_result
from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn
from towr.rules.npc_wound_turn_end import end_npc_wound_turn


def public_fixture():
    examples = Path(__file__).resolve().parents[2] / 'docs/examples/m8'
    spec = importlib.util.spec_from_file_location('adr0056_protection_public_fixture', examples / 'crushed_rib_owner.py')
    module = importlib.util.module_from_spec(spec)
    with patch.object(sys, 'path', [str(examples), *sys.path]):
        spec.loader.exec_module(module)
    return module


class CrushedRibProtectionOwnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.example = public_fixture()

    def ready(self):
        source = self.example.enemy_first()
        current = self.example.first_ten(source)
        request = self.example.shooting(source, current, 'integration:protection', Context(current, 'wizard', True))
        return source, current, request

    def test_upper_none_cannot_use_a_lower_pending_preparation(self):
        _, current, request = self.ready()
        with self.assertRaises(ValueError):
            NpcRosterChampionAttackRequest(current, request.attack)

    def test_deserialized_result_cannot_drop_its_required_upper_context(self):
        _, current, request = self.ready()
        first, _ = self.example.attack(request, (10,) * 6)
        bad = deepcopy(first)
        object.__setattr__(bad.source, 'crushed_rib_context', None)
        with self.assertRaises(ValueError):
            replace(bad)
        with self.assertRaises(ValueError):
            apply_npc_roster_champion_attack_result(current, bad)

    def test_foreign_full_owner_or_raw_fact_context_refused_before_rng(self):
        _, current, request = self.ready()
        foreign = replace(current, consumed_execution_ids=(*current.consumed_execution_ids, 'foreign:action'))
        self.assertEqual(foreign.champion_attack, current.champion_attack)
        with self.assertRaises(ValueError):
            replace(request, state=foreign)
        context = deepcopy(request.crushed_rib_context)
        object.__setattr__(context, 'no_external_condition_sources', 1)
        with self.assertRaises(TypeError):
            replace(request, crushed_rib_context=context)

    def test_pending_context_cannot_be_replaced_by_a_late_consumed_context_or_receipt(self):
        _, current, request = self.ready()
        first, updated = self.example.attack(request, (10,) * 6)
        consumed = Context(updated, 'wizard', True, Witness(first, first.attack.crushed_rib))
        with self.assertRaises(ValueError):
            replace(request, crushed_rib_context=consumed)
        with self.assertRaises(ValueError):
            replace(request, attack=replace(request.attack, crushed_rib_preparation=None,
                crushed_rib_consumption=first.attack.crushed_rib))
        self.assertEqual(apply_npc_roster_champion_attack_result(current, first), updated)
        with self.assertRaises(ValueError):
            apply_npc_roster_champion_attack_result(updated, first)

    def test_later_consumed_request_requires_the_full_first_witness(self):
        source, _, request = self.ready()
        first, updated = self.example.attack(request, (10,) * 6)
        witness = Witness(first, first.attack.crushed_rib)
        ended = end_npc_wound_turn(NpcWoundTurnEndRequest('integration:end:E2', updated, 'E2')).state
        current = start_npc_roster_turn(NpcRosterTurnStartRequest('integration:start:E3', ended, 'E3',
            CombatActionDeclaration(CombatActionKind.ATTACK))).state
        later = self.example.shooting(source, current, 'integration:later', Context(current, 'wizard', True, witness))
        with self.assertRaises(ValueError):
            replace(later, crushed_rib_context=None)
        dice = Dice((10,) * 6)
        lower = execute_npc_champion_attack(later.attack, dice)
        dice.exhausted()
        self.assertIsNone(lower.crushed_rib)
        with self.assertRaises(ValueError):
            replace(later, crushed_rib_context=request.crushed_rib_context)


if __name__ == '__main__':
    unittest.main()
