# Upstream-Aligned GHCR Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the fork's push-triggered GHCR workflow prebuild `web/out` before Docker Buildx, matching the upstream release workflow's build order.

**Architecture:** GitHub Actions installs Node.js 22, performs a clean npm install and static export in `web/`, and verifies `web/out/index.html`. The existing multi-platform Docker build then receives that artifact in its context, causing the unchanged Dockerfile to reuse it instead of rebuilding the frontend inside Buildx.

**Tech Stack:** GitHub Actions YAML, Node.js 22, npm, Next.js static export, Python `unittest`, PyYAML, Docker Buildx

## Global Constraints

- Modify only the fork-specific GHCR workflow and its targeted regression coverage.
- Keep font source, Dockerfile, application code, dependencies, and package lock files unchanged.
- Preserve the existing image name, tags, GHCR login, platforms, and Buildx cache configuration.
- The frontend artifact check must run before QEMU and Buildx setup.

---

### Task 1: Prebuild the static frontend before Buildx

**Files:**
- Create: `server/tests/test_fork_ghcr_workflow.py`
- Modify: `.github/workflows/ghcr-image.yml:19-27`

**Interfaces:**
- Consumes: `web/package-lock.json`, the `build:export` npm script, and the Dockerfile's existing `/src/out/index.html` reuse branch.
- Produces: `web/out/index.html` in the GitHub Actions workspace before `docker/setup-qemu-action@v3` and `docker/build-push-action@v6` execute.

- [x] **Step 1: Write the failing workflow-order test**

Create `server/tests/test_fork_ghcr_workflow.py` with:

```python
from __future__ import annotations

import unittest
from pathlib import Path

import yaml


_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _ROOT / '.github' / 'workflows' / 'ghcr-image.yml'


class ForkGhcrWorkflowTest(unittest.TestCase):
    def test_static_export_is_verified_before_buildx(self) -> None:
        workflow = yaml.safe_load(_WORKFLOW.read_text(encoding='utf-8'))
        steps = workflow['jobs']['docker']['steps']

        setup_node_index = next(
            (index for index, step in enumerate(steps)
             if str(step.get('uses', '')).startswith('actions/setup-node@')),
            -1,
        )
        self.assertGreaterEqual(setup_node_index, 0,
                                'GHCR 工作流没有安装 Node，无法像上游一样预构建前端')
        setup_node = steps[setup_node_index]
        self.assertEqual(str(setup_node['with']['node-version']), '22')
        self.assertEqual(setup_node['with']['cache'], 'npm')
        self.assertEqual(setup_node['with']['cache-dependency-path'], 'web/package-lock.json')

        buildx_index = next(
            index for index, step in enumerate(steps)
            if str(step.get('uses', '')).startswith('docker/setup-buildx-action@')
        )
        frontend_index = next(
            (index for index, step in enumerate(steps)
             if step.get('working-directory') == 'web'
             and 'npm ci' in step.get('run', '')
             and 'npm run build:export' in step.get('run', '')),
            -1,
        )
        artifact_index = next(
            (index for index, step in enumerate(steps)
             if 'test -f web/out/index.html' in step.get('run', '')),
            -1,
        )

        self.assertGreaterEqual(frontend_index, 0, '没有生成 web/out 的前端静态导出步骤')
        self.assertGreaterEqual(artifact_index, 0, '没有在 Buildx 前校验 web/out/index.html')
        self.assertLess(setup_node_index, frontend_index)
        self.assertLess(frontend_index, artifact_index)
        self.assertLess(artifact_index, buildx_index)


if __name__ == '__main__':
    unittest.main()
```

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python3 -m unittest server.tests.test_fork_ghcr_workflow -v
```

Expected: FAIL with `GHCR 工作流没有安装 Node` because the fork workflow currently proceeds from checkout directly to QEMU.

- [x] **Step 3: Add the upstream-equivalent frontend build steps**

Insert these steps immediately after `actions/checkout@v4` and before QEMU in `.github/workflows/ghcr-image.yml`:

```yaml
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: npm
          cache-dependency-path: web/package-lock.json

      - name: Build frontend static export
        working-directory: web
        run: |
          npm ci
          npm run build:export

      - name: Verify frontend artifact
        run: |
          test -f web/out/index.html || { echo "Build failed: missing web/out/index.html"; exit 1; }
```

- [x] **Step 4: Run the targeted workflow test and verify GREEN**

Run:

```bash
python3 -m unittest server.tests.test_fork_ghcr_workflow -v
```

Expected: one test passes.

- [x] **Step 5: Run the existing Docker deployment regression tests**

Run:

```bash
python3 -m unittest server.tests.test_docker_deploy -v
```

Expected: all Docker deployment tests pass; environment-dependent skips remain reported as skips rather than passes.

- [x] **Step 6: Verify a clean frontend static export**

Use a temporary directory so the working tree's ignored build artifacts and dependencies are not replaced:

```bash
task_tmp=$(mktemp -d /tmp/workbuddy-ghcr-web.XXXXXX)
rsync -a --exclude node_modules --exclude out --exclude .next web/ "$task_tmp"/
cd "$task_tmp"
npm ci --no-audit --no-fund
npm run build:export
test -f out/index.html
```

Expected: Next.js exits zero and `out/index.html` exists. Existing lint warnings may be reported but must not fail the export.

- [x] **Step 7: Review the diff and commit the implementation**

Run:

```bash
git diff --check
git diff -- .github/workflows/ghcr-image.yml server/tests/test_fork_ghcr_workflow.py
git status --short
git add .github/workflows/ghcr-image.yml server/tests/test_fork_ghcr_workflow.py docs/superpowers/plans/2026-10-14-align-ghcr-build-with-upstream.md
git commit -m "fix(ci): prebuild frontend before GHCR image"
```

Expected: the implementation commit contains only the workflow, focused regression test, and this plan; the prior design commit remains separate.
