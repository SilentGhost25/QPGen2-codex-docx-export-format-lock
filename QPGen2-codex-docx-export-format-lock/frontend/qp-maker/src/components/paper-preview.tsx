import type { GeneratedPaper, PaperQuestion } from "@/lib/ai-api";

interface PaperPreviewProps {
  formData?: {
    examType?: string;
    department?: string;
    subjectName?: string;
    subjectCode?: string;
    semester?: string;
    maxMarks?: number;
    batch?: string;
    duration?: string;
    dateOfIat?: string;
    teachingDept?: string;
    instructions?: string;
    coDescriptions?: Record<string, string>;
  };
  questions: PaperQuestion[];
  generatedPaper?: GeneratedPaper | null;
}

const DEFAULT_COS = {
  CO1: "",
  CO2: "",
  CO3: "",
  CO4: "",
  CO5: "",
};

function formatQuestionLabel(questionNumber: number, subpart: string) {
  return `${questionNumber}${subpart}`;
}

function normalizeQuestionLabel(label: string | undefined, fallback: string) {
  const text = (label || fallback).trim();
  const match = text.match(/^(\d+)([a-z])$/i);
  return match ? formatQuestionLabel(Number(match[1]), match[2].toLowerCase()) : text;
}

type PaperRow =
  | { type: "module"; title: string; key: string }
  | { type: "or"; key: string }
  | {
      type: "question";
      key: string;
      qno: string;
      text: string;
      marks: number;
      co: string;
      rbtl: string;
    };

function buildPercentageMap(
  values: Record<string, any> | undefined,
  keys: string[],
) {
  return Object.fromEntries(keys.map((key) => [key, values?.[key] ?? 0]));
}

function normalizeQuestions(questions: PaperQuestion[], maxMarks: number): PaperRow[] {
  const rows: PaperRow[] = [];
  let currentModule = -1;
  let currentBaseQuestion = -1;

  questions.forEach((q, index) => {
    const label = (q.section_label || "").trim();
    const match = label.match(/^(\d+)[(]?([a-z])?[)]?$/i);
    let qNum = -1;
    let subpart = "";
    if (match) {
      qNum = parseInt(match[1]);
      subpart = match[2]?.toLowerCase() || "";
    }
    
    // Module logic
    if (qNum > 0) {
      const mod = Math.floor((qNum - 1) / 2) + 1;
      if (mod !== currentModule) {
        rows.push({ type: "module", title: `Module - ${mod}`, key: `module-${mod}` });
        currentModule = mod;
      }
    }

    // OR logic
    if (qNum > 0 && qNum % 2 === 0 && qNum !== currentBaseQuestion) {
      if (currentBaseQuestion !== -1) {
        rows.push({ type: "or", key: `or-${qNum}` });
      }
    }
    if (qNum > 0) {
      currentBaseQuestion = qNum;
    }

    rows.push({
      type: "question",
      key: `question-${label || index}-${rows.length}`,
      qno: normalizeQuestionLabel(label, label),
      text: q.text || "",
      marks: q.custom_marks || 0,
      co: q.course_outcome || "",
      rbtl: q.bloom_level || "",
    });
  });

  return rows;
}

