# AI-First Architecture: Llama 3.2 Vision as the Core Brain

## Vision

Transform QPGen so that **Llama 3.2 Vision is the central intelligence** that:
1. **Reads and understands** every uploaded question bank
2. **Classifies and indexes** all questions with proper metadata
3. **Maintains context** of the entire question database
4. **Intelligently selects** questions when generating papers
5. **Generates** properly formatted DOCX output

---

## System Architecture: AI at the Center

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        QPGen AI-First Architecture                         │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────┐
    │                     TEACHER / HOD INTERFACE                         │
    │   • Upload Question Banks                                           │
    │   • View Question Bank                                              │
    │   • Generate Papers                                                 │
    │   • Review Generated Papers                                         │
    └──────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                      FRONTEND (React)                               │
    │   • Upload Page (drag & drop files)                                 │
    │   • Question Bank View (search/filter)                              │
    │   • Generate Page (RBT/CO config)                                   │
    │   • Preview Page (DOCX preview)                                     │
    └──────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                       FASTAPI BACKEND                               │
    │                                                                       │
    │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐   │
    │  │  Auth Service │  │ Upload Service│  │   Paper Service      │   │
    │  └───────┬───────┘  └───────┬───────┘  └───────────┬───────────┘   │
    └──────────┼───────────────────┼──────────────────────┼───────────────┘
               │                   │                      │
               └───────────────────┼──────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │     AI ORCHESTRATION LAYER  │
                    │   ┌────────────────────────┐│
                    │   │   Llama 3.2 Vision     ││
                    │   │      (The Brain)       ││
                    │   └────────────────────────┘│
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┴───────────────┐
                    │      DATABASE LAYER           │
                    │  ┌─────────┐ ┌─────────────┐ │
                    │  │Questions│ │  Subjects   │ │
                    │  │   +     │ │   + CO/PO    │ │
                    │  │ Papers  │ │  Departments│ │
                    │  └─────────┘ └─────────────┘ │
                    └──────────────────────────────┘
```

---

## AI Context System: What Llama 3.2 Vision "Sees"

### 1. Question Bank Context
```python
class AIQuestionContext:
    """
    Everything the AI knows about questions in the system
    """
    # From database
    all_questions: list[Question]
    question_count: int
    
    # Grouped views
    by_subject: dict[str, list[Question]]
    by_module: dict[int, list[Question]]      # Module 1-5
    by_bloom_level: dict[str, list[Question]] # L1-L6
    by_co: dict[str, list[Question]]          # CO1-CO6
    by_difficulty: dict[str, list[Question]] # easy/medium/hard
    
    # Statistics
    rbt_distribution: dict[str, int]
    co_coverage: dict[str, int]
    difficulty_distribution: dict[str, int]
    
    # Quality metrics
    verified_questions: int
    ai_extracted_questions: int
    manual_questions: int
```

### 2. Subject Context
```python
class AISubjectContext:
    """
    AI understands each subject comprehensively
    """
    subject_name: str
    subject_code: str
    semester: int
    max_marks: int
    
    # Course structure
    course_outcomes: list[str]  # CO1-CO6
    modules_covered: list[int] # 1-5
    
    # Question availability
    questions_per_module: dict[int, int]
    questions_per_co: dict[str, int]
    questions_per_rbt: dict[str, int]
    
    # Teaching department info
    teaching_department: str
    affiliated_to: str  # VTU
```

### 3. Generation Context (When Teacher Generates Paper)
```python
class AIGenerationContext:
    """
    What AI receives when asked to generate a paper
    """
    # Input from teacher
    subject: Subject
    exam_type: str              # IAT-1, IAT-2, End-Sem
    max_marks: int             # 50 or 100
    duration: int              # 90 or 180 minutes
    date: date
    batch: str
    
    # Requirements
    selected_modules: list[int]     # [1, 2, 3, 4, 5]
    required_rbt: dict[str, int]    # {"L1": 20, "L2": 30, ...}
    required_co: dict[str, int]      # {"CO1": 20, "CO2": 20, ...}
    difficulty: str                  # easy/medium/hard
    
    # Constraints
    question_count_preferred: int
    or_pattern_required: bool        # For 100 marks papers
```

---

## AI Integration Points

### Point 1: Question Upload (AI Reads Everything)

```
Teacher uploads: question_bank.pdf
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AI PROCESSING                               │
│                                                                 │
│  1. Read file (PDF/DOCX/Image)                                  │
│  2. Llama 3.2 Vision extracts ALL questions                    │
│  3. For each question, AI identifies:                           │
│     • Module number (from content/headers)                     │
│     • RBT Level (L1-L6)                                        │
│     • Course Outcome (CO1-CO6)                                 │
│     • Marks (estimated)                                        │
│     • Difficulty                                              │
│  4. Store in database with AI tags                              │
│  5. Update AI's understanding of question bank                │
└─────────────────────────────────────────────────────────────────┘
```

**AI Prompt for Extraction:**
```
You are an expert academic AI for VTU engineering courses.

