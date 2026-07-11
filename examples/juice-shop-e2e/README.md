# Juice Shop Evidence Fixture

This fixture is a sanitized subset of a RedCode end-to-end validation performed
twice against a disposable OWASP Juice Shop container bound to
`127.0.0.1:3000`.

It demonstrates the contrast between normal customer registration and a
client-supplied `role: admin` field accepted by the local training application.
The exercise validates RedCode's scope, evidence, and testing workflow; it is
not presented as a novel Juice Shop vulnerability.

Passwords, authorization headers, JWTs, and disposable account email addresses
are replaced with explicit redaction markers. Runtime output remains ignored by
Git. Reproduce the integration test using [`docs/juice-shop-e2e.md`](../../docs/juice-shop-e2e.md).
