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

from apebind.backends.java import JavaGenerator
from apebind.models import OptionSpec, ResultFormat, ResultSpec, ValueType
from apebind.schema import SchemaCodec


JAVA = shutil.which('java')
JAVAC = shutil.which('javac')
JAR = shutil.which('jar')
pytestmark = pytest.mark.skipif(
    JAVA is None or JAVAC is None,
    reason='Java 17+ is not installed',
)


def generate_fixture(tmp_path: Path, fixture_ape_path: Path) -> Path:
    project_root = Path(__file__).resolve().parents[3]
    spec = SchemaCodec().load(project_root / 'examples' / 'fixture.apebind.yaml')
    output_directory = tmp_path / 'generated-java'
    JavaGenerator().generate(spec, fixture_ape_path, output_directory)
    return output_directory


def compile_generated(project: Path, output_directory: Path) -> None:
    sources = sorted((project / 'src' / 'main' / 'java').rglob('*.java'))
    subprocess.run(
        [JAVAC, '--release', '17', '-d', str(output_directory), *map(str, sources)],
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=60,
    )
    resources = project / 'src' / 'main' / 'resources'
    if resources.exists():
        shutil.copytree(resources, output_directory, dirs_exist_ok=True)


def run_java(
    classes_directory: Path,
    source: str,
    *,
    class_name: str = 'Main',
    qualified_name: str | None = None,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    source_path = classes_directory.parent / f'{class_name}.java'
    source_path.write_text(source, encoding='utf-8')
    subprocess.run(
        [
            JAVAC,
            '--release',
            '17',
            '-cp',
            str(classes_directory),
            '-d',
            str(classes_directory),
            str(source_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=60,
    )
    launch_name = class_name if qualified_name is None else qualified_name

    return subprocess.run(
        [JAVA, '-cp', str(classes_directory), launch_name],
        cwd=classes_directory.parent,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=30,
    )


def test_java_backend_generates_dependency_free_maven_project(
    tmp_path: Path,
    fixture_ape_path: Path,
):
    output_directory = generate_fixture(tmp_path, fixture_ape_path)

    pom = (output_directory / 'pom.xml').read_text(encoding='utf-8')
    binding = next((output_directory / 'src' / 'main' / 'java').rglob('*Binding.java'))
    binding_source = binding.read_text(encoding='utf-8')

    assert '<maven.compiler.release>17</maven.compiler.release>' in pom
    assert '<dependencies>' not in pom
    assert '\n\n        private final' not in binding_source
    assert (
        output_directory
        / 'src'
        / 'main'
        / 'resources'
        / 'apebind'
        / 'fixture.com'
    ).is_file()


def test_java_backend_separates_generated_logical_units(
    tmp_path: Path,
    fixture_ape_path: Path,
):
    output_directory = generate_fixture(tmp_path, fixture_ape_path)
    source_directory = (
        output_directory / 'src' / 'main' / 'java' / 'apebind' / 'generated' / 'fixturebind'
    )

    binding = (source_directory / 'FixturebindBinding.java').read_text(encoding='utf-8')
    client = (source_directory / 'APEClient.java').read_text(encoding='utf-8')
    json = (source_directory / 'Json.java').read_text(encoding='utf-8')
    resource = (source_directory / 'BinaryResource.java').read_text(encoding='utf-8')
    session = (source_directory / 'ProcessSession.java').read_text(encoding='utf-8')

    assert 'Objects.requireNonNull(parameters, "parameters");\n\n        return' in binding
    assert 'Map<String, Object> values = new LinkedHashMap<>();\n\n            values.put' in binding
    assert 'return result;\n            }\n\n            while (true)' in json
    assert 'Process process = spawn(argv);\n\n        CompletableFuture<String> stdout' in client
    assert 'appendOptions(\n' in client
    assert '            );\n\n            appendPositionals' in client
    assert 'String resourceName = "/apebind/" + binaryName;\n\n        try' in resource
    assert 'stderrCollector.await(stoppedByClient);\n\n            waitForEventChannel();' in session


def test_java_backend_runs_oneshot_json_raw_and_persistent_operations(
    tmp_path: Path,
    fixture_ape_path: Path,
):
    output_directory = generate_fixture(tmp_path, fixture_ape_path)
    classes_directory = tmp_path / 'classes'
    classes_directory.mkdir()
    compile_generated(output_directory, classes_directory)

    completed = run_java(
        classes_directory,
        '''
import apebind.generated.fixturebind.FixturebindBinding;
import java.util.concurrent.atomic.AtomicBoolean;

public class Main {
    public static void main(String[] args) throws Exception {
        var echo = FixturebindBinding.EchoParameters.builder()
            .text(java.util.List.of("hello", "world"))
            .upper(true)
            .repeat(1L)
            .build();
        var json = FixturebindBinding.JsonValueParameters.builder()
            .value("value")
            .build();
        var serve = FixturebindBinding.ServeParameters.builder()
            .message("ready")
            .build();
        String echoValue = FixturebindBinding.echo(echo);
        Object jsonValue = FixturebindBinding.jsonValue(json);
        String raw = FixturebindBinding.raw(java.util.List.of("echo", "raw")).stdout().trim();
        var session = FixturebindBinding.serve(serve);
        var exited = new AtomicBoolean();
        session.onExit(() -> exited.set(true));
        String link = String.valueOf(session.result());
        boolean before = session.running();
        session.stop();
        boolean after = session.running();
        long deadline = System.nanoTime() + 1_000_000_000L;
        while (!exited.get() && System.nanoTime() < deadline) {
            Thread.sleep(10);
        }
        if (!exited.get()) {
            throw new AssertionError("Missing process exit callback");
        }
        System.out.println(
            echoValue + "|" + jsonValue + "|" + raw + "|" + link + "|" + before + "|" + after
        );
    }
}
''',
    )

    assert completed.stdout.strip() == (
        'HELLO WORLD|value|raw|https://example.test/ready|true|false'
    )


def test_java_backend_streams_input_to_persistent_operations(
    tmp_path: Path,
    fixture_ape_path: Path,
):
    output_directory = generate_fixture(tmp_path, fixture_ape_path)
    classes_directory = tmp_path / 'classes'
    classes_directory.mkdir()
    compile_generated(output_directory, classes_directory)

    completed = run_java(
        classes_directory,
        '''
import apebind.generated.fixturebind.FixturebindBinding;
import java.io.IOException;
import java.io.InputStream;

public class Main {
    private static final class TrackingInputStream extends InputStream {
        private final byte[] source;
        private int offset;
        private int bytesRead;
        private boolean closed;

        private TrackingInputStream(byte[] source) {
            this.source = source;
        }

        @Override
        public int read() {
            if (offset >= source.length) {
                return -1;
            }

            bytesRead += 1;
            return Byte.toUnsignedInt(source[offset++]);
        }

        @Override
        public void close() {
            closed = true;
        }
    }

    private static final class FailingInputStream extends InputStream {
        private boolean returnedByte;

        @Override
        public int read() throws IOException {
            if (!returnedByte) {
                returnedByte = true;
                return 1;
            }

            throw new IOException("source failure");
        }
    }

    public static void main(String[] args) throws Exception {
        var parameters = FixturebindBinding.ServeParameters.builder()
            .message("stream")
            .build();
        var source = new TrackingInputStream(new byte[] {0, 1, 2, 3});
        var session = FixturebindBinding.serve(parameters, source);
        long deadline = System.nanoTime() + 2_000_000_000L;

        while (source.bytesRead < 4 && System.nanoTime() < deadline) {
            Thread.sleep(10);
        }

        session.stop();
        if (source.bytesRead != 4 || !source.closed) {
            throw new AssertionError("Persistent operation did not clean up stdin");
        }

        try {
            FixturebindBinding.serve(parameters, new FailingInputStream());
            throw new AssertionError("Persistent operation hid source failure");
        } catch (IllegalStateException error) {
            if (error.getCause() == null || !error.getCause().getMessage().contains("source failure")) {
                throw error;
            }
        }
        System.out.println("stream-ok");
    }
}
''',
    )

    assert completed.stdout.strip() == 'stream-ok'


def test_java_backend_surfaces_process_error_and_timeout(
    tmp_path: Path,
    fixture_ape_path: Path,
):
    output_directory = generate_fixture(tmp_path, fixture_ape_path)
    classes_directory = tmp_path / 'classes'
    classes_directory.mkdir()
    compile_generated(output_directory, classes_directory)

    completed = run_java(
        classes_directory,
        '''
import apebind.generated.fixturebind.APEProcessException;
import apebind.generated.fixturebind.APETimeoutException;
import apebind.generated.fixturebind.FixturebindBinding;

public class Main {
    public static void main(String[] args) {
        boolean processError = false;
        boolean timeoutError = false;
        try {
            FixturebindBinding.raw(java.util.List.of("fail", "--code", "9"));
        } catch (APEProcessException error) {
            processError = error.result().returnCode() == 9
                && error.result().stderr().contains("requested failure");
        }
        try {
            FixturebindBinding.raw(
                java.util.List.of("serve", "--json", "timeout-result.json"),
                0.05
            );
        } catch (APETimeoutException error) {
            timeoutError = true;
        }
        System.out.println(processError + "|" + timeoutError);
    }
}
''',
    )

    assert completed.stdout.strip() == 'true|true'


def test_java_backend_unsets_configured_environment(
    tmp_path: Path,
    fixture_ape_path: Path,
):
    output_directory = generate_fixture(tmp_path, fixture_ape_path)
    classes_directory = tmp_path / 'classes'
    classes_directory.mkdir()
    compile_generated(output_directory, classes_directory)

    helper_source = classes_directory.parent / 'EnvEcho.java'
    helper_source.write_text(
        '''
public class EnvEcho {
    public static void main(String[] args) {
        System.out.println(System.getenv("APEBIND_TEST_SECRET"));
    }
}
''',
        encoding='utf-8',
    )
    subprocess.run(
        [
            JAVAC,
            '--release',
            '17',
            '-d',
            str(classes_directory),
            str(helper_source),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )

    completed = run_java(
        classes_directory,
        '''
import apebind.generated.fixturebind.APEClient;

public class Main {
    public static void main(String[] args) {
        String javaBinary = java.nio.file.Path.of(
            System.getProperty("java.home"),
            "bin",
            System.getProperty("os.name").toLowerCase().startsWith("windows") ? "java.exe" : "java"
        ).toString();
        var client = new APEClient(
            java.nio.file.Path.of(javaBinary),
            java.util.Map.of(),
            java.util.Map.of("env_unset", java.util.List.of("APEBIND_TEST_SECRET"))
        );
        var result = client.raw(java.util.List.of(
            "-cp",
            System.getProperty("java.class.path"),
            "EnvEcho"
        ));
        System.out.println(result.stdout().trim());
    }
}
''',
        environment={**os.environ, 'APEBIND_TEST_SECRET': 'hidden'},
    )

    assert completed.stdout.strip() == 'null'


def test_java_runtime_supports_optional_value_flags(
    tmp_path: Path,
    fixture_ape_path: Path,
):
    project_root = Path(__file__).resolve().parents[3]
    spec = SchemaCodec().load(project_root / 'examples' / 'fixture.apebind.yaml')
    optional_option = OptionSpec(
        flags=('--label',),
        api_name='label',
        value_type=ValueType.STRING,
        value_optional=True,
    )
    commands = tuple(
        command.__class__(
            path=command.path,
            summary=command.summary,
            positionals=command.positionals,
            options=(*command.options, optional_option),
        )
        if command.path == ('echo',)
        else command
        for command in spec.commands
    )
    operation = next(operation for operation in spec.operations if operation.name == 'echo')
    text_operation = operation.__class__(
        operation.name,
        operation.command,
        result=ResultSpec(ResultFormat.TEXT),
    )
    modified_spec = spec.__class__(
        schema_version=spec.schema_version,
        ape=spec.ape,
        commands=commands,
        operations=(text_operation,),
        runtime=spec.runtime,
    )
    output_directory = tmp_path / 'generated-java'
    JavaGenerator().generate(modified_spec, fixture_ape_path, output_directory)
    classes_directory = tmp_path / 'classes'
    classes_directory.mkdir()
    compile_generated(output_directory, classes_directory)

    completed = run_java(
        classes_directory,
        """
import apebind.generated.fixturebind.FixturebindBinding;

public class Main {
    private static String output(boolean flagOnly) {
        var builder = FixturebindBinding.EchoParameters.builder().text("x");
        if (flagOnly) {
            builder.label();
        } else {
            builder.label("value");
        }
        return FixturebindBinding.echo(builder.build());
    }

    public static void main(String[] args) {
        System.out.println(output(true));
        System.out.println(output(false));
    }
}
""",
    )

    lines = completed.stdout.splitlines()
    assert lines[0] == '--label x'
    assert lines[1] == '--label value x'


@pytest.mark.skipif(JAR is None, reason='jar tool is not installed')
def test_java_backend_jar_installs_and_runs(
    tmp_path: Path,
    fixture_ape_path: Path,
):
    output_directory = generate_fixture(tmp_path, fixture_ape_path)
    classes_directory = tmp_path / 'classes'
    classes_directory.mkdir()
    compile_generated(output_directory, classes_directory)

    jar_path = tmp_path / 'fixturebind.jar'
    subprocess.run(
        [JAR, '--create', '--file', str(jar_path), '-C', str(classes_directory), '.'],
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=60,
    )
    consumer_directory = tmp_path / 'consumer'
    consumer_directory.mkdir()
    source = consumer_directory / 'Consumer.java'
    source.write_text(
        '''
import apebind.generated.fixturebind.FixturebindBinding;

public class Consumer {
    public static void main(String[] args) {
        var parameters = FixturebindBinding.EchoParameters.builder()
            .text("installed")
            .build();
        System.out.println(FixturebindBinding.echo(parameters));
    }
}
''',
        encoding='utf-8',
    )
    subprocess.run(
        [
            JAVAC,
            '--release',
            '17',
            '-cp',
            str(jar_path),
            '-d',
            str(consumer_directory),
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=60,
    )
    completed = subprocess.run(
        [
            JAVA,
            '-cp',
            os.pathsep.join((str(jar_path), str(consumer_directory))),
            'Consumer',
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=30,
    )
    assert completed.stdout.strip() == 'installed'


def test_java_backend_generates_event_runtime_contract(
    tmp_path: Path,
    fixture_ape_path: Path,
    event_spec,
):
    output_directory = tmp_path / 'generated-java-events'

    JavaGenerator().generate(event_spec, fixture_ape_path, output_directory)
    binding_source = next(
        (output_directory / 'src' / 'main' / 'java').rglob('*Binding.java')
    ).read_text(encoding='utf-8')

    assert '"runtime_role": "events"' in binding_source
    assert '"api_name": "bytesSent"' in binding_source
    assert (
        output_directory
        / 'src'
        / 'main'
        / 'java'
        / 'apebind'
        / 'generated'
        / 'ape_fixture'
        / 'APEEvent.java'
    ).is_file()


def test_java_runtime_streams_jsonl_events(
    tmp_path: Path,
    fixture_ape_path: Path,
    event_spec,
    event_writer_path: Path,
    event_operation_factory,
):
    output_directory = tmp_path / 'generated-java-events-runtime'

    JavaGenerator().generate(event_spec, fixture_ape_path, output_directory)

    classes_directory = tmp_path / 'classes'
    classes_directory.mkdir()
    compile_generated(output_directory, classes_directory)
    operation = event_operation_factory(
        str(event_writer_path),
        bytes_api_name='bytesSent',
    )
    operations_json = json.dumps({'transfer': operation}, indent=2).replace('\\', '\\\\')
    python_executable = json.dumps(sys.executable)
    source = f'''
package apebind.generated.ape_fixture;

import java.nio.file.Path;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;

public class EventMain {{
    public static void main(String[] args) {{
        String operationsJSON = """
{operations_json}
            """;
        var client = new APEClient(
            Path.of({python_executable}),
            APEClient.parseObject(operationsJSON),
            Map.of()
        );
        var received = new CopyOnWriteArrayList<Map<String, Object>>();

        var session = (ProcessSession) client.invoke("transfer", Map.of());
        session.on("progress", received::add);
        int returnCode = session.done().join();
        var history = session.eventHistory();

        if (!"https://example.test/events".equals(session.result())) {{
            throw new AssertionError("Unexpected session result");
        }}

        if (returnCode != 0 || received.size() != 2 || history.size() != 3) {{
            throw new AssertionError("Unexpected event lifecycle");
        }}

        if (((Number) received.get(0).get("bytesSent")).longValue() != 10L) {{
            throw new AssertionError("Missing first progress value");
        }}

        if (received.get(1).containsKey("speed")) {{
            throw new AssertionError("Optional event field should be absent");
        }}

        if (history.get(2).known() || !"future_event".equals(history.get(2).name())) {{
            throw new AssertionError("Unknown event was not preserved");
        }}

        System.out.println("events-ok");
    }}
}}
'''

    completed = run_java(
        classes_directory,
        source,
        class_name='EventMain',
        qualified_name='apebind.generated.ape_fixture.EventMain',
    )

    assert completed.stdout.strip() == 'events-ok'


def test_java_runtime_rejects_invalid_event_field_types(
    tmp_path: Path,
    fixture_ape_path: Path,
    event_spec,
    invalid_event_writer_path: Path,
    event_operation_factory,
):
    output_directory = tmp_path / 'generated-java-invalid-events'

    JavaGenerator().generate(event_spec, fixture_ape_path, output_directory)

    classes_directory = tmp_path / 'classes-invalid-events'
    classes_directory.mkdir()
    compile_generated(output_directory, classes_directory)

    operation = event_operation_factory(
        str(invalid_event_writer_path),
        bytes_api_name='bytesSent',
    )
    operations_json = json.dumps({'transfer': operation}, indent=2).replace('\\', '\\\\')
    python_executable = json.dumps(sys.executable)
    source = f'''
package apebind.generated.ape_fixture;

import java.nio.file.Path;
import java.util.Map;
import java.util.concurrent.CompletionException;

public class InvalidEventMain {{
    public static void main(String[] args) {{
        String operationsJSON = """
{operations_json}
            """;
        var client = new APEClient(
            Path.of({python_executable}),
            APEClient.parseObject(operationsJSON),
            Map.of()
        );
        var session = (ProcessSession) client.invoke("transfer", Map.of());

        try {{
            session.done().join();
            throw new AssertionError("Expected event type failure");
        }} catch (CompletionException error) {{
            if (!(error.getCause() instanceof APEEventException eventError)) {{
                throw error;
            }}

            if (!eventError.getMessage().contains("must be integer")) {{
                throw new AssertionError("Unexpected event error", eventError);
            }}
        }}

        System.out.println("invalid-event-ok");
    }}
}}
'''

    completed = run_java(
        classes_directory,
        source,
        class_name='InvalidEventMain',
        qualified_name='apebind.generated.ape_fixture.InvalidEventMain',
    )

    assert completed.stdout.strip() == 'invalid-event-ok'
