import unittest

from weavve.final.experiment_design import evaluate_scenario, rollout_exposure, sample_per_arm


def synthetic_config():
    return {
        "label": "Synthetic arithmetic fixture, not business evidence",
        "annual_eligible": 1200, "baseline_rate": 0.1,
        "target_rates": {"adverse": 0.08, "zero": 0.1, "benefit": 0.15},
        "mature_buyer_net_sales": 100, "value_horizon_days": 365,
        "contribution_margin": 0.5, "setup_cost": 100,
        "annual_operating_cost": 200, "additional_cost_per_treated_person": 1,
        "rollout": [{"months": 6, "fraction": 0.5}, {"months": 6, "fraction": 1}],
        "outcome_days": 90, "unpriced_costs": [], "notes": ["Synthetic only"],
    }


class ExperimentDesignTests(unittest.TestCase):
    def test_subsidy_applies_to_every_treated_person_and_fixed_costs_once(self):
        result = evaluate_scenario(synthetic_config())
        zero = result["scenarios"][1]
        benefit = result["scenarios"][2]
        self.assertAlmostEqual(zero["mature_cohort_contribution_rollout_exposure_after_costs"], -1200)
        self.assertAlmostEqual(benefit["mature_cohort_contribution_full_exposure_after_costs"], 1500)
        self.assertAlmostEqual(benefit["mature_cohort_contribution_rollout_exposure_after_costs"], 1050)
        self.assertIsNone(zero["approximate_binary_endpoint_n_per_arm"])
        self.assertNotIn("calendar_year_profit", result)

    def test_followup_is_added_after_last_recruit(self):
        row = evaluate_scenario(synthetic_config())["scenarios"][2]
        self.assertAlmostEqual(row["equal_allocation_last_outcome_matures_months"] - row["equal_allocation_recruitment_months"], 90 / (365.25 / 12))

    def test_sample_size_reference_and_smaller_effect(self):
        # Conventional normal approximation for hypothetical 10% versus 15%.
        self.assertEqual(sample_per_arm(0.1, 0.15), 686)
        self.assertGreater(sample_per_arm(0.1, 0.12), sample_per_arm(0.1, 0.15))
        self.assertIsNone(sample_per_arm(0.1, 0.1))

    def test_zero_and_adverse_cases_cannot_be_omitted(self):
        config = synthetic_config()
        config["target_rates"] = {"benefit": 0.15}
        with self.assertRaises(ValueError):
            evaluate_scenario(config)

    def test_invalid_inputs_fail_instead_of_plausible_outputs(self):
        for baseline, target in [(0, .1), (.1, 1), (float("nan"), .1), (True, .1)]:
            with self.subTest(baseline=baseline, target=target), self.assertRaises(ValueError):
                sample_per_arm(baseline, target)
        with self.assertRaises(ValueError):
            rollout_exposure([{"months": 7, "fraction": .5}])
        with self.assertRaises(ValueError):
            rollout_exposure([{"months": 12, "fraction": 1.1}])
        config = synthetic_config()
        config["annual_eligible"] = 0
        with self.assertRaises(ValueError):
            evaluate_scenario(config)


if __name__ == "__main__":
    unittest.main()
