import unittest

from weavve.final.reward_test import evaluate_reward_test, evaluate_post_purchase_test


def synthetic_inputs():
    return {
        "label": "Synthetic arithmetic fixture only", "eligible_people": 1000,
        "treatment_fraction": .5, "baseline_purchase_rate": .1,
        "baseline_reward_redemption_rate": .01,
        "contribution_per_purchaser_before_tested_reward": 50,
        "tested_reward_cost_per_redemption": 10,
        "contact_cost_per_treated_person": .2,
        "additional_operations_cost_per_treated_person": 0,
        "setup_cost": 100,
        "scenarios": {
            "adverse": {"purchase_rate": .08, "reward_redemption_rate": .06},
            "zero_purchase_lift": {"purchase_rate": .1, "reward_redemption_rate": .06},
            "benefit": {"purchase_rate": .13, "reward_redemption_rate": .06},
        },
        "notes": ["No actual member data or business assumptions"], "unpriced_costs": [],
    }


class RewardTestEconomicsTests(unittest.TestCase):
    def test_content_only_model_rejects_hidden_reward(self):
        inputs = synthetic_inputs()
        with self.assertRaises(ValueError):
            evaluate_post_purchase_test(inputs)
        inputs["baseline_reward_redemption_rate"] = 0
        inputs["tested_reward_cost_per_redemption"] = 0
        for case in inputs["scenarios"].values():
            case["reward_redemption_rate"] = 0
        result = evaluate_post_purchase_test(inputs)
        self.assertIn("no added incentive", result["proposal"])
    def test_zero_uplift_still_has_subsidy_and_contact_cost(self):
        result = evaluate_reward_test(synthetic_inputs())
        zero = result["scenarios"][1]
        self.assertAlmostEqual(zero["incremental_redemption_cost_per_treated_person"], .5)
        self.assertAlmostEqual(zero["trial_incremental_contribution_after_setup"], -450)
        self.assertEqual(result["treated_people"], 500)
        self.assertNotIn("annual_profit", result)

    def test_benefit_must_cover_all_incremental_costs(self):
        row = evaluate_reward_test(synthetic_inputs())["scenarios"][2]
        self.assertAlmostEqual(row["trial_incremental_contribution_after_setup"], 300)
        self.assertAlmostEqual(row["break_even_purchase_rate_difference_given_entered_redemptions"], .018)

    def test_redemption_cannot_exceed_people_who_purchase(self):
        inputs = synthetic_inputs()
        inputs["scenarios"]["adverse"]["reward_redemption_rate"] = .09
        with self.assertRaises(ValueError):
            evaluate_reward_test(inputs)

    def test_adverse_and_zero_cases_are_required(self):
        for remove in ("adverse", "zero_purchase_lift"):
            inputs = synthetic_inputs()
            del inputs["scenarios"][remove]
            with self.subTest(remove=remove), self.assertRaises(ValueError):
                evaluate_reward_test(inputs)

    def test_invalid_numeric_inputs_do_not_produce_a_forecast(self):
        for key, value in (("eligible_people", 1), ("eligible_people", 10.5),
                           ("setup_cost", float("nan")), ("treatment_fraction", 1),
                           ("baseline_reward_redemption_rate", .2)):
            inputs = synthetic_inputs()
            inputs[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                evaluate_reward_test(inputs)


if __name__ == "__main__":
    unittest.main()
