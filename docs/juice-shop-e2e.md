# Juice Shop End-to-End Validation

This document describes how to reproduce RedCode's local-lab CTF workflow
against an OWASP Juice Shop container.

## Start the Lab

Run a disposable Juice Shop container bound to localhost only:

```bash
docker run -d --name redcode-juiceshop \
  -p 127.0.0.1:3000:3000 \
  bkimminich/juice-shop@sha256:e68144772ebaaca0ec117b38d44903af92416793230288ef7c5437fc4f26850a
```

Wait for the service to respond:

```bash
for i in {1..30}; do
  curl -sf http://127.0.0.1:3000/ >/dev/null && break
  sleep 2
done
```

## Run the Integration Test

The test is skipped unless `REDCODE_JUICE_SHOP_URL` is explicitly set:

```bash
REDCODE_JUICE_SHOP_URL=http://127.0.0.1:3000 \
  python3 -m unittest tests.test_juice_shop_integration -v
```

To run the full suite including the conditional test:

```bash
REDCODE_JUICE_SHOP_URL=http://127.0.0.1:3000 \
  python3 -m unittest discover -s tests -v
```

The test does not start Docker itself and does not modify the engagement scope.
It skips unless the configured URL resolves directly to a loopback address.

## Review the Fixture

Sanitized evidence from the validated two-run session is tracked under:

```text
examples/juice-shop-e2e/
  README.md
  evidence/*.json
```

The original runtime output remains excluded from Git. The tracked fixture keeps
method, loopback URL, status, role result, timestamp, and timing while replacing
passwords, authorization headers, JWTs, and account email addresses.

To create a new sanitized copy from a local run:

```bash
python3 scripts/redact_evidence.py SOURCE_EVIDENCE_DIR DESTINATION_DIR
```

## Clean Up

Stop and remove the container when finished:

```bash
docker rm -f redcode-juiceshop
```
