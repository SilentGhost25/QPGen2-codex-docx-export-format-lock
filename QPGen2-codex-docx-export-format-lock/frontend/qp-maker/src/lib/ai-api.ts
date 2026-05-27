import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const API_BASE_URL = import.meta.env.VITE_API_URL || "/api/v1";

async function fetchWithAuth<T>(url: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem("access_token");
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options?.headers,
  };

  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Request failed" }));
    const error: any = new Error(err.detail || "Request failed");
    error.status = response.status;
    throw error;
  }

  return response.json();
}

export interface AIProcessResult {
  success: boolean;
  document_id?: number;
  filename: string;
  total_extracted: number;
  auto_approved: number;
  processing_time: number;
  ai_model: string;
  ai_mode: string;
  summary: {
    by_module: Record<string, number>;
    by_rbt: Record<string, number>;
    by_co: Record<string, number>;
    by_difficulty: Record<string, number>;
  };
  error?: string;
}

export interface Question {
  id: number;
  text: string;
  marks: number;
  course_outcome: string;
  bloom_level: string;
  difficulty: string;
  module_number: number;
  question_type: string;
  is_verified: boolean;
}

export interface PaperQuestion {
  id: number;
  question_id: number;
  order_index: number;
  section_label: string;
  custom_marks: number | null;
  text: string;
  course_outcome?: string | null;
  bloom_level?: string | null;
  module_number?: number | null;
  difficulty?: string | null;
  confidence?: number | null;
  source_documents?: string[];
  validation_errors?: string[];
  validation_warnings?: string[];
}

export interface GeneratedPaper {
  id: number;
  subject_id: number;
  subject_name?: string | null;
  subject_code?: string | null;
  department_name?: string | null;
  title: string;
  exam_type: string;
  semester: string;
  batch: string;
  max_marks: number;
  duration_minutes: number;
  exam_date?: string;
  teaching_department: string;
  status: string;
  prompt_used?: string;
  generated_summary?: string;
  ai_config: Record<string, any>;
  coverage_stats: Record<string, any>;
  questions: PaperQuestion[];
  download_path?: string;
}

export type PaperGenerationJobStatus = "pending" | "processing" | "completed" | "failed";

export interface PaperGenerationJob {
  id: number;
  subject_id: number;
  status: PaperGenerationJobStatus;
  progress: number;
  error_message?: string | null;
  stage?: string | null;
  message?: string | null;
  paper_id?: number | null;
  paper?: GeneratedPaper | null;
  created_at: string;
  completed_at?: string | null;
}

export interface GeneratePaperParams {
  subject_id: number;
  title: string;
  exam_type: string;
  semester: string;
  batch: string;
  max_marks: number;
  duration_minutes: number;
  exam_date?: string;
  teaching_department: string;
  prompt: string;
  rbt_levels: string[];
  module_numbers: number[];
  module_co_map?: Record<number, string>;
  module_image_map?: Record<number, boolean>;
  co_targets?: Record<string, number>;
  co_descriptions?: Record<string, string>;
  difficulty?: string;
  instructions?: string;
  manual_question_ids?: number[];
  creativity?: number;
  use_notes?: boolean;
  use_question_bank?: boolean;
  use_previous_papers?: boolean;
  use_syllabus?: boolean;
}

export interface QuestionBankSummary {
  total_documents: number;
  total_questions: number;
  verified_questions: number;
  pending_questions: number;
  retrieval_ready_questions: number;
  by_module: Record<string, number>;
  by_rbt: Record<string, number>;
  by_co: Record<string, number>;
  by_difficulty: Record<string, number>;
  recent_documents: Array<{
    id: number;
    filename: string;
    upload_status: string;
    created_at: string;
    question_count: number;
  }>;
  gaps: string[];
}

export function useAIPrintQuestionBank() {
  const queryClient = useQueryClient();

  return useMutation<AIProcessResult, Error, { subject_id: number; file: File }>({
    mutationFn: async ({ subject_id, file }) => {
      const token = localStorage.getItem("access_token");
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE_URL}/ai/process-question-bank?subject_id=${subject_id}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Processing failed" }));
        throw new Error(error.detail || "Processing failed");
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["questions"] });
    },
  });
}

export function useAIGeneratePaper() {
  const queryClient = useQueryClient();

  return useMutation<GeneratedPaper, Error, GeneratePaperParams>({
    mutationFn: async (params) => {
      return fetchWithAuth<GeneratedPaper>("/ai/generate-paper", {
        method: "POST",
        body: JSON.stringify(params),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["papers"] });
    },
  });
}

export function useCreatePaperGenerationJob() {
  return useMutation<PaperGenerationJob, Error, GeneratePaperParams>({
    mutationFn: async (params) => {
      return fetchWithAuth<PaperGenerationJob>("/ai/generate-paper/jobs", {
        method: "POST",
        body: JSON.stringify(params),
      });
    },
  });
}

