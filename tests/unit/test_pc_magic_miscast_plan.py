from dataclasses import FrozenInstanceError, replace
import unittest

from towr.domain.magic_models import MiscastTableEntryId as Entry
from towr.domain.pc_magic_miscast_plan import PcMagicTask, PcMagicTaskKind as Kind, pc_miscast_tasks
from towr.rules.miscast_table import lookup_miscast


def plan(entry, *, party=('pc2','mage','pc1'), enemies=('npc2','npc1')):
    return pc_miscast_tasks(entry,'actual-roll:effect','mage',party,enemies)


class PcMiscastPlanTests(unittest.TestCase):
    def test_every_actual_table_range_has_exact_supported_or_gm_boundary(self):
        unsupported = {5,6,17,18,23,24,33,34,37,38}
        for total in range(1,46):
            with self.subTest(total=total):
                tasks = plan(lookup_miscast(total).id)
                if total in unsupported:
                    self.assertIsNone(tasks)
                else:
                    self.assertTrue(tasks)
                    self.assertEqual(len({task.id for task in tasks}),len(tasks))

    def test_wind_and_fixed_ears_affect_each_current_actor_once_in_source_order(self):
        actors = ('pc2','mage','pc1','npc2','npc1')
        for entry,kind,amount in ((Entry.UNNATURAL_WIND,Kind.PRONE,0),(Entry.EAR_DAMAGE,Kind.FIXED_EARS,11)):
            with self.subTest(entry=entry):
                tasks = plan(entry)
                self.assertEqual(tuple(task.target_id for task in tasks),actors)
                self.assertTrue(all(task.kind is kind and task.value == amount for task in tasks))
                self.assertTrue(all(task.note is entry for task in tasks))

    def test_stench_applies_only_book_penalty_and_caster_fellowship_quality(self):
        tasks = plan(Entry.HIDEOUS_STENCH)
        self.assertEqual(tuple(task.target_id for task in tasks[:-1]),('pc2','mage','pc1','npc2','npc1'))
        self.assertTrue(all(task.kind is Kind.NEXT_TEST_PENALTY and task.value == -1 for task in tasks[:-1]))
        self.assertEqual((tasks[-1].kind,tasks[-1].target_id,tasks[-1].value),(Kind.FELLOWSHIP_GRIM,'mage',0))

    def test_arcane_spill_keeps_real_stagger_and_harmless_lore_manifestation(self):
        tasks = plan(Entry.ARCANE_SPILL)
        self.assertEqual(tuple(task.kind for task in tasks),(Kind.STAGGER,Kind.NOTE))
        self.assertEqual(tasks[0].target_id,'mage')
        self.assertEqual(tasks[1].affected_ids,('pc2','mage','pc1','npc2','npc1'))
        self.assertIs(tasks[1].note,Entry.ARCANE_SPILL)

    def test_caster_effects_do_not_create_attacks_or_imagined_general_modifiers(self):
        for entry,kind in ((Entry.SUNLIGHT_BLINDNESS,Kind.BLINDED),
                (Entry.INTERNAL_DAMAGE,Kind.RANDOM_WOUND),(Entry.CATASTROPHIC_DEATH,Kind.DEATH)):
            with self.subTest(entry=entry):
                tasks = plan(entry)
                self.assertEqual(len(tasks),1)
                self.assertEqual((tasks[0].kind,tasks[0].target_id),(kind,'mage'))
        sight = plan(Entry.ARCANE_SIGHT)
        self.assertEqual(tuple(task.kind for task in sight),(Kind.AWARENESS_GRIM,Kind.NOTE))
        for entry in (Entry.SENSE_OF_LOSS,Entry.NAUSEATING_WAVE,Entry.FOOD_SPOILED,Entry.UNNATURAL_WEATHER,
                Entry.SHADOW_CHITTERING,Entry.TRUTHBOUND,Entry.FEARED_FOE_ILLUSION):
            with self.subTest(entry=entry):
                tasks = plan(entry)
                self.assertEqual(len(tasks),1)
                self.assertIs(tasks[0].kind,Kind.NOTE)
                self.assertEqual(tasks[0].value,0)

    def test_plan_is_repeatable_immutable_and_retains_source_id(self):
        before_party,before_enemies = ('mage',),('npc',)
        first = plan(Entry.ARCANE_SPILL,party=before_party,enemies=before_enemies)
        self.assertEqual(first,plan(Entry.ARCANE_SPILL,party=before_party,enemies=before_enemies))
        self.assertTrue(all(task.id.startswith('actual-roll:effect:') for task in first))
        self.assertNotEqual(first,pc_miscast_tasks(Entry.ARCANE_SPILL,'other-roll:effect','mage',before_party,before_enemies))
        self.assertEqual((before_party,before_enemies),(('mage',),('npc',)))
        with self.assertRaises(FrozenInstanceError):
            first[0].value = 1
        self.assertEqual(replace(first[0]),first[0])

    def test_dead_enemies_need_not_be_reintroduced_after_a_winning_spell(self):
        tasks = plan(Entry.EAR_DAMAGE,party=('mage',),enemies=())
        self.assertEqual(tuple(task.target_id for task in tasks),('mage',))
        self.assertEqual(plan(Entry.CATASTROPHIC_DEATH,party=('mage',),enemies=())[0].kind,Kind.DEATH)

    def test_bad_ids_kinds_duplicates_and_bool_amounts_are_rejected(self):
        for values in (('sense_of_loss','source','mage',('mage',),()),
                (Entry.SENSE_OF_LOSS,'','mage',('mage',),()),
                (Entry.SENSE_OF_LOSS,'source','mage',['mage'],()),
                (Entry.SENSE_OF_LOSS,'source','mage',('mage','mage'),()),
                (Entry.SENSE_OF_LOSS,'source','mage',('mage',),('mage',)),
                (Entry.SENSE_OF_LOSS,'source','mage',('other',),())):
            with self.subTest(values=values), self.assertRaises((ValueError,TypeError)):
                pc_miscast_tasks(*values)
        for amount in (True,False,1.0,'1'):
            with self.subTest(amount=amount),self.assertRaises(TypeError):
                PcMagicTask('task',Kind.DAMAGE,'npc',amount)
        with self.assertRaises(TypeError):
            PcMagicTask('task','damage','npc',1)
        with self.assertRaises(ValueError):
            PcMagicTask('task',Kind.NOTE,'pc')
        with self.assertRaises(ValueError):
            PcMagicTask('task',Kind.NEXT_TEST_PENALTY,'pc',-2)
        with self.assertRaises(ValueError):
            PcMagicTask('task',Kind.FIXED_EARS,'pc',12)
        with self.assertRaises(ValueError):
            PcMagicTask('task',Kind.DAMAGE,'npc',0)


if __name__ == '__main__':
    unittest.main()
