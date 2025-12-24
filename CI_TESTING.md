# CI Testing with Makefile

## Quick Start

### Check Prerequisites
```bash
make ci-check
```

### Run CI-like Tests Locally
```bash
make ci-test-local
```
This runs tests and saves output to `ci-test-output.log` for debugging.

### Run Tests in Debian Container (Like GitHub CI)
```bash
make ci-test-debian
```
This replicates the exact CI environment from GitHub Actions. Output saved to `ci-test-debian-output.log`.

## Debugging

When CI fails, check the output log:

```bash
# Local test log
cat ci-test-output.log

# Container test log
cat ci-test-debian-output.log
```

Look for:
- Import errors (e.g., libvips not found)
- Test failures
- Coverage issues

## Common Issues

### libvips.so.42 not found
**Error:** `OSError: cannot load library 'libvips.so.42'`

**Solution:**
```bash
sudo apt install libvips
```

### xvfb not found (local only)
**Error:** `xvfb-run not found`

**Solution:**
```bash
sudo apt install xvfb
```
Or use `make ci-test-debian` which includes xvfb in the container.

## Make Targets

- `ci-check` - Verify CI prerequisites are installed
- `ci-test-local` - Run tests locally with CI-like settings
- `ci-test-debian` - Run tests in debian container (exact CI replication)
- `pytest` - Run tests normally
- `lint` - Run linting

## Troubleshooting File

Output files for debugging:
- `ci-test-output.log` - Local CI test output
- `ci-test-debian-output.log` - Container CI test output

These files contain full test output including any errors, warnings, and coverage reports.
