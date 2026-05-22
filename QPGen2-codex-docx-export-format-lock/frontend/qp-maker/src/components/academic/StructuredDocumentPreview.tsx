/**
 * StructuredDocumentPreview
 *
 * Renders the multimodal structured content of an academic document:
 *   - Headings with hierarchy
 *   - Equations with LaTeX rendering (fallback to monospace)
 *   - Figures with description + component badges
 *   - Tables with grid layout
 *   - Summary badge strip showing what was found
 */

import React, { useState } from "react";
import {
  useStructuredContent,
  type DocumentBlock,
  type EquationBlock,
  type FigureBlock,
  type TableBlock,
  type TextBlock,
  type StructuredPage,
} from "@/lib/academic-api";

// ─── Icon helpers (inline SVG to avoid icon dep) ───────────────────────────

const EqIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="5" y1="12" x2="19" y2="12" /><line x1="5" y1="6" x2="19" y2="6" /><line x1="5" y1="18" x2="19" y2="18" />
  </svg>
);
const FigIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" />
    <polyline points="21 15 16 10 5 21" />
  </svg>
);
const TblIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <line x1="3" y1="9" x2="21" y2="9" /><line x1="3" y1="15" x2="21" y2="15" />
    <line x1="9" y1="3" x2="9" y2="21" /><line x1="15" y1="3" x2="15" y2="21" />
  </svg>
);
const TxtIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="4" y1="6" x2="20" y2="6" /><line x1="4" y1="12" x2="20" y2="12" /><line x1="4" y1="18" x2="14" y2="18" />
  </svg>
);

// ─── Individual block renderers ─────────────────────────────────────────────

function EquationRenderer({ block }: { block: EquationBlock }) {
  const latex = block.latex || block.content || "";
  const methodLabel = {
    nougat: "Nougat",
    vision_llm: "Vision LLM",
    heuristic: "Heuristic",
    none: "Raw",
  }[block.latex_method] ?? "OCR";

  return (
    <div style={{
      background: "linear-gradient(135deg, rgba(139,92,246,0.08), rgba(99,102,241,0.05))",
      border: "1px solid rgba(139,92,246,0.25)",
      borderLeft: "3px solid #8b5cf6",
      borderRadius: "8px",
      padding: "12px 16px",
      margin: "8px 0",
    }}>
      <div style={{
        display: "flex", alignItems: "center", gap: "6px",
        marginBottom: "8px", color: "#a78bfa", fontSize: "11px", fontWeight: 600,
      }}>
        <EqIcon /> EQUATION
        <span style={{
          marginLeft: "auto", background: "rgba(139,92,246,0.15)",
          borderRadius: "4px", padding: "1px 6px", fontSize: "10px", color: "#c4b5fd",
        }}>
          via {methodLabel}
        </span>
      </div>
      <code style={{
        display: "block",
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
        fontSize: "13px",
        color: "#e2e8f0",
        whiteSpace: "pre-wrap",
        wordBreak: "break-all",
        lineHeight: 1.6,
      }}>
        {latex}
      </code>
    </div>
  );
}

