#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from apebind.backends.node import NodeGenerator
from apebind.schema import SchemaCodec


NODE = shutil.which('node')
NPM = shutil.which('npm')
pytestmark = pytest.mark.skipif(NODE is None, reason='Node.js is not installed')


def generate_fixture(tmp_path: Path, fixture_ape_path: Path) -> Path:
    project_root = Path(__file__).resolve().parents[3]
    spec = SchemaCodec().load(project_root / 'examples' / 'fixture.apebind.yaml')
    output_directory = tmp_path / 'generated-node'
    NodeGenerator().generate(spec, fixture_ape_path, output_directory)
    return output_directory


def run_node(project: Path, source: str, environment=None):
    return subprocess.run(
        [NODE, '--input-type=module', '-e', source],
        cwd=project,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=30,
    )


def test_node_backend_generates_dependency_free_esm_project(
    tmp_path: Path,
    fixture_ape_path: Path,
):
    output_directory = generate_fixture(tmp_path, fixture_ape_path)
    package = json.loads((output_directory / 'package.json').read_text(encoding='utf-8'))

    assert package['type'] == 'module'
    assert 'dependencies' not in package
    assert package['main'] == './src/index.js'
    assert package['types'] == './src/index.d.ts'
    assert (output_directory / 'src' / 'bin' / 'fixture.com').is_file()

    runtime = (output_directory / 'src' / '_runtime.js').read_text(encoding='utf-8')
    client = (output_directory / 'src' / 'client.js').read_text(encoding='utf-8')

    assert 'windowsHide: false' in runtime
    assert 'statSync(this._binaryPath).mode & 0o111' in runtime
    assert '\n\n\nexport async function' not in client


def test_node_backend_runs_oneshot_json_raw_and_persistent_operations(
    tmp_path: Path,
    fixture_ape_path: Path,
):
    output_directory = generate_fixture(tmp_path, fixture_ape_path)
    completed = run_node(
        output_directory,
        """
import { echo, jsonValue, raw, serve } from './src/index.js';
const values = {};
values.echo = await echo({ text: ['hello', 'world'], upper: true, repeat: 1 });
values.single = await echo({ text: 'single', verbose: true });
values.json = await jsonValue({ value: 'value' });
values.raw = (await raw(['echo', 'raw'])).stdout.trim();
const session = await serve({ message: 'ready' });
values.link = session.result;
values.runningBeforeStop = session.running;
await session.stop();
values.runningAfterStop = session.running;
values.returnCode = session.returnCode;
console.log(JSON.stringify(values));
""",
    )
    values = json.loads(completed.stdout)
    assert values == {
        'echo': 'HELLO WORLD',
        'single': 'single',
        'json': 'value',
        'raw': 'raw',
        'link': 'https://example.test/ready',
        'runningBeforeStop': True,
        'runningAfterStop': False,
        'returnCode': 0,
    }


def test_node_runtime_streams_stdout_without_capturing_and_handles_early_stdin_exit(
    tmp_path: Path,
    fixture_ape_path: Path,
):
    output_directory = generate_fixture(tmp_path, fixture_ape_path)
    completed = run_node(
        output_directory,
        """
import { spawn } from 'node:child_process';
import { Readable } from 'node:stream';
import { ProcessSession } from './src/_runtime.js';

const outputChild = spawn(process.execPath, [
  '-e', 'process.stdout.write(Buffer.alloc(1024 * 1024, 255))',
], { stdio: ['ignore', 'pipe', 'pipe'] });
const outputSession = new ProcessSession(
  outputChild,
  ['output'],
  null,
  null,
  { captureStdout: false },
);
const chunks = [];

for await (const chunk of outputSession.iterStdout()) {
  chunks.push(chunk);
}

await outputSession.wait();

const source = Readable.from((async function* generate() {
  while (true) {
    yield Buffer.alloc(64 * 1024);
  }
})());
const inputChild = spawn(process.execPath, [
  '-e', 'process.stdin.destroy(); setTimeout(() => process.exit(0), 10)',
], { stdio: ['pipe', 'pipe', 'pipe'] });
const inputSession = new ProcessSession(inputChild, ['input']);
inputSession._attachInput(source);
await inputSession.wait();

console.log(JSON.stringify({
  bytes: Buffer.concat(chunks).length,
  stdout: outputSession._stdoutText(),
  processResultStdout: outputSession.processResult?.stdout,
  sourceDestroyed: source.destroyed,
}));
""",
    )
    values = json.loads(completed.stdout)
    assert values == {
        'bytes': 1024 * 1024,
        'stdout': '',
        'processResultStdout': '',
        'sourceDestroyed': True,
    }


