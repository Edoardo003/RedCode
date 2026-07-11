# Case Study: Evidence-First CTF Validation

## Context

RedCode needed a persisted example showing that its scope, CTF workspace, and
evidence handoff work outside prompt descriptions. The validation target was a
disposable OWASP Juice Shop container bound only to `127.0.0.1:3000`.

## Method

The active engagement allowed only the `ctf` action against the loopback URL.
The run verified service readiness and public APIs, created a disposable normal
account, then supplied an additional `role: admin` field during registration.
The application accepted the privileged role, and a subsequent authenticated
profile request confirmed it.

The container was recreated and the same sequence was repeated. Both runs
produced the same customer/admin role distinction. No destructive action,
persistence, brute force, host-file access, or external flag submission was
performed.

## Engineering Result

- A conditional integration test exercises four application behaviors only
  when `REDCODE_JUICE_SHOP_URL` names a loopback service.
- Two additional tests enforce the loopback boundary itself.
- The full repository suite contains 30 tests; four integration cases skip when
  the lab URL is absent.
- Six representative JSON exchanges from two runs are tracked after automatic
  redaction of passwords, authorization headers, JWTs, and account identities.
- The Docker image used for validation is recorded by digest in the reproduction
  guide.

## What This Demonstrates

This is a known training weakness, not a novel vulnerability claim. The useful
result is the workflow around it: declared scope, a disposable target,
reproducible behavior, preserved evidence, secret redaction, and a test that
cannot be pointed at a remote host by configuration alone.

## Suggested Visual Sequence

1. Light-theme RedCode session with the active loopback engagement.
2. `./redcode doctor` showing a healthy backend and zero errors.
3. Normal registration evidence returning `role: customer`.
4. Sanitized mass-assignment evidence returning `role: admin`.
5. Terminal test result showing all six live integration and boundary tests pass.
