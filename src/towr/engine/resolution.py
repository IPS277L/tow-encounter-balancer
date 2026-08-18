from __future__ import annotations

from dataclasses import dataclass

from towr.domain.actions import AttackAction
from towr.domain.combatants import CombatantState
from towr.engine.events import BattleEvent, EventSink
from towr.rules.damage import DamageOutcome, calculate_damage, resolve_damage
from towr.rules.dice import RandomSource, roll_pool
from towr.rules.health import HealthChange, apply_miss_stagger, apply_stagger, apply_wound
from towr.rules.opposed_roll import OpposedOutcome, resolve_opposed


@dataclass(slots=True)
class AttackResolver:
    rng: RandomSource
    events: EventSink

    def resolve(
        self,
        *,
        round_number: int,
        attacker: CombatantState,
        defender: CombatantState,
        action: AttackAction,
    ) -> None:
        attack_profile = action.roll_source.resolve(attacker.definition.stats)
        defense_profile = defender.definition.stats.roll("DEF")
        attack_roll = roll_pool(attack_profile, self.rng)
        defense_roll = roll_pool(defense_profile, self.rng)

        self.events.emit(
            BattleEvent(
                type="opposed_roll",
                round=round_number,
                actor_id=attacker.definition.id,
                target_id=defender.definition.id,
                data={
                    "action_id": action.id,
                    "attack_dice": attack_roll.values,
                    "attack_successes": attack_roll.successes,
                    "defense_dice": defense_roll.values,
                    "defense_successes": defense_roll.successes,
                },
            )
        )

        outcome = resolve_opposed(attack_roll.successes, defense_roll.successes)
        if outcome is OpposedOutcome.DOUBLE_ZERO:
            attacker_change = apply_stagger(attacker)
            defender_change = apply_stagger(defender)
            self._emit_health(round_number, attacker, attacker_change, "double_zero")
            self._emit_health(round_number, defender, defender_change, "double_zero")
            return

        if outcome is OpposedOutcome.DEFENDER_WINS:
            change = apply_miss_stagger(attacker)
            self._emit_health(round_number, attacker, change, "miss")
            return

        damage = calculate_damage(
            attack_roll.successes,
            defense_roll.successes,
            action.weapon,
        )
        damage_outcome = resolve_damage(damage, defender.definition.stats.value("RES"))
        if damage_outcome is DamageOutcome.WOUND:
            change = apply_wound(defender)
        else:
            change = apply_stagger(defender)
        self.events.emit(
            BattleEvent(
                type="damage_resolved",
                round=round_number,
                actor_id=attacker.definition.id,
                target_id=defender.definition.id,
                data={
                    "action_id": action.id,
                    "damage": damage,
                    "resilience": defender.definition.stats.value("RES"),
                    "outcome": damage_outcome.value,
                    "health_change": change.value,
                    "target_wounds": defender.wounds,
                    "target_stagger": defender.stagger,
                },
            )
        )

    def _emit_health(
        self,
        round_number: int,
        target: CombatantState,
        change: HealthChange,
        reason: str,
    ) -> None:
        self.events.emit(
            BattleEvent(
                type="health_changed",
                round=round_number,
                target_id=target.definition.id,
                data={
                    "reason": reason,
                    "change": change.value,
                    "wounds": target.wounds,
                    "stagger": target.stagger,
                },
            )
        )
