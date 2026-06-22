# Demo 08 — Drive bootkit as an MCP server

## Where this comes from

An AI agent (or any MCP client) wants to plan a cluster by speaking JSON-RPC to
bootkit instead of shelling out. bootkit ships a stdio MCP server exposing four
tools: `preflight`, `plan`, `manifest`, and `bundle`. `session.jsonl` is a
recorded client session you can replay to see the exact wire traffic.

## Run it

Pipe the recorded session into the server (run from the repo root so the spec
paths resolve):

```bash
python -m bootkit mcp < demos/08-mcp-session/session.jsonl
```

## What to expect

One JSON-RPC response object per request line:

1. `initialize` -> `serverInfo` with `name: "bootkit"` and the protocol version.
2. `tools/list` -> the four tools with their input schemas.
3. `tools/call preflight` -> a `content` block whose text is the preflight JSON;
   `isError` is `false` because this 3-server/1-agent spec passes.
4. `tools/call plan` -> the ordered plan as JSON text.
5. `tools/call manifest` -> the carry list as JSON text.

(The `notifications/initialized` line produces no response, by design.)

## How to act

Wire this command into your MCP client config:

```json
{"command": "python", "args": ["-m", "bootkit", "mcp"]}
```

Then the agent calls `preflight` first and only proceeds to `plan` when
`isError` is `false`.
