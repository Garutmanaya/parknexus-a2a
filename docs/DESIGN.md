# ParkNexus A2A Design Document

## Requirements

ParkNexus A2A is a multi-agent parking reservation platform with these requirements:

1. A user interacts only with the Host Agent/UI.
2. Parking providers are independent agents with their own databases and schemas.
3. Provider agents publish Agent Cards containing capabilities, skills, and input schema contracts.
4. Registry Agent discovers and persists provider Agent Cards.
5. Host Agent parses natural language, discovers providers, maps canonical intent into provider-specific schemas, validates payloads, and calls providers over signed A2A.
6. Search is parallel across providers but returns a synchronous aggregated response to the UI.
7. User accounts and user-facing booking transactions are persisted in the platform database.
8. Provider databases remain isolated and own slot/reservation state.
9. UI communicates only with Host Agent.
10. All local services run over HTTPS and A2A calls require bearer token plus HMAC signature.

## Runtime Architecture

```text
React UI
  ↓ REST/HTTPS
Host Agent
  ├─ Admin/user APIs
  ├─ Transaction history APIs
  ├─ LangGraph workflow
  ├─ Provider schema mapping/validation
  └─ signed A2A client
      ↓
Registry Agent
  └─ registered provider Agent Cards
      ↓
Provider Agents
  └─ provider-owned PostgreSQL databases
```

## Platform Database

The platform database stores:

- registered provider Agent Cards
- user accounts
- user-facing transaction history

Tables:

```text
registered_agents
user_accounts
user_transactions
```

## Provider Database

Each provider database stores:

- provider metadata
- garage inventory
- parking slots
- slot holds
- reservations
- slot events

Provider state is never directly read by Host or UI.

## Agent Card Schema Negotiation

Provider skills include input schemas:

```json
{
  "id": "search_slots",
  "input_schema": {
    "type": "object",
    "properties": {
      "level_name": {"type": ["string", "null"], "x-canonical": "level_name"},
      "ev_charger": {"type": ["boolean", "null"], "x-canonical": "ev_charger"},
      "budget_amount": {"type": ["number", "string", "null"], "x-canonical": "budget_amount"}
    }
  }
}
```

The Host Agent keeps a canonical intent model, maps it into each provider schema, validates the outgoing payload, then calls the provider through A2A.

## Host Agent Workflow

```text
parse intent
  ↓
discover providers
  ↓
parallel provider search
  ↓
rank slots
  ↓
return response
```

Booking operations:

```text
hold_slot
confirm_reservation
cancel_hold
release_slot
```

Every successful hold/reservation/cancellation is persisted as a user transaction in the platform DB.

## Security

A2A requests require:

```text
Authorization: Bearer <token>
X-Agent-Id: <agent_id>
X-Request-Id: <uuid>
X-Timestamp: <unix_timestamp>
X-Signature: <hmac_sha256>
```

The request signature covers:

```text
agent_id + request_id + timestamp + body
```

Local HTTPS uses self-signed certificates. Production should use managed certificates and optionally mTLS at the load balancer/service mesh layer.

## UI Design

The UI is chat-first:

- left side: chat, history, admin panel
- right side: provider summaries, recommendations, selected slot action panel, visual garage layout

The UI never calls Provider Agent directly.
