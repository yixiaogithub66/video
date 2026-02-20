<script setup>
import { computed, onMounted, reactive, ref } from "vue";

const messages = {
  en: {
    title: "Video Ops Studio",
    subtitle: "Self-hosted Vue console for planning, QA loop, and review operations",
    token: "API Token",
    refresh: "Refresh",
    lang: "中文",
    tabOps: "Ops Studio",
    tabWorkflow: "Workflow Board",
    createJob: "Create Job",
    instruction: "Instruction",
    inputUri: "Input URI",
    callbackUrl: "Callback URL (optional)",
    create: "Submit",
    jobs: "Jobs",
    selected: "Selected Job",
    selectHint: "Select one job from table",
    approve: "Approve",
    reject: "Reject",
    rerun: "Rerun",
    qa: "QA Report",
    artifacts: "Artifacts",
    events: "Events",
    none: "None",
    status: "Status",
    capability: "Capability",
    model: "Model Bundle",
    score: "Latest QA Score",
    workflowHint: "Drag-free board grouped by current status",
    empty: "No jobs in this column",
    timeline: "Event Timeline",
    runtimeMode: "Runtime Mode",
    provider: "Provider",
    source: "Model Source",
    created: "Created",
    updated: "Updated",
    successCreate: "Job submitted",
    statusMap: {
      queued: "queued",
      planning: "planning",
      editing: "editing",
      qa: "qa",
      human_review: "human_review",
      succeeded: "succeeded",
      failed: "failed",
      blocked: "blocked"
    }
  },
  zh: {
    title: "视频运营控制台",
    subtitle: "基于 Vue 的自研前端，支持任务编排、质检闭环与人工审核",
    token: "API 令牌",
    refresh: "刷新",
    lang: "English",
    tabOps: "运营视图",
    tabWorkflow: "工作流看板",
    createJob: "创建任务",
    instruction: "编辑指令",
    inputUri: "输入 URI",
    callbackUrl: "回调地址（可选）",
    create: "提交任务",
    jobs: "任务列表",
    selected: "当前任务",
    selectHint: "请从左侧列表选择任务",
    approve: "通过",
    reject: "驳回",
    rerun: "重跑",
    qa: "质检报告",
    artifacts: "产物清单",
    events: "事件日志",
    none: "暂无",
    status: "状态",
    capability: "能力类型",
    model: "模型包",
    score: "最新质检分",
    workflowHint: "按当前状态分组的工作流看板",
    empty: "此列暂无任务",
    timeline: "事件时间线",
    runtimeMode: "运行模式",
    provider: "提供方",
    source: "模型来源",
    created: "创建时间",
    updated: "更新时间",
    successCreate: "任务已提交",
    statusMap: {
      queued: "排队中",
      planning: "规划中",
      editing: "编辑中",
      qa: "质检中",
      human_review: "人工复核",
      succeeded: "已完成",
      failed: "失败",
      blocked: "已拦截"
    }
  }
};

const statusColumns = ["queued", "planning", "editing", "qa", "human_review", "succeeded", "failed", "blocked"];
const boardColumns = ["queued", "editing", "human_review", "succeeded"];