function FigureRenderer({ block }: { block: FigureBlock }) {
  const analysis = block.analysis;
  return (
    <div style={{
      background: "linear-gradient(135deg, rgba(16,185,129,0.06), rgba(5,150,105,0.04))",
      border: "1px solid rgba(16,185,129,0.2)",
      borderLeft: "3px solid #10b981",
      borderRadius: "8px",
      padding: "12px 16px",
      margin: "8px 0",
    }}>
      <div style={{
        display: "flex", alignItems: "center", gap: "6px",
        marginBottom: "8px", color: "#34d399", fontSize: "11px", fontWeight: 600,
      }}>
        <FigIcon /> FIGURE
        {analysis?.figure_type && (
          <span style={{
            marginLeft: "auto", background: "rgba(16,185,129,0.15)",
            borderRadius: "4px", padding: "1px 6px", fontSize: "10px", color: "#6ee7b7",
          }}>
            {analysis.figure_type.replace(/_/g, " ")}
          </span>
        )}
      </div>

      {block.caption && (
        <p style={{ fontSize: "12px", color: "#94a3b8", fontStyle: "italic", margin: "0 0 8px" }}>
          {block.caption}
        </p>
      )}

      {analysis?.description && (
        <p style={{ fontSize: "13px", color: "#cbd5e1", margin: "0 0 8px", lineHeight: 1.5 }}>
          {analysis.description}
        </p>
      )}

      {analysis?.components && analysis.components.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", marginTop: "6px" }}>
          <span style={{ fontSize: "11px", color: "#64748b", marginRight: "4px" }}>Components:</span>
          {analysis.components.slice(0, 8).map((c, i) => (
            <span key={i} style={{
              background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.2)",
              borderRadius: "4px", padding: "1px 7px", fontSize: "11px", color: "#6ee7b7",
            }}>
              {c}
            </span>
          ))}
        </div>
      )}

      {analysis?.labels && analysis.labels.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", marginTop: "5px" }}>
          <span style={{ fontSize: "11px", color: "#64748b", marginRight: "4px" }}>Labels:</span>
          {analysis.labels.slice(0, 6).map((l, i) => (
            <code key={i} style={{
              background: "rgba(99,102,241,0.1)", borderRadius: "3px",
              padding: "0 5px", fontSize: "11px", color: "#a5b4fc",
            }}>
              {l}
            </code>
          ))}
        </div>
      )}

      {analysis?.academic_concepts && analysis.academic_concepts.length > 0 && (
        <div style={{ marginTop: "6px", fontSize: "11px", color: "#64748b" }}>
          Concepts: {analysis.academic_concepts.slice(0, 4).join(" · ")}
        </div>
      )}
    </div>
  );
}

