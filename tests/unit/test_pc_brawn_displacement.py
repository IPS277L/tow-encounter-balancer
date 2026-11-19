"""The automatic alternative needs a real current mount or later ready ally."""
from dataclasses import replace
import unittest

from tests.support.brawn_displacement_battles import pc_shove_scene as source
from towr.domain.brawn_impact_models import BrawnAttackEffect
from towr.domain.pc_battlefield_models import battlefield_range
from towr.domain.pc_brawn_displacement_models import selected_brawn_effect, _shove_battlefield
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.pc_mount_models import CombatMount
from towr.domain.pc_scene_feature_models import PcVisibilityFact
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.weapon_use_models import build_weapon_use


def selection(battle):
    state = initial_pc_melee_state(battle)
    actor, target = battle.pc_activation_order[0], battle.enemy_activation_order[0]
    use = build_weapon_use(actor, state.participant(actor).weapon_inventory, None)
    return state, selected_brawn_effect(state, actor, target, use)


class PcBrawnDisplacementTests(unittest.TestCase):
    def test_shove_is_selected_only_to_enable_real_later_held_sling(self):
        battle = source()
        state, effect = selection(battle)
        self.assertIs(effect, BrawnAttackEffect.SHOVE)
        actor, target = battle.pc_activation_order[0], battle.enemy_activation_order[0]
        after = _shove_battlefield(state, actor, target)
        self.assertIs(battlefield_range(state.battlefield, actor, target), RangedWeaponRange.CLOSE)
        self.assertIs(battlefield_range(after, actor, target), RangedWeaponRange.SHORT)
        self.assertEqual(after.spatial, state.battlefield.spatial)
        self.assertEqual(after.air_to_ground, state.battlefield.air_to_ground)
        self.assertFalse(any(target in pair for pair in after.close_pairs))

    def test_other_close_enemy_prevents_claiming_that_sling_is_now_usable(self):
        _, effect = selection(source(count=2))
        self.assertIs(effect, BrawnAttackEffect.STAGGER)

    def test_unloaded_crossbow_is_not_a_ready_ally_shot(self):
        _, effect = selection(source(weapon='crossbow', loaded=False))
        self.assertIs(effect, BrawnAttackEffect.STAGGER)

    def test_hidden_target_does_not_create_a_fictitious_ready_sling_attack(self):
        battle = source()
        visibility = PcVisibilityFact(battle.pc_activation_order[1], battle.enemy_activation_order[0], False)
        battle = replace(battle, battlefield=replace(battle.battlefield, visibility=(visibility,)))
        _, effect = selection(battle)
        self.assertIs(effect, BrawnAttackEffect.STAGGER)

    def test_real_current_mount_has_priority_over_merely_creating_short_range(self):
        battle = source()
        enemy = battle.enemies[0]
        generated = replace(enemy.definition.generated_components, mount=CombatMount.HORSE)
        battle = replace(battle, enemies=(generated.participant(enemy.state.actor_id),),
            facts=replace(battle.facts, unmounted=False))
        state, effect = selection(battle)
        self.assertIs(effect, BrawnAttackEffect.DISMOUNT)
        self.assertTrue(state.mounts[0].mounted)

    def test_absent_brawn_source_cannot_grant_an_unarmed_alternative(self):
        battle = source()
        actor = battle.party[0]
        # A Staff actor does not acquire a Brawn rating just because a caller
        # constructed an itemless WeaponUse outside the normal selector.
        from towr.domain.pc_combat_equipment_models import PcWeaponItem, PcItemLocation
        from towr.domain.pc_melee_models import PcWeaponHand
        actor = replace(actor, pc=replace(actor.pc, weapon=PcMeleeWeapon.STAFF, brawn=None),
            initial_weapon_hand=PcWeaponHand.LEFT,
            combat_equipment=(PcWeaponItem('staff', PcMeleeWeapon.STAFF,
                PcItemLocation.HELD, PcWeaponHand.LEFT),))
        battle = replace(battle, party=(actor, battle.party[1]))
        _, effect = selection(battle)
        self.assertIs(effect, BrawnAttackEffect.STAGGER)


if __name__ == '__main__':
    unittest.main()
