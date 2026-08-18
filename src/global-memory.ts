import fs from "node:fs";
import path from "node:path";
import { ensureDir, globalExportsDir, globalMemoryPath, globalVrosDir } from "./paths";
import { LockedSqliteDatabase } from "./locked-sqlite";
import { globalLearningInputSchema } from "./schemas";
import type { GlobalLearningInput } from "./types";

export interface GlobalLearningRow {
  id: number;
  category: string;
  scope: string;
  title: string;
  body: string;
  tags: string[];
  sourceTarget: string;
  confidence: number;
  status: string;
  createdAt: string;
  updatedAt: string;
}

export interface GlobalLearningQuery {
  text?: string;
  scope?: string;
  category?: string;
  tags?: string[];
  limit?: number;
  includeRetired?: boolean;
}

// Fields a learning can be refined with as it is re-used, so global memory
// improves instead of only growing. Every field is optional: supply just the
// dimensions being corrected. `confidenceDelta` nudges the stored confidence
// (clamped to [0,1]); `confidence` sets it absolutely and wins over the delta.
// `status: "retired"` supersedes a learning without destroying it (it drops out
// of normal queries but stays auditable).
export interface GlobalLearningRefinement {
  id: number;
  title?: string;
  body?: string;
  scope?: string;
  category?: string;
  tags?: string[];
  sourceTarget?: string;
  confidence?: number;
  confidenceDelta?: number;
  status?: "active" | "retired";
  note?: string;
}

export class GlobalMemoryDb {
  readonly dbPath: string;
  private readonly db: LockedSqliteDatabase;

  constructor(dbPath = globalMemoryPath()) {
    ensureDir(path.dirname(dbPath));
    this.dbPath = dbPath;
    this.db = new LockedSqliteDatabase(dbPath);
    this.db.exec("PRAGMA journal_mode = WAL;");
    this.migrate();
  }

  close(): void {
    this.db.close();
  }

  addLearning(input: GlobalLearningInput): number {
    const learning = globalLearningInputSchema.parse(input);
    const now = nowIso();
    const result = this.db
      .prepare(
        `INSERT INTO global_learnings
          (category, scope, title, body, tags_json, source_target, confidence, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
      )
      .run(
        learning.category,
        learning.scope,
        learning.title,
        learning.body,
        json(learning.tags),
        learning.sourceTarget ?? "",
        learning.confidence,
        now,
        now
      );
    const id = Number(result.lastInsertRowid);
    this.indexFts(id, renderSearchContent({ ...learning, sourceTarget: learning.sourceTarget ?? "" }));
    return id;
  }

  // Refine an existing learning in place: correct fields, adjust confidence, or
  // retire it. Returns the updated row, or null if the id does not exist. This
  // is what turns append-only storage into a self-improving loop — a re-used
  // learning gets sharper (or retired) instead of spawning a near-duplicate.
  refineLearning(refinement: GlobalLearningRefinement): GlobalLearningRow | null {
    const existing = this.getLearning(refinement.id);
    if (!existing) return null;

    let confidence = existing.confidence;
    if (typeof refinement.confidence === "number") {
      confidence = refinement.confidence;
    } else if (typeof refinement.confidenceDelta === "number") {
      confidence = existing.confidence + refinement.confidenceDelta;
    }
    confidence = Math.max(0, Math.min(1, confidence));

    let body = refinement.body ?? existing.body;
    if (refinement.note && refinement.note.trim()) {
      const stamp = nowIso();
      body = `${body}\n\n[refined ${stamp}] ${refinement.note.trim()}`;
    }

    const merged = {
      category: refinement.category ?? existing.category,
      scope: refinement.scope ?? existing.scope,
      title: refinement.title ?? existing.title,
      body,
      tags: refinement.tags ?? existing.tags,
      sourceTarget: refinement.sourceTarget ?? existing.sourceTarget,
      confidence,
      status: refinement.status ?? existing.status
    };

    this.db
      .prepare(
        `UPDATE global_learnings
         SET category = ?, scope = ?, title = ?, body = ?, tags_json = ?,
             source_target = ?, confidence = ?, status = ?, updated_at = ?
         WHERE id = ?`
      )
      .run(
        merged.category,
        merged.scope,
        merged.title,
        merged.body,
        json(merged.tags),
        merged.sourceTarget,
        merged.confidence,
        merged.status,
        nowIso(),
        refinement.id
      );

    this.db.prepare("DELETE FROM global_learning_fts WHERE learning_id = ?").run(refinement.id);
    this.indexFts(
      refinement.id,
      renderSearchContent({
        category: merged.category as GlobalLearningInput["category"],
        scope: merged.scope,
        title: merged.title,
        body: merged.body,
        tags: merged.tags,
        confidence: merged.confidence,
        sourceTarget: merged.sourceTarget
      })
    );

    return this.getLearning(refinement.id);
  }

  getLearning(id: number): GlobalLearningRow | null {
    const row = this.db.prepare("SELECT * FROM global_learnings WHERE id = ?").get(id);
    return row ? toGlobalLearningRow(row as Record<string, unknown>) : null;
  }

  queryLearnings(query: GlobalLearningQuery): GlobalLearningRow[] {
    const limit = Math.max(1, Math.min(query.limit ?? 20, 100));
    const rows = query.text?.trim()
      ? this.db
          .prepare(
            `SELECT gl.*
             FROM global_learning_fts fts
             JOIN global_learnings gl ON gl.id = fts.learning_id
             WHERE global_learning_fts MATCH ?
             ORDER BY rank
             LIMIT ?`
          )
          .all(ftsQuery(query.text), limit * 4)
      : this.db
          .prepare("SELECT * FROM global_learnings ORDER BY id DESC LIMIT ?")
          .all(limit * 4);

    return rows
      .map(toGlobalLearningRow)
      .filter((row) => (query.includeRetired ? true : row.status !== "retired"))
      .filter((row) => matchesFilter(row, query))
      .slice(0, limit);
  }

  exportMarkdown(outPath?: string): string {
    const outDir = globalExportsDir();
    ensureDir(outDir);
    const fullPath = outPath ?? path.join(outDir, "global-learnings.md");
    ensureDir(path.dirname(fullPath));
    const rows = this.queryLearnings({ limit: 100 });
    fs.writeFileSync(fullPath, renderGlobalLearnings(rows));
    return fullPath;
  }

  private migrate(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS global_learnings (
        id INTEGER PRIMARY KEY,
        category TEXT NOT NULL,
        scope TEXT NOT NULL,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        tags_json TEXT NOT NULL,
        source_target TEXT NOT NULL,
        confidence REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );

      CREATE VIRTUAL TABLE IF NOT EXISTS global_learning_fts USING fts5(
        learning_id UNINDEXED,
        content
      );
    `);
    // Additive migration for databases created before the status column existed.
    if (!this.hasColumn("global_learnings", "status")) {
      this.db.exec("ALTER TABLE global_learnings ADD COLUMN status TEXT NOT NULL DEFAULT 'active';");
    }
  }

