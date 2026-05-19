# MCP Logging and Observability

This document covers how the Model Context Protocol (MCP) supports logging and observability, including its notification system, and provides context on OpenTelemetry as the broader observability standard.

## 1. MCP Logging Primitive

MCP includes a built-in **Logging** utility primitive that enables servers to send structured log messages to clients for debugging and monitoring purposes.

### Capability Declaration

Servers that emit log messages must declare the `logging` capability during initialization:

```json
{
  "capabilities": {
    "logging": {}
  }
}
```

### Log Levels

MCP logging uses severity levels aligned with RFC-5424 syslog conventions:

| Level | Description |
|-------|-------------|
| `debug` | Detailed debugging information |
| `info` | Informational messages |
| `notice` | Normal but significant conditions |
| `warning` | Warning conditions |
| `error` | Error conditions |
| `critical` | Critical conditions |
| `alert` | Action must be taken immediately |
| `emergency` | System is unusable |

### Protocol Flow

1. **Client sets verbosity**: Client sends `logging/setLevel` request specifying the minimum log level (e.g., `info`)
2. **Server acknowledges**: Server responds with an empty result confirming the level
3. **Server emits logs**: Server sends `notifications/message` containing logs at or above the configured level
4. **Dynamic adjustment**: Client can issue another `logging/setLevel` to change verbosity at any time

### Log Message Structure

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/message",
  "params": {
    "level": "error",
    "logger": "router",
    "data": {
      "error_code": 500,
      "details": "Internal Server Error"
    }
  }
}
```

Fields:
- **level** (required): Severity level of the message
- **logger** (optional): Name of the logger/module issuing the message
- **data** (required): The log payload—any JSON-serializable value

### Important Considerations

When running MCP servers over STDIO transport, avoid writing logs directly to stdout/stderr as this can disrupt the MCP protocol stream. MCP itself relies on STDIO for structured communication, so mixing logs with protocol messages can cause parsing errors or disconnections.

## 2. MCP Notifications

Notifications are a core messaging primitive in MCP, built on JSON-RPC 2.0. Unlike requests, notifications are one-way messages that do not expect a response.

### Notification Types

MCP uses notifications for several purposes:

| Notification | Purpose |
|-------------|---------|
| `notifications/message` | Log messages from server to client |
| `notifications/progress` | Progress updates for long-running operations |
| `notifications/resources/list_changed` | Server's available resources have changed |
| `notifications/resources/updated` | A specific subscribed resource has changed |
| `notifications/tools/list_changed` | Server's available tools have changed |
| `notifications/prompts/list_changed` | Server's available prompts have changed |
| `notifications/cancelled` | A request has been cancelled |

### Progress Tracking

For long-running operations, MCP supports progress notifications:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/progress",
  "params": {
    "progressToken": "abc123",
    "progress": 50,
    "total": 100,
    "message": "Processing records..."
  }
}
```

The sender includes a `progressToken` in the request metadata, and the receiver can emit progress updates referencing that token.

## 3. What MCP Doesn't Include (Yet)

MCP's current logging primitive covers basic structured logging but lacks deeper observability features like:

- **Distributed tracing**: No built-in support for trace context propagation across MCP calls
- **Metrics collection**: No primitives for exposing counters, gauges, or histograms
- **Span correlation**: No mechanism to connect MCP server operations to broader application traces

There is an [active proposal](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/269) to add OpenTelemetry trace support to MCP, which would allow servers to emit OTel spans back to clients, enabling full-stack observability in agentic workflows.

---

## 4. OpenTelemetry Overview

OpenTelemetry (OTel) is an open-source observability framework under the Cloud Native Computing Foundation (CNCF) that provides a unified, vendor-neutral approach to collecting telemetry data.

### The Three Pillars (Plus One)

OpenTelemetry standardizes collection of four observability signals:

| Signal | Description | Use Case |
|--------|-------------|----------|
| **Traces** | Records the path of a request through distributed services | Understanding request flow, identifying bottlenecks |
| **Metrics** | Quantitative measurements (counters, gauges, histograms) | Monitoring health, alerting on thresholds |
| **Logs** | Timestamped records of discrete events | Debugging, audit trails |
| **Profiles** | CPU/memory usage snapshots (newer addition) | Performance optimization |

### Key Concepts

**Spans and Traces**
- A **span** represents a single unit of work (e.g., an HTTP request, a database query)
- A **trace** is a collection of spans forming the complete journey of a request
- Spans contain: name, start/end timestamps, attributes, status, and parent context

**Context Propagation**
- OTel automatically propagates trace context (trace ID, span ID) across service boundaries
- This enables correlation of logs, metrics, and traces from different services participating in the same request

**Resources**
- Metadata describing the entity producing telemetry (service name, version, host, etc.)
- Automatically attached to all signals for consistent attribution

### Architecture Components

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Application    │     │  OTel Collector │     │   Backend       │
│  (SDK + API)    │────▶│  (optional)     │────▶│  (Jaeger,       │
│                 │     │                 │     │   Prometheus,   │
└─────────────────┘     └─────────────────┘     │   etc.)         │
                                                └─────────────────┘
```

- **API**: Defines instrumentation interface (vendor-agnostic)
- **SDK**: Implements the API, handles sampling, batching, export
- **Collector**: Optional middleware for receiving, processing, and routing telemetry
- **Exporters**: Send data to backends (Jaeger, Prometheus, Zipkin, vendor solutions)

### Why It Matters for MCP

As agentic AI applications grow more complex—with multiple MCP calls, LLM interactions, and tool invocations—the ability to trace execution end-to-end becomes critical. Without tracing support:

- MCP servers are "black boxes" in observability dashboards
- Debugging multi-step agent workflows requires correlating disconnected logs
- Performance analysis across the agent→MCP→external service chain is difficult

The proposed OTel integration would allow MCP servers to emit spans that clients can forward to their observability backends, creating unified traces across the entire agent execution.

---

## References

### MCP Documentation

| Topic | URL |
|-------|-----|
| Architecture Overview | https://modelcontextprotocol.io/docs/learn/architecture |
| Logging Specification | https://spec.modelcontextprotocol.io/specification/2024-11-05/server/utilities/logging/ |
| Progress Tracking | https://spec.modelcontextprotocol.io/specification/draft/basic/utilities/progress/ |
| Resources & Notifications | https://modelcontextprotocol.info/docs/concepts/resources/ |
| OTel Integration Proposal | https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/269 |

### OpenTelemetry Documentation

| Topic | URL |
|-------|-----|
| Observability Primer | https://opentelemetry.io/docs/concepts/observability-primer/ |
| Specification Overview | https://opentelemetry.io/docs/specs/otel/overview/ |
| Logs in OpenTelemetry | https://opentelemetry.io/docs/specs/otel/logs/ |
| Getting Started | https://opentelemetry.io/docs/getting-started/ |
| Collector | https://opentelemetry.io/docs/collector/ |
| Language SDKs | https://opentelemetry.io/docs/languages/ |

### Observability Backends (OTel-compatible)

- **Jaeger**: https://www.jaegertracing.io/ (distributed tracing)
- **Prometheus**: https://prometheus.io/ (metrics)
- **Grafana**: https://grafana.com/ (visualization)
- **Loki**: https://grafana.com/oss/loki/ (log aggregation)