def test_node_backend_surfaces_process_error_and_timeout(
    tmp_path: Path,
    fixture_ape_path: Path,
):
    output_directory = generate_fixture(tmp_path, fixture_ape_path)
    completed = run_node(
        output_directory,
        """
import { APEProcessError, APETimeoutError, raw } from './src/index.js';
const values = {};
try {
  await raw(['fail', '--code', '9']);
} catch (error) {
  values.processError = error instanceof APEProcessError;
  values.returnCode = error.result.returnCode;
  values.stderr = error.result.stderr.includes('requested failure');
}
try {
  await raw(['serve', '--json', 'timeout-result.json'], { timeoutSeconds: 0.05 });
} catch (error) {
  values.timeoutError = error instanceof APETimeoutError;
}
console.log(JSON.stringify(values));
""",
    )
    values = json.loads(completed.stdout)
    assert values == {
        'processError': True,
        'returnCode': 9,
        'stderr': True,
        'timeoutError': True,
    }


def test_node_backend_unsets_configured_environment(
    tmp_path: Path,
    fixture_ape_path: Path,
):
    output_directory = generate_fixture(tmp_path, fixture_ape_path)
    environment = dict(os.environ)
    environment['APEBIND_TEST_SECRET'] = 'hidden'
    completed = run_node(
        output_directory,
        """
import { APEClient } from './src/_runtime.js';
const client = new APEClient('unused', {}, { env_unset: ['APEBIND_TEST_SECRET'] });
console.log(client._environment().APEBIND_TEST_SECRET === undefined);
""",
        environment,
    )
    assert completed.stdout.strip() == 'true'


