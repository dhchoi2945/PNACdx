# PGCHECK Phase 0 JSONL contract v1.0

All files are UTF-8 (no BOM). JSON uses strict syntax, finite numbers and unique object keys. One nonempty JSON object per JSONL line. All six files are required, including empty unresolved.jsonl. Additional fields are allowed for site diagnostics. No network dependency or telemetry exists.

## Identity and occurrences

IDs are nonempty strings unique across all records and nested terminal records within a run. Human-readable paths are strings built by escaping each path component (`~` to `~0`, `/` to `~1`) and joining with `/`. IDs are opaque; readers must not derive connectivity from them or from paths. Cell definitions are deduplicated by library/cell/view. **Nets and connections are occurrence scoped**: the same LOAD cell used twice has two independent sets of local nets. Names never imply electrical equivalence across occurrences, cellviews, or global scopes.

## manifest.json

Required fields: `schema_version: "1.0"`, `run_id: string`, `status: "complete" | "incomplete"`, `root_instance_id: string`, `top: {library, cell, view}` (all strings), `files: {cells: "cells.jsonl", instances: "instances.jsonl", nets: "nets.jsonl", connections: "connections.jsonl", unresolved: "unresolved.jsonl"}`, `counts: {cells, instances, nets, connections, unresolved}` (nonnegative integers), `capabilities: object`, `validation_context: "synthetic" | "virtuoso_unverified" | "virtuoso_internal"`.

`complete` means exporter finished with no unresolved extraction errors; it does not certify saved/check status or Phase 0 internal acceptance. Any unresolved record requires `incomplete`. A missing/finalization-interrupted manifest is an invalid interrupted export. Required nonempty string capability keys: `binding_policy`, `saved_status`, `connectivity_status`, `placement_support`, `pin_helper_policy`. Default DB binding is explicit schematic selection, not Config/HDB elaboration. Test statuses are PASS, FAIL, BLOCKED, NOT_TESTED and must never label external internal-only checks PASS.

## cells.jsonl

`id`, `path`, `library`, `cell`, `view`, `db_id` (all strings); `terminals: [{id, name, direction}]` (all strings); `local_net_names: [string]`. Directions are preserved as returned by DB; not inferred. `db_id` is a diagnostic representation valid only in the source session, not a stable persistent ID.

## instances.jsonl

Includes one root occurrence. Required: `id`, `path`, `name` (strings), `parent_id: string | null`, `cell_id: string | null`, `master: {library, cell, view}`, `selected: {library, cell, view} | null`, `placement: null | {x: finite number, y: finite number, orientation: string, coordinate_system: "parent_local", units: string | null}`. Root has null parent and placement. An unopenable/unsupported selected view has null cell_id and selected, and an unresolved record. `master` is the actually placed view; `selected` is the explicitly chosen analysis view. No guessed connectivity.

## nets.jsonl

`id`, `path`, `name`, `cell_id`, `occurrence_id` (strings). cell_id must match the occurrence's cell_id. Exactly one net per local net name per resolved occurrence. Global/inherited/bus semantics are unsupported until validated and must be recorded unresolved, never silently merged.

## connections.jsonl

`id`, `path`, `kind: "instance_port" | "cell_port"`, `owner_instance_id`, `instance_id`, `port` (strings), `terminal_id: string | null`, `net_id: string | null`, `status: "connected" | "unconnected" | "unresolved"`, `evidence: "db" | "none"`, `reason: string | null`.

For instance_port: instance_id is the child, owner_instance_id its direct parent, terminal_id is the child's selected cell terminal when known, net is scoped to the parent. Each placed master port must produce an edge; symbol/selected terminal mismatch is unresolved. For cell_port: owner and instance are the same occurrence, terminal_id is that cell terminal, net is local to that occurrence. Each selected terminal must produce exactly one cell_port. Root has no instance_port. `connected` requires existing scoped net, terminal and `evidence: "db"`; `unconnected` requires null net and successful DB inspection (`evidence: "db"`); `unresolved` requires null net, nonempty reason and a matching unresolved record. Failed access/missing instTerm must be unresolved, never unconnected. No inferred edge may be marked connected.

## unresolved.jsonl

`id`, `path`, `code`, `message` (nonempty strings), `severity: "error" | "warning"`, `object_id: string | null`. object_id if nonnull references a cell, terminal, instance, net or connection. Every unresolved connection has a diagnostic referencing that connection. Optional coordinate failures belong in manifest warnings, not extraction errors. Any unresolved record forces incomplete status conservatively.

## Independent T01 oracle

Exactly two direct LOAD children of root: U_LOAD0 and U_LOAD1, same selected PGC_T01_LOAD/schematic, placed PGC_T01_LOAD/symbol. VDD/VSS directions inputOutput; EN input. Root is PGC_T01_TOP/schematic with ports/local nets VDD_A, VDD_B, VSS_A (inputOutput), CTRL (input). Instance edges: U_LOAD0 VDD→VDD_A, VSS→VSS_A, EN→CTRL; U_LOAD1 VDD→VDD_B, VSS→VSS_A, EN→CTRL. Each LOAD occurrence has local nets/ports VDD, VSS, EN with same-name cell_port connections. Top has same-name cell_port connections. Pin graphic instances (e.g. basic/ipin/iopin/sympin) are not logical circuit occurrences; exporter must identify/exclude only known pin helper masters and record this policy.
