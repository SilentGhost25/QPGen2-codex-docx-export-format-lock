import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  AlertCircle,
  ArrowLeftRight,
  CheckCircle,
  RefreshCw,
  Edit2,
  Check,
  BookOpen,
  AlertTriangle,
  Info,
  Trash2,
  Plus,
  Search,
  Sparkles,
  CheckSquare
} from "lucide-react";
import { toast } from "sonner";

interface Question {
  id: number;
  text: string;
  marks: number;
  course_outcome: string;
  bloom_level: string;
  difficulty: string;
  module_number: number;
  tags?: string[];
  source_doc_id?: number | null;
  source_documents?: string[];
  confidence?: number | null;
  match_level?: string | null;
  match_reason?: string | null;
  source_topic?: string | null;
  recommendation_score?: number;
  recommended?: boolean;
  image_path?: string | null;
  source?: string;
}


interface BlueprintSlot {
  questionNumber: number;
  subpart: string;
  label: string;
  marks: number;
  moduleNumber: number;
}

interface QuestionReviewPanelProps {
  blueprint: BlueprintSlot[];
  allocatedQuestions: Record<string, Question>;
  subjectQuestions: Question[];
  onQuestionChange: (slotLabel: string, nextQuestion: Question | null) => void;
  onQuestionTextEdit: (slotLabel: string, editedText: string) => void;
}

function calculateRecommendationScore(q: any): number {
  if (q.recommendation_score !== undefined) return q.recommendation_score;
  let score = 0.0;
  if (q.is_verified) score += 0.30;
  if (q.marks === 5 || q.marks === 10) score += 0.40;
  const bloom = (q.bloom_level || q.rbt || "").toUpperCase().trim();
  if (bloom === "L1" || bloom === "L2" || bloom === "L3") score += 0.30;
  return Math.min(1.0, score);
}

function confidenceColor(score: number): string {
  if (score >= 0.9) return "bg-emerald-500/10 text-emerald-700 border-emerald-500/20 dark:bg-emerald-950/20 dark:text-emerald-300";
  if (score >= 0.7) return "bg-sky-500/10 text-sky-700 border-sky-500/20 dark:bg-sky-950/20 dark:text-sky-300";
  if (score >= 0.5) return "bg-amber-500/10 text-amber-700 border-amber-500/20 dark:bg-amber-950/20 dark:text-amber-300";
  return "bg-red-500/10 text-red-700 border-red-500/20 dark:bg-red-950/20 dark:text-red-300";
}

