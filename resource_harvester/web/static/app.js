const $ = (selector) => document.querySelector(selector);
const terminal = new Set(["completed", "partial", "failed"]);
let media = null;
let pollTimer = null;

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[character]);
}

function bytes(value) {
  if (value === null || value === undefined) return "未知大小";
  const units = ["B", "KB", "MB", "GB"];
  let amount = value;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toFixed(unit ? 1 : 0)} ${units[unit]}`;
}

function showError(message) {
  $("#loading").classList.remove("hidden");
  $("#loading").innerHTML = `<div class="message error">${escapeHtml(message)}</div>`;
}

async function loadMedia() {
  try {
    const response = await fetch("/api/media");
    if (!response.ok) throw new Error("视频信息加载失败");
    media = await response.json();
    $("#loading").classList.add("hidden");
    $("#media").classList.remove("hidden");
    $("#options").classList.remove("hidden");
    $("#cover").src = media.cover_url;
    $("#title").textContent = media.title;
    $("#owner").textContent = `UP 主 · ${media.owner || "未知"}`;
    $("#description").textContent = media.description || "没有视频简介";
    $("#auth-badge").textContent = media.authenticated ? "已使用登录态" : "游客模式";

    const selectedPart = media.selected_part;
    $("#parts").innerHTML = media.parts.map((part) => `
      <label class="part">
        <input class="part-input" type="checkbox" value="${part.cid}"
          ${!selectedPart || selectedPart === part.index ? "checked" : ""}>
        <span>P${part.index} · ${escapeHtml(part.title)}</span>
        <small>${Math.ceil(part.duration / 60)} 分钟</small>
      </label>
    `).join("");

    const qualityMap = new Map();
    for (const part of media.parts) {
      for (const quality of part.qualities) {
        if (!qualityMap.has(quality.id)) qualityMap.set(quality.id, quality.label);
      }
    }
    const qualities = [...qualityMap.entries()].sort((a, b) => b[0] - a[0]);
    $("#quality").innerHTML = qualities.map(([id, label]) =>
      `<option value="${id}">${escapeHtml(label)}</option>`
    ).join("");
  } catch (error) {
    showError(error.message);
  }
}

async function startJob() {
  const partCids = [...document.querySelectorAll(".part-input:checked")]
    .map((input) => Number(input.value));
  if (!partCids.length) {
    alert("请至少选择一个分P。");
    return;
  }
  const payload = {
    part_cids: partCids,
    quality_id: Number($("#quality").value),
    download_cover: $("#download-cover").checked,
    download_metadata: $("#download-metadata").checked,
    download_subtitles: $("#download-subtitles").checked,
    download_danmaku_xml: $("#download-xml").checked,
    download_danmaku_ass: $("#download-ass").checked,
  };
  $("#start").disabled = true;
  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "任务创建失败");
    $("#job").classList.remove("hidden");
    pollJob(data.job_id);
  } catch (error) {
    $("#start").disabled = false;
    showJobMessages([], [error.message]);
  }
}

function showJobMessages(warnings, errors) {
  $("#job").classList.remove("hidden");
  $("#messages").innerHTML = [
    ...warnings.map((value) => `<div class="message warning">${escapeHtml(value)}</div>`),
    ...errors.map((value) => `<div class="message error">${escapeHtml(value)}</div>`),
  ].join("");
}

async function pollJob(jobId) {
  clearTimeout(pollTimer);
  try {
    const response = await fetch(`/api/jobs/${jobId}`);
    const job = await response.json();
    if (!response.ok) throw new Error(job.detail || "任务状态读取失败");

    $("#stage").textContent = job.stage;
    $("#status").textContent = job.status;
    $("#current-file").textContent = job.current_file || "";
    $("#actual-quality").textContent = job.actual_quality
      ? `实际画质：${job.actual_quality}` : "";
    const progress = $("#progress");
    if (job.total_bytes) {
      const percent = Math.min(100, job.downloaded_bytes / job.total_bytes * 100);
      progress.classList.remove("indeterminate");
      progress.style.width = `${percent}%`;
      $("#progress-text").textContent =
        `${bytes(job.downloaded_bytes)} / ${bytes(job.total_bytes)} · ${percent.toFixed(1)}%`;
    } else {
      progress.style.width = "";
      progress.classList.add("indeterminate");
      $("#progress-text").textContent = bytes(job.downloaded_bytes);
    }
    showJobMessages(job.warnings, job.errors);
    $("#artifacts").innerHTML = job.artifacts
      .map((path) => `<li>${escapeHtml(path)}</li>`).join("");

    if (terminal.has(job.status)) {
      $("#start").disabled = false;
      progress.classList.remove("indeterminate");
      if (job.status === "completed") progress.style.width = "100%";
      return;
    }
    pollTimer = setTimeout(() => pollJob(jobId), 700);
  } catch (error) {
    showJobMessages([], [error.message]);
    $("#start").disabled = false;
  }
}

$("#start").addEventListener("click", startJob);
loadMedia();
