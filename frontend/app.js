const { contractAddress, chainId, chainName } = window.SUBSCRIPTION_CONFIG;
const abi = [
  "function subscriptionPrice() view returns (uint128)",
  "function membershipOf(address) view returns (uint256 tokenId, uint64 expiry, bool active)",
  "function subscribe() payable"
];

let provider;
let signer;
let contract;
let account;

const connectButton = document.querySelector("#connectButton");
const subscribeButton = document.querySelector("#subscribeButton");
const message = document.querySelector("#message");

function setMessage(text) {
  message.textContent = text;
}

function formatError(error) {
  if (error.code === 4001 || error.code === "ACTION_REJECTED") return "你已取消钱包签名。";
  if (error.code === "INSUFFICIENT_FUNDS") return "钱包余额不足以支付订阅费和 Gas。";
  return error.shortMessage || error.info?.error?.message || error.message || "交易失败，请稍后重试。";
}

function requireDeployedContract() {
  if (contractAddress === "0x0000000000000000000000000000000000000000") {
    throw new Error("合约尚未配置。请在 config.js 中填入 Sepolia 代理合约地址。");
  }
}

async function refreshMembership() {
  const [tokenId, expiry, active] = await contract.membershipOf(account);
  const status = document.querySelector("#status");
  const expiryElement = document.querySelector("#expiry");
  const action = tokenId === 0n ? "立即订阅" : "续费 30 天";

  subscribeButton.textContent = `${action} · 0.01 ETH / 30 天`;
  status.textContent = active ? "会员有效" : tokenId === 0n ? "尚未订阅" : "权益已失效";
  status.className = `status ${active ? "active" : "expired"}`;

  if (tokenId !== 0n) {
    const expiryDate = new Date(Number(expiry) * 1000);
    expiryElement.textContent = `会员有效期至：${expiryDate.toLocaleString("zh-CN")}`;
  } else {
    expiryElement.textContent = "订阅后即可获得不可转让的会员 NFT。";
  }
}

async function connect() {
  try {
    if (!window.ethereum) throw new Error("未检测到钱包。请安装 MetaMask 或兼容的钱包扩展。");
    requireDeployedContract();
    provider = new ethers.BrowserProvider(window.ethereum);
    await provider.send("eth_requestAccounts", []);
    const network = await provider.getNetwork();
    if (Number(network.chainId) !== chainId) {
      await provider.send("wallet_switchEthereumChain", [{ chainId: `0x${chainId.toString(16)}` }]);
    }

    signer = await provider.getSigner();
    account = await signer.getAddress();
    contract = new ethers.Contract(contractAddress, abi, signer);
    document.querySelector("#account").textContent = account;
    document.querySelector("#network").textContent = `已连接 ${chainName}`;
    document.querySelector("#membership").hidden = false;
    connectButton.hidden = true;
    await refreshMembership();
  } catch (error) {
    setMessage(formatError(error));
  }
}

async function subscribe() {
  try {
    subscribeButton.disabled = true;
    setMessage("正在请求钱包签名...");
    const price = await contract.subscriptionPrice();
    const transaction = await contract.subscribe({ value: price });
    setMessage("交易已提交，正在等待链上确认...");
    await transaction.wait();
    setMessage("订阅已生效。");
    await refreshMembership();
  } catch (error) {
    setMessage(formatError(error));
  } finally {
    subscribeButton.disabled = false;
  }
}

connectButton.addEventListener("click", connect);
subscribeButton.addEventListener("click", subscribe);
