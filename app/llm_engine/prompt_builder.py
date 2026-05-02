"""Prompt builder for LLM resume analysis."""

from typing import Dict, Any, Optional, cast

from app.llm_engine.json_utils import dumps_compact_json, dumps_pretty_json


class PromptBuilder:
    """Build structured prompts for LLM API clients."""

    PLACEHOLDERS = {
        "summary",
        "experience_block",
        "projects_block",
        "education_block",
        "skills_block",
        "other_block",
    }

    SYSTEM_PROMPT = """You are an ATS Resume Optimization Engine.

STRICT OUTPUT REQUIREMENTS:
- Output ONLY valid JSON
- Do NOT wrap in markdown
- Do NOT truncate output
- Do NOT stop early
- Ensure JSON is complete and closed
- If unsure, still return complete JSON

FAILURE TO FOLLOW WILL BREAK THE SYSTEM.

RULES:
- Do NOT invent experience
- You MAY infer commonly used tools based on role context when evidence supports it
- For Data Analyst profiles, include tools such as Excel, Tableau, and Power BI when context supports them
- Rewrite aggressively for ATS optimization while preserving factual meaning
- You may infer conservative, realistic metrics and outcomes when context supports them
- Use strong action verbs
- No personal pronouns"""

    TASK_INSTRUCTIONS = """TASK:

1. Rewrite weak resume bullets:
   - Add action verbs
   - Add measurable impact if possible
   - Improve clarity and specificity

2. Suggest missing skills:
   - Only if logically inferred from experience

3. Explain gaps:
   - Why ATS score is low
   - How to fix

IMPORTANT:
- If data insufficient, use "insufficient_data"
- Do NOT generate ATS score

LIMITS:
- Provide up to 5 bullet improvements (quality over quantity)
- Provide up to 5 skill suggestions (only high-confidence)
- Provide up to 5 gap explanations (focus on top-3 issues)

OUTPUT SIZE LIMIT:
- Keep each improvement concise (actionable and clear)
- Keep skills brief (skill name + 1-sentence rationale)
- Keep gaps focused (identify problem + suggested fix)

OUTPUT QUALITY:
- Prioritize COMPLETENESS and JSON validity over length
- Missing keys are acceptable; use empty arrays if needed
- Return valid JSON even if fewer items than suggested max

Return ONLY valid JSON matching the schema."""

    SCHEMA_ENFORCEMENT = """{
  "bullet_improvements": [
    {
      "original": "string",
      "improved": "string",
      "reason": "string"
    }
  ],
  "skill_suggestions": [
    {
      "skill": "string",
      "reason": "string"
    }
  ],
  "gap_explanations": [
    {
      "gap": "string",
      "fix": "string"
    }
  ]
}"""

    RESUME_ONLY_SYSTEM_PROMPT = """You are a professional resume optimizer.

STRICT OUTPUT REQUIREMENTS:
- Output ONLY valid JSON
- Do NOT wrap in markdown
- Do NOT truncate output
- Do NOT stop early
- Ensure JSON is complete and closed

RULES:
- No job description is provided
- Focus on general ATS and industry standards
- Do NOT hallucinate experience, tools, or education
- Improve clarity, impact framing, and readability"""

    RESUME_ONLY_TASK_INSTRUCTIONS = """TASK:

1. Improve weak resume bullets
2. Add measurable impact if logically inferable
3. Suggest missing general skills
4. Explain generic ATS/readability gaps

IMPORTANT:
- If data insufficient, use "insufficient_data"
- Keep recommendations broadly applicable
- Do NOT generate ATS score

LIMITS:
- Provide up to 5 bullet improvements (quality over quantity)
- Provide up to 5 skill suggestions (only high-confidence)
- Provide up to 5 gap explanations (focus on top-3 issues)

OUTPUT SIZE LIMIT:
- Keep each improvement concise (actionable and clear)
- Keep skills brief (skill name + 1-sentence rationale)
- Keep gaps focused (identify problem + suggested fix)

OUTPUT QUALITY:
- Return VALID JSON above all else
- Missing keys are acceptable; omit if unclear
- Empty arrays better than partial truncated data

Return valid JSON (may have fewer items than max)."""

    LLM_SCORING_TASK = """TASK:

Evaluate resume quality and return score (0-100) based on:

1. Impact strength (metrics, results)
2. Clarity and readability
3. Technical depth
4. Role alignment
5. ATS friendliness

Return JSON:
{
    "llm_score": number,
    "reason": "short explanation"
}

OUTPUT RULES:
- Return ONLY valid JSON
- No markdown
- No extra commentary
"""

    GENERATION_SYSTEM_PROMPT = """You are an expert ATS (Applicant Tracking System) Optimization Engine.

Your goal is to rewrite the provided resume to achieve a 95+ match score for a specific Job Description. You must adhere to a rigid, logic-based framework that prioritizes keyword density, quantified impact, and structural precision.

Phase 1: Diagnostic and Gap Analysis
Before rewriting, analyze the input data based on these metrics:
- Critical Skills: Identify the top 5 skills in the JD. Flag if 2 or more are missing.
- Experience Years: Ensure the resume covers at least 75% of requested years using MM/YYYY logic.
- Role Alignment: Flag any title mismatch against target role.
- Responsibility Coverage: Ensure at least 80% of JD responsibilities are represented.

Phase 2: Content Engineering Logic
Apply these strict logic rules to all generated text:
- The 2+1 Rule: Every critical skill must appear at least twice in Experience/Projects and once in Skills.
- Semantic Mapping: Use exact JD phrases when present (example: Agentic AI).
- Impact Formula (mandatory): Every bullet must follow
    [Action Verb] + [Technical Context/Task] + [Quantified Outcome]
- Quantification: Every bullet must include a number (%, ₹, $, or count), time/throughput metric, or a clear scale/outcome signal.
- Language: Remove personal pronouns and weak filler words such as assisted, helped, worked on, responsible for.
- Action Verbs: Use strong, high-impact verbs and avoid repetitive weak starters.
- Bullet Starter Rule: Every bullet must start with a strong past-tense verb unless the role is current.

Phase 3: Rigid Structural Rules
- Header format requirement: Name line, then LinkedIn (hyperlinked) | Email | Mobile in one horizontal line.
- Summary rule: Delete summary unless experience is 10+ years.
- Section order: Experience -> Projects -> Skills -> Education -> Certifications.
- Layout: Single-column text only. No tables, icons, images, or emojis.
- Font: Standard sans serif only (Arial or Calibri). Use size 12 for headings and 11 for body text.
- Date format: Strict MM/YYYY - MM/YYYY.
- Bullet constraints: Exactly 3-4 bullets per job/project; maximum 20 bullets total.
- Bullet length: Keep each bullet ideally one line; allow overflow only when technically necessary.

Section-specific rules:
- Experience/Projects: Use heading format like Company / Role or Project / Role (bold-ready heading text). Remove subheadings like Roles or Description.
- Show growth where relevant (example: Level 1 to Level 2).
- Add teamwork evidence where relevant (team size or cross-functional collaboration).
- Skills categories must be exactly:
    Programming Languages, Data Science, Data Visualization, Databases, Tools.
- Keep specific ML libraries primarily in project/experience bullets, not as standalone skill-category padding.
- Education: Latest degree first; use a single concise bullet for the college/institution name only (no long descriptions).
- Certifications: Maximum 5 items in Topic-Provider-Year format.

Phase 4: Final Output Requirements
- Word count must be 500-600 words.
- Keyword overlap target is at least 85% with JD skills.
- Use active voice; use past tense for completed roles unless currently employed.

Output rules:
- Output only valid JSON.
- Do not use markdown.
- Do not add commentary outside JSON."""

    GENERATION_TASK_INSTRUCTIONS = """Generate a production-ready ATS-optimized resume from the provided user profile and JD context hints.

Mandatory execution checklist:
- Run the Phase 1 diagnostic checks before rewriting.
- Enforce the 2+1 skill rule for all critical JD skills.
- Enforce exact semantic mapping for JD-critical terms.
- Enforce bullet formula on every bullet: action + technical context + quantified outcome.
- Enforce bullet starter rule: each bullet starts with a strong past-tense verb unless currently employed.
- Enforce 3-4 bullets per role/project and max 20 bullets total.
- Enforce section order: Experience, Projects, Skills, Education, Certifications.
- Enforce exact skills categories and max 5 certifications.
- Enforce layout and typography rules: single-column text-only, sans serif (Arial/Calibri), heading size 12, body size 11.
- Enforce date format MM/YYYY - MM/YYYY.
- Enforce bullet readability: ideally one-line bullets unless technical detail requires more.
- Enforce 500-600 words and active-voice writing.

Safety and factual integrity:
- Do not invent employers, projects, dates, credentials, or claims.
- You may infer conservative, realistic metrics only when context evidence supports them.
- Preserve factual input details.
- Keep summary empty when experience is below 10 years.

Return complete valid JSON only."""

    @staticmethod
    def _compress_generation_input(user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Preserve generation signal; only trim extreme payload sizes."""
        compressed: Dict[str, Any] = dict(user_input)

        raw_resume_text = str(compressed.get("raw_resume_text", "") or "").strip()
        if raw_resume_text:
            compressed["raw_resume_text"] = raw_resume_text[:12000]

        parsed_skills_flat = PromptBuilder._safe_str_list(compressed.get("parsed_skills_flat", []))
        if parsed_skills_flat:
            compressed["parsed_skills_flat"] = parsed_skills_flat

        context_enrichment_raw = compressed.get("context_enrichment")
        if isinstance(context_enrichment_raw, dict):
            enrichment = cast(Dict[str, Any], context_enrichment_raw)
            compact_enrichment: Dict[str, Any] = {}

            inferred = PromptBuilder._safe_str_list(enrichment.get("inferred_skills", []))
            if inferred:
                compact_enrichment["inferred_skills"] = inferred

            evidence_list = PromptBuilder._safe_list(enrichment.get("evidence", []))
            compact_evidence: list[dict[str, str]] = []
            for row in evidence_list:
                if isinstance(row, dict):
                    item = cast(Dict[str, Any], row)
                    compact_evidence.append(
                        {
                            "signal": str(item.get("signal", "")).strip(),
                            "mapped_skill": str(item.get("mapped_skill", "")).strip(),
                        }
                    )
            if compact_evidence:
                compact_enrichment["evidence"] = compact_evidence

            mode = str(enrichment.get("mode", "")).strip()
            if mode:
                compact_enrichment["mode"] = mode

            if compact_enrichment:
                compressed["context_enrichment"] = compact_enrichment

        # EXPLICITLY PRESERVE CONTACT FIELDS
        contact = compressed.get("contact", {})
        if isinstance(contact, dict):
            preserved_contact: Dict[str, Any] = {}
            contact_dict = cast(Dict[object, object], contact)
            for key in ("location", "email", "phone", "linkedin", "github", "name"):
                value = contact_dict.get(key, "")
                if value:
                    preserved_contact[str(key)] = str(value).strip()
            compressed["contact"] = preserved_contact

        experience = compressed.get("experience", [])
        if isinstance(experience, list):
            compressed["experience"] = experience

        projects = compressed.get("projects", [])
        if isinstance(projects, list):
            compressed["projects"] = projects

        skills = compressed.get("skills", {})
        if isinstance(skills, dict):
            preserved_skills: Dict[str, Any] = {}
            skills_dict = cast(Dict[object, object], skills)
            for key, values in skills_dict.items():
                if isinstance(values, list):
                    value_list = cast(list[object], values)
                    preserved_skills[str(key)] = [str(v) for v in value_list]
            compressed["skills"] = preserved_skills

        certifications = compressed.get("certifications", [])
        if isinstance(certifications, list):
            compressed["certifications"] = certifications

        extra_context = str(compressed.get("extra_context", "")).strip()
        if extra_context:
            compressed["extra_context"] = extra_context[:2000]

        jd_context_raw = compressed.get("jd_context")
        if isinstance(jd_context_raw, dict):
            jd_context = cast(Dict[str, Any], jd_context_raw)
            compact_jd: Dict[str, Any] = {}

            def _merge_unique(*values: Any) -> list[str]:
                merged: list[str] = []
                seen_local: set[str] = set()
                for value in values:
                    for item in PromptBuilder._safe_str_list(value):
                        token = item.lower()
                        if token in seen_local:
                            continue
                        seen_local.add(token)
                        merged.append(item)
                return merged

            job_title = str(jd_context.get("job_title") or jd_context.get("target_role") or "").strip()
            if job_title:
                compact_jd["job_title"] = job_title

            seniority = str(jd_context.get("seniority", "")).strip()
            if seniority:
                compact_jd["seniority"] = seniority

            req = _merge_unique(
                jd_context.get("skills_required", []),
                jd_context.get("required_skills", []),
                jd_context.get("must_have_skills", []),
            )
            if not req:
                req = _merge_unique(jd_context.get("skills", []))

            opt = _merge_unique(
                jd_context.get("skills_optional", []),
                jd_context.get("preferred_skills", []),
                jd_context.get("nice_to_have_skills", []),
            )

            resp = _merge_unique(
                jd_context.get("responsibilities", []),
                jd_context.get("job_responsibilities", []),
                jd_context.get("key_responsibilities", []),
                jd_context.get("requirements", []),
            )

            if req:
                compact_jd["skills_required"] = req
            if opt:
                compact_jd["skills_optional"] = opt
            if resp:
                compact_jd["responsibilities"] = resp

            intent_skills = PromptBuilder._safe_str_list(
                jd_context.get("skills_inferred_from_intent", [])
            )
            if intent_skills:
                compact_jd["skills_inferred_from_intent"] = intent_skills

            intent_rows = PromptBuilder._safe_list(jd_context.get("responsibility_intents", []))
            compact_intent_rows: list[dict[str, Any]] = []
            for row in intent_rows:
                if not isinstance(row, dict):
                    continue
                item = cast(Dict[str, Any], row)
                compact_intent_rows.append(
                    {
                        "cluster": str(item.get("cluster", "")).strip(),
                        "intent": str(item.get("intent", "")).strip(),
                        "mapped_skills": PromptBuilder._safe_str_list(item.get("mapped_skills", [])),
                        "evidence": PromptBuilder._safe_str_list(item.get("evidence", [])),
                    }
                )
            if compact_intent_rows:
                compact_jd["responsibility_intents"] = compact_intent_rows

            importance = jd_context.get("importance_weights", {})
            if isinstance(importance, dict) and importance:
                compact_jd["importance_weights"] = importance

            if compact_jd:
                compressed["jd_context"] = compact_jd

        return compressed

    @staticmethod
    def _safe_list(value: Any) -> list[Any]:
        """Normalize input to a list for robust slicing/iteration."""
        if value is None:
            return []
        if isinstance(value, list):
            return cast(list[Any], value)
        if isinstance(value, tuple):
            return list(cast(tuple[Any, ...], value))
        if isinstance(value, set):
            return list(cast(set[Any], value))
        if isinstance(value, dict):
            return list(cast(Dict[Any, Any], value).values())
        return [value]

    @staticmethod
    def _safe_str_list(value: Any) -> list[str]:
        """Normalize input to list[str] for joins and prompt text."""
        raw = PromptBuilder._safe_list(value)
        result: list[str] = []
        seen: set[str] = set()
        for item in raw:
            if isinstance(item, dict):
                item_dict = cast(Dict[str, Any], item)
                # Prefer common skill keys before generic stringification
                for key in (
                    "name",
                    "skill",
                    "jd_skill",
                    "resume_skill",
                    "responsibility",
                    "requirement",
                    "text",
                    "description",
                    "title",
                    "label",
                    "value",
                ):
                    if key in item_dict and item_dict.get(key):
                        value_text = str(item_dict.get(key)).strip()
                        token = value_text.lower()
                        if value_text and token not in seen:
                            seen.add(token)
                            result.append(value_text)
                        break
                else:
                    value_text = str(item_dict).strip()
                    token = value_text.lower()
                    if value_text and token not in seen:
                        seen.add(token)
                        result.append(value_text)
            else:
                value_text = str(item).strip()
                token = value_text.lower()
                if value_text and token not in seen:
                    seen.add(token)
                    result.append(value_text)
        return result

    @staticmethod
    def _normalize_rewrite_mode(user_input: Dict[str, Any]) -> str:
        raw_mode = str(user_input.get("rewrite_mode", "ats_rewrite") or "").strip().lower()
        if raw_mode in {"safe_fix", "safe", "edit", "edit_mode"}:
            return "safe_fix"
        return "ats_rewrite"

    @staticmethod
    def _format_raw_resume_text(user_input: Dict[str, Any]) -> str:
        text = str(user_input.get("raw_resume_text", "") or "").strip()
        if not text:
            return "No raw resume text provided."
        return text[:12000]

    @staticmethod
    def _format_context_enrichment(user_input: Dict[str, Any]) -> str:
        enrichment = user_input.get("context_enrichment", {})
        if not isinstance(enrichment, dict):
            return "No context enrichment hints provided."
        enrichment_dict = cast(Dict[str, Any], enrichment)

        inferred = PromptBuilder._safe_str_list(enrichment_dict.get("inferred_skills", []))
        evidence = PromptBuilder._safe_list(enrichment_dict.get("evidence", []))

        lines: list[str] = []
        if inferred:
            lines.append("Inferred skills (use in bullets and skills block): " + ", ".join(inferred))

        compact_evidence: list[str] = []
        for row in evidence:
            if isinstance(row, dict):
                item = cast(Dict[str, Any], row)
                signal = str(item.get("signal", "")).strip()
                skill = str(item.get("mapped_skill", "")).strip()
                if signal and skill:
                    compact_evidence.append(f"{signal} -> {skill}")

        if compact_evidence:
            lines.append("Evidence: " + " | ".join(compact_evidence))

        return "\n".join(lines) if lines else "No context enrichment hints provided."

    @staticmethod
    def _format_jd_intents(user_input: Dict[str, Any]) -> str:
        jd_context = user_input.get("jd_context", {})
        if not isinstance(jd_context, dict):
            return "No JD intent hints provided."
        jd_context_dict = cast(Dict[str, Any], jd_context)

        intent_rows = PromptBuilder._safe_list(jd_context_dict.get("responsibility_intents", []))
        inferred = PromptBuilder._safe_str_list(jd_context_dict.get("skills_inferred_from_intent", []))

        lines: list[str] = []
        if inferred:
            lines.append("Intent-inferred skills (must appear in targeted bullets): " + ", ".join(inferred))

        compact_rows: list[str] = []
        for row in intent_rows:
            if not isinstance(row, dict):
                continue
            item = cast(Dict[str, Any], row)
            cluster = str(item.get("cluster", "")).strip()
            intent = str(item.get("intent", "")).strip()
            mapped = PromptBuilder._safe_str_list(item.get("mapped_skills", []))
            if cluster or intent or mapped:
                compact_rows.append(
                    f"{cluster or 'intent'}: {intent or 'n/a'}"
                    + (f" -> {', '.join(mapped)}" if mapped else "")
                )
        if compact_rows:
            lines.append("Clusters: " + " | ".join(compact_rows))

        return "\n".join(lines) if lines else "No JD intent hints provided."

    @staticmethod
    def _format_jd_coverage_requirements(user_input: Dict[str, Any]) -> str:
        """Render explicit all-point JD checklist for generation prompts."""
        jd_context = user_input.get("jd_context", {})
        if not isinstance(jd_context, dict):
            return "No JD coverage checklist available."
        jd_context_dict = cast(Dict[str, Any], jd_context)

        def _merge_unique(*values: Any) -> list[str]:
            merged: list[str] = []
            seen_local: set[str] = set()
            for value in values:
                for item in PromptBuilder._safe_str_list(value):
                    token = item.lower()
                    if token in seen_local:
                        continue
                    seen_local.add(token)
                    merged.append(item)
            return merged

        required = _merge_unique(
            jd_context_dict.get("skills_required", []),
            jd_context_dict.get("required_skills", []),
            jd_context_dict.get("must_have_skills", []),
        )
        if not required:
            required = _merge_unique(jd_context_dict.get("skills", []))

        optional = _merge_unique(
            jd_context_dict.get("skills_optional", []),
            jd_context_dict.get("preferred_skills", []),
            jd_context_dict.get("nice_to_have_skills", []),
        )

        responsibilities = _merge_unique(
            jd_context_dict.get("responsibilities", []),
            jd_context_dict.get("job_responsibilities", []),
            jd_context_dict.get("key_responsibilities", []),
            jd_context_dict.get("requirements", []),
        )
        inferred = PromptBuilder._safe_str_list(jd_context_dict.get("skills_inferred_from_intent", []))

        if not any((required, optional, responsibilities, inferred)):
            return "No JD coverage checklist available."

        lines: list[str] = []
        if required:
            lines.append("Required skills (ALL should be represented in resume output):")
            lines.extend([f"- {item}" for item in required])
        if optional:
            lines.append("Optional skills (include where supported by evidence):")
            lines.extend([f"- {item}" for item in optional])
        if inferred:
            lines.append("Intent-inferred skills (cover where semantically supported):")
            lines.extend([f"- {item}" for item in inferred])
        if responsibilities:
            lines.append("Responsibilities (ALL should be covered in bullets):")
            lines.extend([f"- {item}" for item in responsibilities])

        return "\n".join(lines)

    @staticmethod
    def _compress_resume_only_data(resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """Preserve resume data - do NOT slice experience or skills."""
        compressed = dict(resume_data)
        entities = compressed.get("entities", {})
        if not isinstance(entities, dict):
            entities = {}
        entities_dict = cast(Dict[str, Any], entities)

        experience = PromptBuilder._safe_list(entities_dict.get("experience", []))
        skills = PromptBuilder._safe_str_list(entities_dict.get("skills", []))

        # CRITICAL FIX: Do NOT slice - preserve ALL data
        entities_dict["experience"] = experience
        entities_dict["skills"] = skills
        compressed["entities"] = entities_dict
        return compressed

    @staticmethod
    def _compress_recommendation_resume_data(resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """Shrink recommendation context to reduce truncation risk.

        Keeps only first 2 experience entries and first 2 projects for recommendation calls.
        """
        compressed = dict(resume_data)
        entities = compressed.get("entities", {})
        if not isinstance(entities, dict):
            entities = {}
        entities_dict = cast(Dict[str, Any], entities)

        experience = PromptBuilder._safe_list(entities_dict.get("experience", []))
        projects = PromptBuilder._safe_list(entities_dict.get("projects", []))
        skills = PromptBuilder._safe_str_list(entities_dict.get("skills", []))

        entities_dict["experience"] = experience[:2]
        entities_dict["projects"] = projects[:2]
        entities_dict["skills"] = skills
        compressed["entities"] = entities_dict
        return compressed

    @staticmethod
    def _format_experience_entry(exp: Any) -> str:
        """Format one experience record into a prompt-safe string."""
        if not isinstance(exp, dict):
            return f"- {str(exp)}"

        exp_dict = cast(Dict[str, Any], exp)
        role = str(exp_dict.get("role", "") or exp_dict.get("title", ""))
        company = str(exp_dict.get("company", ""))
        duration = str(exp_dict.get("duration", ""))
        bullets = PromptBuilder._safe_str_list(exp_dict.get("bullets", []))
        bullet_lines = "\n".join([f"  - {b}" for b in bullets])
        header_parts = [part for part in [role, company] if str(part).strip()]
        header = " @ ".join(header_parts).strip()
        if duration:
            header = f"{header} ({duration})" if header else f"({duration})"
        return f"- {header}\n{bullet_lines}".strip()

    @staticmethod
    def build_analysis_prompt(
        resume_data: Dict[str, Any],
        jd_data: Dict[str, Any],
        ats_analysis: Dict[str, Any],
    ) -> str:
        """Build complete analysis prompt for LLM."""
        resume_text = PromptBuilder._format_resume_data(resume_data)
        jd_text = PromptBuilder._format_jd_data(jd_data)
        ats_text = PromptBuilder._format_ats_analysis(ats_analysis)

        prompt = f"""{PromptBuilder.SYSTEM_PROMPT}

{PromptBuilder.TASK_INSTRUCTIONS}

REQUIRED JSON SCHEMA:
{PromptBuilder.SCHEMA_ENFORCEMENT}

RESUME DATA:
{resume_text}

JOB DESCRIPTION DATA:
{jd_text}

CURRENT ATS ANALYSIS:
{ats_text}

Now analyze and respond ONLY with valid JSON matching the schema. No markdown. No extra text. Pure JSON output."""

        return prompt

    @staticmethod
    def build_resume_only_prompt(resume_data: Dict[str, Any]) -> str:
        """Build prompt for general resume improvement without JD context."""
        compact_resume = PromptBuilder._compress_resume_only_data(resume_data)
        resume_text = PromptBuilder._format_resume_data(compact_resume)

        return f"""{PromptBuilder.RESUME_ONLY_SYSTEM_PROMPT}

{PromptBuilder.RESUME_ONLY_TASK_INSTRUCTIONS}

REQUIRED JSON SCHEMA:
{PromptBuilder.SCHEMA_ENFORCEMENT}

RESUME DATA:
{resume_text}

Now analyze and respond ONLY with valid JSON matching the schema. No markdown. No extra text. Pure JSON output."""

    @staticmethod
    def build_bullet_improvements_prompt(
        resume_data: Dict[str, Any],
        jd_data: Optional[Dict[str, Any]] = None,
        ats_analysis: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build focused prompt for bullet improvements only."""
        compact_resume = PromptBuilder._compress_recommendation_resume_data(resume_data)
        resume_text = PromptBuilder._format_resume_data(compact_resume)
        jd_text = PromptBuilder._format_jd_data(jd_data) if isinstance(jd_data, dict) else "No JD provided."
        ats_text = (
            PromptBuilder._format_ats_analysis(ats_analysis)
            if isinstance(ats_analysis, dict)
            else "No ATS analysis provided."
        )

        return f"""You are an ATS resume bullet optimizer.

Return JSON only in this exact shape:
{{
  "bullet_improvements": [
    {{"original": "string", "improved": "string", "reason": "string"}}
  ]
}}

Task:
- Improve weak resume bullets with strong action verbs and realistic impact.
- Keep concise and factual.
- If data is limited, return an empty array.

Rules:
- Do NOT include skill suggestions.
- Do NOT include gap explanations.
- Do NOT add extra top-level keys.

RESUME DATA:
{resume_text}

JOB DESCRIPTION DATA:
{jd_text}

ATS SIGNALS:
{ats_text}

Return ONLY valid JSON."""

    @staticmethod
    def build_skill_suggestions_prompt(
        resume_data: Dict[str, Any],
        jd_data: Optional[Dict[str, Any]] = None,
        ats_analysis: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build focused prompt for skill suggestions only."""
        compact_resume = PromptBuilder._compress_recommendation_resume_data(resume_data)
        resume_text = PromptBuilder._format_resume_data(compact_resume)
        jd_text = PromptBuilder._format_jd_data(jd_data) if isinstance(jd_data, dict) else "No JD provided."
        ats_text = (
            PromptBuilder._format_ats_analysis(ats_analysis)
            if isinstance(ats_analysis, dict)
            else "No ATS analysis provided."
        )

        return f"""You are an ATS skill-gap analyzer.

Return JSON only in this exact shape:
{{
  "skill_suggestions": [
    {{"skill": "string", "reason": "string"}}
  ]
}}

Task:
- Suggest high-confidence missing skills relevant to role alignment.
- Keep rationale concise and evidence-based.
- If data is limited, return an empty array.

Rules:
- Do NOT include bullet improvements.
- Do NOT include gap explanations.
- Do NOT add extra top-level keys.

RESUME DATA:
{resume_text}

JOB DESCRIPTION DATA:
{jd_text}

ATS SIGNALS:
{ats_text}

Return ONLY valid JSON."""

    @staticmethod
    def build_gap_explanations_prompt(
        resume_data: Dict[str, Any],
        jd_data: Optional[Dict[str, Any]] = None,
        ats_analysis: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build focused prompt for gap explanations only."""
        compact_resume = PromptBuilder._compress_recommendation_resume_data(resume_data)
        resume_text = PromptBuilder._format_resume_data(compact_resume)
        jd_text = PromptBuilder._format_jd_data(jd_data) if isinstance(jd_data, dict) else "No JD provided."
        ats_text = (
            PromptBuilder._format_ats_analysis(ats_analysis)
            if isinstance(ats_analysis, dict)
            else "No ATS analysis provided."
        )

        return f"""You are an ATS gap explainer.

Return JSON only in this exact shape:
{{
  "gap_explanations": [
    {{"gap": "string", "fix": "string"}}
  ]
}}

Task:
- Explain the most important ATS gaps and how to fix each.
- Keep fixes practical and concise.
- If data is limited, return an empty array.

Rules:
- Do NOT include bullet improvements.
- Do NOT include skill suggestions.
- Do NOT add extra top-level keys.

RESUME DATA:
{resume_text}

JOB DESCRIPTION DATA:
{jd_text}

ATS SIGNALS:
{ats_text}

Return ONLY valid JSON."""

    @staticmethod
    def build_generation_prompt(user_input: Dict[str, Any]) -> str:
        """Build prompt for generating a full resume from structured user input."""
        compact_input = PromptBuilder._compress_generation_input(user_input)
        profile_json = dumps_pretty_json(compact_input)

        return f"""{PromptBuilder.GENERATION_SYSTEM_PROMPT}

{PromptBuilder.GENERATION_TASK_INSTRUCTIONS}

USER PROFILE INPUT:
    {profile_json}

Generate and return ONLY valid JSON."""

    @staticmethod
    def build_placeholder_prompt(user_input: Dict[str, Any]) -> str:
        """Build strict plain-text ATS enhancement prompt for section-block generation."""
        compact_input = PromptBuilder._compress_generation_input(user_input)
        rewrite_mode = PromptBuilder._normalize_rewrite_mode(compact_input)
        profile_json = dumps_compact_json(compact_input)
        raw_resume_text = PromptBuilder._format_raw_resume_text(compact_input)
        enrichment_text = PromptBuilder._format_context_enrichment(compact_input)
        jd_intent_text = PromptBuilder._format_jd_intents(compact_input)
        jd_coverage_text = PromptBuilder._format_jd_coverage_requirements(compact_input)
        years = compact_input.get("years_of_experience", 0)
        try:
            years_value = float(years)
        except (TypeError, ValueError):
            years_value = 0.0
        include_summary = years_value >= 10

        experience_rows_raw = compact_input.get("experience", [])
        project_rows_raw = compact_input.get("projects", [])
        experience_rows = cast(list[Dict[str, Any]], experience_rows_raw) if isinstance(experience_rows_raw, list) else []
        project_rows = cast(list[Dict[str, Any]], project_rows_raw) if isinstance(project_rows_raw, list) else []

        required_companies = [
            str(row.get("company", "")).strip()
            for row in experience_rows
            if str(row.get("company", "")).strip()
        ]
        required_projects = [
            str(row.get("name", "")).strip()
            for row in project_rows
            if str(row.get("name", "")).strip()
        ]

        company_text = ", ".join(required_companies) if required_companies else "None"
        project_text = ", ".join(required_projects) if required_projects else "None"
        has_experience_entries = bool(experience_rows)

        if has_experience_entries:
            experience_retention_rule = "- EXPERIENCE_BLOCK must include EVERY experience entry from user data."
            experience_company_rule = "- EXPERIENCE_BLOCK must include company names exactly as provided."
            experience_empty_rule = ""
        else:
            experience_retention_rule = "- EXPERIENCE_BLOCK should remain empty when user data has no experience entries."
            experience_company_rule = ""
            experience_empty_rule = "- Do NOT invent or fabricate employment history when experience is absent in USER DATA."

        summary_rule = (
            "SUMMARY: Include 1-2 concise sentences (max 40 words) because profile is 10+ years."
            if include_summary
            else "SUMMARY: Leave this section blank because profile is below 10 years."
        )

        rewrite_mode_text = (
            "ATS_REWRITE mode: Rewrite aggressively for ATS optimization. Infer conservative, realistic metrics when missing, while preserving factual meaning."
            if rewrite_mode == "ats_rewrite"
            else "SAFE_FIX mode: Keep edits conservative. Improve clarity and ATS phrasing without aggressive expansion."
        )

        return f"""You are an expert ATS (Applicant Tracking System) Optimization Engine.

Your goal is to rewrite the provided resume to achieve a 95+ match score for a specific Job Description. Follow this rigid rule-based framework.

Phase 1: Diagnostic and Gap Analysis
- Identify top 5 critical JD skills and flag if 2 or more are missing.
- Validate timeline years using MM/YYYY logic and ensure at least 75% years coverage.
- Flag role-title mismatch against target role.
- Ensure at least 80% responsibility coverage.

Phase 2: Content Engineering Logic
- Apply the 2+1 rule: each critical skill appears at least 2 times in Experience/Projects and 1 time in Skills.
- Use exact JD wording for critical terms when present.
- Every bullet must follow: Action Verb + Technical Context/Task + Quantified Outcome.
- Every bullet must include a number (%, ₹, $, or count), time/throughput metric, or clear scale signal.
- Remove personal pronouns and filler verbs (assisted, helped, worked on, responsible for).
- Prefer strong, distinct action verbs and ATS-aligned wording.
- Ensure every bullet starts with a strong past-tense verb unless the role is currently active.

Phase 3: Rigid Structural Rules
- Header requirement: Name, then LinkedIn | Email | Mobile on one line (handled by template; preserve contact fields).
- Header detail: LinkedIn must remain hyperlink-ready in final rendering.
- Summary rule: {summary_rule}
- Required order: Experience -> Projects -> Skills -> Education -> Certifications.
- Output must be single-column plain text only.
- Formatting rule: no tables, icons, images, or emojis.
- Font policy: standard sans serif only (Arial or Calibri), heading size 12, body size 11.
- Use strict date format MM/YYYY - MM/YYYY.
- Bullet constraints: exactly 3-4 bullets per role/project, maximum 20 bullets total.
- Keep each bullet ideally one line; extend only when technically necessary.

Section-specific logic:
- Experience/Projects headings should follow Company / Role or Project / Role style and be bold-ready heading text; do not add Roles or Description subheadings.
- Show growth progression when evident (example: Level 1 to Level 2).
- Include teamwork or cross-functional evidence when present.
- Skills must use EXACT categories:
  Programming Languages
  Data Science
  Data Visualization
  Databases
  Tools
- Keep specific ML libraries primarily in project/experience bullets, not as standalone skill-category padding.
- Education must list latest degree first and use one concise bullet line for college/institution name only.
- Certifications must be maximum 5 items in Topic-Provider-Year format.

Non-negotiable retention rules:
{experience_retention_rule}
{experience_company_rule}
- PROJECTS_BLOCK must include every project name from USER DATA.
- Do not merge entries, rename companies, or drop roles/projects.
{experience_empty_rule}

Mandatory experience companies (must appear in EXPERIENCE_BLOCK):
{company_text}

Mandatory project names (must appear in PROJECTS_BLOCK):
{project_text}

Final output requirements:
- Total output should be 500-600 words.
- Maximize JD skill overlap to at least 85%.
- Use active voice and past tense for completed roles unless currently employed.

REWRITE MODE:
{rewrite_mode_text}

RAW RESUME TEXT (primary context):
{raw_resume_text}

CONTEXT ENRICHMENT HINTS:
{enrichment_text}

JD INTENT HINTS:
{jd_intent_text}

JD COVERAGE REQUIREMENTS CHECKLIST:
{jd_coverage_text}

USER DATA:
{profile_json}

STRICT OUTPUT FORMAT (plain text only, no JSON, no markdown, no LaTeX):

EXPERIENCE_BLOCK:
<role entries with quantified ATS-optimized bullets>

PROJECTS_BLOCK:
<project entries with quantified ATS-optimized bullets>

SKILLS_BLOCK:
<skills grouped in exact required categories>

EDUCATION_BLOCK:
<latest degree first, concise format>

OTHER_BLOCK:
<certifications max 5 in Topic-Provider-Year format>

SUMMARY:
<blank unless 10+ years>

FINAL RULE:
Return ONLY text in the exact section format above."""

    @staticmethod
    def build_placeholder_retry_prompt(
        user_input: Dict[str, Any],
        previous_output: str,
        issues: list[str],
    ) -> str:
        """Build correction prompt for strict ATS placeholder mode."""
        compact_input = PromptBuilder._compress_generation_input(user_input)
        rewrite_mode = PromptBuilder._normalize_rewrite_mode(compact_input)
        profile_json = dumps_compact_json(compact_input)
        raw_resume_text = PromptBuilder._format_raw_resume_text(compact_input)
        enrichment_text = PromptBuilder._format_context_enrichment(compact_input)
        jd_intent_text = PromptBuilder._format_jd_intents(compact_input)
        jd_coverage_text = PromptBuilder._format_jd_coverage_requirements(compact_input)
        issues_text = "\n".join([f"- {issue}" for issue in issues])
        years = compact_input.get("years_of_experience", 0)
        try:
            years_value = float(years)
        except (TypeError, ValueError):
            years_value = 0.0
        experience_rows_raw = compact_input.get("experience", [])
        experience_rows = cast(list[Dict[str, Any]], experience_rows_raw) if isinstance(experience_rows_raw, list) else []
        has_experience_entries = bool(experience_rows)
        summary_rule = (
            "Include summary (1-2 sentences, max 40 words) because profile is 10+ years."
            if years_value >= 10
            else "Leave summary blank because profile is below 10 years."
        )

        rewrite_mode_text = (
            "ATS_REWRITE mode: perform aggressive ATS rewrite with conservative inferred metrics from evidence."
            if rewrite_mode == "ats_rewrite"
            else "SAFE_FIX mode: keep edits conservative and minimally invasive."
        )
        experience_rule = (
            "- Keep EVERY experience entry with exact company names when experience exists."
            if has_experience_entries
            else "- Keep EXPERIENCE_BLOCK empty and do NOT fabricate employment history when user data has no experience entries."
        )

        return f"""You violated the required ATS rule-base in the previous output.

FAILED CHECKS:
{issues_text}

Regenerate all sections and fix every violation using this rigid framework:

Phase 1 diagnostics to re-check:
- Top 5 critical JD skills and missing count.
- Timeline years coverage >= 75% with MM/YYYY logic.
- Role-title alignment.
- Responsibility coverage >= 80%.

Phase 2 content engineering to enforce:
- 2+1 rule for every critical skill.
- Exact semantic mapping for JD phrases.
- Every bullet: Action Verb + Technical Context/Task + Quantified Outcome.
- Every bullet must include a number (%, ₹, $, or count), time/throughput metric, or scale/outcome signal.
- Remove personal pronouns and weak filler verbs.
- Keep strong, non-repetitive action verbs.
- Ensure each bullet starts with a strong past-tense verb unless role is current.

Phase 3 structure to enforce:
- Header line must preserve LinkedIn (hyperlinked) | Email | Mobile formatting when rendered.
- Section order: Experience -> Projects -> Skills -> Education -> Certifications.
- Layout: single-column text only with no tables/icons/images/emojis.
- Font policy: standard sans serif only (Arial or Calibri), heading size 12, body size 11.
- Date format: MM/YYYY - MM/YYYY.
- Bullet constraints: exactly 3-4 bullets per role/project, maximum 20 bullets total.
- Keep each bullet ideally one line; extend only when technically necessary.
- Skills categories: Programming Languages, Data Science, Data Visualization, Databases, Tools.
- Keep specific ML libraries primarily in project/experience bullets, not as standalone skill-category padding.
- Education must remain concise: one bullet line for institution/college name only (no long descriptions).
- Summary rule: {summary_rule}
{experience_rule}
- Preserve all project names from USER DATA.

Additional mandatory constraints:
- Keep all factual entities from USER DATA.
- Do not merge entries, rename companies, or drop roles/projects.
- If jd_context exists in USER DATA, align bullets to JD skills and responsibilities.
- Use RAW_RESUME_TEXT as primary narrative context.
- Infer only conservative, realistic metrics when supported by evidence.
- Target 500-600 words and at least 85% JD skill overlap.

REWRITE MODE:
{rewrite_mode_text}

STRICT OUTPUT FORMAT (plain text only, no JSON, no markdown, no LaTeX):

EXPERIENCE_BLOCK:
<all roles with exact company names and quantified bullets>

PROJECTS_BLOCK:
<all project names retained and quantified bullets>

SKILLS_BLOCK:
<skills grouped in exact required categories>

EDUCATION_BLOCK:
<text>

OTHER_BLOCK:
<certifications max 5 in Topic-Provider-Year format>

SUMMARY:
<blank unless 10+ years>

PREVIOUS OUTPUT (for correction):
{previous_output}

RAW RESUME TEXT (PRIMARY CONTEXT):
{raw_resume_text}

CONTEXT ENRICHMENT HINTS:
{enrichment_text}

JD INTENT HINTS:
{jd_intent_text}

JD COVERAGE REQUIREMENTS CHECKLIST:
{jd_coverage_text}

USER DATA (source of truth):
{profile_json}

FINAL RULE:
Return ONLY text in the exact section format above, with no missing entries and quantified bullets."""

    @staticmethod
    def build_generation_fix_prompt(
        user_input: Dict[str, Any],
        problematic_sections: Dict[str, Any],
        errors: list[str],
        stronger: bool = False,
    ) -> str:
        """Build a compact correction prompt using validator errors only."""
        compact_input = PromptBuilder._compress_generation_input(user_input)
        profile_json = dumps_compact_json(compact_input)
        problem_json = dumps_compact_json(problematic_sections)
        errors_text = "\n".join([f"- {err}" for err in errors])
        extra = "\n- CRITICAL: Preserve ALL data while fixing errors - do NOT drop any entries." if stronger else ""

        return f"""DATA PRESERVATION CRITICAL! You are an ATS resume correction engine."

REQUIREMENT: Your output MUST have:
✓ EVERY experience entry from user profile
✓ Every project from user profile when project count <= 4
✓ If project count > 4, keep only the top 4 most influential projects
✓ ALL skills from user profile
✓ Data loss = automatic failure and regeneration

Fix these validation errors:
{errors_text}

Constraints:
    - 400-675 words, strong action verbs, quantified bullets
    - Keep EVERY experience entry (do NOT drop)
    - Keep EVERY project entry when project count <= 4
    - If project count > 4, keep only top 4 most influential projects
    - STRICT SECTION ISOLATION: Experience is jobs/leadership only; Projects is project work only
    - NEVER merge projects into experience and NEVER convert projects to jobs
    - Remove personal pronouns from all sections
    - Normalize duration to MM/YYYY or MM/YYYY - Present
    - Preserve project dates when present in input
    - Preserve factual consistency with user profile
    - CRITICAL: Preserve ALL contact information (location, email, phone, LinkedIn, GitHub)
    - CONTACT LOCK: email, linkedin, github are mandatory
    - EDUCATION FORMAT RULE: education must be clean readable text, never Python dict string
    - COMPANY RULE: never output "N/A"; recover company from input
{extra}

USER PROFILE INPUT:
{profile_json}

PROBLEMATIC SECTIONS ONLY:
{problem_json}

Return ONLY corrected valid JSON using this schema:
{{
  "contact": {{
        "location": "string",
    "name": "string",
    "email": "string",
    "phone": "string",
    "linkedin": "string",
    "github": "string"
  }},
  "summary": "string",
  "experience": [{{"title": "string", "company": "string", "duration": "string", "bullets": ["string"]}}],
    "projects": [{{"name": "string", "bullets": ["string"], "technologies": ["string"]}}],
    "education": "string",
    "skills": {{
        "programming_languages": ["string"],
        "data_science": ["string"],
        "data_visualization": ["string"],
        "databases": ["string"],
        "tools": ["string"]
    }},
    "certifications": ["string"]
}}"""

    @staticmethod
    def build_llm_scoring_prompt(
        resume_data: Dict[str, Any],
        jd_data: Optional[Dict[str, Any]] = None,
        ats_analysis: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build compact prompt for numeric LLM quality scoring."""
        compact_resume = PromptBuilder._compress_resume_only_data(resume_data)
        resume_text = PromptBuilder._format_resume_data(compact_resume)
        jd_text = PromptBuilder._format_jd_data(jd_data) if isinstance(jd_data, dict) else "No JD provided."
        ats_text = (
            PromptBuilder._format_ats_analysis(ats_analysis)
            if isinstance(ats_analysis, dict)
            else "No ATS analysis provided."
        )

        return f"""{PromptBuilder.SYSTEM_PROMPT}

{PromptBuilder.LLM_SCORING_TASK}

RESUME DATA:
{resume_text}

JOB DESCRIPTION DATA:
{jd_text}

ATS SIGNALS:
{ats_text}

Return ONLY valid JSON."""

    @staticmethod
    def _format_resume_data(resume_data: Dict[str, Any]) -> str:
        """Format resume data for prompt injection."""
        entities = resume_data.get("entities", {})
        experience = PromptBuilder._safe_list(entities.get("experience", []))
        skills = PromptBuilder._safe_str_list(entities.get("skills", []))

        # Show ALL experience entries (removed [:1] slicing)
        formatted_exp = "\n".join(
            [
                PromptBuilder._format_experience_entry(exp)
                for exp in experience
            ]
        )

        # Show ALL skills (removed [:5] slicing)
        formatted_skills = ", ".join(skills)
        formatted_years = resume_data.get("metadata", {}).get("years_of_experience", "unknown")

        return f"""Experience ({formatted_years} years):
{formatted_exp}

Top Skills:
{formatted_skills}

Resume Quality Metrics:
- Completeness: {resume_data.get('metadata', {}).get('completeness_score', 0):.0%}
- Parse Confidence: {resume_data.get('metadata', {}).get('parsing_confidence', 0):.0%}"""

    @staticmethod
    def _format_jd_data(jd_data: Dict[str, Any]) -> str:
        """Format JD data for prompt injection."""
        skills_required = PromptBuilder._safe_str_list(jd_data.get("skills_required", []))
        skills_optional = PromptBuilder._safe_str_list(jd_data.get("skills_optional", []))
        intent_skills = PromptBuilder._safe_str_list(
            jd_data.get("skills_inferred_from_intent", [])
        )
        responsibilities = PromptBuilder._safe_str_list(jd_data.get("responsibilities", []))
        formatted_required = ", ".join(skills_required) if skills_required else "None"
        formatted_optional = ", ".join(skills_optional) if skills_optional else "None"
        formatted_intent = ", ".join(intent_skills) if intent_skills else "None"
        formatted_resp = "\n".join([f"- {r}" for r in responsibilities]) if responsibilities else "- None"

        return f"""Required Skills: {formatted_required}

Optional Skills: {formatted_optional}

Intent Skills: {formatted_intent}

Responsibilities:
{formatted_resp}"""

    @staticmethod
    def _format_ats_analysis(ats_analysis: Dict[str, Any]) -> str:
        """Format ATS analysis for prompt injection."""
        components = ats_analysis.get("components", {})
        evidence = ats_analysis.get("evidence", {})
        skill_alignment = evidence.get("skill_alignment", {})

        missing_skills = PromptBuilder._safe_str_list(skill_alignment.get("missing", []))[:3]
        weak_evidence = PromptBuilder._safe_str_list(evidence.get("weak_evidence_skills", []))[:5]

        return f"""Current ATS Score: {ats_analysis.get('ats_score', 0):.1%}

Component Scores:
- Skill: {components.get('skill_score', 0):.1%}
- Experience: {components.get('experience_score', 0):.1%}
- Impact: {components.get('impact_score', 0):.1%}
- Format: {components.get('format_score', 0):.1%}

Missing Critical Skills: {", ".join(missing_skills) if missing_skills else "None"}

Skills with Weak Evidence: {", ".join(weak_evidence) if weak_evidence else "None"}

Matched Skills: {len(skill_alignment.get('matched', []))}
Covered Responsibilities: {len(evidence.get('experience_alignment', {}).get('covered', []))}"""

    @staticmethod
    def build_text_resume_prompt(user_input: Dict[str, Any]) -> str:
        """Build strict ATS text-generation prompt based on enhancement framework."""
        profile_text = dumps_pretty_json(user_input)
        years = user_input.get("years_of_experience", 0)
        try:
            years_value = float(years)
        except (TypeError, ValueError):
            years_value = 0.0
        summary_rule = (
            "Include a 1-2 sentence summary (max 40 words) only because profile is 10+ years."
            if years_value >= 10
            else "Do NOT include summary content; leave summary empty because profile is below 10 years."
        )

        return f"""
You are an expert ATS Optimization Engine.

Objective:
Rewrite the resume so that it aligns strongly with the target JD and improves ATS relevance while preserving factual truth.

PHASE 1: Diagnostic and Gap Analysis
- Identify top 5 critical JD skills and flag missing coverage.
- Validate years and timeline consistency (MM/YYYY logic) with target >= 75% coverage.
- Check title alignment to target role.
- Ensure responsibility coverage appears in role/project bullets.
- If jd_context is included in USER DATA, use it as the primary targeting source.

PHASE 2: Content Engineering
- Apply the 2+1 rule for critical skills:
  >= 2 mentions in Experience/Projects and >= 1 mention in Skills.
- Every bullet MUST use: Action Verb + Technical Context + Quantified Outcome.
- Every bullet must contain a metric (percent, count, currency, time, throughput).
- Use exact JD terminology when it exists in source evidence.
- Remove pronouns, filler language, and weak verb starters.

PHASE 3: Rigid Formatting and Structure
- Header: Name, then one-line contact (LinkedIn | Email | Mobile).
- {summary_rule}
- Section order: Experience -> Projects -> Skills -> Education -> Certifications.
- Experience and Projects: ensure complete evidence coverage first; trim in later validation if needed.
- Date format: MM/YYYY - MM/YYYY.
- Skills categories EXACTLY:
  Programming Languages
  Data Science
  Data Visualization
  Databases
  Tools
- Certifications: max 5, format Topic-Provider-Year.

PHASE 4: Final Quality Bar
- Word count target: 500-600 words.
- Keyword overlap target: >= 85% with JD-critical skills.
- Active voice and measurable impact throughout.

OUTPUT RULES
- Output ONLY the final resume text.
- No markdown.
- No explanations.
- No extra commentary.

USER DATA:
{profile_text}

Generate the final resume.
""".strip()
