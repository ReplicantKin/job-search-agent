# Publishing and local installation

This is a skills-only Codex plugin. It has no cloud endpoint, account service, or bundled MCP server. The public package contains the manifest, skills, local Python core, public documentation, examples, and legal documents; development tests and internal planning notes remain in the source repository.

## Local test

Use the plugin creator's personal marketplace flow to expose the folder to Codex. The marketplace source must point at the plugin directory being edited. After changing skills or the manifest, refresh/reinstall the local entry and start a new Codex task so the updated skill list is loaded.

The standalone package can also be shared as `dist/job-search-agent-*.zip`; a recipient should unpack it, validate the manifest, and run the README smoke test before installing it.

## Public submission checklist

Before submitting to a public directory:

1. Put the repository on a public Git host and add its repository/homepage URL to `.codex-plugin/plugin.json`.
2. Host `PRIVACY.md` and `TERMS.md` at stable public URLs, then add the corresponding manifest interface links.
3. Add a real icon/logo and screenshots only after reviewing that they contain no personal job data.
4. Run the full test suite, plugin validator, clean-process CLI smoke test, archive scan, and a new-task evaluation set.
5. Test both positive prompts (discovery, fit review, material preparation, application status) and negative prompts (unrelated tasks, unsupported automated submission, and requests to bypass CAPTCHA/MFA).
6. Validate each live source in the user's own browser session. If a site changes layout, keep the adapter warning/manual fallback instead of claiming coverage.

The repository and legal URLs must be real before they enter the manifest. The release helper can check the current state:

```bash
python3 scripts/prepare_public_release.py --check
```

For this repository, the public metadata is already filled with these URLs. If the plugin is forked, replace them with the fork's URLs:

```bash
python3 scripts/prepare_public_release.py --write \
  --repository https://github.com/ReplicantKin/job-search-agent \
  --homepage https://github.com/ReplicantKin/job-search-agent \
  --privacy-url https://github.com/ReplicantKin/job-search-agent/blob/main/PRIVACY.md \
  --terms-url https://github.com/ReplicantKin/job-search-agent/blob/main/TERMS.md
```

The helper rejects non-HTTPS URLs, embedded credentials, and URL fragments.

The package is designed so publication does not require a cloud service. Actual public-directory submission still requires the publisher's repository, legal URLs, visual assets, and approval in the publishing portal.
