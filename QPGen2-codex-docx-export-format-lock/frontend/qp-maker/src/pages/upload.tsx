/**
 * Upload Center — World-class academic upload workflow.
 *
 * Features:
 * - Drag & drop / multi-file upload
 * - Document type selection
 * - Subject association
 * - Real-time processing pipeline visualization
 * - File status & confidence indicators
 */
import { useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload,
  FileText,
  Image,
  Presentation,
  File,
  X,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  CloudUpload,
  FolderOpen,
  BookOpen,
  Trash2,
  RefreshCw,
  Plus,
  Filter,
  Sigma,
  BarChart3,
  Table2,
  Eye,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { ProcessingTimeline, AIConfidenceBadge, AcademicEmptyState } from "@/components/academic";
import { StructuredDocumentPreview } from "@/components/academic/StructuredDocumentPreview";
import {
  useAcademicDocuments,
  useUploadAcademicDocument,
  useDeleteAcademicDocument,
  type DocumentType,
  type AcademicDocument,
} from "@/lib/academic-api";
import { useSubjects, useCreateSubject, useDepartments } from "@/lib/ai-api";
import { toast } from "sonner";

/* ------------------------------------------------------------------ */
/*  File type helpers                                                   */
/* ------------------------------------------------------------------ */

const FILE_ICONS: Record<string, typeof FileText> = {
  pdf: FileText,
  docx: FileText,
  pptx: Presentation,
  png: Image,
  jpg: Image,
  jpeg: Image,
  txt: File,
  md: File,
};

const DOC_TYPE_OPTIONS: { value: DocumentType; label: string; icon: typeof FileText }[] = [
  { value: "notes", label: "Lecture Notes", icon: BookOpen },
  { value: "question_bank", label: "Question Bank", icon: FileText },
  { value: "previous_paper", label: "Previous Paper", icon: File },
  { value: "syllabus", label: "Syllabus", icon: FolderOpen },
  { value: "lab_manual", label: "Lab Manual", icon: File },
  { value: "ppt", label: "Presentation", icon: Presentation },
];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* ------------------------------------------------------------------ */
/*  Upload queue item                                                  */
/* ------------------------------------------------------------------ */

interface QueueItem {
  id: string;
  file: File;
  documentType: DocumentType;
  status: "queued" | "uploading" | "done" | "error";
  result?: AcademicDocument;
  error?: string;
}

/* ------------------------------------------------------------------ */
/*  Upload Center Page                                                 */
/* ------------------------------------------------------------------ */

export default function UploadCenter() {
  const { data: subjects } = useSubjects();
  const [selectedSubject, setSelectedSubject] = useState<number | undefined>();
  const [docType, setDocType] = useState<DocumentType>("notes");
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: departments } = useDepartments();
  const { data: existingDocs, isLoading: loadingDocs } = useAcademicDocuments(selectedSubject);
  const uploadMutation = useUploadAcademicDocument();
  const deleteMutation = useDeleteAcademicDocument();
  const createSubjectMutation = useCreateSubject();
  const [expandedDocId, setExpandedDocId] = useState<number | null>(null);

  const [isCreateSubjectOpen, setIsCreateSubjectOpen] = useState(false);
  const [newSubjectData, setNewSubjectData] = useState({ name: "", code: "", department_id: 1, semester: 1 });

  const handleCreateSubject = async () => {
    if (!newSubjectData.name || !newSubjectData.code) {
      toast.error("Subject name and code are required");
      return;
    }
    try {
      const res = await createSubjectMutation.mutateAsync(newSubjectData);
      toast.success("Subject created successfully!");
      setIsCreateSubjectOpen(false);
      setSelectedSubject(res.id);
      setNewSubjectData({ name: "", code: "", department_id: 1, semester: 1 });
    } catch (err: any) {
      toast.error("Failed to create subject: " + err.message);
    }
  };

  // ---- File handling ----
  const addFiles = useCallback(
    (files: FileList | File[]) => {
      const items: QueueItem[] = Array.from(files).map((file) => ({
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        file,
        documentType: docType,
        status: "queued" as const,
      }));
      setQueue((prev) => [...prev, ...items]);
    },
    [docType]
  );

  const removeFromQueue = (id: string) => {
    setQueue((prev) => prev.filter((q) => q.id !== id));
  };

  const processQueue = async () => {
    if (!selectedSubject) {
      toast.error("Please select a subject first.");
      return;
    }
    const pending = queue.filter((q) => q.status === "queued");
    for (const item of pending) {
      setQueue((prev) => prev.map((q) => (q.id === item.id ? { ...q, status: "uploading" } : q)));
      try {
        const result = await uploadMutation.mutateAsync({
          subjectId: selectedSubject,
          file: item.file,
          documentType: item.documentType,
        });
        setQueue((prev) => prev.map((q) => (q.id === item.id ? { ...q, status: "done", result } : q)));
        toast.success(`${item.file.name} processed — ${result.total_chunks} chunks created`);
      } catch (err: any) {
        setQueue((prev) => prev.map((q) => (q.id === item.id ? { ...q, status: "error", error: err.message } : q)));
        toast.error(`Failed: ${item.file.name}`);
      }
    }
  };

  // ---- Drag & Drop ----
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragIn = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragOut = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
    },
    [addFiles]
  );

  const queuedCount = queue.filter((q) => q.status === "queued").length;
  const doneCount = queue.filter((q) => q.status === "done").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground tracking-tight">Upload Center</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Upload academic materials for AI-powered chunking and indexing
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select
            value={selectedSubject?.toString() ?? ""}
            onValueChange={(v) => setSelectedSubject(Number(v))}
          >
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Select Subject" />
            </SelectTrigger>
            <SelectContent>
              {subjects?.map((s: any) => (
                <SelectItem key={s.id} value={s.id.toString()}>
                  {s.name} ({s.code})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" size="icon" onClick={() => setIsCreateSubjectOpen(true)} title="Add New Subject">
            <Plus className="h-4 w-4" />
          </Button>
          
          <Dialog open={isCreateSubjectOpen} onOpenChange={setIsCreateSubjectOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add New Subject</DialogTitle>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="name">Subject Name</Label>
                  <Input id="name" value={newSubjectData.name} onChange={(e) => setNewSubjectData({...newSubjectData, name: e.target.value})} placeholder="e.g. Machine Learning" />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="code">Subject Code</Label>
                  <Input id="code" value={newSubjectData.code} onChange={(e) => setNewSubjectData({...newSubjectData, code: e.target.value})} placeholder="e.g. 21AI51" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label htmlFor="dept">Department</Label>
                    <Select
                      value={newSubjectData.department_id.toString()}
                      onValueChange={(v) => setNewSubjectData({...newSubjectData, department_id: parseInt(v)})}
                    >
                      <SelectTrigger id="dept">
                        <SelectValue placeholder="Select department" />
                      </SelectTrigger>
                      <SelectContent>
                        {departments?.map((d: any) => (
                          <SelectItem key={d.id} value={d.id.toString()}>{d.name}</SelectItem>
                        )) ?? <SelectItem value="1">Default Department</SelectItem>}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="sem">Semester</Label>
                    <Input id="sem" type="number" value={newSubjectData.semester} onChange={(e) => setNewSubjectData({...newSubjectData, semester: parseInt(e.target.value) || 1})} />
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsCreateSubjectOpen(false)}>Cancel</Button>
                <Button onClick={handleCreateSubject} disabled={createSubjectMutation.isPending}>
                  {createSubjectMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Create Subject
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Select value={docType} onValueChange={(v) => setDocType(v as DocumentType)}>
            <SelectTrigger className="w-[170px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DOC_TYPE_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  <span className="flex items-center gap-2">
                    <opt.icon className="h-3.5 w-3.5" />
                    {opt.label}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid lg:grid-cols-5 gap-6">
        {/* ---- Left: Upload Zone ---- */}
        <div className="lg:col-span-3 space-y-5">
          {/* Dropzone */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            onDragEnter={handleDragIn}
            onDragLeave={handleDragOut}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={cn(
              "relative rounded-2xl border-2 border-dashed transition-all duration-200 cursor-pointer",
              isDragging
                ? "border-primary bg-primary/5 scale-[1.01]"
                : "border-border/60 hover:border-primary/40 hover:bg-muted/30"
            )}
            onClick={() => inputRef.current?.click()}
          >
            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".pdf,.docx,.pptx,.txt,.md,.png,.jpg,.jpeg,.gif,.webp"
              className="hidden"
              onChange={(e) => e.target.files && addFiles(e.target.files)}
            />
            <div className="flex flex-col items-center justify-center py-14 px-6 text-center">
              <motion.div
                className={cn(
                  "rounded-2xl p-4 mb-4 transition-colors",
                  isDragging ? "bg-primary/15" : "bg-muted/50"
                )}
                animate={isDragging ? { scale: 1.1 } : { scale: 1 }}
              >
                <CloudUpload className={cn("h-10 w-10", isDragging ? "text-primary" : "text-muted-foreground/50")} />
              </motion.div>
              <h3 className="text-lg font-semibold text-foreground mb-1">
                {isDragging ? "Drop files here" : "Drag & drop academic files"}
              </h3>
              <p className="text-sm text-muted-foreground mb-4">
                PDF, DOCX, PPTX, Images — up to 50MB each
              </p>
              <Button variant="outline" size="sm" className="pointer-events-none">
                <Plus className="h-4 w-4 mr-2" />
                Browse Files
              </Button>
            </div>
          </motion.div>

          {/* Upload Queue */}
          <AnimatePresence>
            {queue.length > 0 && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
              >
                <Card className="border-border/60">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base font-semibold">
                        Upload Queue
                        <Badge variant="secondary" className="ml-2 text-[10px]">
                          {queuedCount} pending
                        </Badge>
                      </CardTitle>
                      <Button
                        size="sm"
                        onClick={processQueue}
                        disabled={!queuedCount || !selectedSubject || uploadMutation.isPending}
                      >
                        {uploadMutation.isPending ? (
                          <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Processing...</>
                        ) : (
                          <><Upload className="h-4 w-4 mr-2" />Process All</>
                        )}
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {queue.map((item) => {
                      const ext = item.file.name.split(".").pop()?.toLowerCase() ?? "";
                      const Icon = FILE_ICONS[ext] ?? File;
                      return (
                        <motion.div
                          key={item.id}
                          initial={{ opacity: 0, x: -8 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: 8 }}
                          className="flex items-center gap-3 rounded-lg border border-border/40 p-3"
                        >
                          <div className="h-9 w-9 rounded-lg bg-muted flex items-center justify-center shrink-0">
                            <Icon className="h-4 w-4 text-muted-foreground" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-foreground truncate">{item.file.name}</p>
                            <p className="text-[11px] text-muted-foreground">
                              {formatFileSize(item.file.size)} · {item.documentType.replace(/_/g, " ")}
                            </p>
                          </div>
                          {item.status === "uploading" && <Loader2 className="h-4 w-4 text-primary animate-spin" />}
                          {item.status === "done" && (
                            <div className="flex items-center gap-2">
                              <span className="text-[11px] text-emerald-600 font-medium">
                                {item.result?.processing_status === "completed"
                                  ? `${item.result?.total_chunks} chunks`
                                  : "Queued"}
                              </span>
                              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                            </div>
                          )}
                          {item.status === "error" && (
                            <AlertTriangle className="h-4 w-4 text-red-500" />
                          )}
                          {item.status === "queued" && (
                            <button onClick={() => removeFromQueue(item.id)} className="p-1 rounded hover:bg-muted">
                              <X className="h-3.5 w-3.5 text-muted-foreground" />
                            </button>
                          )}
                        </motion.div>
                      );
                    })}
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* ---- Right: Existing Documents ---- */}
        <div className="lg:col-span-2">
          <Card className="border-border/60">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <FolderOpen className="h-4 w-4 text-primary" />
                Processed Documents
                {existingDocs?.total != null && (
                  <Badge variant="secondary" className="ml-auto text-[10px]">{existingDocs.total}</Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loadingDocs ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-16 rounded-lg bg-muted animate-pulse" />
                  ))}
                </div>
              ) : existingDocs?.documents?.length ? (
                <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
                  {existingDocs.documents.map((doc) => (
                    <div key={doc.id} className="rounded-lg border border-border/40 overflow-hidden">
                      {/* Document row */}
                      <div className="flex items-center gap-3 p-3 group">
                        <div className="h-9 w-9 rounded-lg bg-muted flex items-center justify-center shrink-0">
                          <FileText className="h-4 w-4 text-muted-foreground" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-foreground truncate">{doc.file_name}</p>
                          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                            <ProcessingTimeline status={doc.processing_status} />
                            {/* Multimodal badges */}
                            {doc.has_equations && (
                              <span className="inline-flex items-center gap-1 text-[10px] text-violet-400 bg-violet-500/10 border border-violet-500/20 rounded px-1.5 py-0.5">
                                <Sigma className="h-2.5 w-2.5" /> {doc.equation_count}
                              </span>
                            )}
                            {doc.has_figures && (
                              <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded px-1.5 py-0.5">
                                <Eye className="h-2.5 w-2.5" /> {doc.figure_count}
                              </span>
                            )}
                            {doc.has_tables && (
                              <span className="inline-flex items-center gap-1 text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded px-1.5 py-0.5">
                                <Table2 className="h-2.5 w-2.5" /> {doc.table_count}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-[11px] text-muted-foreground tabular-nums">
                            {doc.processing_status === "completed" ? `${doc.total_chunks} chunks` : doc.processing_status}
                          </span>
                          {doc.processing_status === "completed" && (
                            <button
                              onClick={() => setExpandedDocId(expandedDocId === doc.id ? null : doc.id)}
                              className="p-1 rounded hover:bg-primary/10 transition-colors"
                              title="View structured content"
                            >
                              {expandedDocId === doc.id
                                ? <ChevronUp className="h-3.5 w-3.5 text-primary" />
                                : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
                            </button>
                          )}
                          <button
                            onClick={() => deleteMutation.mutate(doc.id)}
                            className="p-1 rounded hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <Trash2 className="h-3.5 w-3.5 text-red-500" />
                          </button>
                        </div>
                      </div>
                      {/* Structured content preview */}
                      <AnimatePresence>
                        {expandedDocId === doc.id && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            style={{ overflow: "hidden" }}
                          >
                            <div className="border-t border-border/40 p-4 bg-muted/20">
                              <StructuredDocumentPreview
                                documentId={doc.id}
                                fileName={doc.file_name}
                              />
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  ))}
                </div>
              ) : (
                <AcademicEmptyState
                  title="No documents yet"
                  description={selectedSubject ? "Upload your first document to get started" : "Select a subject to view documents"}
                  icon={Upload}
                />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