function TableRenderer({ block }: { block: TableBlock }) {
  if (!block.rows || block.rows.length === 0) {
    return (
      <div style={{
        background: "rgba(251,191,36,0.06)", border: "1px solid rgba(251,191,36,0.2)",
        borderLeft: "3px solid #f59e0b", borderRadius: "8px", padding: "10px 14px", margin: "8px 0",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#fbbf24", fontSize: "11px", fontWeight: 600 }}>
          <TblIcon /> TABLE
        </div>
        <p style={{ fontSize: "12px", color: "#94a3b8", margin: "6px 0 0" }}>{block.content || "Table detected"}</p>
      </div>
    );
  }

  const headers = block.rows[0];
  const dataRows = block.rows.slice(1);

  return (
    <div style={{
      background: "rgba(251,191,36,0.04)", border: "1px solid rgba(251,191,36,0.2)",
      borderLeft: "3px solid #f59e0b", borderRadius: "8px", padding: "12px 16px", margin: "8px 0",
      overflowX: "auto",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#fbbf24", fontSize: "11px", fontWeight: 600, marginBottom: "10px" }}>
        <TblIcon /> TABLE
        <span style={{ color: "#64748b", fontWeight: 400 }}>· {block.rows.length} rows × {headers.length} cols</span>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={i} style={{
                background: "rgba(251,191,36,0.12)", color: "#fbbf24",
                padding: "6px 10px", textAlign: "left", fontWeight: 600,
                border: "1px solid rgba(251,191,36,0.15)", whiteSpace: "nowrap",
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {dataRows.slice(0, 8).map((row, ri) => (
            <tr key={ri} style={{ background: ri % 2 === 0 ? "transparent" : "rgba(255,255,255,0.02)" }}>
              {row.map((cell, ci) => (
                <td key={ci} style={{
                  padding: "5px 10px", color: "#cbd5e1",
                  border: "1px solid rgba(255,255,255,0.06)",
                }}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {dataRows.length > 8 && (
        <p style={{ fontSize: "11px", color: "#64748b", margin: "6px 0 0" }}>
          +{dataRows.length - 8} more rows…
        </p>
      )}
    </div>
  );
}

function TextRenderer({ block }: { block: TextBlock }) {
  if (block.type === "heading") {
    return (
      <h3 style={{
        fontSize: "14px", fontWeight: 700, color: "#f1f5f9",
        margin: "14px 0 4px", borderBottom: "1px solid rgba(255,255,255,0.06)",
        paddingBottom: "4px",
      }}>
        {block.content}
      </h3>
    );
  }
  if (block.type === "code") {
    return (
      <pre style={{
        background: "rgba(0,0,0,0.3)", border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: "6px", padding: "10px 12px", margin: "6px 0",
        fontSize: "12px", color: "#a5f3fc", overflowX: "auto",
        fontFamily: "'JetBrains Mono', monospace",
      }}>
        {block.content}
      </pre>
    );
  }
  if (block.type === "list") {
    return (
      <p style={{ fontSize: "13px", color: "#94a3b8", margin: "3px 0", paddingLeft: "12px" }}>
        • {block.content}
      </p>
    );
  }
  if (block.type === "caption") {
    return (
      <p style={{ fontSize: "12px", color: "#64748b", fontStyle: "italic", margin: "2px 0 6px" }}>
        {block.content}
      </p>
    );
  }
  return (
    <p style={{ fontSize: "13px", color: "#94a3b8", margin: "4px 0", lineHeight: 1.55 }}>
      {block.content.length > 400 ? `${block.content.slice(0, 400)}…` : block.content}
    </p>
  );
}

function BlockRenderer({ block }: { block: DocumentBlock }) {
  switch (block.type) {
    case "equation": return <EquationRenderer block={block as EquationBlock} />;
    case "figure":   return <FigureRenderer block={block as FigureBlock} />;
    case "table":    return <TableRenderer block={block as TableBlock} />;
    default:         return <TextRenderer block={block as TextBlock} />;
  }
}

// ─── Page renderer ──────────────────────────────────────────────────────────

function PageRenderer({ page }: { page: StructuredPage }) {
  return (
    <div style={{ marginBottom: "24px" }}>
      <div style={{
        fontSize: "11px", fontWeight: 600, color: "#475569",
        textTransform: "uppercase", letterSpacing: "0.08em",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        paddingBottom: "6px", marginBottom: "10px",
      }}>
        Page {page.page_number} · {page.blocks.length} blocks
      </div>
      {page.blocks.map((block, i) => (
        <BlockRenderer key={i} block={block} />
      ))}
    </div>
  );
}

// ─── Summary badge strip ────────────────────────────────────────────────────

interface SummaryBadge {
  icon: React.ReactNode;
  label: string;
  count: number;
  color: string;
  bg: string;
}

function SummaryStrip({
  equationCount, figureCount, tableCount, headingCount,
}: {
  equationCount: number; figureCount: number; tableCount: number; headingCount: number;
}) {
  const badges: SummaryBadge[] = [
    { icon: <EqIcon />, label: "Equations",  count: equationCount, color: "#a78bfa", bg: "rgba(139,92,246,0.12)" },
    { icon: <FigIcon />, label: "Figures",    count: figureCount,   color: "#34d399", bg: "rgba(16,185,129,0.10)" },
    { icon: <TblIcon />, label: "Tables",     count: tableCount,    color: "#fbbf24", bg: "rgba(251,191,36,0.10)" },
    { icon: <TxtIcon />, label: "Sections",   count: headingCount,  color: "#60a5fa", bg: "rgba(96,165,250,0.10)" },
  ];

  return (
    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "16px" }}>
      {badges.map(b => (
        <div key={b.label} style={{
          display: "flex", alignItems: "center", gap: "5px",
          background: b.bg, border: `1px solid ${b.color}30`,
          borderRadius: "8px", padding: "5px 10px",
          color: b.color, fontSize: "12px", fontWeight: 500,
        }}>
          {b.icon}
          <span style={{ fontWeight: 700 }}>{b.count}</span>
          <span style={{ opacity: 0.75 }}>{b.label}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Main component ─────────────────────────────────────────────────────────

interface StructuredDocumentPreviewProps {
  documentId: number;
  fileName?: string;
}

export function StructuredDocumentPreview({
  documentId,
  fileName,
}: StructuredDocumentPreviewProps) {
  const { data, isLoading, error } = useStructuredContent(documentId);
  const [currentPage, setCurrentPage] = useState(0);
  const [filterType, setFilterType] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div style={{
        display: "flex", alignItems: "center", gap: "10px",
        color: "#64748b", fontSize: "13px", padding: "16px",
      }}>
        <div style={{
          width: "16px", height: "16px", borderRadius: "50%",
          border: "2px solid #6366f1", borderTopColor: "transparent",
          animation: "spin 0.8s linear infinite",
        }} />
        Loading structured content…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ color: "#f87171", fontSize: "13px", padding: "12px" }}>
        Could not load structured content.
      </div>
    );
  }

  const { structured_content } = data;

  if (!structured_content) {
    if (data.processing_status !== "completed") {
      return (
        <div style={{
          background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.2)",
          borderRadius: "10px", padding: "14px 18px", color: "#818cf8", fontSize: "13px",
        }}>
          Multimodal parsing in progress ({data.processing_status})…
          <br />
          <span style={{ fontSize: "11px", color: "#64748b", marginTop: "4px", display: "block" }}>
            Equations, figures, and tables will appear here once processing completes.
          </span>
        </div>
      );
    }
    return (
      <div style={{ color: "#64748b", fontSize: "13px", padding: "12px" }}>
        No structured content available for this document.
      </div>
    );
  }

  const { pages, summary } = structured_content;

  // Filter pages containing blocks of selected type
  const filteredPages = filterType
    ? pages.map(p => ({
        ...p,
        blocks: p.blocks.filter(b => b.type === filterType),
      })).filter(p => p.blocks.length > 0)
    : pages;

  const displayPages = filteredPages.slice(currentPage * 3, currentPage * 3 + 3);
  const totalGroups = Math.ceil(filteredPages.length / 3);

  const filterButtons = [
    { type: null,       label: "All",       color: "#94a3b8" },
    { type: "equation", label: "Equations", color: "#a78bfa" },
    { type: "figure",   label: "Figures",   color: "#34d399" },
    { type: "table",    label: "Tables",    color: "#fbbf24" },
    { type: "heading",  label: "Headings",  color: "#60a5fa" },
  ];

  return (
    <div style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginBottom: "14px",
      }}>
        <div>
          <div style={{ fontSize: "13px", fontWeight: 600, color: "#e2e8f0" }}>
            Structured Content
          </div>
          <div style={{ fontSize: "11px", color: "#64748b" }}>
            {summary.total_pages} page{summary.total_pages !== 1 ? "s" : ""} · {summary.parser}
          </div>
        </div>
        <span style={{
          background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.3)",
          borderRadius: "6px", padding: "3px 10px", fontSize: "11px", color: "#818cf8",
        }}>
          Multimodal
        </span>
      </div>

      {/* Summary badges */}
      <SummaryStrip
        equationCount={summary.equation_count}
        figureCount={summary.figure_count}
        tableCount={summary.table_count}
        headingCount={summary.heading_count}
      />

      {/* Filter bar */}
      <div style={{ display: "flex", gap: "6px", marginBottom: "14px", flexWrap: "wrap" }}>
        {filterButtons.map(fb => (
          <button
            key={String(fb.type)}
            onClick={() => { setFilterType(fb.type); setCurrentPage(0); }}
            style={{
              background: filterType === fb.type ? `${fb.color}20` : "transparent",
              border: `1px solid ${filterType === fb.type ? fb.color : "rgba(255,255,255,0.1)"}`,
              borderRadius: "6px", padding: "4px 10px",
              fontSize: "11px", color: filterType === fb.type ? fb.color : "#64748b",
              cursor: "pointer", transition: "all 0.15s",
            }}
          >
            {fb.label}
          </button>
        ))}
      </div>

      {/* Pages */}
      {filteredPages.length === 0 ? (
        <div style={{ color: "#64748b", fontSize: "13px", padding: "20px", textAlign: "center" }}>
          No {filterType ? `${filterType} ` : ""}blocks found in this document.
        </div>
      ) : (
        <>
          {displayPages.map(page => (
            <PageRenderer key={page.page_number} page={page} />
          ))}

          {/* Pagination */}
          {totalGroups > 1 && (
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              gap: "8px", marginTop: "12px",
            }}>
              <button
                onClick={() => setCurrentPage(p => Math.max(0, p - 1))}
                disabled={currentPage === 0}
                style={{
                  background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: "6px", padding: "4px 12px", color: "#94a3b8",
                  cursor: currentPage === 0 ? "not-allowed" : "pointer", fontSize: "12px",
                  opacity: currentPage === 0 ? 0.4 : 1,
                }}
              >
                ← Prev
              </button>
              <span style={{ fontSize: "12px", color: "#64748b" }}>
                {currentPage + 1} / {totalGroups}
              </span>
              <button
                onClick={() => setCurrentPage(p => Math.min(totalGroups - 1, p + 1))}
                disabled={currentPage >= totalGroups - 1}
                style={{
                  background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: "6px", padding: "4px 12px", color: "#94a3b8",
                  cursor: currentPage >= totalGroups - 1 ? "not-allowed" : "pointer", fontSize: "12px",
                  opacity: currentPage >= totalGroups - 1 ? 0.4 : 1,
                }}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
