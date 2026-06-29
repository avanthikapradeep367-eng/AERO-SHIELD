// ============================================================
//  AERO-SHIELD X — Deployment Script
//  Target contract : EvidenceVault
//  Framework       : Hardhat + Ethers v6
// ============================================================
//
//  Usage:
//    npx hardhat run scripts/deploy.js --network ganache
//    npx hardhat run scripts/deploy.js --network localhost
//
//  After a successful run this script writes two artefacts:
//    abi/EvidenceVault.json          — ABI for Web3.py / front-end
//    deployment/EvidenceVault.json   — Address, tx hash, gas, network
// ============================================================

const { ethers, artifacts, network } = require("hardhat");
const fs   = require("fs");
const path = require("path");

// --------------------------------------------------------
//  Helpers
// --------------------------------------------------------

/**
 * Ensure a directory exists; create it recursively if not.
 */
function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

/**
 * Write JSON data to a file with pretty-printing.
 */
function writeJson(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), "utf8");
  console.log(`  [saved] ${filePath}`);
}

/**
 * Format a BigInt wei value to a human-readable ETH string.
 */
function formatEth(weiValue) {
  return ethers.formatEther(weiValue) + " ETH";
}

// --------------------------------------------------------
//  Main Deployment Function
// --------------------------------------------------------
async function main() {
  console.log("=".repeat(60));
  console.log(" AERO-SHIELD X — EvidenceVault Deployment");
  console.log("=".repeat(60));

  // ---- 1. Signer ----------------------------------------
  const [deployer] = await ethers.getSigners();
  const deployerAddress = await deployer.getAddress();

  console.log("\n  Network      :", network.name);
  console.log("  Chain ID     :", (await ethers.provider.getNetwork()).chainId.toString());
  console.log("  Deployer     :", deployerAddress);

  // Balance check
  const balanceBefore = await ethers.provider.getBalance(deployerAddress);
  console.log("  Balance      :", formatEth(balanceBefore));

  if (balanceBefore === 0n) {
    throw new Error("Deployer account has zero balance. Fund the account in Ganache first.");
  }

  // ---- 2. Compile check ---------------------------------
  console.log("\n  Compiling contracts...");
  // Hardhat compiles automatically before deployment, but
  // fetching the artifact here confirms it succeeded.
  const artifact = await artifacts.readArtifact("EvidenceVault");
  console.log("  Artifact     : EvidenceVault (Solidity", artifact.sourceName + ")");

  // ---- 3. Deploy ----------------------------------------
  console.log("\n  Deploying EvidenceVault...");

  const Factory = await ethers.getContractFactory("EvidenceVault");

  // Estimate gas before deploying so we can print it
  const deployTx     = await Factory.getDeployTransaction();
  const estimatedGas = await ethers.provider.estimateGas(deployTx);
  console.log("  Est. gas     :", estimatedGas.toString(), "units");

  const contract = await Factory.deploy();
  const receipt  = await contract.deploymentTransaction().wait(1); // wait 1 confirmation

  // ---- 4. Collect deployment data -----------------------
  const contractAddress = await contract.getAddress();
  const txHash          = receipt.hash;
  const gasUsed         = receipt.gasUsed.toString();
  const blockNumber     = receipt.blockNumber;
  const deployedAt      = new Date().toISOString();

  // ---- 5. Verify ownership ------------------------------
  const onChainOwner = await contract.owner();
  const contractVersion = await contract.version();

  // ---- 6. Print deployment summary ----------------------
  console.log("\n" + "=".repeat(60));
  console.log(" DEPLOYMENT SUCCESSFUL");
  console.log("=".repeat(60));
  console.log("  Contract     :", contractAddress);
  console.log("  Tx Hash      :", txHash);
  console.log("  Gas Used     :", gasUsed, "units");
  console.log("  Block #      :", blockNumber);
  console.log("  Owner        :", onChainOwner);
  console.log("  Version      :", contractVersion);
  console.log("  Network      :", network.name);
  console.log("  Timestamp    :", deployedAt);

  const balanceAfter = await ethers.provider.getBalance(deployerAddress);
  const gasCost      = balanceBefore - balanceAfter;
  console.log("  Gas cost     :", formatEth(gasCost));
  console.log("=".repeat(60));

  // ---- 7. Save ABI ---------------------------------------
  const abiDir  = path.join(__dirname, "..", "abi");
  const abiPath = path.join(abiDir, "EvidenceVault.json");
  ensureDir(abiDir);

  const abiPayload = {
    contractName: "EvidenceVault",
    abi: artifact.abi,
    generatedAt: deployedAt,
    network: network.name,
    contractAddress,
  };
  console.log("\n  Saving ABI...");
  writeJson(abiPath, abiPayload);

  // ---- 8. Save deployment record -------------------------
  const deploymentDir  = path.join(__dirname, "..", "deployment");
  const deploymentPath = path.join(deploymentDir, "EvidenceVault.json");
  ensureDir(deploymentDir);

  const chainId = (await ethers.provider.getNetwork()).chainId;

  const deploymentRecord = {
    contractName:    "EvidenceVault",
    contractAddress,
    txHash,
    gasUsed,
    blockNumber,
    deployedAt,
    deployer:        deployerAddress,
    owner:           onChainOwner,
    version:         contractVersion,
    network: {
      name:    network.name,
      chainId: chainId.toString(),
      rpcUrl:  process.env.GANACHE_RPC_URL || "http://127.0.0.1:7545",
    },
  };

  console.log("\n  Saving deployment record...");
  writeJson(deploymentPath, deploymentRecord);

  // ---- 9. Done -------------------------------------------
  console.log("\n  Next steps:");
  console.log("    1. Load the ABI from abi/EvidenceVault.json in your Web3.py integration.");
  console.log("    2. Use the address from deployment/EvidenceVault.json when calling contract methods.");
  console.log("    3. Proceed to Phase 2 to implement the four on-chain modules.");
  console.log("");
}

// --------------------------------------------------------
//  Entry point — top-level error handler
// --------------------------------------------------------
main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n[DEPLOY ERROR]", error.message || error);
    process.exit(1);
  });