  private hasColumn(table: string, column: string): boolean {
    const rows = this.db.prepare(`PRAGMA table_info(${table})`).all() as Array<{ name?: unknown }>;
    return rows.some((row) => String(row.name) === column);
  }

  private indexFts(learningId: number, content: string): void {
    this.db
      .prepare("INSERT INTO global_learning_fts (learning_id, content) VALUES (?, ?)")
      .run(learningId, content);
  }
}

export function defaultGlobalScopeFromTarget(target: {
  name: string;
  contract: { inScope: string[]; primaryImpactClasses: string[]; assumptions: string[] };
}): string {
  return [target.name, ...target.contract.inScope, ...target.contract.primaryImpactClasses, ...target.contract.assumptions]
    .filter(Boolean)
    .join(", ");
}

function renderGlobalLearnings(rows: GlobalLearningRow[]): string {
  const rendered = rows
    .map(
      (row) =>
        `## G${row.id}: ${row.title}\n\nCategory: ${row.category}\n\nScope: ${row.scope}\n\nTags: ${row.tags.join(", ") || "-"}\n\nConfidence: ${row.confidence.toFixed(2)}\n\nSource target: ${row.sourceTarget || "-"}\n\n${row.body}\n`
    )
    .join("\n");
  return `# Proteus Global Learnings\n\n${rendered || "No global learnings recorded yet.\n"}`;
}

function renderSearchContent(input: GlobalLearningInput & { sourceTarget: string }): string {
  return `${input.category}\n${input.scope}\n${input.title}\n${input.body}\n${input.tags.join("\n")}\n${input.sourceTarget}`;
}

function matchesFilter(row: GlobalLearningRow, query: GlobalLearningQuery): boolean {
  if (query.category && row.category !== query.category) return false;
  if (query.scope && !contains(row.scope, query.scope) && !contains(row.title, query.scope) && !contains(row.body, query.scope)) {
    return false;
  }
  for (const tag of query.tags ?? []) {
    if (!row.tags.some((item) => item.toLowerCase() === tag.toLowerCase())) return false;
  }
  return true;
}

function contains(value: string, needle: string): boolean {
  return value.toLowerCase().includes(needle.toLowerCase());
}

function toGlobalLearningRow(row: Record<string, unknown>): GlobalLearningRow {
  return {
    id: Number(row.id),
    category: String(row.category),
    scope: String(row.scope),
    title: String(row.title),
    body: String(row.body),
    tags: JSON.parse(String(row.tags_json)) as string[],
    sourceTarget: String(row.source_target ?? ""),
    confidence: Number(row.confidence),
    status: String(row.status ?? "active"),
    createdAt: String(row.created_at),
    updatedAt: String(row.updated_at)
  };
}

function ftsQuery(query: string): string {
  return query
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => `"${part.replace(/"/g, '""')}"`)
    .join(" OR ");
}

function json(value: unknown): string {
  return JSON.stringify(value);
}

function nowIso(): string {
  return new Date().toISOString();
}

export function globalMemoryLocation(): string {
  ensureDir(globalVrosDir());
  return globalMemoryPath();
}
