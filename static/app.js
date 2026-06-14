let editor = null;
let schemaData = { tables: [], tableDetails: {}, columnsByTable: {} };

const logOutput = document.getElementById("log-output");
const previewBody = document.getElementById("preview-body");
const previewHead = document.getElementById("preview-head");
const previewTable = document.getElementById("preview-table");
const previewEmpty = document.getElementById("preview-empty");
const previewMeta = document.getElementById("preview-meta");
const schemaStatus = document.getElementById("schema-status");
const targetSelect = document.getElementById("target-select");
const runBtn = document.getElementById("run-btn");
const applyBtn = document.getElementById("apply-btn");

function appendLog(message, type = "info") {
  const line = document.createElement("p");
  line.className = `log-line ${type}`;
  line.textContent = message;
  logOutput.appendChild(line);
  logOutput.scrollTop = logOutput.scrollHeight;
}

function clearLog() {
  logOutput.innerHTML = "";
}

function validateSelectOnly(sql) {
  const trimmed = sql.trim().replace(/;+\s*$/, "");
  if (!trimmed) return "Query is empty";

  const withoutStrings = trimmed
    .replace(/'[^']*'/g, "''")
    .replace(/"[^"]*"/g, '""');

  if (/;/.test(withoutStrings)) {
    return "Only a single SELECT statement is allowed";
  }
  if (!/^\s*(WITH\b[\s\S]+?\bSELECT\b|SELECT\b)/i.test(trimmed)) {
    return "Only SELECT queries are allowed";
  }
  if (/\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|MERGE|EXEC|EXECUTE|ALTER|CREATE|GRANT|REVOKE|DENY|DBCC)\b/i.test(withoutStrings)) {
    return "Only SELECT queries are allowed";
  }
  if (/\bSELECT\b[\s\S]*\bINTO\b/i.test(withoutStrings)) {
    return "SELECT INTO is not allowed";
  }
  if (!/\bFROM\b/i.test(withoutStrings)) {
    return "Query must contain a FROM clause";
  }
  return null;
}

function parseAliases(sql) {
  const aliases = new Map();
  const pattern =
    /(?:\bFROM\b|\bJOIN\b)\s+(?:\[[\w\s]+\]|\w+)(?:\.\[[\w\s]+\]|\.[\w]+)?(?:\s+(?:AS\s+)?(\[[\w\s]+\]|[\w]+))?/gi;
  let match;
  while ((match = pattern.exec(sql)) !== null) {
    if (match[1]) {
      const alias = match[1].replace(/^\[|\]$/g, "");
      aliases.set(alias.toLowerCase(), alias);
    }
  }
  return aliases;
}

function buildHintTables() {
  const hints = {};
  for (const fullName of schemaData.tables) {
    const detail = schemaData.tableDetails[fullName];
    if (!detail) continue;
    hints[fullName] = detail.columns;
    hints[detail.name] = detail.columns;
    hints[`${detail.schema}.${detail.name}`] = detail.columns;
  }
  return hints;
}

