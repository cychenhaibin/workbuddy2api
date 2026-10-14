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
