from __future__ import annotations


ROLE_TAXONOMY: dict[str, dict[str, dict[str, list[str]]]] = {
    "data analyst": {
        "intent_groups": {
            "analysis": ["analyze", "data analysis", "eda", "statistics", "business data", "trends", "sql"],
            "reporting": ["dashboard", "report", "power bi", "tableau", "excel", "visualization", "kpi"],
            "insights": ["insight", "recommendation", "storytelling", "stakeholder", "decision", "actionable"],
        }
    },
    "data scientist": {
        "intent_groups": {
            "analysis": ["analysis", "statistics", "hypothesis", "experiment", "eda"],
            "modeling": ["model", "predict", "classification", "regression", "forecast", "train"],
            "communication": ["insight", "presentation", "stakeholder", "recommendation", "report"],
        }
    },
    "machine learning engineer": {
        "intent_groups": {
            "modeling": ["train", "fine tune", "evaluate", "model", "prediction", "classification"],
            "deployment": ["deploy", "api", "docker", "kubernetes", "cloud", "production"],
            "mlops": ["pipeline", "monitoring", "ci/cd", "automation", "retraining"],
        }
    },
    "ml engineer": {
        "intent_groups": {
            "modeling": ["train", "fine tune", "evaluate", "model", "prediction", "classification"],
            "deployment": ["deploy", "api", "docker", "kubernetes", "cloud", "production"],
            "mlops": ["pipeline", "monitoring", "ci/cd", "automation", "retraining"],
        }
    },
    "ai engineer": {
        "intent_groups": {
            "modeling": ["ai model", "llm", "rag", "prompt", "train", "evaluate"],
            "deployment": ["deploy", "api", "docker", "cloud", "production", "serve"],
            "automation": ["pipeline", "workflow", "monitoring", "automation", "orchestration"],
        }
    },
    "software engineer": {
        "intent_groups": {
            "build": ["build", "develop", "implement", "service", "application", "feature"],
            "quality": ["test", "debug", "optimize", "performance", "reliability"],
            "delivery": ["deploy", "release", "ci/cd", "production", "maintain"],
        }
    },
    "backend engineer": {
        "intent_groups": {
            "services": ["api", "backend", "service", "server", "microservice", "integration"],
            "data": ["database", "sql", "query", "schema", "etl"],
            "operations": ["deploy", "monitor", "performance", "scalability", "production"],
        }
    },
    "frontend engineer": {
        "intent_groups": {
            "ui": ["frontend", "ui", "ux", "component", "react", "javascript"],
            "delivery": ["build", "ship", "optimize", "responsive", "browser"],
            "collaboration": ["stakeholder", "design", "accessibility", "testing", "feedback"],
        }
    },
    "full stack developer": {
        "intent_groups": {
            "frontend": ["frontend", "ui", "react", "javascript", "css"],
            "backend": ["backend", "api", "database", "server", "integration"],
            "delivery": ["deploy", "monitor", "optimize", "production", "ci/cd"],
        }
    },
    "business analyst": {
        "intent_groups": {
            "analysis": ["business analysis", "requirements", "analyze", "process", "gap analysis"],
            "reporting": ["report", "dashboard", "excel", "visualization", "documentation"],
            "stakeholders": ["stakeholder", "present", "communicate", "recommendation", "insight"],
        }
    },
    "marketing analyst": {
        "intent_groups": {
            "analysis": ["campaign analysis", "trend", "audience", "market research", "analyze"],
            "reporting": ["report", "dashboard", "excel", "weekly report", "performance"],
            "insights": ["insight", "recommendation", "conversion", "engagement", "decision"],
        }
    },
    "product manager": {
        "intent_groups": {
            "strategy": ["roadmap", "strategy", "prioritize", "research", "vision"],
            "delivery": ["launch", "ship", "requirements", "cross functional", "execution"],
            "insights": ["metric", "stakeholder", "customer", "feedback", "decision"],
        }
    },
    "project manager": {
        "intent_groups": {
            "planning": ["plan", "timeline", "scope", "deliverable", "milestone"],
            "coordination": ["coordinate", "manage", "stakeholder", "cross functional", "resource"],
            "reporting": ["report", "status", "risk", "budget", "documentation"],
        }
    },
    "sales executive": {
        "intent_groups": {
            "growth": ["sales", "revenue", "lead", "conversion", "target"],
            "relationship": ["client", "customer", "account", "relationship", "negotiation"],
            "reporting": ["report", "forecast", "pipeline", "crm", "market feedback"],
        }
    },
    "hr executive": {
        "intent_groups": {
            "recruitment": ["recruit", "hiring", "screening", "interview", "talent"],
            "operations": ["onboarding", "documentation", "compliance", "policy", "coordination"],
            "people": ["employee engagement", "communication", "training", "stakeholder", "support"],
        }
    },
    "finance analyst": {
        "intent_groups": {
            "analysis": ["financial analysis", "forecast", "variance", "budget", "modeling"],
            "reporting": ["report", "excel", "dashboard", "statement", "kpi"],
            "insights": ["recommendation", "stakeholder", "decision", "risk", "trend"],
        }
    },
}
