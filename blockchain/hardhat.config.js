// ============================================================
//  AERO-SHIELD X — Hardhat Configuration
//  Blockchain & Digital Forensics Module
// ============================================================
//
//  Hardhat is a development environment for compiling, testing,
//  deploying and debugging Ethereum smart contracts.
//
//  This config targets Ganache as the local development network.
//  Additional networks (testnets, mainnet) are reserved for
//  future phases.
// ============================================================

require("@nomicfoundation/hardhat-toolbox");
require("hardhat-gas-reporter");
require("dotenv").config();

// --------------------------------------------------------
//  Environment variable helpers
//  All sensitive values are loaded from .env (never committed).
// --------------------------------------------------------
const GANACHE_RPC_URL  = process.env.GANACHE_RPC_URL  || "http://127.0.0.1:7545";
const PRIVATE_KEY      = process.env.PRIVATE_KEY       || "0x0000000000000000000000000000000000000000000000000000000000000001";
const CHAIN_ID         = parseInt(process.env.CHAIN_ID || "1337", 10);
const REPORT_GAS       = process.env.REPORT_GAS        === "true";
const COINMARKETCAP_KEY = process.env.COINMARKETCAP_API_KEY || "";

// --------------------------------------------------------
//  Hardhat Configuration Object
// --------------------------------------------------------
/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {

  // ----------------------------------------------------------
  //  Solidity Compiler
  //
  //  version  — must match the pragma in every .sol file.
  //  optimizer — reduces deployed bytecode size and lowers gas
  //              costs for end-users. runs=200 is the standard
  //              trade-off (optimise for average call frequency).
  // ----------------------------------------------------------
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
      // evmVersion can be overridden here if a specific EVM
      // hardfork is required (e.g. "paris", "shanghai").
    },
  },

  // ----------------------------------------------------------
  //  Networks
  //
  //  Ganache — local private Ethereum blockchain used for
  //  development. Provides instant mining, deterministic
  //  accounts, and zero-cost transactions.
  //
  //  localhost — Hardhat's built-in network (npx hardhat node).
  //  Kept here as a secondary option during unit testing.
  // ----------------------------------------------------------
  networks: {
    // Primary development network
    ganache: {
      url: GANACHE_RPC_URL,       // RPC endpoint exposed by Ganache
      chainId: CHAIN_ID,           // Must match Ganache chain ID (default 1337)
      accounts: [PRIVATE_KEY],     // Array of private keys; index 0 = deployer
      gas: "auto",                 // Let Hardhat estimate gas limit
      gasPrice: "auto",            // Let Hardhat read current gas price
      timeout: 60000,              // 60 s RPC timeout
    },

    // Hardhat's in-process network (fast unit tests, no Ganache required)
    hardhat: {
      chainId: 31337,
      gas: "auto",
      gasPrice: "auto",
      accounts: {
        count: 10,             // Generate 10 test accounts
        accountsBalance: "10000000000000000000000", // 10,000 ETH each
      },
      mining: {
        auto: true,            // Mine a block on every transaction
        interval: 0,
      },
    },

    // localhost — points to npx hardhat node when running separately
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 31337,
    },

    // ---- Future networks (uncomment in later phases) ----
    // sepolia: {
    //   url: process.env.SEPOLIA_RPC_URL,
    //   accounts: [PRIVATE_KEY],
    //   chainId: 11155111,
    // },
    // mainnet: {
    //   url: process.env.MAINNET_RPC_URL,
    //   accounts: [PRIVATE_KEY],
    //   chainId: 1,
    // },
  },

  // ----------------------------------------------------------
  //  Gas Reporter
  //
  //  Prints a table of gas consumption for every function call
  //  and contract deployment after running the test suite.
  //  Set REPORT_GAS=true in .env to enable.
  // ----------------------------------------------------------
  gasReporter: {
    enabled: REPORT_GAS,
    currency: "USD",
    coinmarketcap: COINMARKETCAP_KEY,
    outputFile: "gas-report.txt",
    noColors: true,
    excludeContracts: [],
  },

  // ----------------------------------------------------------
  //  Solidity Coverage
  //
  //  Generates an Istanbul-compatible coverage report after
  //  running: npx hardhat coverage
  // ----------------------------------------------------------
  // coverage configuration is handled by the plugin defaults;
  // add `solidity-coverage` exclusions here if needed:
  // mocha: { timeout: 120000 },

  // ----------------------------------------------------------
  //  Paths
  //
  //  Override default Hardhat output directories to match the
  //  AERO-SHIELD project structure.
  // ----------------------------------------------------------
  paths: {
    sources:   "./contracts",    // .sol source files
    tests:     "./test",         // Mocha/Chai test files
    cache:     "./cache",        // Compilation cache
    artifacts: "./artifacts",    // Compiled ABI + bytecode
  },

  // ----------------------------------------------------------
  //  Etherscan (reserved for Phase 3 — public testnet deploy)
  // ----------------------------------------------------------
  // etherscan: {
  //   apiKey: process.env.ETHERSCAN_API_KEY,
  // },
};
