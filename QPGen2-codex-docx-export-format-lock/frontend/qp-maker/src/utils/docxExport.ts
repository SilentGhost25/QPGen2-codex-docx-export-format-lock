import {
  AlignmentType,
  BorderStyle,
  convertInchesToTwip,
  Document,
  Packer,
  Paragraph,
  Table,
  TableCell,
  TableLayoutType,
  TableRow,
  TextRun,
  VerticalAlignTable,
  WidthType,
  ImageRun,
} from "docx";
import { saveAs } from "file-saver";

import type { GeneratedPaper, PaperQuestion } from "@/lib/ai-api";
import { DSU_LOGO_BASE64 } from "./logoBase64";

const FONT = "Times New Roman";
const BODY_SIZE = 22;
const SMALL_SIZE = 20;
const QUESTION_WIDTHS = [8, 62, 10, 10, 10];

const tableBorders = {
  top: { style: BorderStyle.SINGLE, size: 4, color: "000000" },
  bottom: { style: BorderStyle.SINGLE, size: 4, color: "000000" },
  left: { style: BorderStyle.SINGLE, size: 4, color: "000000" },
  right: { style: BorderStyle.SINGLE, size: 4, color: "000000" },
  insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: "000000" },
  insideVertical: { style: BorderStyle.SINGLE, size: 4, color: "000000" },
};

const noBorders = {
  top: { style: BorderStyle.NIL, size: 0, color: "FFFFFF" },
  bottom: { style: BorderStyle.NIL, size: 0, color: "FFFFFF" },
  left: { style: BorderStyle.NIL, size: 0, color: "FFFFFF" },
  right: { style: BorderStyle.NIL, size: 0, color: "FFFFFF" },
  insideHorizontal: { style: BorderStyle.NIL, size: 0, color: "FFFFFF" },
  insideVertical: { style: BorderStyle.NIL, size: 0, color: "FFFFFF" },
};

type BlueprintSlot = {
  questionNumber: number;
  subpart: string;
  label: string;
  marks: number;
  moduleNumber: number;
};

type PaperRow =
  | { type: "module"; title: string }
  | { type: "or" }
  | {
      type: "question";
      qno: string;
      text: string;
      marks: string;
      co: string;
      rbtl: string;
      subQuestions?: Array<{ label?: string; text: string }>;
    };

function tr(text: string | number, options: { bold?: boolean; italics?: boolean; size?: number; color?: string } = {}) {
  return new TextRun({
    text: String(text ?? ""),
    font: FONT,
    size: options.size ?? BODY_SIZE,
    bold: options.bold,
    italics: options.italics,
    color: options.color,
  });
}

function paragraph(
  children: TextRun[],
  options: {
    alignment?: (typeof AlignmentType)[keyof typeof AlignmentType];
    before?: number;
    after?: number;
    indentLeft?: number;
  } = {},
) {
  return new Paragraph({
    children,
    alignment: options.alignment,
    spacing: {
      before: options.before ?? 0,
      after: options.after ?? 0,
    },
    indent: options.indentLeft ? { left: options.indentLeft } : undefined,
  });
}

function cell(
  children: Paragraph[],
  options: {
    width?: number;
    borders?: typeof tableBorders | typeof noBorders;
    verticalAlign?: (typeof VerticalAlignTable)[keyof typeof VerticalAlignTable];
    shading?: string;
    columnSpan?: number;
  } = {},
) {
  return new TableCell({
    children,
    width: options.width
      ? { size: options.width, type: WidthType.PERCENTAGE }
      : undefined,
    borders: options.borders ?? tableBorders,
    verticalAlign: options.verticalAlign ?? VerticalAlignTable.TOP,
    shading: options.shading ? { fill: options.shading } : undefined,
    columnSpan: options.columnSpan,
    margins: {
      top: 80,
      bottom: 80,
      left: 90,
      right: 90,
    },
  });
}

function formatQuestionLabel(questionNumber: number, subpart: string) {
  return `${questionNumber}(${subpart})`;
}

function normalizeQuestionLabel(label: string | undefined, fallback: string) {
  const text = (label || fallback).trim();
  const match = text.match(/^(\d+)([a-z])$/i);
  return match ? formatQuestionLabel(Number(match[1]), match[2].toLowerCase()) : text;
}

