# Publish and verify the automation

1. Create an empty GitHub repository and push this project with Git. Do not upload
   the archive or drag the whole raw dataset into the web uploader. `.gitignore`
   excludes raw CSVs, environments, secrets and caches. Keep the bundled reports
   because the reference tests use them before each replay.
2. Open Actions > Historical analytics replay > Run workflow. Leave both inputs
   false. The lint job and five March-July replay jobs must succeed. Download each
   artifact to inspect its distinct cutoff, report, workbook and timings.
3. Configure repository Actions secrets SMTP_HOST, SMTP_USER, SMTP_PASSWORD,
   SMTP_FROM and SMTP_TO. SMTP_TO is the explicit report/alert recipient. Use an
   SMTP service that supports TLS on port 465 for the failure alert.
4. Run with `demo_failure=true`. The July quality gate should fail and its job
   should be red; the other four jobs should finish. Check the quality report and
   `last_run.json`, then verify the failure alert in the configured inbox.
5. Run normally with `send_email=true`. The July report includes its workbook as
   an attachment. SMTP acceptance is not proof of inbox delivery; check the inbox.
6. In Settings > Pages choose GitHub Actions as the source. Run Publish operating
   review to publish the committed portable HTML snapshot. It is not a live feed.
7. Add your real successful/failed run URLs, inbox screenshots and Pages URL to the
   README. Wait for an actual scheduled run before claiming weekly operation.

Badge template (replace OWNER and REPOSITORY with your actual repository):

```markdown
[![Replay](https://github.com/OWNER/REPOSITORY/actions/workflows/weekly.yml/badge.svg)](https://github.com/OWNER/REPOSITORY/actions/workflows/weekly.yml)
```

Each matrix job has a separate database and artifact. Local run history appends
across executions; GitHub runners are ephemeral, so their histories persist in
artifacts rather than an automatically committed shared CSV. Artifacts are kept
for 90 days; download any you need to retain longer. Never fabricate commit history.
