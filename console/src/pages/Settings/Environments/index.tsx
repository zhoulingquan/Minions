import { useState, useCallback, useMemo } from "react";
import { Button, Modal } from "@agentscope-ai/design";

import api from "../../../api";
import { useEnvVars } from "./useEnvVars";
import { EmptyState, AddButton, Toolbar, EnvRow, type Row } from "./components";
import { PageHeader } from "@/components/PageHeader";
import { useAppMessage } from "../../../hooks/useAppMessage";
import styles from "./index.module.less";

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

/** Reindex selected set after a splice at `idx`. */
function shiftIndices(prev: Set<number>, removedIdx: number): Set<number> {
  const next = new Set<number>();
  prev.forEach((i) => {
    if (i < removedIdx) next.add(i);
    else if (i > removedIdx) next.add(i - 1);
  });
  return next;
}

/* ------------------------------------------------------------------ */
/* Main Page                                                           */
/* ------------------------------------------------------------------ */

function EnvironmentsPage() {
    const { message } = useAppMessage();
  const { envVars, loading, error, fetchAll } = useEnvVars();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [keyErrors, setKeyErrors] = useState<Record<number, string>>({});
  const [selected, setSelected] = useState<Set<number>>(new Set());

  /* ---- derived state ---- */

  const workingRows: Row[] = useMemo(
    () => rows ?? envVars.map((e) => ({ key: e.key, value: e.value })),
    [rows, envVars],
  );

  const dirty = rows !== null;
  const someSelected = selected.size > 0;
  const allSelected =
    workingRows.length > 0 && workingRows.every((_, i) => selected.has(i));

  /* ---- ensure we have a mutable local copy ---- */

  const ensureLocal = useCallback((): Row[] => {
    if (rows) return [...rows];
    return envVars.map((e) => ({ key: e.key, value: e.value }));
  }, [rows, envVars]);

  /* ---- selection ---- */

  const toggleSelect = useCallback((idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(workingRows.map((_, i) => i)));
    }
  }, [allSelected, workingRows]);

  /* ---- row mutations ---- */

  const updateRow = useCallback(
    (idx: number, field: "key" | "value", val: string) => {
      const next = ensureLocal();
      next[idx] = { ...next[idx], [field]: val };
      setRows(next);
      if (field === "key") {
        setKeyErrors((prev) => {
          const copy = { ...prev };
          delete copy[idx];
          return copy;
        });
      }
    },
    [ensureLocal],
  );

  const addRow = useCallback(() => {
    const next = ensureLocal();
    next.push({ key: "", value: "", isNew: true });
    setRows(next);
  }, [ensureLocal]);

  const insertRowAfter = useCallback(
    (idx: number) => {
      const next = ensureLocal();
      next.splice(idx + 1, 0, { key: "", value: "", isNew: true });
      setRows(next);
      setSelected((prev) => {
        const rebuilt = new Set<number>();
        prev.forEach((i) => rebuilt.add(i <= idx ? i : i + 1));
        return rebuilt;
      });
    },
    [ensureLocal],
  );

  const removeRow = useCallback(
    (idx: number) => {
      const row = workingRows[idx];

      // New (unsaved) row — just remove from local state, no API call needed
      if (row.isNew) {
        const next = ensureLocal();
        next.splice(idx, 1);
        setRows(next.length === 0 && envVars.length === 0 ? null : next);
        setSelected((prev) => shiftIndices(prev, idx));
        return;
      }

      // Persisted row — confirm then call DELETE API immediately
      Modal.confirm({
        title: "删除变量",
        content: `删除 "${row.key}"?`,
        okText: "删除",
        okButtonProps: { danger: true },
        cancelText: "取消",
        onOk: async () => {
          try {
            await api.deleteEnv(row.key);
            message.success(`"${row.key}" 已删除`);
            // Refresh from server so local state is in sync
            setRows(null);
            setSelected(new Set());
            setKeyErrors({});
            fetchAll();
          } catch (err) {
            const errMsg =
              err instanceof Error
                ? err.message
                : "删除失败";
            message.error(errMsg);
          }
        },
      });
    },
    [workingRows, ensureLocal, envVars.length, fetchAll, message],
  );

  const removeSelected = useCallback(() => {
    if (selected.size === 0) return;
    const indices = Array.from(selected).sort((a, b) => a - b);
    const names = indices.map((i) => workingRows[i]?.key).filter(Boolean);
    const hasPersistedRows = indices.some((i) => !workingRows[i]?.isNew);

    // All selected rows are new — just remove from local state
    if (!hasPersistedRows) {
      const next = ensureLocal().filter((_, i) => !selected.has(i));
      setRows(next.length === 0 && envVars.length === 0 ? null : next);
      setSelected(new Set());
      return;
    }

    const label =
      names.length <= 3
        ? names.map((n) => `"${n}"`).join(", ")
        : `${names.length} variables`;

    Modal.confirm({
      title: "删除选中项",
      content: `删除 ${label}?`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        try {
          const persistedKeysToDelete = indices
            .map((i) => workingRows[i])
            .filter((row) => row && !row.isNew)
            .map((row) => row.key.trim())
            .filter(Boolean);

          if (persistedKeysToDelete.length > 0) {
            await Promise.all(
              persistedKeysToDelete.map((key) => api.deleteEnv(key)),
            );
          }

          message.success(`"${label}" 已删除`);
          setRows(null);
          setSelected(new Set());
          setKeyErrors({});
          fetchAll();
        } catch (err) {
          const errMsg =
            err instanceof Error ? err.message : "删除失败";
          message.error(errMsg);
        }
      },
    });
  }, [
    selected,
    workingRows,
    ensureLocal,
    envVars.length,
    fetchAll,
    message,
  ]);

  /* ---- validate & save ---- */

  const validate = useCallback((): boolean => {
    const errors: Record<number, string> = {};
    const seen = new Set<string>();
    for (let i = 0; i < workingRows.length; i++) {
      const k = workingRows[i].key.trim();
      if (!k) {
        errors[i] = "键为必填项";
      } else if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(k)) {
        errors[i] = "键格式无效";
      } else if (seen.has(k)) {
        errors[i] = "键重复";
      }
      seen.add(k);
    }
    setKeyErrors(errors);
    return Object.keys(errors).length === 0;
  }, [workingRows]);

  const handleSave = useCallback(async () => {
    if (!validate()) return;
    const dict: Record<string, string> = {};
    for (const r of workingRows) {
      dict[r.key.trim()] = r.value;
    }
    setSaving(true);
    try {
      await api.saveEnvs(dict);
      message.success("环境变量已保存");
      setRows(null);
      setKeyErrors({});
      setSelected(new Set());
      fetchAll();
    } catch (err) {
      const errMsg =
        err instanceof Error ? err.message : "保存失败";
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  }, [fetchAll, message, validate, workingRows]);

  const handleReset = useCallback(() => {
    setRows(null);
    setKeyErrors({});
    setSelected(new Set());
  }, []);

  /* ---- render ---- */

  return (
    <div className={styles.environmentsPage}>
      {/* ---- Page header ---- */}
      <PageHeader
        parent={"设置"}
        current={"环境变量"}
        className={styles.pageHeader}
      />

      {/* ---- Content ---- */}
      {loading ? (
        <div className={styles.centerState}>
          <span className={styles.stateText}>{"加载中…"}</span>
        </div>
      ) : error ? (
        <div className={styles.centerState}>
          <span className={styles.stateTextError}>{error}</span>
          <Button size="small" onClick={fetchAll} style={{ marginTop: 12 }}>
            {"重试"}
          </Button>
        </div>
      ) : (
        <div className={styles.tableCard}>
          {/* ---- Toolbar ---- */}
          <Toolbar
            workingRowsLength={workingRows.length}
            allSelected={allSelected}
            someSelected={someSelected}
            selectedSize={selected.size}
            dirty={dirty}
            saving={saving}
            indeterminate={someSelected && !allSelected}
            onToggleSelectAll={toggleSelectAll}
            onRemoveSelected={removeSelected}
            onReset={handleReset}
            onSave={handleSave}
          />

          {/* ---- Rows ---- */}
          <div className={styles.rowList}>
            {workingRows.map((row, idx) => (
              <EnvRow
                key={idx}
                row={row}
                idx={idx}
                checked={selected.has(idx)}
                error={keyErrors[idx]}
                onToggle={toggleSelect}
                onChange={updateRow}
                onInsert={insertRowAfter}
                onRemove={removeRow}
              />
            ))}

            {workingRows.length === 0 && <EmptyState />}
          </div>

          {/* ---- Add button ---- */}
          <AddButton onClick={addRow} />
        </div>
      )}
    </div>
  );
}

export default EnvironmentsPage;