function buildQuestionBlueprint(maxMarks: number): BlueprintSlot[] {
  if (maxMarks <= 50) {
    const patterns = [
      ...Array.from({ length: 4 }, () => [5, 5] as const),
      ...Array.from({ length: 6 }, () => [4, 6] as const),
    ];

    return patterns.flatMap(([partA, partB], index) => [
      {
        questionNumber: index + 1,
        subpart: "a",
        label: formatQuestionLabel(index + 1, "a"),
        marks: partA,
        moduleNumber: Math.floor(index / 2) + 1,
      },
      {
        questionNumber: index + 1,
        subpart: "b",
        label: formatQuestionLabel(index + 1, "b"),
        marks: partB,
        moduleNumber: Math.floor(index / 2) + 1,
      },
    ]);
  }

  const rows = [
    [1, "a", 6, 1],
    [1, "b", 6, 1],
    [1, "c", 8, 1],
    [2, "a", 6, 1],
    [2, "b", 6, 1],
    [2, "c", 8, 1],
    [3, "a", 5, 2],
    [3, "b", 8, 2],
    [3, "c", 7, 2],
    [4, "a", 5, 2],
    [4, "b", 8, 2],
    [4, "c", 7, 2],
    [5, "a", 5, 3],
    [5, "b", 8, 3],
    [5, "c", 7, 3],
    [6, "a", 5, 3],
    [6, "b", 8, 3],
    [6, "c", 7, 3],
    [7, "a", 10, 4],
    [7, "b", 10, 4],
    [8, "a", 10, 4],
    [8, "b", 10, 4],
    [9, "a", 10, 5],
    [9, "b", 10, 5],
    [10, "a", 10, 5],
    [10, "b", 10, 5],
  ] as const;

  return rows.map(([questionNumber, subpart, marks, moduleNumber]) => ({
    questionNumber,
    subpart,
    label: formatQuestionLabel(questionNumber, subpart),
    marks,
    moduleNumber,
  }));
}

function buildPaperRows(maxMarks: number, questions: PaperQuestion[]): PaperRow[] {
  const blueprint = buildQuestionBlueprint(maxMarks);
  const rows: PaperRow[] = [];

  blueprint.forEach((slot, index) => {
    const question = questions[index];
    const previousSlot = index > 0 ? blueprint[index - 1] : null;

    if (maxMarks > 50 && (!previousSlot || previousSlot.moduleNumber !== slot.moduleNumber)) {
      rows.push({ type: "module", title: `Module - ${slot.moduleNumber}` });
    }

    if (slot.subpart === "a" && slot.questionNumber % 2 === 0) {
      rows.push({ type: "or" });
    }

    const subQuestions = (question as any)?.subQuestions as PaperRow extends any
      ? Array<{ label?: string; text: string }> | undefined
      : never;
    const hasSubQuestions = Boolean(subQuestions?.length);

    rows.push({
      type: "question",
      qno: normalizeQuestionLabel(question?.section_label, slot.label),
      text: question?.text || "",
      marks: hasSubQuestions ? "" : String(question?.custom_marks ?? slot.marks),
      co: hasSubQuestions ? "" : question?.course_outcome || "",
      rbtl: hasSubQuestions ? "" : question?.bloom_level || "",
      subQuestions,
    });
  });

  return rows;
}

function metadataTable(paper: GeneratedPaper) {
  const duration = paper.duration_minutes
    ? `${paper.duration_minutes} Minutes`
    : "";

  const rows = [
    ["Subject:", paper.subject_name || "", "Subject Code:", paper.subject_code || ""],
    ["Semester:", paper.semester || "", "Max. Marks:", paper.max_marks || ""],
    ["Batch:", paper.batch || "", "Duration:", duration],
    ["Date of IAT:", paper.exam_date || "To be announced", "Teaching Department:", paper.teaching_department || ""],
  ];

  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    layout: TableLayoutType.FIXED,
    borders: tableBorders,
    rows: [
      ...rows.map(
        (row) =>
          new TableRow({
            children: [
              cell([paragraph([tr(row[0], { bold: true })])], { width: 20 }),
              cell([paragraph([tr(row[1])])], { width: 30 }),
              cell([paragraph([tr(row[2], { bold: true })])], { width: 20 }),
              cell([paragraph([tr(row[3])])], { width: 30 }),
            ],
          }),
      ),
      new TableRow({
        children: [
          cell([paragraph([tr("RBT Levels:", { bold: true })])], { width: 20 }),
          cell(
            [paragraph([tr("L1-Remember, L2-Understand, L3-Apply, L4-Analyze, L5-Evaluate, L6-Create")])],
            { width: 80, columnSpan: 3 },
          ),
        ],
      }),
    ],
  });
}

