import unittest
from types import SimpleNamespace

from job_search_agent.fit import evaluate_fit, rank_jobs


def job(**overrides):
    values = {
        "company": "示例科技",
        "title": "解决方案顾问",
        "location": "深圳",
        "description": "面向企业客户做需求分析、方案设计和产品演示。",
        "work_mode": "hybrid",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FitTests(unittest.TestCase):
    def test_matching_role_location_and_keywords_get_an_explainable_score(self):
        assessment = evaluate_fit(
            job(),
            {
                "target_roles": ["解决方案顾问", "售前"],
                "locations": ["深圳", "广州"],
                "must_have_keywords": ["需求分析", "方案设计"],
                "preferred_keywords": ["企业客户", "产品演示"],
                "work_modes": ["hybrid"],
            },
        )

        self.assertGreaterEqual(assessment.score, 80)
        self.assertEqual(assessment.verdict, "strong_match")
        self.assertIn("role", assessment.matched_dimensions)
        self.assertIn("location", assessment.matched_dimensions)
        self.assertTrue(assessment.strengths)

    def test_excluded_company_is_never_a_recommended_match(self):
        assessment = evaluate_fit(
            job(company="明确排除公司"),
            {"target_roles": ["解决方案顾问"], "exclude_companies": ["明确排除公司"]},
        )

        self.assertEqual(assessment.verdict, "excluded")
        self.assertEqual(assessment.score, 0)
        self.assertTrue(any("company" in gap for gap in assessment.gaps))

    def test_empty_profile_is_unconfigured_instead_of_a_false_rejection(self):
        assessment = evaluate_fit(job(), {})

        self.assertEqual(assessment.verdict, "unconfigured")
        self.assertIsNone(assessment.score)

    def test_rank_jobs_orders_recommendations_and_keeps_exclusions_visible(self):
        ranked = rank_jobs(
            [
                job(company="排除公司"),
                job(title="完全不同的岗位", description="文案写作。"),
                job(company="高匹配公司"),
            ],
            {"target_roles": ["解决方案顾问"], "exclude_companies": ["排除公司"]},
        )

        self.assertEqual(ranked[0][0].company, "高匹配公司")
        self.assertEqual(ranked[-1][1].verdict, "excluded")


if __name__ == "__main__":
    unittest.main()
