# Specmatic Arazzo Auth Sample

## Overview

An OpenAPI sample with four FastAPI services. Its `PlaceOrder` Arazzo workflow calls Location, Products, Inventory, and Orders, using a different authentication setup for each provider.

## Services and authentication

| Service   | Local URL                               | Endpoint                                  | Authentication                       |
|-----------|-----------------------------------------|-------------------------------------------|--------------------------------------|
| Location  | [localhost:8001](http://localhost:8001) | `GET /location`                           | Bearer token                         |
| Products  | [localhost:8002](http://localhost:8002) | `GET /products`                           | OAuth password grant                 |
| Orders    | [localhost:8003](http://localhost:8003) | `POST /orders`<br>`GET /orders/{orderId}` | OAuth client credentials (Basic)     |
| Inventory | [localhost:8004](http://localhost:8004) | `PUT /inventory`                          | JWT bearer grant + `private_key_jwt` |

## Identity providers

| Component                              | Local URL                               | Used for                              |
|----------------------------------------|-----------------------------------------|---------------------------------------|
| Commerce Keycloak (`commerce` realm)   | [localhost:9002](http://localhost:9002) | Issues tokens for Products and Orders |
| Inventory Keycloak (`inventory` realm) | [localhost:9001](http://localhost:9001) | Issues tokens for Inventory           |

## Vaults

| Component      | Local URL                               | Used for                                |
|----------------|-----------------------------------------|-----------------------------------------|
| Commerce Vault | [localhost:8200](http://localhost:8200) | Location token and Commerce credentials |
| Identity Vault | [localhost:8201](http://localhost:8201) | Inventory signing keys                  |

## Authentication

- **Bearer:** send a token with each request.
- **Password grant:** exchange a username and password for an access token.
- **Client credentials:** exchange a client ID and secret for an access token.
- **JWT grant and `private_key_jwt`:** send two signed JWTs to get an access token: one requests access, the other authenticates the client.

## Tests

Requires Docker and [uv](https://docs.astral.sh/uv/), Run from this directory:

```bash
uv sync --locked
```

Run all tests:

```bash
uv run --locked pytest tests -v -s
```

Run all provider contracts:

```bash
uv run --locked pytest tests/contract/*/test_contract.py -v -s                         # All providers
uv run --locked pytest "tests/contract/<service_name>/test_contract.py" -v -s          # location, products, orders, inventory
```

Run the Arazzo workflow:

```bash
uv run --locked pytest tests/workflow/arazzo -v -s
```

## Start services and Studio

To reuse the existing Arazzo spec in Studio, run this command to create the config with vault and security settings:

```bash
python3 -c "from pathlib import Path; Path('specmatic.yaml').write_text(Path('tests/workflow/arazzo/specmatic.yaml').read_text().replace('directory: ../../../spec', 'directory: ./spec'))"
```

Start the APIs, dependencies, and Studio:

```bash
docker compose --profile studio up --build
```

Once the services are ready, open Studio at [http://localhost:9000/_specmatic/studio](http://localhost:9000/_specmatic/studio).

To stop the stack and remove volumes and orphan containers:

```bash
docker compose --profile studio down -v --remove-orphans
```
