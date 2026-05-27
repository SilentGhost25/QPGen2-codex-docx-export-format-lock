import { useMemo } from "react";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

interface Question {
  id?: number;
  text?: string;
  marks?: number;
  custom_marks?: number;
  course_outcome?: string;
  bloom_level?: string;
  module_number?: number;
}

interface COCoverageTableProps {
  questions: Question[];
  moduleCOMap?: Record<number, string>;
}

export function COCoverageTable({ questions, moduleCOMap = {} }: COCoverageTableProps) {
  const coStats = useMemo(() => {
    // 1. Calculate total marks in the paper
    const totalMarks = questions.reduce((sum, q) => {
      const qMarks = q.custom_marks || q.marks || 0;
      return sum + qMarks;
    }, 0);

    // 2. Aggregate marks by Course Outcome
    const coMarks: Record<string, number> = {
      CO1: 0,
      CO2: 0,
      CO3: 0,
      CO4: 0,
      CO5: 0,
    };

    questions.forEach((q) => {
      const co = (q.course_outcome || "").toUpperCase().trim();
      if (co in coMarks) {
        coMarks[co] += q.custom_marks || q.marks || 0;
      }
    });

    // 3. Map modules to each CO
    const coModules: Record<string, number[]> = {
      CO1: [],
      CO2: [],
      CO3: [],
      CO4: [],
      CO5: [],
    };

    // Check moduleCOMap settings
    Object.entries(moduleCOMap).forEach(([mod, co]) => {
      const normalizedCO = co.toUpperCase().trim();
      if (normalizedCO in coModules) {
        coModules[normalizedCO].push(parseInt(mod));
      }
    });

    // Fallback: Check mapped modules from questions if map is empty
    questions.forEach((q) => {
      const co = (q.course_outcome || "").toUpperCase().trim();
      const mod = q.module_number;
      if (co in coModules && mod != null && !coModules[co].includes(mod)) {
        coModules[co].push(mod);
      }
    });

    // Sort modules for presentation
    Object.keys(coModules).forEach((co) => {
      coModules[co].sort((a, b) => a - b);
    });

    // 4. Compute percentages
    const coPercentages = Object.fromEntries(
      Object.entries(coMarks).map(([co, marks]) => [
        co,
        totalMarks > 0 ? Math.round((marks / totalMarks) * 100) : 0,
      ])
    );

    return {
      totalMarks,
      coMarks,
      coPercentages,
      coModules,
    };
  }, [questions, moduleCOMap]);

  const coKeys = ["CO1", "CO2", "CO3", "CO4", "CO5"];

  return (
    <Card className="border-muted shadow-sm hover:shadow-md transition-shadow duration-300">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-bold tracking-tight">Course Outcome (CO) Weightage Analytics</CardTitle>
        <CardDescription className="text-xs">
          Dynamic percentage distributions computed directly from final compiled question marks.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-muted bg-muted/40 font-semibold text-muted-foreground">
                <th className="px-4 py-2.5 rounded-l-md">Course Outcome</th>
                <th className="px-4 py-2.5">Mapped Modules</th>
                <th className="px-4 py-2.5 text-center">Marks Allocated</th>
                <th className="px-4 py-2.5 w-1/3">Weightage Distribution (%)</th>
                <th className="px-4 py-2.5 text-right rounded-r-md">Percentage</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-muted/50 font-medium">
              {coKeys.map((co) => {
                const pct = coStats.coPercentages[co] || 0;
                const marks = coStats.coMarks[co] || 0;
                const modules = coStats.coModules[co] || [];

                return (
                  <tr key={co} className="hover:bg-muted/10 transition-colors duration-200">
                    <td className="px-4 py-3 font-bold text-primary">{co}</td>
                    <td className="px-4 py-3">
                      {modules.length > 0 ? (
                        <div className="flex gap-1">
                          {modules.map((m) => (
                            <span
                              key={m}
                              className="inline-flex items-center rounded-md bg-secondary px-2 py-0.5 text-[10px] font-semibold text-secondary-foreground"
                            >
                              Mod {m}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-[10px]">Unmapped</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center font-mono font-semibold">{marks} M</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <Progress value={pct} className="h-1.5 flex-1" />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right font-bold text-foreground">{pct}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
