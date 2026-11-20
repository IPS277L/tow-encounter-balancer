"""Source-bound Bash equipment preparation; these are not full Bash battles."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.domain.armour_models import ArmourLoadout, ShieldKind
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc
from towr.domain.injury_models import WoundEffectDuration, WoundEntryId, WoundRecord, WoundRestriction, WoundRestrictionEffect
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_bash_weapon_models import BashWeaponSelection, select_bash_weapon
from towr.domain.pc_briarroot_models import PcBriarrootBinding
from towr.domain.pc_combat_equipment_models import PcWeaponItem
from towr.domain.pc_heavy_wound_models import PcBodyFact, PcBodyFactKind
from towr.domain.pc_melee_models import (
    PcMeleePolicy, PcMeleeWeapon, PcShieldHandConflictPolicy, PcShieldLoadout, PcShieldRecoveryPolicy,
    PcTwoHandedGrip, PcWeaponHand,
)
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.pc_mount_models import CombatMount
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.pc_npc_weapon_inventory import PcNpcWeaponEquipProof
from towr.domain.npc_roster_models import NpcProtectionProfile
from towr.domain.pc_tactical_models import PcTacticalChoice
from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatActionKind
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_equip_models import plan_weapon_equip
from towr.domain.weapon_inventory_models import WeaponGrip as G, WeaponItemLocation as L, WeaponItemSource
from towr.domain.weapon_use_models import build_weapon_use


def item(kind=W.SWORD, *, id='sword', location=L.HELD, grip=G.LEFT):
    return WeaponItemSource(id, kind, location, grip)


def preparation(items, *, npc=False, shield=False, mount=None):
    """Complete immutable sources plus explicit preparation-only body/history views."""
    first = next(value for value in items if value.initial_location is L.HELD)
    source = make_pc_melee_scenario()
    battlefield = PcBattlefieldSpec(RangedWeaponRange.CLOSE, RangedWeaponRange.LONG) if mount else None
    if npc:
        components = GeneratedNpc(3, 3, 3, 3, 5, 4, items,
            ArmourLoadout(shield=ShieldKind.SHIELD if shield else None), defence=4, brawn=4, mount=mount)
        source = replace(source, enemies=(components.participant('minion1'),),
            facts=replace(source.facts, unmounted=mount is None), battlefield=battlefield)
    else:
        row = source.party[0]
        enemy = source.enemies[0]
        definition = replace(enemy.definition, protection=(
            NpcProtectionProfile('authored:minion:athletics', Skill.ATHLETICS, InlineProfile(2,4)),))
        enemy = replace(enemy, definition=definition)
        weapons = tuple(PcWeaponItem(value.id, value.kind, value.initial_location,
            None if value.initial_grip is None else PcTwoHandedGrip.BOTH if value.initial_grip is G.BOTH
            else PcWeaponHand(value.initial_grip.value)) for value in items)
        loadout = (PcShieldLoadout(PcWeaponHand.RIGHT, PcShieldHandConflictPolicy.WEAPON_FIRST,
            PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK) if shield else None)
        row = replace(row, pc=replace(row.pc, weapon=first.kind, brawn=4), combat_equipment=weapons,
            initial_weapon_hand=PcTwoHandedGrip.BOTH if first.initial_grip is G.BOTH
                else PcWeaponHand(first.initial_grip.value), shield=loadout, mount=mount,
            policy=PcMeleePolicy.AUTOMATIC_COMBAT if mount else row.policy)
        source = replace(source, party=(row,), enemies=(enemy,),
            facts=replace(source.facts, unmounted=mount is None, can_leave_zone=mount is not None),
            battlefield=battlefield)
    initial = initial_pc_melee_state(source)
    state = SimpleNamespace(source=source, party=initial.party, enemies=initial.enemies,
        round_state=initial.round_state, mounts=initial.mounts, history=(),
        briarroot_bindings=(), exited_npc_ids=())
    state.participant = lambda actor: next(member for member in state.party if member.actor_id == actor)
    state.enemy = lambda actor: next(enemy for enemy in state.enemies if enemy.state.actor_id == actor)
    return state


def inventory(state, actor):
    return state.participant(actor).weapon_inventory if actor == 'pc' else state.enemy(actor).state.weapon_inventory


def with_inventory(state, actor, current):
    if actor == 'pc':
        state.party = (replace(state.participant(actor), weapon_inventory=current),)
    else:
        enemy = state.enemy(actor)
        state.enemies = (replace(enemy, state=replace(enemy.state, weapon_inventory=current,
            wields_weapon=any(unit.location is L.HELD for unit in current.items))),)


def spend_equip(state, actor, source_id):
    before = inventory(state, actor)
    unit = next(value for value in before.items if value.source_item_id == source_id)
    transition = plan_weapon_equip(actor, 1, before, held_items=((unit.id, G.LEFT),),
        active_item_id=unit.id, usable_hands=(G.LEFT, G.RIGHT))
    if actor == 'pc':
        intent = PcTacticalChoice(actor, CombatActionKind.ATTACK, 'minion1', None, 0.0,
            'prepared incidental witness', weapon_item_id=unit.id)
        proof = PcWeaponSwapProof(actor, 'prepared:equip', before, transition.after, intent, round_number=1)
    else:
        proof = PcNpcWeaponEquipProof(transition)
    state.history = (proof,)
    with_inventory(state, actor, transition.after)


class BashWeaponSelectionTests(unittest.TestCase):
    def test_held_melee_can_be_selected_without_changing_active_primary_or_inventory(self):
        for npc in (False, True):
            actor, target = ('minion1', 'pc') if npc else ('pc', 'minion1')
            state = preparation((item(W.KNUCKLEDUSTERS, id='knuckles'),
                item(W.SWORD, grip=G.RIGHT)), npc=npc)
            before = inventory(state, actor)
            for active in (before.active_item_id, None):
                current = replace(before, active_item_id=active)
                with_inventory(state, actor, current)
                selected = select_bash_weapon(state, actor, target)
                self.assertIs(selected.use.inventory, current)
                self.assertIs(selected.use.kind, W.SWORD)
                self.assertIsNone(selected.equip)
                self.assertFalse(selected.release_shield)
                self.assertEqual(inventory(state, actor), current)

    def test_unarmed_and_knuckles_are_not_a_melee_strike_permission(self):
        for npc in (False, True):
            state = preparation((item(W.KNUCKLEDUSTERS, id='knuckles'),), npc=npc)
            actor, target = ('minion1', 'pc') if npc else ('pc', 'minion1')
            self.assertIsNone(select_bash_weapon(state, actor, target))
            before = inventory(state, actor)
            with_inventory(state, actor, replace(before, active_item_id=None))
            self.assertIsNone(select_bash_weapon(state, actor, target))

    def test_actual_target_trait_selects_a_held_contributor_and_drained_suppresses_its_bonus(self):
        state = preparation((item(), item(W.WARHAMMER, id='hammer', grip=G.RIGHT)))
        ordinary = select_bash_weapon(state, 'pc', 'minion1')
        self.assertEqual(len(ordinary.use.item_ids), 1)
        enemy = state.enemy('minion1')
        state.enemies = (replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=enemy.state.injury.conditions.with_condition(Condition.STAGGERED)))),)
        selected = select_bash_weapon(state, 'pc', 'minion1')
        self.assertEqual(len(selected.use.item_ids), 2)
        self.assertGreater(selected.utility, ordinary.utility)
        self.assertIsNone(selected.equip)
        member = state.participant('pc')
        state.party = (replace(member,injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.DRAINED))),)
        self.assertEqual(select_bash_weapon(state, 'pc', 'minion1').utility, ordinary.utility)

    def test_carried_draw_has_complete_actual_source_and_preserves_compatible_held_weapon(self):
        state = preparation((item(W.KNUCKLEDUSTERS, id='knuckles'),
            item(W.SWORD, location=L.CARRIED, grip=None)))
        before = inventory(state, 'pc')
        selected = select_bash_weapon(state, 'pc', 'minion1')
        self.assertIs(selected.equip.before, before)
        self.assertEqual(selected.equip.after, selected.use.inventory)
        self.assertTrue(selected.equip.changes_equipment)
        self.assertIs(selected.use.primary_grip, G.RIGHT)
        self.assertIs(selected.use.inventory.items[0].location, L.HELD)
        self.assertEqual(tuple(value.source for value in selected.equip.after.items),
            tuple(value.source for value in before.items))
        self.assertIs(inventory(state, 'pc'), before)

    def test_real_incidental_receipts_block_another_draw_for_both_roles(self):
        for npc in (False, True):
            actor, target = ('minion1', 'pc') if npc else ('pc', 'minion1')
            state = preparation((item(W.KNUCKLEDUSTERS, id='knuckles'),
                item(W.SWORD, location=L.CARRIED, grip=None),
                item(W.HALBERD, id='halberd', location=L.CARRIED, grip=None)), npc=npc)
            spend_equip(state, actor, 'sword')
            selected = select_bash_weapon(state, actor, target)
            self.assertIs(selected.use.kind, W.SWORD)
            self.assertIsNone(selected.equip)
            only_carried = replace(inventory(state, actor), active_item_id=None,
                items=tuple(replace(unit, location=L.CARRIED, grip=None)
                    for unit in inventory(state, actor).items))
            with_inventory(state, actor, only_carried)
            self.assertIsNone(select_bash_weapon(state, actor, target))

    def test_two_handed_draw_forecasts_a_real_separate_shield_release(self):
        for npc in (False, True):
            actor, target = ('minion1', 'pc') if npc else ('pc', 'minion1')
            state = preparation((item(W.KNUCKLEDUSTERS, id='knuckles'),
                item(W.HALBERD, id='halberd', location=L.CARRIED, grip=None)), npc=npc, shield=True)
            before = inventory(state, actor)
            selected = select_bash_weapon(state, actor, target)
            self.assertTrue(selected.release_shield)
            self.assertIs(selected.use.primary_grip, G.BOTH)
            self.assertEqual(selected.equip.before, replace(before, shield_hand=None))
            self.assertIsNone(selected.equip.after.shield_hand)
            self.assertIs(inventory(state, actor), before)
            # Parent executes a typed Shield proof; this only checks the next
            # independently derived preparation after that physical change.
            with_inventory(state, actor, replace(before, shield_hand=None))
            after_drop = select_bash_weapon(state, actor, target)
            self.assertFalse(after_drop.release_shield)
            self.assertEqual(after_drop.use, selected.use)

    def test_unusable_and_clutch_hands_prevent_two_handed_use_without_erasing_sources(self):
        for kind in (PcBodyFactKind.UNUSABLE_ARM, PcBodyFactKind.LOST_ARM, PcBodyFactKind.CLUTCH_STOMACH):
            state = preparation((item(W.HALBERD, id='halberd', grip=G.BOTH),))
            member = state.participant('pc')
            entry, total = {PcBodyFactKind.UNUSABLE_ARM:(WoundEntryId.SLASHED_FOREARMS,16),
                PcBodyFactKind.LOST_ARM:(WoundEntryId.SEVERED_ARM,20),
                PcBodyFactKind.CLUTCH_STOMACH:(WoundEntryId.SPILLING_GUTS,18)}[kind]
            injury = replace(member.injury, wounds=(WoundRecord(1, entry, total,
                (total//2,total//2), effect_resolved=True),))
            state.party = (replace(member, injury=injury,
                body_facts=(PcBodyFact(kind, 1, PcWeaponHand.LEFT),)),)
            before = inventory(state, 'pc')
            self.assertIsNone(select_bash_weapon(state, 'pc', 'minion1'))
            self.assertEqual(inventory(state, 'pc'), before)

    def test_injured_hand_twelve_is_usable_but_healthy_regrip_is_preferred(self):
        state = preparation((item(),))
        member = state.participant('pc')
        injury = replace(member.injury, wounds=(WoundRecord(1,WoundEntryId.SMASHED_HAND,12,
            (6,6),effect_resolved=True),), active_wound_effects=(WoundRestrictionEffect(1,
            WoundRestriction.USING_INJURED_HAND_CAUSES_CRITICAL, WoundEffectDuration.UNTIL_HEALED),))
        state.party = (replace(member, injury=injury,
            body_facts=(PcBodyFact(PcBodyFactKind.INJURED_HAND, 1, PcWeaponHand.LEFT),)),)
        selected = select_bash_weapon(state, 'pc', 'minion1')
        self.assertIs(selected.use.primary_grip, G.RIGHT)
        self.assertIsNotNone(selected.equip)
        # A real spent equip does not invalidate an actually usable injured hand.
        current = inventory(state, 'pc')
        with_inventory(state, 'pc', replace(current,items=(replace(current.items[0],grip=G.RIGHT),)))
        spend_equip(state, 'pc', 'sword')
        selected = select_bash_weapon(state, 'pc', 'minion1')
        self.assertIs(selected.use.primary_grip, G.LEFT)
        self.assertIsNone(selected.equip)
        self.assertFalse(state.participant('pc').injury.conditions.has(Condition.CRITICALLY_INJURED))

    def test_dropped_deployed_stuck_and_spent_units_cannot_be_drawn(self):
        for location in (L.DROPPED, L.DEPLOYED, L.STUCK, L.SPENT):
            state = preparation((item(),))
            before = inventory(state, 'pc')
            unavailable = replace(before, items=(replace(before.items[0], location=location, grip=None),))
            with_inventory(state, 'pc', unavailable)
            self.assertIsNone(select_bash_weapon(state, 'pc', 'minion1'))
            self.assertEqual(inventory(state, 'pc'), unavailable)

    def test_binding_prevents_stowing_a_real_held_unit_to_draw_two_handed_weapon(self):
        state = preparation((item(W.KNUCKLEDUSTERS, id='knuckles'),
            item(W.HALBERD, id='halberd', location=L.CARRIED, grip=None)))
        first = inventory(state, 'pc').items[0]
        state.briarroot_bindings = (PcBriarrootBinding('binding', 'minion1', 'pc', first.id,
            'preceding:attack', 0),)
        self.assertIsNone(select_bash_weapon(state, 'pc', 'minion1'))

    def test_mounted_lance_selection_keeps_no_charge_only_bonus(self):
        state = preparation((item(W.LANCE, id='lance'),), mount=CombatMount.HORSE)
        ordinary = select_bash_weapon(state, 'pc', 'minion1')
        # The selector does not read or copy a Charge receipt: its scoring
        # explicitly retains ordinary mounted facts and charging=False.
        self.assertIs(ordinary.use.kind, W.LANCE)
        self.assertAlmostEqual(ordinary.utility, 2.125)
        self.assertEqual(select_bash_weapon(state, 'pc', 'minion1'), ordinary)

    def test_selection_strictly_rechecks_cached_use_transition_and_scalar_types(self):
        state = preparation((item(),))
        selected = select_bash_weapon(state, 'pc', 'minion1')
        for field, value in (('utility', True), ('utility', float('nan')), ('release_shield', 1),
                ('equip', object())):
            with self.subTest(field=field), self.assertRaises((TypeError, ValueError)):
                replace(selected, **{field: value})
        with self.assertRaises(ValueError):
            replace(selected, release_shield=True)
        with self.assertRaises(ValueError):
            replace(selected, use=build_weapon_use('pc', inventory(state, 'pc'), None))
        forged = deepcopy(selected.use)
        object.__setattr__(forged, 'primary_item_id', 'absent')
        with self.assertRaises((KeyError, ValueError)):
            BashWeaponSelection(forged, None, False, 1.0)
        for actor, target in ((True, 'minion1'), ('unknown', 'minion1'), ('pc', 'pc')):
            with self.subTest(actor=actor, target=target), self.assertRaises((TypeError, ValueError)):
                select_bash_weapon(state, actor, target)


if __name__ == '__main__':
    unittest.main()