function questionTable(paper: GeneratedPaper) {
  const rows = buildPaperRows(paper.max_marks || 50, paper.questions || []);

  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    layout: TableLayoutType.FIXED,
    borders: tableBorders,
    rows: [
      new TableRow({
        tableHeader: true,
        children: [
          cell([paragraph([tr("Q", { bold: true }), tr("\nNo", { bold: true })], { alignment: AlignmentType.CENTER })], { width: QUESTION_WIDTHS[0], verticalAlign: VerticalAlignTable.CENTER }),
          cell([paragraph([tr("Questions", { bold: true })], { alignment: AlignmentType.CENTER })], { width: QUESTION_WIDTHS[1], verticalAlign: VerticalAlignTable.CENTER }),
          cell([paragraph([tr("Marks", { bold: true })], { alignment: AlignmentType.CENTER })], { width: QUESTION_WIDTHS[2], verticalAlign: VerticalAlignTable.CENTER }),
          cell([paragraph([tr("COs", { bold: true })], { alignment: AlignmentType.CENTER })], { width: QUESTION_WIDTHS[3], verticalAlign: VerticalAlignTable.CENTER }),
          cell([paragraph([tr("RBTL", { bold: true })], { alignment: AlignmentType.CENTER })], { width: QUESTION_WIDTHS[4], verticalAlign: VerticalAlignTable.CENTER }),
        ],
      }),
      ...rows.map((row) => {
        if (row.type === "module") {
          return new TableRow({
            children: [
              cell([paragraph([tr(row.title, { bold: true })], { alignment: AlignmentType.CENTER })], {
                columnSpan: 5,
                shading: "F2F2F2",
              }),
            ],
          });
        }

        if (row.type === "or") {
          return new TableRow({
            children: [
              cell([paragraph([tr("OR", { bold: true })], { alignment: AlignmentType.CENTER })], {
                columnSpan: 5,
              }),
            ],
          });
        }

        const questionParagraphs = [
          paragraph([tr(row.text)], { after: row.subQuestions?.length ? 80 : 0 }),
          ...(row.subQuestions || []).map((item) =>
            paragraph([tr(`${item.label ? `${item.label}. ` : ""}${item.text}`)], {
              indentLeft: convertInchesToTwip(0.25),
              after: 40,
            }),
          ),
        ];

        return new TableRow({
          children: [
            cell([paragraph([tr(row.qno)], { alignment: AlignmentType.CENTER })], { width: QUESTION_WIDTHS[0] }),
            cell(questionParagraphs, { width: QUESTION_WIDTHS[1] }),
            cell([paragraph([tr(row.marks)], { alignment: AlignmentType.CENTER })], { width: QUESTION_WIDTHS[2] }),
            cell([paragraph([tr(row.co)], { alignment: AlignmentType.CENTER })], { width: QUESTION_WIDTHS[3] }),
            cell([paragraph([tr(row.rbtl)], { alignment: AlignmentType.CENTER })], { width: QUESTION_WIDTHS[4] }),
          ],
        });
      }),
    ],
  });
}

function coverageTable(title: string, label: string, values: Record<string, any> | undefined, keys: string[]) {
  return [
    paragraph([tr(title, { bold: true })], { before: 260, after: 80 }),
    new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      layout: TableLayoutType.FIXED,
      borders: tableBorders,
      rows: [
        new TableRow({
          children: [
            cell([paragraph([tr(label, { bold: true })], { alignment: AlignmentType.CENTER })], { width: 28 }),
            ...keys.map((key) =>
              cell([paragraph([tr(key, { bold: true })], { alignment: AlignmentType.CENTER })], {
                width: 72 / keys.length,
              }),
            ),
          ],
        }),
        new TableRow({
          children: [
            cell([paragraph([tr("Percentage", { bold: true })], { alignment: AlignmentType.CENTER })], { width: 28 }),
            ...keys.map((key) =>
              cell([paragraph([tr(values?.[key] ?? 0)], { alignment: AlignmentType.CENTER })], {
                width: 72 / keys.length,
              }),
            ),
          ],
        }),
      ],
    }),
  ];
}