@pytest.mark.skipif(NPM is None, reason='npm is not installed')
def test_node_backend_npm_pack_installs_and_runs(
    tmp_path: Path,
    fixture_ape_path: Path,
):
    output_directory = generate_fixture(tmp_path, fixture_ape_path)
    pack_directory = tmp_path / 'packed'
    pack_directory.mkdir()
    packed = subprocess.run(
        [NPM, 'pack', '--pack-destination', str(pack_directory)],
        cwd=output_directory,
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=60,
    )
    tarball = pack_directory / packed.stdout.strip().splitlines()[-1]
    consumer = tmp_path / 'consumer'
    consumer.mkdir()
    subprocess.run(
        [NPM, 'init', '-y'],
        cwd=consumer,
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    subprocess.run(
        [
            NPM,
            'install',
            '--ignore-scripts',
            '--no-audit',
            '--no-fund',
            str(tarball),
        ],
        cwd=consumer,
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=60,
    )
    completed = run_node(
        consumer,
        """
import { echo } from 'fixturebind';
console.log(await echo({ text: ['installed'] }));
""",
    )
    assert completed.stdout.strip() == 'installed'


def test_node_runtime_supports_optional_value_flags(
    tmp_path: Path,
    fixture_ape_path: Path,
):
    output_directory = generate_fixture(tmp_path, fixture_ape_path)
    completed = run_node(
        output_directory,
        """
import { APEClient } from './src/_runtime.js';
const operation = {
  result: { format: 'command', option_flag: null },
  levels: [{
    token: null,
    positionals: [],
    options: [{
      api_name: 'label',
      primary_flag: '--label',
      boolean: false,
      required: false,
      multiple: false,
      value_optional: true,
      runtime_owned: false,
    }],
  }],
};
const client = new APEClient('unused', {});
console.log(JSON.stringify({
  absent: client._buildArgv(operation, { label: null }, null),
  flag: client._buildArgv(operation, { label: true }, null),
  value: client._buildArgv(operation, { label: 'value' }, null),
}));
""",
    )
    assert json.loads(completed.stdout) == {
        'absent': [],
        'flag': ['--label'],
        'value': ['--label', 'value'],
    }


def test_node_backend_generates_typed_event_contract(
    tmp_path: Path,
    fixture_ape_path: Path,
    event_spec,
):
    output_directory = tmp_path / 'generated-node-events'

    NodeGenerator().generate(event_spec, fixture_ape_path, output_directory)
    declarations = (output_directory / 'src' / 'client.d.ts').read_text(encoding='utf-8')
    client_source = (output_directory / 'src' / 'client.js').read_text(encoding='utf-8')

    assert 'export interface ServeProgressEvent' in declarations
    assert 'bytesSent: number;' in declarations
    assert 'speed?: number;' in declarations
    assert 'export interface ServeEventMap' in declarations
    assert 'Promise<ProcessSession<ServeEventMap>>' in declarations
    assert 'events?:' not in declarations
    assert '"runtime_role": "events"' in client_source


def test_node_runtime_streams_jsonl_events(
    tmp_path: Path,
    fixture_ape_path: Path,
    event_spec,
    event_writer_path: Path,
    event_operation_factory,
):
    output_directory = tmp_path / 'generated-node-events'

    NodeGenerator().generate(event_spec, fixture_ape_path, output_directory)

    operation = event_operation_factory(
        str(event_writer_path),
        bytes_api_name='bytesSent',
    )
    source = f"""
import {{ APEClient }} from './src/_runtime.js';

const operation = {json.dumps(operation)};
const client = new APEClient({json.dumps(sys.executable)}, {{ transfer: operation }});
const received = [];

const session = await client.invoke('transfer');
session.on('progress', (progress) => received.push(progress));

const events = [];

for await (const event of session.events()) {{
  events.push({{
    name: event.name,
    data: event.data,
    known: event.known,
  }});
}}

const returnCode = await session.done;

console.log(JSON.stringify({{
  result: session.result,
  received,
  events,
  returnCode,
}}));
"""

    completed = run_node(output_directory, source)
    values = json.loads(completed.stdout)

    assert values == {
        'result': 'https://example.test/events',
        'received': [
            {'bytesSent': 10, 'speed': 1.5},
            {'bytesSent': 20},
        ],
        'events': [
            {
                'name': 'progress',
                'data': {'bytesSent': 10, 'speed': 1.5},
                'known': True,
            },
            {
                'name': 'progress',
                'data': {'bytesSent': 20},
                'known': True,
            },
            {
                'name': 'future_event',
                'data': {
                    'event': 'future_event',
                    'value': 42,
                },
                'known': False,
            },
        ],
        'returnCode': 0,
    }


def test_node_runtime_rejects_invalid_event_field_types(
    tmp_path: Path,
    fixture_ape_path: Path,
    event_spec,
    invalid_event_writer_path: Path,
    event_operation_factory,
):
    output_directory = tmp_path / 'generated-node-invalid-events'

    NodeGenerator().generate(event_spec, fixture_ape_path, output_directory)

    operation = event_operation_factory(
        str(invalid_event_writer_path),
        bytes_api_name='bytesSent',
    )
    source = f"""
import {{ APEClient, APEEventError }} from './src/_runtime.js';

const operation = {json.dumps(operation)};
const client = new APEClient({json.dumps(sys.executable)}, {{ transfer: operation }});
const session = await client.invoke('transfer');

let message = null;

try {{
  await session.done;
}} catch (error) {{
  if (!(error instanceof APEEventError)) {{
    throw error;
  }}

  message = error.message;
}}

console.log(message);
"""

    completed = run_node(output_directory, source)

    assert 'must be integer' in completed.stdout
