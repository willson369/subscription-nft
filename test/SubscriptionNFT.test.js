const { expect } = require("chai");
const { ethers, upgrades } = require("hardhat");
const { time, loadFixture } = require("@nomicfoundation/hardhat-toolbox/network-helpers");

describe("SubscriptionNFT", function () {
  const price = ethers.parseEther("0.01");
  const duration = 30 * 24 * 60 * 60;

  async function deployFixture() {
    const [admin, alice, bob, operator, treasury] = await ethers.getSigners();
    const factory = await ethers.getContractFactory("SubscriptionNFT");
    const subscription = await upgrades.deployProxy(
      factory,
      [admin.address, price, duration, "Subscription Membership", "SUB"],
      { kind: "uups" }
    );
    await subscription.waitForDeployment();
    return { subscription, admin, alice, bob, operator, treasury };
  }

  it("mints one NFT and sets the initial expiry after payment", async function () {
    const { subscription, alice } = await loadFixture(deployFixture);
    const before = await time.latest();

    await expect(subscription.connect(alice).subscribe({ value: price }))
      .to.emit(subscription, "SubscriptionPurchased")
      .withArgs(alice.address, 1, before + duration + 1);

    expect(await subscription.ownerOf(1)).to.equal(alice.address);
    expect(await subscription.tokenIdOf(alice.address)).to.equal(1);
    expect(await subscription.isActive(alice.address)).to.equal(true);
  });

  it("renews the existing NFT instead of minting a second one", async function () {
    const { subscription, alice } = await loadFixture(deployFixture);
    await subscription.connect(alice).subscribe({ value: price });
    const firstExpiry = await subscription.expiresAt(1);

    await time.increase(24 * 60 * 60);
    await subscription.connect(alice).subscribe({ value: price });

    expect(await subscription.tokenIdOf(alice.address)).to.equal(1);
    expect(await subscription.expiresAt(1)).to.equal(firstExpiry + BigInt(duration));
    await expect(subscription.ownerOf(2)).to.be.revertedWithCustomError(
      subscription,
      "ERC721NonexistentToken"
    );
  });

  it("starts a renewed expired membership from the current time", async function () {
    const { subscription, alice } = await loadFixture(deployFixture);
    await subscription.connect(alice).subscribe({ value: price });
    await time.increase(duration + 1);

    expect(await subscription.isActive(alice.address)).to.equal(false);
    const before = await time.latest();
    await subscription.connect(alice).subscribe({ value: price });

    expect(await subscription.expiresAt(1)).to.equal(before + duration + 1);
    expect(await subscription.isActive(alice.address)).to.equal(true);
  });

  it("rejects an incorrect payment", async function () {
    const { subscription, alice } = await loadFixture(deployFixture);
    await expect(subscription.connect(alice).subscribe({ value: price - 1n }))
      .to.be.revertedWithCustomError(subscription, "IncorrectPayment")
      .withArgs(price, price - 1n);
  });

  it("prevents transfers between wallets", async function () {
    const { subscription, alice, bob } = await loadFixture(deployFixture);
    await subscription.connect(alice).subscribe({ value: price });

    await expect(
      subscription.connect(alice)["safeTransferFrom(address,address,uint256)"](
        alice.address,
        bob.address,
        1
      )
    ).to.be.revertedWithCustomError(subscription, "TransfersDisabled");
  });

  it("lets operators extend existing memberships", async function () {
    const { subscription, admin, alice, operator } = await loadFixture(deployFixture);
    await subscription.connect(alice).subscribe({ value: price });
    const originalExpiry = await subscription.expiresAt(1);
    await subscription.connect(admin).grantRole(await subscription.OPERATOR_ROLE(), operator.address);

    await subscription.connect(operator).extendMembership(alice.address, 7 * 24 * 60 * 60);
    expect(await subscription.expiresAt(1)).to.equal(originalExpiry + BigInt(7 * 24 * 60 * 60));
  });

  it("allows admins to pause sales without blocking account status", async function () {
    const { subscription, admin, alice } = await loadFixture(deployFixture);
    await subscription.connect(alice).subscribe({ value: price });
    await subscription.connect(admin).pause();

    expect(await subscription.isActive(alice.address)).to.equal(true);
    await expect(subscription.connect(alice).subscribe({ value: price }))
      .to.be.revertedWithCustomError(subscription, "EnforcedPause");
  });

  it("withdraws collected ETH only to the configured treasury", async function () {
    const { subscription, admin, alice, treasury } = await loadFixture(deployFixture);
    await subscription.connect(alice).subscribe({ value: price });
    await subscription.connect(admin).setTreasury(treasury.address);

    await expect(subscription.connect(admin).withdraw())
      .to.changeEtherBalances([subscription, treasury], [-price, price]);
  });

  it("allows only admins to authorize UUPS upgrades", async function () {
    const { subscription, admin, alice } = await loadFixture(deployFixture);
    const V2 = await ethers.getContractFactory("SubscriptionNFTV2");

    await expect(upgrades.upgradeProxy(await subscription.getAddress(), V2.connect(alice)))
      .to.be.revertedWithCustomError(subscription, "AccessControlUnauthorizedAccount")
      .withArgs(alice.address, await subscription.DEFAULT_ADMIN_ROLE());

    const upgraded = await upgrades.upgradeProxy(await subscription.getAddress(), V2.connect(admin));
    expect(await upgraded.version()).to.equal(2);
  });
});
