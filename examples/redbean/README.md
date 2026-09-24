# redbean 3.0 Node.js binding example

This example uses the redbean 3.0 APE as a portable web-server payload.

`redbean.discovered.apebind.yaml` is the raw `--help` import. redbean's custom
help layout does not expose enough structure for the current importer, so the
reviewed `redbean.apebind.yaml` describes the useful root flags explicitly.

Generate the low-level Node.js binding:

```bash
apebind generate examples/redbean/redbean.apebind.yaml \
    --ape ./redbean.com \
    --lang node \
    -o ./generated/redbean-ape
```

The neutral schema intentionally describes CLI/process mechanics only. A useful
redbean SDK should add an author-owned facade for service readiness and shutdown.
The reference `redbean-ape` project uses redbean's native `-d` daemon mode and
`-P` PID file, waits for `/statusz`, and exposes a `RedbeanServer` object.

Why daemon mode? redbean performs process-group shutdown on POSIX. Starting it
as a normal foreground child and then sending `SIGTERM` can also signal the
Node.js parent when both share a process group. redbean's own daemon mode gives
it the lifecycle isolation expected by its documented server operation.
