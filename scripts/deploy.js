const { ethers, upgrades } = require("hardhat");

const PRICE = ethers.parseEther("0.01");
const THIRTY_DAYS = 30 * 24 * 60 * 60;

async function main() {
  const [deployer] = await ethers.getSigners();
  const SubscriptionNFT = await ethers.getContractFactory("SubscriptionNFT");
  const subscription = await upgrades.deployProxy(
    SubscriptionNFT,
    [deployer.address, PRICE, THIRTY_DAYS, "Subscription Membership", "SUB"],
    { kind: "uups" }
  );

  await subscription.waitForDeployment();
  console.log("Proxy address:", await subscription.getAddress());
  console.log("Deployer / initial treasury:", deployer.address);
  console.log("Subscription price: 0.01 ETH");
  console.log("Subscription duration: 30 days");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