export function QuestionReviewPanel({
  blueprint,
  allocatedQuestions,
  subjectQuestions,
  onQuestionChange,
  onQuestionTextEdit,
}: QuestionReviewPanelProps) {
  const [editingSlot, setEditingSlot] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [searchQueries, setSearchQueries] = useState<Record<number, string>>({});
  const [approvedSlots, setApprovedSlots] = useState<Record<string, boolean>>({});
  const [swappingSlot, setSwappingSlot] = useState<string | null>(null);

  const slotsByModule = useMemo(() => {
    const grouped: Record<number, BlueprintSlot[]> = {};
    blueprint.forEach((slot) => {
      if (!grouped[slot.moduleNumber]) {
        grouped[slot.moduleNumber] = [];
      }
      grouped[slot.moduleNumber].push(slot);
    });
    return grouped;
  }, [blueprint]);

  const handleEditStart = (slotLabel: string, currentText: string) => {
    setEditingSlot(slotLabel);
    setEditText(currentText);
  };

  const handleEditSave = (slotLabel: string) => {
    if (!editText.trim()) {
      toast.error("Question text cannot be empty");
      return;
    }
    onQuestionTextEdit(slotLabel, editText.trim());
    setEditingSlot(null);
    toast.success("Question updated successfully!");
  };

  const toggleApproved = (slotLabel: string) => {
    setApprovedSlots((prev) => ({
      ...prev,
      [slotLabel]: !prev[slotLabel],
    }));
  };

  const handleAddQuestionToSlot = (moduleNum: number, question: Question) => {
    // Find all slots in this module matching this question's marks
    const moduleSlots = slotsByModule[moduleNum] || [];
    const matchingSlots = moduleSlots.filter((slot) => slot.marks === question.marks);

    if (matchingSlots.length === 0) {
      toast.error(`No ${question.marks}M slots configured in Module ${moduleNum} for this paper blueprint.`);
      return;
    }

    // First try: Find an empty slot
    const emptySlot = matchingSlots.find((slot) => !allocatedQuestions[slot.label]);
    if (emptySlot) {
      onQuestionChange(emptySlot.label, question);
      toast.success(`Allocated to Slot ${emptySlot.label} (${question.marks}M)!`);
      return;
    }

    // Second try: Replace the first slot of the same marks
    const firstSlot = matchingSlots[0];
    onQuestionChange(firstSlot.label, question);
    toast.success(`Swapped Slot ${firstSlot.label} with this curated question!`);
  };

  const handleClearSlot = (slotLabel: string) => {
    onQuestionChange(slotLabel, null);
    toast.info(`Slot ${slotLabel} cleared.`);
  };

  const getSwapCandidates = (slot: BlueprintSlot, currentQuestionId?: number) => {
    return subjectQuestions.filter(
      (q) =>
        q.module_number === slot.moduleNumber &&
        q.marks === slot.marks &&
        q.id !== currentQuestionId
    );
  };

  const handleShuffle = (slot: BlueprintSlot, currentQuestion?: Question) => {
    const candidates = getSwapCandidates(slot, currentQuestion?.id);
    if (candidates.length === 0) {
      toast.warning("No other matching questions available in the bank for this module and marks.");
      return;
    }
    const randomQuestion = candidates[Math.floor(Math.random() * candidates.length)];
    onQuestionChange(slot.label, randomQuestion);
    toast.success(`Slot ${slot.label} shuffled with a new question!`);
  };

  return (
    <div className="space-y-12">
      <div className="flex flex-col gap-2 border-b pb-5">
        <h2 className="text-2xl font-extrabold tracking-tight font-serif text-foreground flex items-center gap-2.5">
          <BookOpen className="h-6 w-6 text-primary" /> Curated Syllabus Review Stage
        </h2>
        <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
          Inspect, refine, swap, and curate high-fidelity questions directly within each syllabus module. Maintain human curation and export stunning, VTU-grade exam papers.
        </p>
      </div>

      {Object.entries(slotsByModule).map(([moduleNumStr, slots]) => {
        const moduleNum = parseInt(moduleNumStr);
        const searchQuery = searchQueries[moduleNum] || "";

        // Get candidate questions for this module
        const candidates = useMemo(() => {
          return subjectQuestions
            .filter((q) => q.module_number === moduleNum)
            .map((q) => ({
              ...q,
              calculatedScore: calculateRecommendationScore(q)
            }))
            .sort((a, b) => b.calculatedScore - a.calculatedScore);
        }, [subjectQuestions, moduleNum]);

        // Filter candidates by search query
        const filteredCandidates = useMemo(() => {
          if (!searchQuery.trim()) return candidates;
          const lowerQuery = searchQuery.toLowerCase();
          return candidates.filter(
            (c) =>
              c.text.toLowerCase().includes(lowerQuery) ||
              (c.source_topic || "").toLowerCase().includes(lowerQuery) ||
              (c.tags || []).some((t) => t.toLowerCase().includes(lowerQuery))
          );
        }, [candidates, searchQuery]);

        return (
          <div key={moduleNum} className="space-y-6 bg-card rounded-2xl border border-muted/50 p-6 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-primary/40 to-primary" />
            
            <div className="flex flex-wrap items-center justify-between gap-4 border-b pb-4">
              <div className="space-y-1">
                <span className="text-lg font-extrabold text-foreground font-serif tracking-tight flex items-center gap-2">
                  Module {moduleNum} Focus Curation
                </span>
                <p className="text-xs text-muted-foreground">
                  Contains {slots.length} blueprint slots • {candidates.length} pre-generated candidates in library.
                </p>
              </div>
            </div>

            {/* Part 1: Selected Questions / Slots */}
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider">
                Selected Questions in Paper
              </h3>
              
              <div className="grid gap-4">
                {slots.map((slot) => {
                  const q = allocatedQuestions[slot.label];
                  const isEditing = editingSlot === slot.label;
                  const isSwapping = swappingSlot === slot.label;
                  const isApproved = !!approvedSlots[slot.label];
                  const swapCandidates = getSwapCandidates(slot, q?.id);
                  const confidence = q ? (q.confidence ?? calculateRecommendationScore(q)) : 0;
                  const topic = q?.source_topic || (
                    q?.tags?.find(t => t.startsWith("topic:"))?.substring(6).trim() || "Module Concept"
                  );

                  if (!q) {
                    return (
                      <Card
                        key={slot.label}
                        className="border-dashed border-2 border-amber-500/30 bg-amber-500/5 hover:bg-amber-500/10 transition-all p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 rounded-xl"
                      >
                        <div className="flex items-start gap-3.5">
                          <div className="p-2.5 bg-amber-500/10 rounded-lg text-amber-600 dark:text-amber-400 shrink-0">
                            <AlertCircle className="h-5 w-5" />
                          </div>
                          <div>
                            <p className="font-bold text-amber-700 dark:text-amber-400">
                              Blueprint Slot {slot.label} Unallocated
                            </p>
                            <p className="text-xs text-muted-foreground mt-0.5 max-w-xl">
                              No matching question allocated for Module {slot.moduleNumber} ({slot.marks} Marks). Curate a question from the Candidate Library below to fill this slot.
                            </p>
                          </div>
                        </div>
                        <div className="flex gap-2 w-full md:w-auto shrink-0 justify-end">
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-xs font-semibold h-9"
                            onClick={() => {
                              // Find candidates matching this marks
                              const matching = candidates.filter((c) => c.marks === slot.marks);
                              if (matching.length > 0) {
                                onQuestionChange(slot.label, matching[0]);
                                toast.success(`Auto-assigned best candidate to Slot ${slot.label}!`);
                              } else {
                                toast.error("No questions of this mark found in the module library.");
                              }
                            }}
                          >
                            <Sparkles className="mr-1.5 h-3.5 w-3.5 text-primary" /> Auto-Assign
                          </Button>
                        </div>
                      </Card>
                    );
                  }

                  return (
                    <Card
                      key={slot.label}
                      className={`border border-muted/70 hover:border-primary/50 transition-all duration-300 shadow-sm relative overflow-hidden rounded-xl ${
                        isApproved ? "bg-emerald-50/10 border-emerald-300/60 dark:bg-emerald-950/5 dark:border-emerald-800/60" : ""
                      }`}
                    >
                      <div className={`absolute top-0 left-0 w-1.5 h-full ${
                        isApproved ? "bg-emerald-500" : "bg-primary/80"
                      }`} />

                      <CardHeader className="py-3 px-5 flex flex-row items-center justify-between border-b bg-muted/10 gap-3">
                        <div className="flex flex-wrap items-center gap-3">
                          <Badge className="bg-primary hover:bg-primary font-extrabold text-[11px] px-2.5 py-0.5 rounded-md">
                            Slot {slot.label}
                          </Badge>
                          <span className="text-xs font-mono font-bold text-muted-foreground bg-muted/20 px-2 py-0.5 rounded-md">
                            {slot.marks} Marks
                          </span>
                          <Badge variant="outline" className={`text-[10px] font-bold py-0.5 border ${confidenceColor(confidence)}`}>
                            <Sparkles className="mr-1 h-2.5 w-2.5" /> Recommended: {Math.round(confidence * 100)}%
                          </Badge>
                        </div>

                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            variant={isApproved ? "default" : "outline"}
                            className={`h-7 px-2.5 text-xs font-semibold ${
                              isApproved ? "bg-emerald-600 hover:bg-emerald-700 text-white" : ""
                            }`}
                            onClick={() => toggleApproved(slot.label)}
                          >
                            {isApproved ? (
                              <>
                                <CheckCircle className="mr-1 h-3.5 w-3.5" /> Verified
                              </>
                            ) : (
                              <>
                                <Check className="mr-1 h-3.5 w-3.5" /> Verify
                              </>
                            )}
                          </Button>
                        </div>
                      </CardHeader>

                      <CardContent className="py-4 px-5 space-y-4">
                        {isEditing ? (
                          <div className="space-y-3">
                            <Label className="text-xs font-bold text-primary">Edit Question Content</Label>
                            <Textarea
                              value={editText}
                              onChange={(e) => setEditText(e.target.value)}
                              rows={3}
                              className="text-sm font-medium leading-relaxed leading-normal rounded-lg border-muted/80 focus:border-primary"
                            />
                            <div className="flex gap-2 justify-end">
                              <Button size="sm" variant="outline" onClick={() => setEditingSlot(null)}>
                                Cancel
                              </Button>
                              <Button size="sm" onClick={() => handleEditSave(slot.label)}>
                                Save Changes
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            <p className="text-sm font-semibold leading-relaxed text-foreground select-all leading-normal">
                              {q.text}
                            </p>

                            {q.image_path && (
                              <div className="mt-3 overflow-hidden rounded-lg border bg-muted/40 max-w-xs">
                                <div className="px-3 py-1 bg-muted/70 text-[9px] font-bold text-muted-foreground flex items-center gap-1 border-b">
                                  <span>🖼 Image Reference Diagram</span>
                                </div>
                                <img
                                  src={q.image_path.startsWith("http") ? q.image_path : `${import.meta.env.VITE_API_URL || ""}${q.image_path}`}
                                  alt="Diagram"
                                  className="max-h-36 object-contain mx-auto p-2"
                                />
                              </div>
                            )}

                            <div className="flex flex-wrap gap-2 pt-1">
                              <Badge variant="outline" className="text-[10px] py-0 px-2 font-bold font-mono">
                                CO: {q.course_outcome || (q as any).co}
                              </Badge>
                              <Badge variant="outline" className="text-[10px] py-0 px-2 font-bold font-mono">
                                RBT: {q.bloom_level || (q as any).rbt}
                              </Badge>
                              <Badge variant="outline" className="text-[10px] py-0 px-2 font-bold font-mono uppercase">
                                Diff: {q.difficulty}
                              </Badge>
                              <Badge variant="secondary" className="text-[10px] py-0 px-2 font-semibold bg-muted/40">
                                Topic: {topic}
                              </Badge>
                              {q.source_documents && q.source_documents.length > 0 && (
                                <Badge variant="secondary" className="text-[10px] py-0 px-2 font-semibold bg-sky-50 dark:bg-sky-950/20 text-sky-700 border border-sky-200">
                                  Source: {q.source_documents[0]}
                                </Badge>
                              )}
                            </div>
                          </div>
                        )}

                        {isSwapping && (
                          <div className="border-t pt-3 space-y-3 animate-fadeIn">
                            <Label className="text-xs font-bold text-primary flex items-center gap-1.5">
                              <ArrowLeftRight className="h-4 w-4" /> Swap with other Matching Question
                            </Label>
                            {swapCandidates.length === 0 ? (
                              <p className="text-xs text-muted-foreground bg-muted/30 p-2 rounded">
                                No other {slot.marks}M questions exist in the bank for Module {slot.moduleNumber}.
                              </p>
                            ) : (
                              <div className="grid gap-2 max-h-40 overflow-y-auto rounded border p-2 bg-muted/15">
                                {swapCandidates.map((cand) => (
                                  <button
                                    key={cand.id}
                                    className="w-full text-left p-2 hover:bg-primary/5 rounded border text-xs leading-relaxed font-medium transition-colors hover:border-primary/50"
                                    onClick={() => {
                                      onQuestionChange(slot.label, cand);
                                      setSwappingSlot(null);
                                      toast.success(`Slot ${slot.label} swapped!`);
                                    }}
                                  >
                                    {cand.text}
                                    <div className="text-[9px] text-muted-foreground mt-1 flex gap-2">
                                      <span>CO: {cand.course_outcome}</span>
                                      <span>RBT: {cand.bloom_level}</span>
                                      <span>Diff: {cand.difficulty}</span>
                                    </div>
                                  </button>
                                ))}
                              </div>
                            )}
                            <Button size="sm" variant="ghost" onClick={() => setSwappingSlot(null)}>
                              Cancel Swap
                            </Button>
                          </div>
                        )}

                        {!isEditing && !isSwapping && (
                          <div className="flex gap-2 pt-2 justify-end border-t border-muted/50">
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-xs text-muted-foreground hover:text-foreground h-8"
                              onClick={() => handleEditStart(slot.label, q.text)}
                            >
                              <Edit2 className="mr-1.5 h-3 w-3" /> Edit Text
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-xs text-muted-foreground hover:text-foreground h-8"
                              onClick={() => handleShuffle(slot, q)}
                              disabled={swapCandidates.length === 0}
                            >
                              <RefreshCw className="mr-1.5 h-3 w-3" /> Shuffle
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-xs text-muted-foreground hover:text-foreground h-8"
                              onClick={() => setSwappingSlot(slot.label)}
                              disabled={swapCandidates.length === 0}
                            >
                              <ArrowLeftRight className="mr-1.5 h-3 w-3" /> Swap / Replace
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-xs text-red-600 hover:bg-red-500/10 hover:text-red-700 dark:hover:bg-red-950/20 dark:hover:text-red-400 h-8"
                              onClick={() => handleClearSlot(slot.label)}
                            >
                              <Trash2 className="mr-1.5 h-3 w-3" /> Remove
                            </Button>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>

            {/* Part 2: Candidate Library for the Module */}
            <div className="space-y-4 border-t pt-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <h3 className="text-sm font-bold text-primary uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="h-4 w-4" /> Module Candidate Questions Library
                </h3>

                <div className="relative w-full sm:w-64">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search candidate questions..."
                    value={searchQuery}
                    onChange={(e) => setSearchQueries((prev) => ({ ...prev, [moduleNum]: e.target.value }))}
                    className="pl-9 text-xs h-9 bg-muted/20 border-muted/80 rounded-lg"
                  />
                </div>
              </div>

              {filteredCandidates.length === 0 ? (
                <div className="rounded-xl border border-dashed p-6 text-center text-xs text-muted-foreground">
                  No matching questions in library for Module {moduleNum}. Refine search query or upload more resources.
                </div>
              ) : (
                <div className="grid gap-3 max-h-80 overflow-y-auto p-1 pr-2 rounded-xl">
                  {filteredCandidates.map((question) => {
                    const co = question.course_outcome || (question as any).co || "CO1";
                    const bloom = question.bloom_level || (question as any).rbt || "L2";
                    const topic = question.source_topic || question.tags?.[0] || "Module Concept";
                    const isAllocated = Object.values(allocatedQuestions).some(
                      (aq) => aq?.id === question.id
                    );

                    return (
                      <Card
                        key={question.id}
                        className={`border border-muted/50 p-4 transition-all hover:shadow-md hover:border-primary/40 rounded-xl ${
                          isAllocated ? "bg-primary/5 border-primary/20" : "bg-muted/5"
                        }`}
                      >
                        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                          <div className="space-y-2 flex-1">
                            <p className="text-sm font-medium leading-relaxed leading-normal text-foreground">
                              {question.text}
                            </p>

                            {question.image_path && (
                              <div className="mt-2 overflow-hidden rounded-lg border bg-muted/40 max-w-xs">
                                <div className="px-3 py-1 bg-muted/70 text-[9px] font-bold text-muted-foreground flex items-center gap-1 border-b">
                                  <span>🖼 Image Reference Diagram</span>
                                </div>
                                <img
                                  src={question.image_path.startsWith("http") ? question.image_path : `${import.meta.env.VITE_API_URL || ""}${question.image_path}`}
                                  alt="Diagram"
                                  className="max-h-24 object-contain mx-auto p-1.5"
                                />
                              </div>
                            )}

                            <div className="flex flex-wrap gap-2">
                              <Badge className="bg-primary/10 text-primary hover:bg-primary/10 border-0 font-extrabold text-[10px] py-0 px-2">
                                {question.marks}M
                              </Badge>
                              <Badge variant="outline" className="text-[10px] py-0 px-2 font-bold font-mono">
                                CO: {co}
                              </Badge>
                              <Badge variant="outline" className="text-[10px] py-0 px-2 font-bold font-mono">
                                RBT: {bloom}
                              </Badge>
                              <Badge variant="secondary" className="text-[10px] py-0 px-2 font-semibold bg-muted/40">
                                Topic: {topic}
                              </Badge>
                              {question.calculatedScore !== undefined && (
                                <Badge variant="outline" className={`text-[9px] font-bold border ${confidenceColor(question.calculatedScore)}`}>
                                  Score: {Math.round(question.calculatedScore * 100)}%
                                </Badge>
                              )}
                              {question.source && (
                                <Badge variant="secondary" className="text-[9px] py-0 px-2 font-semibold bg-sky-50 dark:bg-sky-950/20 text-sky-700 border border-sky-200">
                                  Source: {question.source}
                                </Badge>
                              )}
                            </div>
                          </div>

                          <div className="shrink-0 w-full md:w-auto flex justify-end">
                            <Button
                              size="sm"
                              className={`h-8 font-semibold text-xs px-3 rounded-lg ${
                                isAllocated ? "bg-muted text-muted-foreground hover:bg-muted" : "bg-primary hover:bg-primary/95 text-primary-foreground"
                              }`}
                              disabled={isAllocated}
                              onClick={() => handleAddQuestionToSlot(moduleNum, question)}
                            >
                              {isAllocated ? (
                                <>
                                  <CheckSquare className="mr-1.5 h-3.5 w-3.5" /> Allocated
                                </>
                              ) : (
                                <>
                                  <Plus className="mr-1.5 h-3.5 w-3.5" /> Add to Paper
                                </>
                              )}
                            </Button>
                          </div>
                        </div>
                      </Card>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
