const titleInput = document.querySelector("#title");
const questionInput = document.querySelector("#question");
const essayInput = document.querySelector("#essay");
const targetScoreInput = document.querySelector("#targetScore");
const wordCountEl = document.querySelector("#wordCount");
const submitBtn = document.querySelector("#submitBtn");
const statusText = document.querySelector("#statusText");
const resultPanel = document.querySelector("#resultPanel");
const modelBadge = document.querySelector("#modelBadge");

const SAMPLE_ESSAY =
  "基层治理是国家治理体系的重要基础，需要以群众需求为导向推进改革与创新。" +
  "在实践中，部分地区仍存在服务流程复杂、部门协同不足、数字化能力薄弱等问题。" +
  "要提升治理效能，首先要优化权责边界，构建跨部门协同机制，其次要完善数字平台，" +
  "推动数据共享和流程再造，最后要强化干部能力建设和群众参与，形成共建共治共享格局。" +
  "同时要把改革成效转化为可持续的制度成果，持续优化公共服务供给。";

if (!essayInput.value.trim()) {
  essayInput.value = SAMPLE_ESSAY;
}

function estimateWordCount(text) {
  const cjk = (text.match(/[\u4e00-\u9fff]/g) || []).length;
  const tokens = (text.match(/[A-Za-z0-9]+/g) || []).length;
  return cjk + tokens;
}

function setStatus(message, isError = false) {
  statusText.textContent = message;
  statusText.style.color = isError ? "var(--warn)" : "var(--muted)";
}

function updateWordCount() {
  wordCountEl.textContent = `字数 ${estimateWordCount(essayInput.value)}`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `请求失败 (${response.status})`);
  }
  return data;
}

function renderResult(result) {
  resultPanel.hidden = false;
  document.querySelector("#overallScore").textContent = Number(result.overall_score).toFixed(1);
  document.querySelector("#summary").textContent = result.summary || "";
  document.querySelector("#providerInfo").textContent =
    `${result.model_info.provider} / ${result.model_info.model}`;
  document.querySelector("#latency").textContent = result.latency_ms
    ? `耗时 ${result.latency_ms} ms`
    : "";
  document.querySelector("#tokenUsage").textContent = result.token_usage
    ? `Token ${result.token_usage.total}`
    : "";

  const dims = document.querySelector("#dimensionScores");
  dims.innerHTML = "";
  Object.entries(result.dimension_scores || {}).forEach(([name, score]) => {
    const el = document.createElement("div");
    el.className = "dim";
    el.innerHTML = `<span>${name}</span><strong>${Number(score).toFixed(1)}</strong>`;
    dims.appendChild(el);
  });

  const issues = document.querySelector("#keyIssues");
  issues.innerHTML = "";
  (result.key_issues || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    issues.appendChild(li);
  });

  const plan = document.querySelector("#revisionPlan");
  plan.innerHTML = "";
  (result.revision_plan || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    plan.appendChild(li);
  });
}

async function waitForResult(taskId) {
  const started = Date.now();
  while (Date.now() - started < 120000) {
    const result = await api(`/api/v1/ai/corrections/${taskId}`);
    if (result.status === "succeeded") {
      return result;
    }
    if (result.status === "failed") {
      throw new Error(result.error_message || "批改失败");
    }
    setStatus("批改中，DeepSeek 正在阅卷…");
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  throw new Error("批改超时，请稍后重试");
}

async function submitGrading() {
  const title = titleInput.value.trim();
  const question = questionInput.value.trim();
  const essay = essayInput.value.trim();
  const targetScore = Number(targetScoreInput.value);

  if (title.length < 2) {
    setStatus("请填写标题", true);
    return;
  }
  if (question.length < 20) {
    setStatus("题干至少 20 字", true);
    return;
  }
  if (essay.length < 50) {
    setStatus("正文至少 50 字", true);
    return;
  }

  submitBtn.disabled = true;
  resultPanel.hidden = true;
  setStatus("正在创建作业…");

  try {
    const phone = `1${String(Date.now()).slice(-10)}`;
    const user = await api("/api/v1/users", {
      method: "POST",
      body: JSON.stringify({ phone }),
    });

    const assignment = await api("/api/v1/assignments", {
      method: "POST",
      body: JSON.stringify({
        user_id: user.id,
        title,
        question_text: question,
        essay_text: essay,
      }),
    });

    setStatus("作业已提交，正在排队批改…");
    const task = await api("/api/v1/ai/corrections", {
      method: "POST",
      body: JSON.stringify({
        assignment_id: assignment.id,
        question_text: question,
        essay_text: essay,
        scoring_standard: "shenlun_v1",
        target_score: Number.isFinite(targetScore) ? targetScore : null,
      }),
    });

    const result = await waitForResult(task.task_id);
    renderResult(result);
    setStatus("批改完成");
  } catch (error) {
    setStatus(error.message || "批改失败", true);
  } finally {
    submitBtn.disabled = false;
  }
}

async function bootstrap() {
  updateWordCount();
  try {
    const health = await api("/healthz");
    const ready = health.api_key_configured ? "已接入" : "未配置 Key";
    modelBadge.textContent = `${health.provider}/${health.model} · ${ready}`;
  } catch {
    modelBadge.textContent = "服务未就绪";
  }
}

essayInput.addEventListener("input", updateWordCount);
submitBtn.addEventListener("click", submitGrading);
bootstrap();
