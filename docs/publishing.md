# Publishing and local installation

This is a skills-only Codex plugin. It has no cloud endpoint, account service, or bundled MCP server. The repository is also a repo-scoped Codex marketplace: `.agents/plugins/marketplace.json` exposes the plugin root for local or Git-backed installation. The public package contains the manifest, skills, local Python core, public documentation, examples, and legal documents; development tests and internal planning notes remain in the source repository.

## Install from GitHub

With the Codex CLI installed and authenticated for Git operations when your Git host requires it:

```bash
codex plugin marketplace add ReplicantKin/job-search-agent --ref main
codex plugin add job-search-agent@job-search-agent-public
```

After installation, start a new Codex task so the bundled skills are loaded. To install from a local clone instead:

```bash
codex plugin marketplace add /path/to/job-search-agent
codex plugin add job-search-agent@job-search-agent-public
```

## Local test

For local development, use the repo marketplace flow above so the marketplace source points at the plugin directory being edited. After changing skills or the manifest, refresh/reinstall the entry and start a new Codex task so the updated skill list is loaded.

The standalone package can also be shared as `dist/job-search-agent-*.zip`; after a GitHub Release is created, a recipient can download the release asset, validate the manifest, and run the README smoke test before installing it.

The current release asset is [job-search-agent-0.1.5.zip](https://github.com/ReplicantKin/job-search-agent/releases/download/v0.1.5/job-search-agent-0.1.5.zip).

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

The ready-to-copy listing metadata, release notes, and exactly five positive plus three negative test cases are in [`docs/public-submission.md`](public-submission.md). The remaining portal gates are publisher identity, availability selection, upload, skill scan, and final attestations.