Read this question bank document and extract EVERY question.

For each question, determine:
1. MODULE NUMBER: Which module (1-5) does this question belong to?
   - Look for module headings in the document
   - Infer from content if not explicitly stated
   
2. RBT LEVEL (Bloom's Taxonomy):
   L1: Define, List, State, Name, Recall
   L2: Explain, Describe, Discuss, Summarize
   L3: Solve, Calculate, Demonstrate, Apply
   L4: Compare, Distinguish, Analyze, Examine
   L5: Evaluate, Judge, Critique, Justify
   L6: Design, Construct, Develop, Create

3. COURSE OUTCOME (CO1-CO6):
   CO1: Remember fundamental concepts
   CO2: Apply knowledge to solve problems
   CO3: Analyze data and interpretations
   CO4: Design engineering solutions
   CO5: Evaluate and justify approaches
   CO6: Create innovative solutions

4. MARKS: Estimate based on complexity (5/10/15/20)

5. QUESTION TYPE: theory | problem | objective

Return JSON:
{
  "questions": [
    {
      "text": "question content",
      "module": 1-5,
      "rbt": "L1-L6",
      "co": "CO1-CO6",
      "marks": 5-20,
      "difficulty": "easy/medium/hard",
      "type": "theory/problem/objective"
    }
  ]
}
```

### Point 2: Question Bank Viewing (AI Search & Context)

```
Teacher views question bank
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI SEARCH & CONTEXT                         │
│                                                                 │
│  • AI understands full question database                      │
│  • Natural language search: "show me module 3 questions"        │
│  • Filter by RBT, CO, difficulty                                │
│  • Show statistics and coverage                                │
│  • Suggest gaps in question bank                               │
└─────────────────────────────────────────────────────────────────┘
```

### Point 3: Paper Generation (AI Selects & Formats)

```
Teacher clicks: "Generate Question Paper"
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                AI PAPER GENERATION                             │
│                                                                 │
│  INPUT:                                                         │
│  • Subject: Operating Systems                                   │
│  • Modules: [1,2,3,4,5]                                        │
│  • RBT: L1=10%, L2=20%, L3=30%, L4=20%, L5=10%, L6=10%        │
│  • CO: CO1=20%, CO2=20%, CO3=20%, CO4=20%, CO5=20%           │
│  • Max Marks: 50                                               │
│  • Difficulty: Medium                                           │
│                                                                 │
│  AI PROCESS:                                                    │
│  1. Query all questions for this subject                       │
│  2. Filter by selected modules                                  │
│  3. Select questions to match:                                │
│     - RBT distribution                                         │
│     - CO coverage                                               │
│     - Total marks = 50                                          │
│     - Difficulty balance                                        │
│                                                                 │
│  4. Generate DOCX with your exact format:                       │
│     - Header with college name                                  │
│     - USN line                                                  │
│     - Department & exam title                                   │
│     - Details table                                             │
│     - Questions with CO/RBT tags                                │
│     - "OR" pattern for 100-mark papers                         │
│     - CO description section                                    │
│     - Module coverage table                                     │
│                                                                 │
│  OUTPUT: Question_Paper.docx                                   │
└─────────────────────────────────────────────────────────────────┘
```

**AI Selection Prompt:**
```
You are generating a question paper for {subject_name} ({subject_code})

REQUIREMENTS:
- Maximum marks: {max_marks}
- Duration: {duration} minutes
- Modules to cover: {selected_modules}
- RBT distribution: {rbt_distribution}
- Course outcomes: {co_coverage}
- Difficulty: {difficulty}

AVAILABLE QUESTIONS (from database):
{question_list_json}

TASK:
1. Select questions that best match the requirements
2. Ensure total marks = {max_marks}
3. Cover all selected modules
4. Match RBT distribution as closely as possible
5. Cover all course outcomes

Return JSON:
{
  "selected_questions": [
    {
      "qno": 1,
      "text": "question",
      "marks": 10,
      "co": "CO1",
      "rbt": "L2",
      "module": 1,
      "section": "A"  // A or B for OR pattern
    }
  ],
  "coverage_stats": {
    "rbt_achieved": {...},
    "co_achieved": {...},
    "module_coverage": {...}
  }
}
```

### Point 4: DOCX Generation (AI Formats Output)

```python
# The AI knows the exact format needed and generates it
def generate_docx(paper_data: dict) -> Document:
    doc = Document()
    
    # AI has learned the VTU/DST format
    # 1. College header
    # 2. USN field
    # 3. Department
    # 4. Exam title
    # 5. Details table
    # 6. RBT legend
    # 7. Questions with OR pattern
    # 8. CO section
    # 9. Module coverage
    
    # The AI orchestrates all of this
    return doc
```

---

## AI Memory System

```python
class QuestionBankMemory:
    """
    AI maintains persistent memory of entire question database
    """
    
    def __init__(self):
        self.ollama_client = OllamaClient()
        self.db = Database()
    
    def update_memory(self, new_questions: list[Question]):
        """
        After each upload, AI updates its understanding
        """
        # Get all questions for this subject
        all_questions = self.db.get_all_questions()
        
        # Create context summary for AI
        context = self._create_context_summary(all_questions)
        
        # Store in AI's context window (or vector DB)
        self.ollama_client.update_context(context)
    
    def _create_context_summary(self, questions: list[Question]) -> str:
        """
        Create a comprehensive text summary of entire question bank
        """
        summary = f"""
        Question Bank Summary:
        - Total Questions: {len(questions)}
        
        By Module:
        """
        for m in range(1, 6):
            count = len([q for q in questions if q.module == m])
            summary += f"\n  Module {m}: {count} questions"
        
        summary += "\n\nBy RBT Level:"
        for rbt in ["L1", "L2", "L3", "L4", "L5", "L6"]:
            count = len([q for q in questions if q.rbt == rbt])
            summary += f"\n  {rbt}: {count}"
        
        summary += "\n\nBy Course Outcome:"
        for co in ["CO1", "CO2", "CO3", "CO4", "CO5", "CO6"]:
            count = len([q for q in questions if q.co == co])
            summary += f"\n  {co}: {count}"
        
        return summary
    
    def search_questions(self, query: str) -> list[Question]:
        """
        Natural language question search
        """
        # AI understands the query and searches
        prompt = f"""
        Based on the question bank context, find questions that match:
        "{query}"
        
        Return list of question IDs.
        """
        return self.ollama_client.generate(prompt)
    
    def suggest_questions_for_paper(self, requirements: dict) -> list[Question]:
        """
        AI intelligently selects questions based on requirements
        """
        prompt = f"""
        Select the best questions from the question bank to create a balanced paper.
        
        Requirements:
        - Max marks: {requirements['max_marks']}
        - Modules: {requirements['modules']}
        - RBT levels: {requirements['rbt_distribution']}
        - Course outcomes: {requirements['co_coverage']}
        
        Available questions:
        {self._format_questions_for_prompt()}
        
        Select questions that:
        1. Match the RBT distribution
        2. Cover all COs
        3. Cover selected modules
        4. Total exactly {requirements['max_marks']} marks
        
        Return question IDs in order.
        """
        
        response = self.ollama_client.generate(prompt)
        return self._parse_question_ids(response)
```

---

## Implementation: AI Service Architecture

```python
# backend/app/ai_service.py

class QPGenAIBrain:
    """
    The central AI brain for the entire application
    """
    
    def __init__(self):
        self.ollama = OllamaClient()
        self.question_memory = QuestionBankMemory()
    
    # ============================================================
    # FUNCTION 1: PROCESS UPLOADED QUESTION BANK
    # ============================================================
    async def process_question_bank(
        self, 
        file: UploadFile, 
        subject_id: int,
        teacher_id: int
    ) -> ProcessingResult:
        """
        1. Read file content
        2. Use Llama 3.2 Vision to extract questions
        3. Classify each question
        4. Store in database
        5. Update AI memory
        """
        # Step 1: Extract text/content based on file type
        content = await self._read_file(file)
        
        # Step 2: Use AI to extract and classify
        if self._is_image(file.filename):
            questions = await self._extract_from_image(content)
        else:
            questions = await self._extract_from_text(content)
        
        # Step 3: Save to database
        saved_questions = await self._save_questions(
            questions, subject_id, teacher_id
        )
        
        # Step 4: Update AI memory
        self.question_memory.update_memory(saved_questions)
        
        return ProcessingResult(
            total_extracted=len(questions),
            saved=saved_questions,
            auto_approved=len([q for q in saved_questions if q.is_verified])
        )
    
    # ============================================================
    # FUNCTION 2: GENERATE QUESTION PAPER (MAIN CORE)
    # ============================================================
    async def generate_question_paper(
        self,
        subject_id: int,
        config: PaperGenerationConfig
    ) -> QuestionPaper:
        """
        The main generation function
        1. Get all questions for subject
        2. AI selects questions based on requirements
        3. Generate DOCX in exact format
        4. Return paper with download link
        """
        # Step 1: Get questions from database
        all_questions = await self._get_questions_for_subject(subject_id)
        
        # Step 2: AI selects questions
        selected = await self._ai_select_questions(
            all_questions, config
        )
        
        # Step 3: Generate DOCX
        docx_path = await self._generate_docx(selected, config)
        
        # Step 4: Save paper to database
        paper = await self._save_paper(selected, config, docx_path)
        
        return paper
    
    # ============================================================
    # FUNCTION 3: NATURAL LANGUAGE SEARCH
    # ============================================================
    async def search_questions(
        self, 
        query: str, 
        subject_id: int | None = None
    ) -> list[Question]:
        """
        Teacher can ask: "Show me difficult questions from module 3"
        AI understands and returns matching questions
        """
        return await self.question_memory.search_questions(query)
    
    # ============================================================
    # FUNCTION 4: ANALYZE QUESTION BANK
    # ============================================================
    async def analyze_question_bank(self, subject_id: int) -> QuestionBankAnalysis:
        """
        AI analyzes the question bank and provides:
        - Coverage statistics
        - Gaps identification
        - Suggestions for improvement
        """
        questions = await self._get_questions_for_subject(subject_id)
        
        return QuestionBankAnalysis(
            total_questions=len(questions),
            rbt_distribution=self._calculate_rbt_dist(questions),
            co_distribution=self._calculate_co_dist(questions),
            module_distribution=self._calculate_module_dist(questions),
            gaps=self._identify_gaps(questions),
            suggestions=self._generate_suggestions(questions)
        )
```

---

## API Endpoints: AI-Powered

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ai/process-question-bank` | POST | Upload & AI processes question bank |
| `/ai/generate-paper` | POST | Generate question paper with AI |
| `/ai/search-questions` | POST | Natural language question search |
| `/ai/analyze-bank` | GET | AI analyzes question bank coverage |
| `/ai/suggest-questions` | POST | AI suggests questions for criteria |
| `/ai/retag-questions` | POST | Re-run AI tagging on existing questions |

---

## Frontend Integration: AI-Powered Pages

### 1. Upload Page
```tsx
// Frontend: Upload with AI processing
function UploadPage() {
  const [files, setFiles] = useState([]);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  
  const handleUpload = async () => {
    setProcessing(true);
    
    for (const file of files) {
      // Upload to AI service
      const result = await aiApi.processQuestionBank({
        file,
        subject_id: selectedSubject
      });
      
      // AI extracts and classifies
      setProgress(p => p + (100 / files.length));
    }
    
    setProcessing(false);
    // Show results: X questions extracted, Y auto-approved
  };
  
  return (
    <div>
      <DropZone onFilesChange={setFiles} />
      {processing && <ProgressBar value={progress} />}
      {!processing && <ResultsSummary />}
    </div>
  );
}
```

### 2. Question Bank View
```tsx
// Frontend: Search with AI
function QuestionBankPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [questions, setQuestions] = useState([]);
  
  const handleSearch = async () => {
    // AI understands natural language
    const results = await aiApi.searchQuestions({
      query: searchQuery,  // "show module 3 questions with L4"
    });
    setQuestions(results);
  };
  
  return (
    <div>
      <SearchBox onSearch={handleSearch} />
      <QuestionList questions={questions} />
    </div>
  );
}
```

### 3. Generate Page
```tsx
// Frontend: Configure and generate
function GeneratePage() {
  const [config, setConfig] = useState({
    subject: null,
    exam_type: "IAT-1",
    max_marks: 50,
    modules: [1,2,3,4,5],
    rbt_distribution: { L1: 20, L2: 20, L3: 20, L4: 20, L5: 10, L6: 10 },
    co_coverage: { CO1: 20, CO2: 20, CO3: 20, CO4: 20, CO5: 20 },
    difficulty: "medium"
  });
  
  const generatePaper = async () => {
    const paper = await aiApi.generatePaper(config);
    // Returns paper with DOCX download link
  };
  
  return (
    <ConfigurationForm config={config} onChange={setConfig} />
    <GenerateButton onClick={generatePaper} />
  );
}
```

---

## Summary: AI-First Features

| Feature | What AI Does |
|---------|-------------|
| **Upload Processing** | Reads every file, extracts all questions, auto-classifies |
| **Question Memory** | Remembers entire question bank context |
| **Smart Selection** | Intelligently picks questions matching RBT/CO requirements |
| **Format Generation** | Generates DOCX in exact VTU/DST format |
| **Natural Search** | Understands "find difficult module 3 questions" |
| **Bank Analysis** | Identifies gaps and suggests improvements |

---

The AI is the **brain** of the entire system - it sees everything, remembers everything, and generates the papers intelligently.

Should I start implementing this AI-first architecture?