function safeFilename(name: string) {
  return name.replace(/[\\/:*?"<>|]+/g, "_").trim() || "question_paper";
}

function base64ToUint8Array(base64: string): Uint8Array {
  const binaryString = typeof window !== "undefined" ? window.atob(base64) : Buffer.from(base64, "base64").toString("binary");
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
}

export async function exportToDocx(paper: GeneratedPaper) {
  const templateNote =
    paper.ai_config?.template_note ||
    (paper.max_marks >= 100
      ? "Answer any FIVE full questions, choosing at least ONE question from each MODULE"
      : "");
  const coDescriptions = {
    CO1: "",
    CO2: "",
    CO3: "",
    CO4: "",
    CO5: "",
    ...(paper.ai_config?.co_descriptions || {}),
  };
  const coverage = paper.coverage_stats?.percentages || {};

  const doc = new Document({
    sections: [
      {
        properties: {
          page: {
            margin: {
              top: convertInchesToTwip(0.45),
              right: convertInchesToTwip(0.45),
              bottom: convertInchesToTwip(0.5),
              left: convertInchesToTwip(0.45),
            },
          },
        },
        children: [
          new Table({
            width: { size: 100, type: WidthType.PERCENTAGE },
            layout: TableLayoutType.FIXED,
            borders: noBorders,
            rows: [
              new TableRow({
                children: [
                  cell(
                    [
                      new Paragraph({
                        children: [
                          new ImageRun({
                            data: base64ToUint8Array(DSU_LOGO_BASE64),
                            transformation: {
                              width: 60,
                              height: 60,
                            },
                            type: "jpg",
                          }),
                        ],
                        alignment: AlignmentType.CENTER,
                      }),
                    ],
                    { width: 15, borders: noBorders, verticalAlign: VerticalAlignTable.CENTER }
                  ),
                  cell(
                    [
                      paragraph([tr("Dayananda Sagar Academy of Technology & Management", { bold: true, size: 24 })], { alignment: AlignmentType.CENTER }),
                      paragraph([tr("(Autonomous Institute under VTU)", { size: SMALL_SIZE })], { alignment: AlignmentType.CENTER }),
                    ],
                    { width: 55, borders: noBorders, verticalAlign: VerticalAlignTable.CENTER }
                  ),
                  cell(
                    [
                      paragraph([tr("Affiliated to VTU", { size: SMALL_SIZE })]),
                      paragraph([
                        tr("Approved by ", { size: SMALL_SIZE }),
                        tr("AICTE", { size: SMALL_SIZE, color: "FF0000" })
                      ]),
                      paragraph([
                        tr("Accredited by ", { size: SMALL_SIZE }),
                        tr("NAAC", { size: SMALL_SIZE, color: "FF0000" }),
                        tr(" with A+ Grade", { size: SMALL_SIZE })
                      ]),
                      paragraph([
                        tr("6 Programs Accredited by ", { size: SMALL_SIZE }),
                        tr("NBA", { size: SMALL_SIZE, color: "FF0000" })
                      ]),
                      paragraph([tr("(CSE, ISE, ECE, EEE, MECH, CV)", { size: SMALL_SIZE })]),
                    ],
                    { width: 30, borders: noBorders, verticalAlign: VerticalAlignTable.CENTER }
                  ),
                ],
              }),
            ],
          }),
          paragraph([tr("_".repeat(115), { size: 14 })], { after: 120 }),
          paragraph([tr("USN:", { bold: true })], { alignment: AlignmentType.RIGHT, after: 100 }),
          paragraph([tr(`Department of ${paper.department_name || ""}`, { bold: true, size: 26 })], {
            alignment: AlignmentType.CENTER,
            after: 120,
          }),
          new Table({
            width: { size: 100, type: WidthType.PERCENTAGE },
            layout: TableLayoutType.FIXED,
            borders: tableBorders,
            rows: [
              new TableRow({
                children: [
                  cell([paragraph([tr(paper.exam_type || paper.title || "Question Paper", { bold: true })], { alignment: AlignmentType.CENTER })], {
                    columnSpan: 1,
                    verticalAlign: VerticalAlignTable.CENTER,
                  }),
                ],
              }),
            ],
          }),
          paragraph([], { after: 120 }),
          metadataTable(paper),
          paragraph([tr(paper.ai_config?.instructions || "Instruction: Answer the following questions", { italics: true })], {
            alignment: AlignmentType.CENTER,
            before: 160,
            after: 120,
          }),
          ...(templateNote
            ? [
                paragraph([tr("Note:", { bold: true })], { after: 0 }),
                paragraph([tr(templateNote, { bold: true })], { after: 120 }),
              ]
            : []),
          questionTable(paper),
          paragraph([tr("Course Outcomes (COs):  At the end of the Course, the Student will be able to:", { bold: true })], {
            alignment: AlignmentType.CENTER,
            before: 320,
            after: 80,
          }),
          new Table({
            width: { size: 100, type: WidthType.PERCENTAGE },
            layout: TableLayoutType.FIXED,
            borders: tableBorders,
            rows: ["CO1", "CO2", "CO3", "CO4", "CO5"].map(
              (co) =>
                new TableRow({
                  children: [
                    cell([paragraph([tr(co, { bold: true })], { alignment: AlignmentType.CENTER })], { width: 10 }),
                    cell([paragraph([tr(coDescriptions[co as keyof typeof coDescriptions] || "")])], { width: 90 }),
                  ],
                }),
            ),
          }),
          ...coverageTable("Percentage of CO Coverage", "Course Outcomes", coverage.co, ["CO1", "CO2", "CO3", "CO4", "CO5"]),
          ...coverageTable("Percentage of Syllabus coverage", "Modules Covered", coverage.modules, ["1", "2", "3", "4", "5"]),
          paragraph([tr("End of Question Paper", { bold: true })], {
            alignment: AlignmentType.CENTER,
            before: 320,
          }),
        ],
      },
    ],
  });

  const blob = await Packer.toBlob(doc);
  saveAs(blob, `${safeFilename(paper.title || "question_paper")}.docx`);
}