function customSqlHint(editorInstance, options) {
  const cursor = editorInstance.getCursor();
  const token = editorInstance.getTokenAt(cursor);
  const sql = editorInstance.getValue();
  const aliases = parseAliases(sql);

  let word = "";
  let start = cursor.ch;
  let end = cursor.ch;

  if (token.string && /[\w\[\].]+/.test(token.string)) {
    word = token.string.slice(0, cursor.ch - token.start);
    start = token.start;
    end = cursor.ch;
  }

  const list = [];
  const lowerWord = word.toLowerCase();

  if (word.includes(".")) {
    const prefix = word.split(".")[0].replace(/^\[|\]$/g, "");
    const colPrefix = word.split(".").slice(1).join(".").toLowerCase();

    let columns = [];
    if (aliases.has(prefix.toLowerCase())) {
      const alias = aliases.get(prefix.toLowerCase());
      for (const [tableName, detail] of Object.entries(schemaData.tableDetails)) {
        const refs = [detail.name, `${detail.schema}.${detail.name}`, alias];
        if (refs.some((r) => r.toLowerCase() === prefix.toLowerCase() || alias.toLowerCase() === prefix.toLowerCase())) {
          columns = detail.columns;
          break;
        }
      }
    } else {
      const tableKey = Object.keys(schemaData.tableDetails).find(
        (k) =>
          k.toLowerCase() === prefix.toLowerCase() ||
          k.split(".")[1]?.toLowerCase() === prefix.toLowerCase()
      );
      if (tableKey) columns = schemaData.columnsByTable[tableKey] || [];
    }

    for (const col of columns) {
      if (!colPrefix || col.toLowerCase().startsWith(colPrefix)) {
        list.push(`${prefix}.${col}`);
      }
    }
  } else {
    for (const tableName of schemaData.tables) {
      if (!lowerWord || tableName.toLowerCase().includes(lowerWord)) {
        list.push(tableName);
      }
    }
    for (const alias of aliases.values()) {
      if (!lowerWord || alias.toLowerCase().startsWith(lowerWord)) {
        list.push(alias);
      }
    }
    for (const tableName of schemaData.tables) {
      for (const col of schemaData.columnsByTable[tableName] || []) {
        if (!lowerWord || col.toLowerCase().startsWith(lowerWord)) {
          list.push(col);
        }
      }
    }
  }

  const unique = [...new Set(list)].sort();
  return {
    list: unique.length ? unique : null,
    from: CodeMirror.Pos(cursor.line, start),
    to: CodeMirror.Pos(cursor.line, end),
  };
}

function setSchemaStatus(text, state = "loading") {
  schemaStatus.className = `status-pill ${state}`;
  schemaStatus.innerHTML = `<span class="status-dot"></span><span class="status-text">${text}</span>`;
}

function showPreviewMessage(message, isError = false) {
  previewHead.innerHTML = "";
  previewBody.innerHTML = "";
  previewTable.classList.add("hidden");
  previewEmpty.hidden = false;
  previewEmpty.innerHTML = isError
    ? `<div class="empty-icon error-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.8"/><path d="M12 8v5m0 3h.01" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></div><p>${message}</p>`
    : `<div class="empty-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.8"/><path d="M3 10h18M8 5V3m8 2V3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></div><p>${message}</p>`;
}

function initEditor() {
  editor = CodeMirror.fromTextArea(document.getElementById("sql-editor"), {
    mode: "text/x-mssql",
    theme: "dracula",
    lineNumbers: true,
    indentWithTabs: false,
    indentUnit: 2,
    extraKeys: {
      "Ctrl-Space": "autocomplete",
      "Ctrl-Enter": () => runPreview(),
    },
    hintOptions: { hint: customSqlHint },
  });

  editor.on("inputRead", (cm, change) => {
    if (change.text[0] && /[\w.]/.test(change.text[0])) {
      cm.showHint({ completeSingle: false });
    }
  });

  editor.setValue(
    "SELECT TOP (100) *\nFROM dbo.YourTable t\n-- JOIN dbo.OtherTable o ON t.Id = o.ParentId\nWHERE 1 = 1"
  );
}

async function loadTargets() {
  try {
    const res = await fetch("/api/targets");
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    targetSelect.innerHTML = "";

    if (!data.targets?.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "No targets configured";
      option.disabled = true;
      targetSelect.appendChild(option);
      applyBtn.disabled = true;
      return;
    }

    for (const name of data.targets) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      targetSelect.appendChild(option);
    }
    applyBtn.disabled = false;
  } catch (err) {
    targetSelect.innerHTML = "";
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Failed to load targets";
    option.disabled = true;
    targetSelect.appendChild(option);
    applyBtn.disabled = true;
    appendLog(`Targets unavailable: ${err.message}`, "error");
  }
}