export function PaperPreview({
  formData,
  questions,
  generatedPaper,
}: PaperPreviewProps) {
  const paperConfig = generatedPaper?.ai_config ?? {};
  const coverage = generatedPaper?.coverage_stats ?? {};
  const coPercentages = buildPercentageMap(coverage?.percentages?.co, [
    "CO1",
    "CO2",
    "CO3",
    "CO4",
    "CO5",
  ]);
  const modulePercentages = buildPercentageMap(coverage?.percentages?.modules, [
    "1",
    "2",
    "3",
    "4",
    "5",
  ]);

  const defaults = {
    examType:
      generatedPaper?.exam_type ||
      formData?.examType ||
      "First Internal Assessment Test (IAT-1)",
    department:
      generatedPaper?.department_name ||
      formData?.department ||
      "Artificial Intelligence and Machine Learning",
    subjectName:
      generatedPaper?.subject_name ||
      formData?.subjectName ||
      "Machine Learning",
    subjectCode:
      generatedPaper?.subject_code ||
      formData?.subjectCode ||
      "21AI51",
    semester:
      generatedPaper?.semester || formData?.semester || "5",
    maxMarks: generatedPaper?.max_marks ?? formData?.maxMarks ?? 50,
    batch: generatedPaper?.batch || formData?.batch || "2022-26",
    duration:
      generatedPaper?.duration_minutes
        ? `${generatedPaper.duration_minutes} Minutes`
        : formData?.duration || "90 Minutes",
    dateOfIat:
      generatedPaper?.exam_date || formData?.dateOfIat || "To be announced",
    teachingDept:
      generatedPaper?.teaching_department ||
      formData?.teachingDept ||
      "AIML",
    instructions:
      formData?.instructions ||
      paperConfig.instructions ||
      "Instruction: Answer the following questions",
    coDescriptions: {
      ...DEFAULT_COS,
      ...(paperConfig.co_descriptions ?? {}),
      ...(formData?.coDescriptions ?? {}),
    },
    templateNote:
      paperConfig.template_note ||
      ((generatedPaper?.max_marks || formData?.maxMarks || 50) >= 100
        ? "Answer any FIVE full questions, choosing at least ONE question from each MODULE"
        : ""),
  };

  const paperRows = normalizeQuestions(questions, defaults.maxMarks || 50);

  return (
    <div className="mx-auto w-full bg-white px-4 py-4 font-sans text-[11px] text-black">
      <div className="flex items-center gap-3 border-b border-black pb-3">
        <img
          src="/dsu-logo.jpg"
          alt="DSU seal"
          className="h-14 w-14 object-contain"
        />
        <div className="flex-1 border-r border-black pr-3 pl-3">
          <p className="text-[14px] font-bold text-black text-center">
            Dayananda Sagar Academy of Technology & Management
          </p>
          <p className="text-[11px] font-medium text-gray-800 text-center">(Autonomous Institute under VTU)</p>
        </div>
        <div className="min-w-[220px] text-[10px] leading-tight pl-3">
          <p>
            Affiliated to VTU
          </p>
          <p>
            Approved by <span className="text-red-600 font-medium">AICTE</span>
          </p>
          <p>
            Accredited by <span className="text-red-600 font-medium">NAAC</span> with A+ Grade
          </p>
          <p>
            6 Programs Accredited by <span className="text-red-600 font-medium">NBA</span>
          </p>
          <p>(CSE, ISE, ECE, EEE, MECH, CV)</p>
        </div>
        <img
          src="/iqac-seal.svg"
          alt="IQAC seal"
          className="h-14 w-14 object-contain"
        />
      </div>

      <div className="mt-3 flex items-center justify-end gap-2 text-[11px]">
        <span>USN:</span>
        <div className="flex gap-[2px]">
          {Array.from({ length: 10 }).map((_, index) => (
            <span key={index} className="h-6 w-6 border border-black" />
          ))}
        </div>
      </div>

      <h2 className="mt-3 text-center text-[15px] font-bold">
        Department of {defaults.department}
      </h2>

      <div className="mt-3 border border-black text-center text-[13px] font-bold">
        <div className="px-3 py-1.5">{defaults.examType}</div>
      </div>

      <table className="mt-3 w-full border-collapse text-[11px]">
        <tbody>
          <tr>
            <td className="border border-black px-2 py-1 font-bold">Subject:</td>
            <td className="border border-black px-2 py-1">{defaults.subjectName}</td>
            <td className="border border-black px-2 py-1 font-bold">Subject Code:</td>
            <td className="border border-black px-2 py-1">{defaults.subjectCode}</td>
          </tr>
          <tr>
            <td className="border border-black px-2 py-1 font-bold">Semester:</td>
            <td className="border border-black px-2 py-1">{defaults.semester}</td>
            <td className="border border-black px-2 py-1 font-bold">Max. Marks:</td>
            <td className="border border-black px-2 py-1">{defaults.maxMarks}</td>
          </tr>
          <tr>
            <td className="border border-black px-2 py-1 font-bold">Batch:</td>
            <td className="border border-black px-2 py-1">{defaults.batch}</td>
            <td className="border border-black px-2 py-1 font-bold">Duration:</td>
            <td className="border border-black px-2 py-1">{defaults.duration}</td>
          </tr>
          <tr>
            <td className="border border-black px-2 py-1 font-bold">Date of IAT:</td>
            <td className="border border-black px-2 py-1">{defaults.dateOfIat}</td>
            <td className="border border-black px-2 py-1 font-bold">
              Teaching Department:
            </td>
            <td className="border border-black px-2 py-1">{defaults.teachingDept}</td>
          </tr>
          <tr>
            <td className="border border-black px-2 py-1 font-bold">RBT Levels:</td>
            <td className="border border-black px-2 py-1" colSpan={3}>
              L1-Remember, L2-Understand, L3-Apply, L4-Analyze, L5-Evaluate, L6-Create
            </td>
          </tr>
        </tbody>
      </table>

      <p className="mt-4 text-center text-[11px] italic">{defaults.instructions}</p>
      {defaults.templateNote ? (
        <div className="mt-3 text-[11px]">
          <p className="font-bold">Note:</p>
          <p className="font-bold">{defaults.templateNote}</p>
        </div>
      ) : null}

      <table className="mt-2 w-full table-fixed border-collapse text-[11px]">
        <colgroup>
          <col className="w-[8%]" />
          <col className="w-[66%]" />
          <col className="w-[10%]" />
          <col className="w-[8%]" />
          <col className="w-[8%]" />
        </colgroup>
        <thead>
          <tr>
            <th className="break-words border border-black px-2 py-1 text-center leading-tight">
              Q<br />No
            </th>
            <th className="break-words border border-black px-2 py-1 text-center">Questions</th>
            <th className="break-words border border-black px-2 py-1 text-center">Marks</th>
            <th className="break-words border border-black px-2 py-1 text-center">COs</th>
            <th className="break-words border border-black px-2 py-1 text-center">RBTL</th>
          </tr>
        </thead>
        <tbody>
          {paperRows.map((row) => {
            if (row.type === "module") {
              return (
                <tr key={row.key} className="bg-slate-100">
                  <td colSpan={5} className="border border-black px-2 py-1 text-center font-bold">
                    {row.title}
                  </td>
                </tr>
              );
            }

            if (row.type === "or") {
              return (
                <tr key={row.key}>
                  <td colSpan={5} className="border border-black px-2 py-1 text-center font-semibold">
                    OR
                  </td>
                </tr>
              );
            }

            return (
              <tr key={row.key}>
                <td className="break-words border border-black px-2 py-1 align-top text-center">
                  {row.qno}
                </td>
                <td className="whitespace-pre-line break-words border border-black px-2 py-1 align-top">
                  {row.text}
                </td>
                <td className="break-words border border-black px-2 py-1 align-top text-center">
                  {row.marks}
                </td>
                <td className="break-words border border-black px-2 py-1 align-top text-center">
                  {row.co}
                </td>
                <td className="break-words border border-black px-2 py-1 align-top text-center">
                  {row.rbtl}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="mt-8">
        <p className="mb-1 text-center text-[11px] font-bold">
          Course Outcomes (COs):&nbsp; At the end of the Course, the Student will be able to:
        </p>
        <table className="w-full border-collapse text-[11px]">
          <tbody>
            {["CO1", "CO2", "CO3", "CO4", "CO5"].map((co) => (
              <tr key={co}>
                <td className="w-12 border border-black px-2 py-1 font-bold">{co}</td>
                <td className="border border-black px-2 py-1">
                  {defaults.coDescriptions[co] || ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
