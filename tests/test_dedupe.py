import unittest

from job_search_agent.dedupe import canonical_job_key, job_fingerprint


class DedupeTests(unittest.TestCase):
    def test_same_source_id_has_same_key(self):
        first = canonical_job_key(
            source="BOSS 直聘",
            source_job_id=" 123 ",
            url="https://example.com/a?utm_source=x",
            company="示例科技",
            title="解决方案顾问",
            location="深圳",
        )
        second = canonical_job_key(
            source="boss",
            source_job_id="123",
            url="https://example.com/b",
            company="其他公司名",
            title="不同标题",
            location="广州",
        )

        self.assertEqual(first, second)

    def test_tracking_query_parameters_do_not_change_url_key(self):
        first = canonical_job_key(
            source="company",
            source_job_id=None,
            url="https://example.com/jobs/1?utm_source=x&ref=feed",
            company="示例公司",
            title="售前",
            location="深圳",
        )
        second = canonical_job_key(
            source="company",
            source_job_id=None,
            url="https://example.com/jobs/1",
            company="示例公司",
            title="售前",
            location="深圳",
        )

        self.assertEqual(first, second)

    def test_description_fingerprint_ignores_whitespace_and_case(self):
        first = job_fingerprint("负责  客户需求分析。\n推动方案落地。")
        second = job_fingerprint("负责客户需求分析。推动方案落地。")

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
