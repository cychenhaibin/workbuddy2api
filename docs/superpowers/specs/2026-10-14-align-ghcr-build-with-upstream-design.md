# Align Fork GHCR Build With Upstream

## Problem

The fork-only `.github/workflows/ghcr-image.yml` invokes Docker Buildx directly.
Because `web/out` is not committed, the Dockerfile builds the frontend inside the
multi-platform image build. That path failed while `next/font/google` parsed the
Google Fonts response.

Upstream's release workflow builds the static frontend on the GitHub Actions
runner first. The resulting `web/out/index.html` enters the Docker build context,
so the Dockerfile reuses it and skips its container-side frontend build.

## Design

Update only `.github/workflows/ghcr-image.yml`:

1. Install Node.js 22 with the npm cache keyed by `web/package-lock.json`.
2. Run `npm ci` and `npm run build:export` from `web/`.
3. Verify that `web/out/index.html` exists before starting QEMU and Buildx.
4. Keep the existing multi-platform build, tags, login, and cache settings.

No font source, Dockerfile, application code, dependencies, or package lock files
will change.

## Failure Behavior

If dependency installation or the static export fails, the job stops at the
frontend build step with the original npm or Next.js error. If the command exits
successfully without producing `web/out/index.html`, the explicit artifact check
fails before the more expensive multi-platform Docker build starts.

## Verification

- Add a workflow regression assertion covering Node setup, frontend build, and
  the `web/out/index.html` guard before Buildx.
- Run the targeted workflow/deployment tests.
- Run a clean frontend static export and confirm `web/out/index.html` exists.
- Review the final diff to ensure the change is limited to the fork workflow and
  its regression coverage.