async function loadSchema() {
  try {
    const res = await fetch("/api/schema");
    if (!res.ok) throw new Error(await res.text());
    schemaData = await res.json();
    if (schemaData.error) {
      setSchemaStatus(`Schema warning: ${schemaData.error}`, "error");
    } else {
      setSchemaStatus(`${schemaData.tables.length.toLocaleString()} tables from production`, "ok");
    }
  } catch (err) {
    setSchemaStatus(`Schema unavailable`, "error");
  }
}

function renderPreview(columns, rows) {
  previewHead.innerHTML = "";
  previewBody.innerHTML = "";

  if (!rows.length) {
    showPreviewMessage("No rows matched your query");
    previewMeta.textContent = "0 rows";
    return;
  }

  previewEmpty.hidden = true;
  previewTable.classList.remove("hidden");
  previewMeta.textContent = `${rows.length.toLocaleString()} row(s) shown`;

  const headerRow = document.createElement("tr");
  for (const col of columns) {
    const th = document.createElement("th");
    th.textContent = col;
    th.title = col;
    headerRow.appendChild(th);
  }
  previewHead.appendChild(headerRow);

  for (const row of rows) {
    const tr = document.createElement("tr");
    for (const col of columns) {
      const td = document.createElement("td");
      const val = row[col];
      td.textContent = val === null || val === undefined ? "NULL" : String(val);
      td.title = td.textContent;
      tr.appendChild(td);
    }
    previewBody.appendChild(tr);
  }
}

async function runPreview() {
  const sql = editor.getValue().trim();
  if (!sql) return;

  const validationError = validateSelectOnly(sql);
  if (validationError) {
    showPreviewMessage(validationError, true);
    previewMeta.textContent = "";
    return;
  }

  runBtn.disabled = true;
  previewMeta.textContent = "Running…";

  try {
    const res = await fetch("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql }),
    });
    const data = await res.json();
    if (!res.ok) {
      const detail = Array.isArray(data.detail)
        ? data.detail.map((d) => d.msg).join("; ")
        : data.detail;
      throw new Error(detail || res.statusText);
    }
    renderPreview(data.columns, data.rows);
  } catch (err) {
    showPreviewMessage(err.message, true);
    previewMeta.textContent = "";
  } finally {
    runBtn.disabled = false;
  }
}

async function consumeSSE(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      if (!part.trim()) continue;
      if (part.startsWith("event: done")) {
        appendLog("Stream closed.", "success");
        continue;
      }
      const dataLine = part.split("\n").find((l) => l.startsWith("data: "));
      if (!dataLine) continue;

      const payload = JSON.parse(dataLine.slice(6));
      const type = payload.error ? "error" : payload.summary ? "summary" : "info";
      appendLog(payload.message, type);

      if (payload.summary) {
        for (const [table, count] of Object.entries(payload.summary)) {
          appendLog(`  ${table}: ${count} row(s) inserted`, "summary");
        }
      }
    }
  }
}

async function runApply() {
  const sql = editor.getValue().trim();
  const target = targetSelect.value;
  if (!sql) return;

  const validationError = validateSelectOnly(sql);
  if (validationError) {
    appendLog(`Error: ${validationError}`, "error");
    return;
  }

  if (!targetSelect.value) {
    appendLog("No target database selected.", "error");
    return;
  }

  if (!confirm(`Copy rows to ${target}? This will upsert data from production.`)) {
    return;
  }

  applyBtn.disabled = true;
  runBtn.disabled = true;
  clearLog();
  appendLog(`Starting sync to ${target}…`, "muted");

  try {
    const res = await fetch("/api/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql, target }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }

    await consumeSSE(res);
  } catch (err) {
    appendLog(`Error: ${err.message}`, "error");
  } finally {
    applyBtn.disabled = false;
    runBtn.disabled = false;
  }
}

runBtn.addEventListener("click", runPreview);
applyBtn.addEventListener("click", runApply);

initEditor();
loadTargets();
loadSchema();
