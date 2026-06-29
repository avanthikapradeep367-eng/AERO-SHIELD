# AERO-SHIELD X — Blockchain & Digital Forensics Module

> **Phase 1 — Infrastructure Setup**  
> Member 2 | Blockchain & Digital Forensics

---

## Table of Contents

1. [Project Purpose](#1-project-purpose)
2. [Folder Structure](#2-folder-structure)
3. [Blockchain Concepts Explained](#3-blockchain-concepts-explained)
4. [Prerequisites — Install Node.js](#4-prerequisites--install-nodejs)
5. [Install Hardhat](#5-install-hardhat)
6. [Install & Run Ganache](#6-install--run-ganache)
7. [Install Project Dependencies](#7-install-project-dependencies)
8. [Configure Environment Variables](#8-configure-environment-variables)
9. [Compile Contracts](#9-compile-contracts)
10. [Deploy Contracts](#10-deploy-contracts)
11. [Understanding Generated Files](#11-understanding-generated-files)
12. [Running Tests](#12-running-tests)
13. [Web3.py Integration (Python)](#13-web3py-integration-python)
14. [Phase 2 — Development Roadmap](#14-phase-2--development-roadmap)

---

## 1. Project Purpose

AERO-SHIELD X is an **Aerospace Cyber Defense Platform**. This module provides the immutable, tamper-proof ledger layer using Ethereum smart contracts.

### Why Blockchain for Aerospace Defense?

| Problem | Blockchain Solution |
|---|---|
| Log tampering by attackers | Immutable on-chain records |
| Chain of custody disputes | Cryptographic hash anchoring |
| Single point of trust failure | Decentralised consensus |
| Repudiation of authentication events | Signed, time-stamped ledger entries |
| Threat intel silos | Shared, permissioned intelligence store |

### Four On-Chain Modules (implemented in Phase 2)

| Module | Purpose |
|---|---|
| **Device Registry** | Register and track every aerospace device on the network |
| **Authentication Ledger** | Log every rolling-key authentication event immutably |
| **Evidence Vault** | Anchor digital forensic evidence with cryptographic hashes |
| **Threat Intelligence** | Store IOCs detected by SentinelX AI on-chain |

---

## 2. Folder Structure

```
blockchain/
├── contracts/
│   └── EvidenceVault.sol       ← Root smart contract (Phase 1 foundation)
│
├── scripts/
│   └── deploy.js               ← Deployment script (compiles, deploys, saves artefacts)
│
├── ignition/                   ← Reserved for Hardhat Ignition deployment modules (Phase 2)
│
├── artifacts/                  ← Auto-generated: compiled ABI + bytecode (git-ignored)
│
├── cache/                      ← Auto-generated: Hardhat compilation cache (git-ignored)
│
├── test/                       ← Mocha/Chai test files (added in Phase 2)
│
├── abi/
│   └── EvidenceVault.json      ← Exported ABI for Web3.py integration
│
├── deployment/
│   └── EvidenceVault.json      ← Deployment record (address, tx hash, gas, network)
│
├── .env.example                ← Template for environment variables (copy to .env)
├── .env                        ← Your local secrets — NEVER commit this file
├── hardhat.config.js           ← Hardhat network, compiler, and plugin configuration
├── package.json                ← Node.js dependencies and npm scripts
├── .gitignore                  ← Excludes secrets, build artefacts, node_modules
└── README.md                   ← This file
```

---

## 3. Blockchain Concepts Explained

### What is Ganache?

Ganache is a **personal Ethereum blockchain** that runs entirely on your local machine. It simulates a real Ethereum network without needing real ETH or internet connectivity.

Think of it as a "fake but real" Ethereum that:
- Mines blocks instantly
- Gives you 10 pre-funded accounts
- Resets to a clean state whenever you restart it
- Costs nothing to use

---

### Accounts

An **account** is an identity on the Ethereum network. It is represented by a public address (42-character hex string starting with `0x`).

```
Example: 0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1
```

Ganache generates **10 accounts** by default, each pre-funded with **100 ETH** for testing.

There are two types:
- **Externally Owned Account (EOA)** — controlled by a private key (your deployer wallet)
- **Contract Account** — controlled by smart contract code (EvidenceVault after deployment)

---

### Private Keys

A **private key** is a 256-bit secret number that proves ownership of an account.

```
Example: 0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b2d
```

- **Never share your private key.**
- The public address is mathematically derived from the private key.
- Ganache displays private keys in the GUI (key icon) and CLI output.
- In this project, the private key is stored in `.env` (which is git-ignored).

---

### Wallets

A **wallet** is software that manages one or more accounts (private keys).

- Ganache acts as a built-in wallet for development.
- MetaMask is the most popular browser wallet.
- Hardhat loads wallet accounts from the `accounts` array in `hardhat.config.js`.

---

### Gas

**Gas** is the unit that measures the computational effort required to execute a transaction or deploy a contract.

| Concept | Explanation |
|---|---|
| **Gas limit** | Maximum units of gas you are willing to spend |
| **Gas price** | ETH you pay per unit of gas (denominated in Gwei; 1 Gwei = 0.000000001 ETH) |
| **Gas cost** | `gas used × gas price` |
| **Gas used** | Actual gas consumed by the transaction |

On Ganache, gas is paid from your test ETH — it does not cost real money.

---

### Transactions

A **transaction** is a signed instruction sent from one account to the network.

Every state-changing operation (deploy a contract, call a write function, transfer ETH) creates a transaction. Transactions are:
- Signed with the sender's private key
- Broadcast to the network
- Included in a block by a miner/validator
- **Immutable** once confirmed

Transactions have:
- `hash` — unique identifier (32-byte hex)
- `from` / `to` — sender and recipient addresses
- `value` — ETH transferred (can be 0)
- `data` — encoded function call or contract bytecode
- `gasLimit`, `gasPrice`, `nonce`

---

### Blocks

A **block** is a batch of confirmed transactions chained to the previous block via its hash.

- Each block has a **block number** (incrementing integer).
- Ganache mines a new block for each transaction by default.
- The chain of blocks forms the immutable **blockchain**.

---

### RPC URL

The **RPC (Remote Procedure Call) URL** is the HTTP endpoint through which Hardhat and Web3.py communicate with the Ethereum node (Ganache).

```
Ganache GUI (default):  http://127.0.0.1:7545
Ganache CLI (default):  http://127.0.0.1:8545
Hardhat node:           http://127.0.0.1:8545
```

Set this in `.env` as `GANACHE_RPC_URL`.

---

### Chain ID

The **Chain ID** is a unique integer that identifies an Ethereum network. It prevents transactions from one network being replayed on another.

| Network | Chain ID |
|---|---|
| Ethereum Mainnet | 1 |
| Sepolia Testnet | 11155111 |
| Ganache (default) | 1337 |
| Hardhat built-in | 31337 |

The Chain ID in `.env`, Ganache settings, and `hardhat.config.js` must all match.

---

## 4. Prerequisites — Install Node.js

Hardhat requires **Node.js v18 or later**.

### Download

Visit [https://nodejs.org](https://nodejs.org) and download the **LTS** version.

### Verify Installation

```bash
node --version    # should print v18.x.x or higher
npm --version     # should print 9.x.x or higher
```

---

## 5. Install Hardhat

Hardhat is installed as a project dependency via npm (not globally).

After cloning the repository and navigating to the `blockchain/` folder, run:

```bash
cd blockchain
npm install
```

This installs Hardhat and all other dependencies listed in `package.json`.

To confirm Hardhat is available:

```bash
npx hardhat --version
```

---

## 6. Install & Run Ganache

### Option A — Ganache GUI (Recommended for Beginners)

1. Download from [https://trufflesuite.com/ganache](https://trufflesuite.com/ganache)
2. Install and open the application.
3. Click **"Quickstart Ethereum"**.
4. Ganache starts a local blockchain on `http://127.0.0.1:7545` with Chain ID `1337`.
5. You will see 10 accounts each with 100 ETH and their private keys.

**Copy a private key:**
- Click the key icon next to any account.
- Paste it into `.env` as `PRIVATE_KEY`.
- Copy the corresponding address as `CONTRACT_OWNER`.

### Option B — Ganache CLI

```bash
npm install --global ganache

# Start with explicit chain ID and port
ganache --port 7545 --chainId 1337 --deterministic
```

`--deterministic` generates the same accounts every time using a fixed mnemonic — useful for CI environments.

---

## 7. Install Project Dependencies

```bash
# From the blockchain/ directory
npm install
```

This installs:

| Package | Purpose |
|---|---|
| `hardhat` | Ethereum development framework |
| `@nomicfoundation/hardhat-toolbox` | Bundled Hardhat plugins (ethers, chai, coverage) |
| `@openzeppelin/contracts` | Audited, reusable Solidity components |
| `dotenv` | Load `.env` into `process.env` |
| `hardhat-gas-reporter` | Gas usage table after test runs |
| `solidity-coverage` | Istanbul code coverage for Solidity |
| `ethers` | JavaScript library for Ethereum interaction |

---

## 8. Configure Environment Variables

```bash
# Copy the template
cp .env.example .env
```

Open `.env` and fill in:

```env
GANACHE_RPC_URL=http://127.0.0.1:7545
PRIVATE_KEY=0xYOUR_GANACHE_PRIVATE_KEY_HERE
CHAIN_ID=1337
CONTRACT_OWNER=0xYOUR_GANACHE_ACCOUNT_ADDRESS_HERE
```

> **Security rule:** `.env` is listed in `.gitignore`. Never commit it.

---

## 9. Compile Contracts

```bash
npm run compile
# or
npx hardhat compile
```

What happens:
1. Hardhat reads every `.sol` file in `contracts/`.
2. Invokes the `solc` Solidity compiler (version set in `hardhat.config.js`).
3. Writes compiled ABI and bytecode to `artifacts/`.
4. Writes a compilation cache to `cache/`.

On success you will see:

```
Compiled 1 Solidity file successfully (evm target: paris).
```

---

## 10. Deploy Contracts

Make sure Ganache is running, then:

```bash
npm run deploy:ganache
# or
npx hardhat run scripts/deploy.js --network ganache
```

Expected output:

```
============================================================
 AERO-SHIELD X — EvidenceVault Deployment
============================================================

  Network      : ganache
  Chain ID     : 1337
  Deployer     : 0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1
  Balance      : 99.9982... ETH

  Compiling contracts...
  Artifact     : EvidenceVault (Solidity contracts/EvidenceVault.sol)

  Deploying EvidenceVault...
  Est. gas     : 543210 units

============================================================
 DEPLOYMENT SUCCESSFUL
============================================================
  Contract     : 0x5b1869D9A4C187F2EAa108f3062412ecf0526b24
  Tx Hash      : 0xabc123...
  Gas Used     : 543210 units
  Block #      : 1
  Owner        : 0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1
  Version      : AERO-SHIELD-X:EvidenceVault:v1.0.0-phase1
  Network      : ganache
  Timestamp    : 2025-01-01T00:00:00.000Z
  Gas cost     : 0.00054321 ETH
============================================================

  Saving ABI...
    [saved] abi/EvidenceVault.json

  Saving deployment record...
    [saved] deployment/EvidenceVault.json
```

---

## 11. Understanding Generated Files

### `artifacts/contracts/EvidenceVault.sol/EvidenceVault.json`

Auto-generated by Hardhat. Contains:
- `abi` — function and event signatures used by clients
- `bytecode` — compiled machine code deployed to the chain
- `deployedBytecode` — bytecode as stored on-chain

### `abi/EvidenceVault.json`

Saved by `deploy.js`. A clean copy of the ABI plus deployment metadata. This file is what `web3.py` and the backend will import.

### `deployment/EvidenceVault.json`

Saved by `deploy.js`. Records:
- `contractAddress` — the address to interact with
- `txHash` — transaction hash for audit purposes
- `gasUsed` — cost of deployment
- `blockNumber` — when it was deployed
- `network` — which network (ganache/sepolia/mainnet)

---

## 12. Running Tests

Test files go in `test/`. They are written with Mocha and Chai (bundled in `hardhat-toolbox`).

```bash
npm test
# or
npx hardhat test
```

For coverage:

```bash
npm run coverage
```

---

## 13. Web3.py Integration (Python)

The backend (Member 1) will integrate with the contract using Web3.py.

Minimal connection example:

```python
from web3 import Web3
import json, os

RPC_URL         = os.getenv("GANACHE_RPC_URL", "http://127.0.0.1:7545")
PRIVATE_KEY     = os.getenv("PRIVATE_KEY")
CONTRACT_OWNER  = os.getenv("CONTRACT_OWNER")

# Load ABI and address generated by deploy.js
with open("blockchain/abi/EvidenceVault.json") as f:
    abi_payload = json.load(f)

with open("blockchain/deployment/EvidenceVault.json") as f:
    deployment = json.load(f)

w3 = Web3(Web3.HTTPProvider(RPC_URL))
assert w3.is_connected(), "Cannot connect to Ganache"

contract = w3.eth.contract(
    address=Web3.to_checksum_address(deployment["contractAddress"]),
    abi=abi_payload["abi"],
)

# Read-only call (no gas)
print(contract.functions.version().call())
print(contract.functions.owner().call())
```

Install Web3.py in the backend virtual environment:

```bash
pip install web3
```

---

## 14. Phase 2 — Development Roadmap

Phase 1 delivers the infrastructure foundation. Phase 2 implements the four on-chain modules inside `EvidenceVault.sol`.

### Module 1 — Device Registry

- `registerDevice(bytes32 deviceId, address deviceAddress, string deviceType)`
- `deactivateDevice(bytes32 deviceId)`
- `getDevice(bytes32 deviceId) returns (DeviceRecord)`

### Module 2 — Authentication Ledger

Integrates with Member 1's Rolling Key Authentication system.

- `logAuthEvent(bytes32 sessionId, string eventType, bytes32 keyHash)`
- `rotateKey(bytes32 sessionId, bytes32 newKeyHash)`
- `getAuthEvents(bytes32 sessionId) returns (AuthEvent[])`

### Module 3 — Evidence Vault

Core forensic anchoring module.

- `submitEvidence(bytes32 contentHash, string classification, string caseRef) returns (bytes32 evidenceId)`
- `sealEvidence(bytes32 evidenceId)`
- `getEvidence(bytes32 evidenceId) returns (EvidenceRecord)`

### Module 4 — Threat Intelligence

Integrates with Member 3's SentinelX AI / CUDA detection engine.

- `reportThreat(string threatType, uint8 severity, bytes32 iocHash) returns (bytes32 threatId)`
- `escalateThreat(bytes32 threatId)`
- `getThreat(bytes32 threatId) returns (ThreatRecord)`

### Additional Phase 2 Work

- [ ] Upgrade to OpenZeppelin `Ownable2Step` and `Pausable`
- [ ] Add role-based access control (`AccessControl`)
- [ ] Write comprehensive unit and integration tests
- [ ] Deploy to Sepolia testnet
- [ ] Implement Web3.py service layer in backend

---

*AERO-SHIELD X — Blockchain & Digital Forensics Module — Phase 1*
