export type Severity = "Critical" | "Major" | "Minor";
export type AnalyzeMode = "jd" | "resume_only";
export type RewriteMode = "ats_rewrite" | "safe_fix";

export interface AtsBreakdownItem {
  id: string;
  name: string;
  score: number;
  total: number;
  desc: string;
}

export interface AtsIssueItem {
  severity: Severity;
  text: string;
}

export interface AtsAnalyzeResponse {
  ok: boolean;
  mode: AnalyzeMode;
  target_role: string;
  decision: string;
  confidence: number;
  score: number;
  percentile?: number | null;
  reasons: string[];
  fail_reasons: string[];
  ats_score: number;
  components: Record<string, any>;
  breakdown: AtsBreakdownItem[];
  issues: AtsIssueItem[];
  raw: Record<string, any>;
  resume_parse: Record<string, any>;
}

export interface AnalyzeAtsRequest {
  resumeFile: File;
  jdText?: string;
  targetRole?: string;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const API_VERSION = "v1";

export async function analyzeAts(request: AnalyzeAtsRequest): Promise<AtsAnalyzeResponse> {
  const formData = new FormData();
  formData.append("resume_file", request.resumeFile);
  
  if (request.jdText) {
    formData.append("jd_text", request.jdText);
  }
  
  if (request.targetRole) {
    formData.append("target_role", request.targetRole);
  }

  const response = await fetch(`${API_BASE_URL}/api/${API_VERSION}/analyze/ats`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let errorDetail = `HTTP error! status: ${response.status}`;
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch (e) {
      // ignore
    }
    throw new Error(errorDetail);
  }

  return response.json();
}
