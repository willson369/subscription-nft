const { ethers, upgrades } = require("hardhat");

async function main() {
  const proxyAddress = process.env.CONTRACT_ADDRESS;
  if (!proxyAddress) {
    throw new Error("Set CONTRACT_ADDRESS in .env before upgrading.");
  }

  const SubscriptionNFTV2 = await ethers.getContractFactory("SubscriptionNFTV2");
  const upgraded = await upgrades.upgradeProxy(proxyAddress, SubscriptionNFTV2, {
    kind: "uups"
  });

  await upgraded.waitForDeployment();
  console.log("Upgraded proxy:", await upgraded.getAddress());
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
