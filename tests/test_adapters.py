import unittest

from job_search_agent.adapters import parse_capture


class AdapterTests(unittest.TestCase):
    def test_boss_capture_is_normalized_to_job_input(self):
        result = parse_capture(
            "boss",
            {
                "jobs": [
                    {
                        "encryptJobId": "boss-100",
                        "jobName": "解决方案顾问",
                        "brandName": "示例科技",
                        "cityName": "深圳",
                        "salaryDesc": "15-25K",
                        "postDescription": "负责客户需求分析和方案演示。",
                        "jobUrl": "https://www.zhipin.com/job_detail/boss-100.html",
                    }
                ]
            },
            source_url="https://www.zhipin.com/web/geek/job?query=解决方案顾问",
            source_checked_at="2026-08-04",
        )

        self.assertEqual(result.warnings, [])
        self.assertEqual(len(result.jobs), 1)
        job = result.jobs[0]
        self.assertEqual(job.source, "boss")
        self.assertEqual(job.source_job_id, "boss-100")
        self.assertEqual(job.company, "示例科技")
        self.assertEqual(job.title, "解决方案顾问")
        self.assertEqual(job.location, "深圳")
        self.assertEqual(job.salary, "15-25K")
        self.assertEqual(job.source_checked_at, "2026-08-04")

    def test_liepin_and_51job_alias_fields_are_supported(self):
        result = parse_capture(
            "51job",
            {
                "jobs": [
                    {
                        "jobid": "51-1",
                        "job_name": "售前产品经理",
                        "co_name": "示例公司",
                        "workarea_text": "广州",
                        "job_detail": "面向企业客户推进产品方案。",
                        "providesalary_text": "20-30K",
                        "job_href": "https://jobs.51job.com/example/51-1.html",
                    }
                ]
            },
            source_url="https://search.51job.com/",
            source_checked_at="2026-08-04",
        )

        job = result.jobs[0]
        self.assertEqual(job.source_job_id, "51-1")
        self.assertEqual(job.title, "售前产品经理")
        self.assertEqual(job.company, "示例公司")
        self.assertEqual(job.location, "广州")

        liepin = parse_capture(
            "猎聘",
            {
                "jobs": [
                    {
                        "jobId": "lp-1",
                        "jobTitle": "解决方案经理",
                        "compName": "猎聘示例公司",
                        "city": "深圳",
                        "jobDesc": "负责企业客户方案咨询。",
                        "url": "https://www.liepin.com/job/lp-1.shtml",
                    }
                ]
            },
            source_url="https://www.liepin.com/zhaopin/",
            source_checked_at="2026-08-04",
        )

        self.assertEqual(liepin.jobs[0].source, "liepin")
        self.assertEqual(liepin.jobs[0].company, "猎聘示例公司")

    def test_company_jobposting_json_ld_is_supported(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"JobPosting",
         "title":"Solutions Consultant","description":"Help enterprise customers adopt the product.",
         "url":"https://careers.example.com/jobs/42",
         "identifier":{"value":"42"},
         "hiringOrganization":{"name":"Example Corp"},
         "jobLocation":{"address":{"addressLocality":"Shanghai"}},
         "datePosted":"2026-08-01"}
        </script></head><body></body></html>
        """

        result = parse_capture(
            "company",
            html,
            source_url="https://careers.example.com/jobs/42",
            source_checked_at="2026-08-04",
        )

        self.assertEqual(result.warnings, [])
        self.assertEqual(len(result.jobs), 1)
        job = result.jobs[0]
        self.assertEqual(job.source_job_id, "42")
        self.assertEqual(job.company, "Example Corp")
        self.assertEqual(job.title, "Solutions Consultant")
        self.assertEqual(job.location, "Shanghai")
        self.assertIn("enterprise customers", job.description)

    def test_greenhouse_api_capture_aliases_are_supported(self):
        result = parse_capture(
            "greenhouse",
            {
                "jobs": [
                    {
                        "id": 7954688,
                        "absolute_url": "https://stripe.com/jobs/search?gh_jid=7954688",
                        "title": "Account Executive, AI Sales (Grower)",
                        "company_name": "Stripe",
                        "location": {"name": "San Francisco, CA"},
                        "content": "<p>Help customers grow their businesses.</p>",
                        "first_published": "2026-06-02T08:58:57-04:00",
                    }
                ]
            },
            source_url="https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true",
            source_checked_at="2026-08-04",
        )

        self.assertEqual(result.warnings, [])
        self.assertEqual(len(result.jobs), 1)
        job = result.jobs[0]
        self.assertEqual(job.source_job_id, "7954688")
        self.assertEqual(job.company, "Stripe")
        self.assertEqual(job.location, "San Francisco, CA")
        self.assertEqual(job.url, "https://stripe.com/jobs/search?gh_jid=7954688")
        self.assertIn("Help customers", job.description)
        self.assertEqual(job.posted_at, "2026-06-02T08:58:57-04:00")

    def test_workday_is_treated_as_an_ats_html_source(self):
        html = """
        <script type="application/ld+json">
        {"@type":"JobPosting","title":"Solution Consultant","description":"Support solution sales.",
         "url":"https://example.wd5.myworkdayjobs.com/job/9","identifier":{"value":"9"},
         "hiringOrganization":{"name":"Example Workday Corp"},
         "jobLocation":{"address":{"addressLocality":"Beijing"}}}
        </script>
        """

        result = parse_capture(
            "workday",
            html,
            source_url="https://example.wd5.myworkdayjobs.com/",
            source_checked_at="2026-08-04",
        )

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.jobs[0].source, "workday")

    def test_detail_capture_uses_source_url_when_record_url_is_missing(self):
        result = parse_capture(
            "company",
            {
                "jobs": [
                    {
                        "title": "Solutions Consultant",
                        "company": "Example Corp",
                        "location": "Shanghai",
                        "description": "Help enterprise customers adopt the product.",
                    }
                ]
            },
            source_url="https://careers.example.com/jobs/42",
            source_checked_at="2026-08-04",
        )

        self.assertEqual(result.warnings, [])
        self.assertEqual(result.jobs[0].url, "https://careers.example.com/jobs/42")

    def test_incomplete_capture_is_reported_without_creating_a_job(self):
        result = parse_capture(
            "boss",
            {"jobs": [{"jobName": "没有公司和描述"}]},
            source_url="https://www.zhipin.com/",
            source_checked_at="2026-08-04",
        )

        self.assertEqual(result.jobs, [])
        self.assertTrue(result.warnings)
        self.assertIn("company", result.warnings[0])


if __name__ == "__main__":
    unittest.main()
