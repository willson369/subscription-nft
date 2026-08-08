const states = {
  active: {
    badge: "ACTIVE",
    badgeClass: "active",
    date: "2026年9月8日",
    days: "剩余 30 天",
    button: "模拟续费 30 天",
    message: "当前会员有效，可以直接续费。"
  },
  renewed: {
    badge: "ACTIVE",
    badgeClass: "active",
    date: "2026年10月8日",
    days: "剩余 60 天",
    button: "已模拟续费",
    message: "NFT 编号保持 #001，到期时间已在原有基础上增加 30 天。"
  },
  expired: {
    badge: "EXPIRED",
    badgeClass: "expired",
    date: "2026年7月9日",
    days: "权益已失效",
    button: "模拟重新订阅",
    message: "NFT 仍在钱包中，但 isActive() 返回 false，权益不可用。"
  },
  operator: {
    badge: "ACTIVE",
    badgeClass: "active",
    date: "2026年9月15日",
    days: "剩余 37 天",
    button: "运营补偿已生效",
    message: "OPERATOR_ROLE 已为现有 NFT 增加 7 天有效期，无需铸造新 NFT。"
  }
};

const badge = document.querySelector("#demoBadge");
const expiryDate = document.querySelector("#expiryDate");
const remainingDays = document.querySelector("#remainingDays");
const renewButton = document.querySelector("#renewButton");
const demoMessage = document.querySelector("#demoMessage");
const flowSteps = document.querySelectorAll(".flow-step");

function renderState(name) {
  const state = states[name];
  badge.textContent = state.badge;
  badge.className = `badge ${state.badgeClass}`;
  expiryDate.textContent = state.date;
  remainingDays.textContent = state.days;
  renewButton.textContent = state.button;
  demoMessage.textContent = state.message;
  flowSteps.forEach((step) => step.classList.toggle("selected", step.dataset.state === name));
}

flowSteps.forEach((step) => {
  step.addEventListener("click", () => renderState(step.dataset.state));
});

renewButton.addEventListener("click", () => renderState("renewed"));