export function usePaperGenerationJob(jobId?: number) {
  return useQuery<PaperGenerationJob>({
    queryKey: ["paper-generation-job", jobId],
    queryFn: async () => {
      return fetchWithAuth<PaperGenerationJob>(`/ai/generate-paper/jobs/${jobId}`);
    },
    enabled: Boolean(jobId),
    staleTime: 0,
    gcTime: 10 * 60 * 1000,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "processing" ? 1200 : false;
    },
  });
}

export function useQuestionBankSummary(subjectId?: number) {
  return useQuery<QuestionBankSummary>({
    queryKey: ["ai-question-bank-summary", subjectId],
    queryFn: async () => {
      const suffix = subjectId ? `?subject_id=${subjectId}` : "";
      return fetchWithAuth<QuestionBankSummary>(`/ai/question-bank-summary${suffix}`);
    },
    staleTime: 30000,
    gcTime: 5 * 60 * 1000,
  });
}

export function useQuestions(subjectId?: number, filters?: {
  bloom_level?: string;
  difficulty?: string;
  module?: number;
}) {
  return useQuery<Question[]>({
    queryKey: ["questions", subjectId, filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (subjectId) params.append("subject_id", subjectId.toString());
      if (filters?.bloom_level) params.append("bloom_level", filters.bloom_level);
      if (filters?.difficulty) params.append("difficulty", filters.difficulty);
      
      return fetchWithAuth<Question[]>(`/questions?${params.toString()}`);
    },
    staleTime: 30000,
    gcTime: 5 * 60 * 1000,
  });
}

export function useSubjects() {
  return useQuery({
    queryKey: ["subjects"],
    queryFn: async () => {
      return fetchWithAuth<any[]>("/subjects");
    },
    staleTime: 60000,
    gcTime: 10 * 60 * 1000,
  });
}

export function useCreateSubject() {
  const queryClient = useQueryClient();
  return useMutation<any, Error, { name: string; code: string; department_id: number; semester: number }>({
    mutationFn: async (params) => {
      return fetchWithAuth<any>("/subjects", {
        method: "POST",
        body: JSON.stringify(params),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subjects"] });
    },
  });
}

export function useDepartments() {
  return useQuery({
    queryKey: ["departments"],
    queryFn: async () => {
      return fetchWithAuth<{ id: number; name: string; code: string }[]>("/departments");
    },
    staleTime: 60000,
    gcTime: 10 * 60 * 1000,
  });
}

export function usePapers() {
  return useQuery({
    queryKey: ["papers"],
    queryFn: async () => {
      return fetchWithAuth<GeneratedPaper[]>("/papers");
    },
  });
}

export interface GeneratePaperParams {
  subject_id: number;
  title: string;
  exam_type: string;
  semester: string;
  batch: string;
  max_marks: number;
  duration_minutes: number;
  exam_date?: string;
  teaching_department: string;
  prompt: string;
  rbt_levels: string[];
  module_numbers: number[];
  module_co_map?: Record<number, string>;
  module_image_map?: Record<number, boolean>;
  co_targets?: Record<string, number>;
  co_descriptions?: Record<string, string>;
  difficulty?: string;
  instructions?: string;
  manual_question_ids?: number[];
  creativity?: number;
  use_notes?: boolean;
  use_question_bank?: boolean;
  use_previous_papers?: boolean;
  use_syllabus?: boolean;
}

export interface QuestionBankSummary {
  total_documents: number;
  total_questions: number;
  verified_questions: number;
  pending_questions: number;
  retrieval_ready_questions: number;
  by_module: Record<string, number>;
  by_rbt: Record<string, number>;
  by_co: Record<string, number>;
  by_difficulty: Record<string, number>;
  recent_documents: Array<{
    id: number;
    filename: string;
    upload_status: string;
    created_at: string;
    question_count: number;
  }>;
  gaps: string[];
}

export function useDownloadPaper() {
  return useMutation<Blob, Error, number>({
    mutationFn: async (paperId) => {
      const token = localStorage.getItem("access_token");
      const response = await fetch(`${API_BASE_URL}/papers/${paperId}/download`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (!response.ok) {
        throw new Error("Download failed");
      }

      return response.blob();
    },
  });
}

export function useUpdateQuestion() {
  const queryClient = useQueryClient();
  return useMutation<any, Error, { id: number; text?: string; marks?: number; course_outcome?: string; bloom_level?: string; difficulty?: string; module_number?: number }>({
    mutationFn: async (params) => {
      const { id, ...body } = params;
      return fetchWithAuth<any>(`/questions/${id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["questions"] });
    },
  });
}