const locale = ref(localStorage.getItem("studio_locale") || ((navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en"));
const token = ref(localStorage.getItem("studio_api_token") || "dev-token");
const activeTab = ref("ops");

const loading = ref(false);
const submitting = ref(false);
const errorMessage = ref("");
const okMessage = ref("");

const jobs = ref([]);
const selectedJobId = ref("");
const selectedJob = ref(null);
const qaReport = ref(null);
const artifacts = ref(null);
const events = ref([]);

const modelInfo = ref(null);

const createForm = reactive({
  instruction: "",
  input_uri: "minio://raw/demo.mp4",
  callback_url: ""
});

function t(key) {
  return messages[locale.value][key] || messages.en[key] || key;
}

function statusLabel(status) {
  return t("statusMap")[status] || status;
}

function formatTime(value) {
  if (!value) {
    return "-";
  }
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function pretty(value) {
  return JSON.stringify(value ?? {}, null, 2);
}

function setLocale(next) {
  locale.value = next;
  localStorage.setItem("studio_locale", next);
}

function toggleLocale() {
  setLocale(locale.value === "zh" ? "en" : "zh");
}

function updateToken(value) {
  token.value = value;
  localStorage.setItem("studio_api_token", value);
}

async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token.value}`
  };
  const response = await fetch(path, {
    ...options,
    headers: {
      ...headers,
      ...(options.headers || {})
    }
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${text}`);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

async function loadModelInfo() {
  try {
    modelInfo.value = await api("/api/v1/models/recommend", {
      method: "POST",
      body: JSON.stringify({})
    });
  } catch (err) {
    modelInfo.value = null;
    errorMessage.value = err.message;
  }
}

async function loadJobs() {
  loading.value = true;
  errorMessage.value = "";
  okMessage.value = "";
  try {
    const payload = await api("/api/v1/jobs?limit=100");
    jobs.value = payload.items || [];
    if (!selectedJobId.value && jobs.value.length > 0) {
      await selectJob(jobs.value[0].job_id);
    }
    if (selectedJobId.value && !jobs.value.find((job) => job.job_id === selectedJobId.value)) {
      selectedJobId.value = "";
      selectedJob.value = null;
      qaReport.value = null;
      artifacts.value = null;
      events.value = [];
    }
  } catch (err) {
    errorMessage.value = err.message;
  } finally {
    loading.value = false;
  }
}

async function selectJob(jobId) {
  selectedJobId.value = jobId;
  errorMessage.value = "";
  try {
    const detailPromise = api(`/api/v1/jobs/${jobId}`);
    const qaPromise = api(`/api/v1/jobs/${jobId}/qa-report`).catch(() => null);
    const artifactsPromise = api(`/api/v1/jobs/${jobId}/artifacts`).catch(() => null);
    const eventsPromise = api(`/api/v1/jobs/${jobId}/events?limit=400`).catch(() => []);

    const [detail, qa, arts, evt] = await Promise.all([detailPromise, qaPromise, artifactsPromise, eventsPromise]);
    selectedJob.value = detail;
    qaReport.value = qa;
    artifacts.value = arts;
    events.value = evt;
  } catch (err) {
    errorMessage.value = err.message;
  }
}

async function submitJob() {
  submitting.value = true;
  errorMessage.value = "";
  okMessage.value = "";
  try {
    const body = {
      instruction: createForm.instruction,
      input_uri: createForm.input_uri
    };
    if (createForm.callback_url.trim()) {
      body.callback_url = createForm.callback_url.trim();
    }
    const created = await api("/api/v1/jobs", {
      method: "POST",
      body: JSON.stringify(body)
    });
    okMessage.value = `${t("successCreate")}: ${created.job_id}`;
    createForm.instruction = "";
    await loadJobs();
    await selectJob(created.job_id);
  } catch (err) {
    errorMessage.value = err.message;
  } finally {
    submitting.value = false;
  }
}

async function reviewDecision(decision) {
  if (!selectedJobId.value) {
    return;
  }
  errorMessage.value = "";
  okMessage.value = "";
  try {
    await api(`/api/v1/reviews/${selectedJobId.value}/decision`, {
      method: "POST",
      body: JSON.stringify({
        decision,
        reviewer: "vue-ops",
        reason: "manual operation from vue studio"
      })
    });
    await loadJobs();
    await selectJob(selectedJobId.value);
  } catch (err) {
    errorMessage.value = err.message;
  }
}

const boardData = computed(() => {
  const map = {};
  statusColumns.forEach((status) => {
    map[status] = [];
  });
  jobs.value.forEach((job) => {
    if (!map[job.status]) {
      map[job.status] = [];
    }
    map[job.status].push(job);
  });
  return map;
});

const canReview = computed(() => selectedJob.value && selectedJob.value.status === "human_review");

onMounted(async () => {
  document.title = t("title");
  await Promise.all([loadJobs(), loadModelInfo()]);
});
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <h1>{{ t("title") }}</h1>
        <p>{{ t("subtitle") }}</p>
      </div>
      <div class="toolbar">
        <input
          class="token-input"
          :placeholder="t('token')"
          :value="token"
          @input="(e) => updateToken(e.target.value)"
        />
        <button class="btn btn-ghost" @click="toggleLocale">{{ t("lang") }}</button>
        <button class="btn btn-primary" :disabled="loading" @click="loadJobs">{{ t("refresh") }}</button>
      </div>
    </header>

    <div class="tabs">
      <button class="tab" :class="{ active: activeTab === 'ops' }" @click="activeTab = 'ops'">
        {{ t("tabOps") }}
      </button>
      <button class="tab" :class="{ active: activeTab === 'workflow' }" @click="activeTab = 'workflow'">
        {{ t("tabWorkflow") }}
      </button>
    </div>

    <section v-if="activeTab === 'ops'" class="panel split">
      <div>
        <h2 class="section-title">{{ t("createJob") }}</h2>
        <div class="create-form">
          <input
            class="field"
            :placeholder="t('inputUri')"
            v-model="createForm.input_uri"
          />
          <input
            class="field"
            :placeholder="t('callbackUrl')"
            v-model="createForm.callback_url"
          />
          <textarea
            class="field"
            :placeholder="t('instruction')"
            v-model="createForm.instruction"
          />
          <button class="btn btn-primary" :disabled="submitting || !createForm.instruction.trim()" @click="submitJob">
            {{ t("create") }}
          </button>
        </div>

        <h2 class="section-title">{{ t("jobs") }}</h2>
        <div class="jobs-table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>{{ t("status") }}</th>
                <th>{{ t("capability") }}</th>
                <th>{{ t("score") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="job in jobs"
                :key="job.job_id"
                :class="{ 'active-row': selectedJobId === job.job_id }"
                @click="selectJob(job.job_id)"
              >
                <td class="mono">{{ job.job_id.slice(0, 8) }}</td>
                <td><span class="chip">{{ statusLabel(job.status) }}</span></td>
                <td>{{ job.capability || "-" }}</td>
                <td>{{ job.latest_qa_score ?? "-" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h2 class="section-title">{{ t("selected") }}</h2>
        <div v-if="!selectedJob" class="muted">{{ t("selectHint") }}</div>
        <template v-else>
          <div class="actions">
            <button class="btn btn-primary" :disabled="!canReview" @click="reviewDecision('approve')">{{ t("approve") }}</button>
            <button class="btn btn-danger" :disabled="!canReview" @click="reviewDecision('reject')">{{ t("reject") }}</button>
            <button class="btn btn-muted" :disabled="!canReview && selectedJob.status !== 'failed'" @click="reviewDecision('rerun')">
              {{ t("rerun") }}
            </button>
          </div>

          <div class="kv">
            <div class="card"><b>ID:</b> <span class="mono">{{ selectedJob.job_id }}</span></div>
            <div class="card"><b>{{ t("status") }}:</b> {{ statusLabel(selectedJob.status) }}</div>
            <div class="card"><b>{{ t("model") }}:</b> {{ selectedJob.model_bundle || "-" }}</div>
            <div class="card"><b>{{ t("created") }}:</b> {{ formatTime(selectedJob.created_at) }}</div>
            <div class="card"><b>{{ t("updated") }}:</b> {{ formatTime(selectedJob.updated_at) }}</div>
          </div>

          <h3 class="section-title">{{ t("qa") }}</h3>
          <pre class="json-box">{{ qaReport ? pretty(qaReport) : t("none") }}</pre>

          <h3 class="section-title">{{ t("artifacts") }}</h3>
          <pre class="json-box">{{ artifacts ? pretty(artifacts) : t("none") }}</pre>

          <h3 class="section-title">{{ t("events") }}</h3>
          <pre class="json-box">{{ events.length ? pretty(events) : t("none") }}</pre>
        </template>

        <h3 class="section-title">{{ t("source") }}</h3>
        <div class="card" v-if="modelInfo">
          <div><b>{{ t("runtimeMode") }}:</b> {{ modelInfo.runtime_mode }}</div>
          <div><b>{{ t("provider") }}:</b> {{ modelInfo.api_provider }}</div>
          <div><b>{{ t("model") }}:</b> {{ modelInfo.default_bundle }}</div>
        </div>
      </div>
    </section>

    <section v-else class="panel">
      <h2 class="section-title">{{ t("tabWorkflow") }}</h2>
      <div class="muted">{{ t("workflowHint") }}</div>
      <div class="workflow-board">
        <div v-for="status in boardColumns" :key="status" class="col">
          <h3>{{ statusLabel(status) }} ({{ boardData[status]?.length || 0 }})</h3>
          <div
            v-for="job in boardData[status]"
            :key="job.job_id"
            class="mini-card"
            @click="selectJob(job.job_id)"
          >
            <div class="mono">{{ job.job_id.slice(0, 10) }}</div>
            <div class="muted">{{ job.capability || "-" }}</div>
          </div>
          <div v-if="!boardData[status] || boardData[status].length === 0" class="muted">{{ t("empty") }}</div>
        </div>
      </div>

      <div class="timeline">
        <h3 class="section-title">{{ t("timeline") }}</h3>
        <div v-if="events.length === 0" class="muted">{{ t("none") }}</div>
        <div v-for="event in events" :key="event.event_id" class="event">
          <div><b>{{ event.stage }}</b> · {{ event.level }}</div>
          <div class="muted">{{ formatTime(event.created_at) }}</div>
          <div>{{ event.message }}</div>
        </div>
      </div>
    </section>

    <div v-if="errorMessage" class="error">{{ errorMessage }}</div>
    <div v-if="okMessage" class="ok">{{ okMessage }}</div>
  </div>
</template>
