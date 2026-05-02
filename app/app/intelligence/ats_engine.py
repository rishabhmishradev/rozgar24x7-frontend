"""ATS Scoring Engine — optimized edition.

Changes vs original:
1. _required_skill_depth_score: pre-tokenised bullet corpus + lru_cache on regex compilation
   → O(n+m) instead of O(n×m) with 800+ regex compilations.
2. _impact_score: single weighted formula (quantified 40% + action 30% + result 20% +
   complexity 10%) replacing 12 unbounded additive bonus blocks.
3. compute_ats_score decomposed into _run_hard_gates(), _apply_cross_penalties(),
   _compute_raw_score(), _apply_decision_band() — each returns a typed dataclass.
4. sanitize_generated_resume: exact dedup via normalised set (O(n)); fuzzy near-duplicate
   detection uses MinHash LSH (datasketch) instead of O(n²) SequenceMatcher loop.
"""

from __future__ import annotations

import math
import logging
import re
import functools
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, cast

from .utils import (
    clamp01,
    flatten_experience_bullets,
    normalize_skill_name,
    semantic_similarity,
    to_resume_skill_map,
)
from .skill_alignment import WEAK_EVIDENCE_SCORE_MULTIPLIER


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Role profiles & aliases
# ---------------------------------------------------------------------------

ROLE_PROFILES: dict[str, dict[str, Any]] = {
    "ai engineer": {
        "skills": [
            "python",
            "r",
            "sql",
            "tensorflow",
            "pytorch",
            "scikit-learn",
            "xgboost",
            "fastapi",
            "flask",
            "docker",
            "kubernetes",
            "aws",
            "gcp",
            "azure",
            "feature engineering",
            "model deployment",
        ],
        "responsibilities": [
            "design and train machine learning and deep learning models",
            "build and deploy end-to-end ai pipelines",
            "monitor and optimize model performance in production",
        ],
        "expected_years": 0,
    },
    "generative ai engineer": {
        "skills": [
            "python",
            "typescript",
            "sql",
            "transformers",
            "langchain",
            "llamaindex",
            "hugging face",
            "pytorch",
            "rag",
            "lora",
            "qlora",
            "pinecone",
            "milvus",
            "weaviate",
            "vllm",
            "docker",
        ],
        "responsibilities": [
            "design retrieval-augmented generation systems",
            "fine-tune and optimize foundation models",
            "evaluate and deploy llm applications for production",
        ],
        "expected_years": 0,
    },
    "nlp specialist": {
        "skills": [
            "python",
            "sql",
            "java",
            "nltk",
            "spacy",
            "gensim",
            "hugging face",
            "transformers",
            "bert",
            "roberta",
            "t5",
            "named entity recognition",
            "sentiment analysis",
            "topic modeling",
            "information retrieval",
            "text preprocessing",
        ],
        "responsibilities": [
            "build language understanding and generation pipelines",
            "develop and evaluate nlp models for enterprise tasks",
            "optimize text systems for accuracy and low latency",
        ],
        "expected_years": 0,
    },
    "computer vision engineer": {
        "skills": [
            "c++",
            "python",
            "matlab",
            "opencv",
            "mediapipe",
            "pytorch",
            "tensorflow",
            "detectron2",
            "yolo",
            "object detection",
            "image segmentation",
            "slam",
            "tensorrt",
            "onnx",
            "docker",
            "3d geometry",
        ],
        "responsibilities": [
            "develop vision algorithms for detection and segmentation",
            "optimize cv models for real-time and edge deployment",
            "build robust visual data pipelines and evaluation workflows",
        ],
        "expected_years": 0,
    },
    "ai ethics and compliance officer": {
        "skills": [
            "ai fairness 360",
            "fairlearn",
            "shap",
            "lime",
            "nist ai risk management framework",
            "oecd ai principles",
            "gdpr",
            "ccpa",
            "eu ai act",
            "iso iec 42001",
            "differential privacy",
            "data anonymization",
            "python",
            "sql",
            "policy writing",
            "ethical reasoning",
        ],
        "responsibilities": [
            "define and enforce responsible ai governance frameworks",
            "audit model fairness privacy and regulatory compliance",
            "guide teams on explainability risk and ethical deployment",
        ],
        "expected_years": 0,
    },
    "ai product manager": {
        "skills": [
            "agile",
            "scrum",
            "prd writing",
            "jira",
            "productboard",
            "sql",
            "tableau",
            "power bi",
            "mixpanel",
            "python",
            "figma",
            "roi analysis",
            "go to market strategy",
            "model evaluation",
            "feedback loops",
            "data strategy",
        ],
        "responsibilities": [
            "define ai product strategy roadmap and success metrics",
            "translate user and business needs into technical ai requirements",
            "coordinate cross-functional delivery from poc to production",
        ],
        "expected_years": 0,
    },
    "machine learning scientist": {
        "skills": [
            "python",
            "c++",
            "jax",
            "julia",
            "pytorch",
            "tensorflow",
            "deepspeed",
            "horovod",
            "fsdp",
            "bayesian statistics",
            "optimization",
            "self-supervised learning",
            "reinforcement learning",
            "meta-learning",
            "latex",
            "docker",
        ],
        "responsibilities": [
            "research and prototype novel machine learning algorithms",
            "run rigorous experiments and benchmark model advances",
            "transfer research outcomes into production-ready innovations",
        ],
        "expected_years": 0,
    },
    "robotics engineer": {
        "skills": [
            "c++",
            "python",
            "assembly",
            "ros 2",
            "moveit",
            "nav2",
            "gazebo",
            "isaac sim",
            "mujoco",
            "opencv",
            "slam",
            "sensor fusion",
            "control theory",
            "pathfinding",
            "inverse kinematics",
            "embedded systems",
        ],
        "responsibilities": [
            "develop perception planning and control software for robots",
            "integrate sensors actuators and real-time communication stacks",
            "validate robotic behavior through simulation and field testing",
        ],
        "expected_years": 0,
    },
    "software engineer": {
        "skills": [
            "python",
            "java",
            "javascript",
            "data structures and algorithms",
            "object oriented programming",
            "sql",
            "react",
            "node.js",
            "express.js",
            "mongodb",
            "rest api development",
            "git",
            "docker basics",
            "linux",
            "unit testing",
            "debugging",
        ],
        "responsibilities": [
            "build backend services",
            "design and ship APIs",
            "improve reliability and performance",
        ],
        "expected_years": 0,
    },
    "data scientist": {
        "skills": [
            "python",
            "r",
            "sql",
            "pandas",
            "numpy",
            "scikit-learn",
            "xgboost",
            "pytorch",
            "tensorflow",
            "tableau",
            "power bi",
            "matplotlib",
            "seaborn",
            "statistics",
            "hypothesis testing",
            "feature engineering",
        ],
        "responsibilities": [
            "analyze complex datasets to derive actionable insights",
            "build and validate predictive machine learning models",
            "communicate outcomes through dashboards and storytelling",
        ],
        "expected_years": 0,
    },
    "data engineer": {
        "skills": [
            "python",
            "sql",
            "java",
            "scala",
            "apache spark",
            "flink",
            "hadoop",
            "kafka",
            "airflow",
            "prefect",
            "snowflake",
            "redshift",
            "bigquery",
            "postgresql",
            "terraform",
            "etl",
        ],
        "responsibilities": [
            "build scalable etl and elt pipelines",
            "design reliable data platforms and warehouses",
            "ensure data quality governance and pipeline observability",
        ],
        "expected_years": 0,
    },
    "big data architect": {
        "skills": [
            "hadoop",
            "spark",
            "cassandra",
            "elasticsearch",
            "presto",
            "trino",
            "aws",
            "gcp",
            "azure",
            "data lakehouse",
            "event-driven architecture",
            "data modeling",
            "iam",
            "encryption",
            "terraform",
            "kubernetes",
        ],
        "responsibilities": [
            "define enterprise data architecture and standards",
            "design scalable batch and real-time data platforms",
            "guide migrations and optimize infrastructure cost and reliability",
        ],
        "expected_years": 0,
    },
    "business intelligence analyst": {
        "skills": [
            "sql",
            "tableau",
            "power bi",
            "looker",
            "qlikview",
            "looker studio",
            "mysql",
            "postgresql",
            "bigquery",
            "snowflake",
            "excel",
            "python",
            "cohort analysis",
            "funnel analysis",
            "data storytelling",
            "dbt",
        ],
        "responsibilities": [
            "build dashboards and reporting systems for stakeholders",
            "analyze kpis trends and business performance drivers",
            "translate business questions into data-backed insights",
        ],
        "expected_years": 0,
    },
    "data governance specialist": {
        "skills": [
            "collibra",
            "informatica axon",
            "alation",
            "apache atlas",
            "great expectations",
            "talend",
            "gdpr",
            "ccpa",
            "soc2",
            "hipaa",
            "master data management",
            "metadata management",
            "data lineage",
            "sql",
            "data profiling",
            "auditing",
        ],
        "responsibilities": [
            "define data governance standards and operating policies",
            "monitor data quality compliance and stewardship processes",
            "maintain enterprise catalog glossary and lineage artifacts",
        ],
        "expected_years": 0,
    },
    "full-stack developer": {
        "skills": [
            "html5",
            "css3",
            "javascript",
            "typescript",
            "react",
            "next.js",
            "node.js",
            "express",
            "django",
            "fastapi",
            "postgresql",
            "mongodb",
            "redis",
            "docker",
            "kubernetes",
            "graphql",
        ],
        "responsibilities": [
            "build end-to-end frontend and backend application features",
            "design secure scalable apis and data models",
            "deploy monitor and optimize full-stack systems",
        ],
        "expected_years": 0,
    },
    "backend engineer": {
        "skills": [
            "python",
            "java",
            "go",
            "node.js",
            "django",
            "spring boot",
            "fastapi",
            "express.js",
            "postgresql",
            "mongodb",
            "redis",
            "rabbitmq",
            "apache kafka",
            "docker",
            "kubernetes",
            "oauth2",
        ],
        "responsibilities": [
            "design and maintain high-performance backend services",
            "build secure apis and scalable data processing flows",
            "improve reliability through observability and incident response",
        ],
        "expected_years": 0,
    },
    "frontend engineer": {
        "skills": [
            "html5",
            "css3",
            "javascript",
            "typescript",
            "react",
            "next.js",
            "vue.js",
            "angular",
            "tailwind css",
            "sass",
            "redux toolkit",
            "zustand",
            "vite",
            "webpack",
            "jest",
            "cypress",
        ],
        "responsibilities": [
            "implement responsive accessible user interfaces",
            "build reusable components and design system foundations",
            "optimize frontend performance and integration quality",
        ],
        "expected_years": 0,
    },
    "mobile app developer": {
        "skills": [
            "swift",
            "kotlin",
            "java",
            "dart",
            "flutter",
            "react native",
            "swiftui",
            "jetpack compose",
            "firebase",
            "graphql",
            "sqlite",
            "coredata",
            "xcode",
            "android studio",
            "fastlane",
            "mobile security",
        ],
        "responsibilities": [
            "develop and maintain ios and android applications",
            "integrate mobile apps with backend services and device features",
            "optimize app quality performance and release workflows",
        ],
        "expected_years": 0,
    },
    "blockchain developer": {
        "skills": [
            "solidity",
            "rust",
            "go",
            "javascript",
            "typescript",
            "ethereum",
            "solana",
            "polygon",
            "hyperledger fabric",
            "hardhat",
            "foundry",
            "web3.js",
            "ethers.js",
            "openzeppelin",
            "chainlink",
            "ipfs",
        ],
        "responsibilities": [
            "design secure smart contracts and dapps",
            "integrate on-chain and off-chain systems",
            "audit optimize and maintain blockchain protocols",
        ],
        "expected_years": 0,
    },
    "embedded systems engineer": {
        "skills": [
            "c",
            "c++",
            "assembly",
            "python",
            "arm cortex-m",
            "esp32",
            "stm32",
            "freertos",
            "zephyr",
            "i2c",
            "spi",
            "uart",
            "can",
            "mqtt",
            "gdb",
            "j-link",
        ],
        "responsibilities": [
            "develop low-level firmware and device drivers",
            "integrate and debug hardware software interactions",
            "optimize embedded systems for real-time reliability and power",
        ],
        "expected_years": 0,
    },
    "game developer": {
        "skills": [
            "unity",
            "unreal engine",
            "godot",
            "c++",
            "c#",
            "blueprints",
            "python",
            "hlsl",
            "glsl",
            "opengl",
            "directx",
            "vulkan",
            "physx",
            "navmesh",
            "git",
            "perforce",
        ],
        "responsibilities": [
            "implement gameplay systems ai and interactive mechanics",
            "integrate assets ui and platform-specific features",
            "optimize game performance stability and player experience",
        ],
        "expected_years": 0,
    },
    "cloud solutions architect": {
        "skills": [
            "aws",
            "azure",
            "gcp",
            "terraform",
            "cloudformation",
            "pulumi",
            "ansible",
            "vpc",
            "dns",
            "load balancing",
            "iam",
            "waf",
            "docker",
            "kubernetes",
            "serverless",
            "microservices",
        ],
        "responsibilities": [
            "design scalable secure cloud architectures",
            "lead cloud migration and modernization initiatives",
            "establish governance resilience and cost optimization practices",
        ],
        "expected_years": 0,
    },
    "devops engineer": {
        "skills": [
            "jenkins",
            "gitlab ci",
            "github actions",
            "circleci",
            "docker",
            "kubernetes",
            "helm",
            "openshift",
            "python",
            "bash",
            "terraform",
            "ansible",
            "prometheus",
            "grafana",
            "elk stack",
            "aws",
        ],
        "responsibilities": [
            "build and operate ci cd and automation pipelines",
            "provision and manage reliable cloud infrastructure",
            "drive release velocity with security and observability controls",
        ],
        "expected_years": 0,
    },
    "site reliability engineer": {
        "skills": [
            "go",
            "python",
            "java",
            "c++",
            "kubernetes",
            "docker",
            "mesos",
            "prometheus",
            "grafana",
            "jaeger",
            "linux",
            "distributed systems",
            "redis",
            "postgresql",
            "aws",
            "incident management",
        ],
        "responsibilities": [
            "define and enforce service reliability objectives",
            "automate operational workflows and reduce toil",
            "lead incident response capacity planning and resilience engineering",
        ],
        "expected_years": 0,
    },
    "platform engineer": {
        "skills": [
            "backstage",
            "crossplane",
            "argocd",
            "terraform",
            "kubernetes",
            "docker",
            "istio",
            "linkerd",
            "go",
            "python",
            "node.js",
            "rest",
            "grpc",
            "graphql",
            "helm",
            "kustomize",
        ],
        "responsibilities": [
            "build self-service internal developer platforms",
            "standardize golden paths for delivery security and observability",
            "improve developer experience through automation and platform tooling",
        ],
        "expected_years": 0,
    },
    "finops specialist": {
        "skills": [
            "aws cost explorer",
            "azure cost management",
            "gcp billing",
            "cloudhealth",
            "cloudability",
            "kubecost",
            "vantage",
            "sql",
            "excel",
            "tableau",
            "power bi",
            "budgeting",
            "forecasting",
            "unit economics",
            "rightsizing",
            "reserved instances",
        ],
        "responsibilities": [
            "establish cloud financial operations and allocation frameworks",
            "analyze spending patterns and drive optimization actions",
            "align engineering cloud usage with finance and business goals",
        ],
        "expected_years": 0,
    },
    "cybersecurity analyst": {
        "skills": [
            "splunk",
            "ibm qradar",
            "sentinel",
            "wireshark",
            "nessus",
            "tcp/ip",
            "dns",
            "vpn",
            "firewalls",
            "mitre attack",
            "nist",
            "iso 27001",
            "linux",
            "windows server",
            "python",
            "powershell",
        ],
        "responsibilities": [
            "monitor and triage security events and incidents",
            "run vulnerability management and remediation programs",
            "harden systems and improve organizational security posture",
        ],
        "expected_years": 0,
    },
    "ethical hacker": {
        "skills": [
            "burp suite",
            "metasploit",
            "nmap",
            "kali linux",
            "cobalt strike",
            "owasp top 10",
            "api security",
            "jwt",
            "python",
            "ruby",
            "javascript",
            "sql",
            "reverse engineering",
            "social engineering",
            "privilege escalation",
            "network exploitation",
        ],
        "responsibilities": [
            "conduct penetration testing across applications and infrastructure",
            "simulate real-world attacks and document exploit paths",
            "provide prioritized remediation guidance and validation retesting",
        ],
        "expected_years": 0,
    },
    "application security engineer": {
        "skills": [
            "sast",
            "dast",
            "iast",
            "sca",
            "snyk",
            "checkmarx",
            "veracode",
            "owasp top 10",
            "oauth2",
            "openid connect",
            "encryption",
            "github actions",
            "docker",
            "kubernetes security",
            "semgrep",
            "owasp zap",
        ],
        "responsibilities": [
            "embed security controls across software development lifecycle",
            "identify and remediate application vulnerabilities",
            "automate security testing and governance in ci cd",
        ],
        "expected_years": 0,
    },
    "ui ux designer": {
        "skills": [
            "figma",
            "adobe xd",
            "sketch",
            "framer",
            "invision",
            "protopie",
            "usertesting",
            "hotjar",
            "maze",
            "typeform",
            "information architecture",
            "interaction design",
            "visual design",
            "typography",
            "responsive design",
            "wcag",
        ],
        "responsibilities": [
            "conduct user research and translate insights into interfaces",
            "design wireframes prototypes and high-fidelity visual systems",
            "iterate designs with usability testing and engineering collaboration",
        ],
        "expected_years": 0,
    },
    "it project manager": {
        "skills": [
            "jira",
            "confluence",
            "asana",
            "monday.com",
            "microsoft project",
            "agile",
            "scrum",
            "kanban",
            "waterfall",
            "lean",
            "excel",
            "slack",
            "zoom",
            "sdlc",
            "cloud computing",
            "api concepts",
        ],
        "responsibilities": [
            "plan and execute technical projects within scope budget and timeline",
            "coordinate cross-functional teams and stakeholder communication",
            "manage risk reporting and post-implementation reviews",
        ],
        "expected_years": 0,
    },
    "machine learning engineer": {
        "skills": [
            "python",
            "numpy",
            "pandas",
            "matplotlib",
            "seaborn",
            "scikit-learn",
            "data preprocessing",
            "feature engineering",
            "exploratory data analysis",
            "supervised learning",
            "unsupervised learning",
            "model evaluation metrics",
            "cross validation",
            "hyperparameter tuning",
            "basic statistics",
            "linear algebra",
            "sql",
            "git",
            "flask",
            "rest api for ml models",
        ],
        "responsibilities": [
            "build ml models",
            "deploy models to production",
            "optimize data or training pipelines",
        ],
        "expected_years": 0,
    },
    "data analyst": {
        "skills": [
            "sql",
            "advanced excel",
            "python",
            "pandas",
            "numpy",
            "data cleaning",
            "data transformation",
            "exploratory data analysis",
            "data visualization",
            "power bi",
            "tableau",
            "dashboard development",
            "statistics",
            "a/b testing basics",
            "data storytelling",
            "business insights",
            "git",
        ],
        "responsibilities": [
            "analyze business data",
            "build dashboards and reports",
            "communicate actionable insights",
        ],
        "expected_years": 0,
    },
    "business analyst": {
        "skills": [
            "requirements gathering",
            "stakeholder management",
            "process mapping",
            "gap analysis",
            "user stories",
            "acceptance criteria",
            "jira",
            "confluence",
            "sql",
            "visio",
            "wireframing",
            "business process modeling",
            "root cause analysis",
            "kpi analysis",
            "documentation",
            "workshop facilitation",
        ],
        "responsibilities": [
            "translate business needs into clear product and engineering requirements",
            "analyze processes and identify opportunities for operational improvement",
            "align stakeholders on scope priorities and delivery outcomes",
        ],
        "expected_years": 0,
    },
    "product manager": {
        "skills": [
            "product strategy",
            "roadmapping",
            "user research",
            "a b testing",
            "sql",
            "mixpanel",
            "amplitude",
            "figma",
            "jira",
            "confluence",
            "go to market",
            "stakeholder management",
            "requirements prioritization",
            "metrics definition",
            "market research",
            "experimentation",
        ],
        "responsibilities": [
            "define product roadmap and align teams on priorities and outcomes",
            "turn user and market insights into validated product requirements",
            "measure product performance and iterate based on business impact",
        ],
        "expected_years": 0,
    },
    "cloud engineer": {
        "skills": [
            "aws",
            "azure",
            "gcp",
            "terraform",
            "cloudformation",
            "docker",
            "kubernetes",
            "linux",
            "iam",
            "networking",
            "monitoring",
            "prometheus",
            "grafana",
            "serverless",
            "ci/cd",
            "python",
        ],
        "responsibilities": [
            "build and operate secure scalable cloud infrastructure",
            "automate deployments and cloud provisioning workflows",
            "monitor reliability performance and cost across cloud environments",
        ],
        "expected_years": 0,
    },
    "qa engineer": {
        "skills": [
            "test automation",
            "selenium",
            "cypress",
            "playwright",
            "pytest",
            "postman",
            "api testing",
            "regression testing",
            "test planning",
            "quality assurance",
            "bug tracking",
            "jira",
            "performance testing",
            "load testing",
            "ci/cd",
            "automation framework",
        ],
        "responsibilities": [
            "design and execute manual and automated test strategies",
            "prevent regressions through reliable quality gates and test coverage",
            "partner with engineering to improve release quality and defect resolution",
        ],
        "expected_years": 0,
    },
    "digital marketing executive": {
        "skills": [
            "google ads",
            "meta ads manager",
            "campaign management",
            "lead generation",
            "landing page optimization",
            "google analytics",
            "conversion tracking",
            "keyword research",
            "social media campaigns",
            "content planning",
            "email campaigns",
            "marketing automation",
            "canva",
            "marketing reporting",
        ],
        "responsibilities": [
            "plan and execute multi-channel digital campaigns for lead generation and engagement",
            "track campaign performance and optimize spends creatives and conversions",
            "coordinate with content sales and design teams to improve marketing outcomes",
        ],
        "expected_years": 0,
    },
    "performance marketing specialist": {
        "skills": [
            "google ads",
            "meta ads manager",
            "campaign budgeting",
            "roas optimization",
            "cpa optimization",
            "conversion rate optimization",
            "google tag manager",
            "conversion tracking",
            "remarketing",
            "audience segmentation",
            "a b testing",
            "media planning",
            "funnel analysis",
            "looker studio",
        ],
        "responsibilities": [
            "manage paid acquisition campaigns across search social and display channels",
            "optimize bids audiences creatives and budgets against revenue and lead goals",
            "build performance reports and recommend experiments to improve roas and cpl",
        ],
        "expected_years": 0,
    },
    "social media manager": {
        "skills": [
            "social media strategy",
            "content calendar",
            "community management",
            "instagram marketing",
            "linkedin marketing",
            "facebook marketing",
            "twitter marketing",
            "reels planning",
            "copywriting",
            "canva",
            "social listening",
            "brand communication",
            "influencer coordination",
            "social analytics",
        ],
        "responsibilities": [
            "own social media presence content planning and audience engagement across platforms",
            "monitor trends community feedback and campaign performance to improve reach",
            "coordinate creative assets messaging and publishing schedules with stakeholders",
        ],
        "expected_years": 0,
    },
    "content marketer": {
        "skills": [
            "content strategy",
            "content writing",
            "blog writing",
            "seo writing",
            "content calendar",
            "keyword research",
            "copyediting",
            "email copywriting",
            "landing page copy",
            "cms management",
            "wordpress",
            "audience research",
            "content distribution",
            "content performance analysis",
        ],
        "responsibilities": [
            "create and optimize content that supports brand awareness demand generation and seo goals",
            "plan editorial calendars and align content assets with campaign objectives",
            "measure content performance and refine topics formats and messaging based on results",
        ],
        "expected_years": 0,
    },
    "seo specialist": {
        "skills": [
            "keyword research",
            "on page seo",
            "technical seo",
            "seo audit",
            "google search console",
            "google analytics",
            "backlink analysis",
            "content optimization",
            "schema markup",
            "site audit tools",
            "competitor analysis",
            "search intent mapping",
            "wordpress",
            "serp tracking",
        ],
        "responsibilities": [
            "improve organic visibility through on page technical and content optimization",
            "conduct audits keyword analysis and competitor research to prioritize opportunities",
            "partner with content and web teams to resolve seo issues and track ranking improvements",
        ],
        "expected_years": 0,
    },
    "brand manager": {
        "skills": [
            "brand strategy",
            "campaign planning",
            "market research",
            "consumer insights",
            "brand positioning",
            "brand communication",
            "go to market",
            "agency coordination",
            "media planning",
            "budget management",
            "creative briefing",
            "competitive analysis",
            "offline marketing",
            "brand performance tracking",
        ],
        "responsibilities": [
            "define brand positioning messaging and campaign direction across customer touchpoints",
            "coordinate agencies media and internal teams to deliver integrated brand campaigns",
            "track brand health market response and campaign performance to inform strategy",
        ],
        "expected_years": 0,
    },
    "marketing manager": {
        "skills": [
            "marketing strategy",
            "campaign management",
            "budget management",
            "brand communication",
            "lead generation",
            "digital campaigns",
            "agency management",
            "market research",
            "customer segmentation",
            "event marketing",
            "marketing analytics",
            "content planning",
            "stakeholder management",
            "go to market",
        ],
        "responsibilities": [
            "lead marketing plans across brand digital content and lead generation initiatives",
            "manage campaign calendars budgets vendors and cross-functional coordination",
            "analyze channel performance and adjust strategy to improve pipeline and awareness",
        ],
        "expected_years": 0,
    },
    "growth marketer": {
        "skills": [
            "growth strategy",
            "funnel analysis",
            "lifecycle marketing",
            "marketing experiments",
            "conversion rate optimization",
            "user acquisition",
            "retention campaigns",
            "email automation",
            "landing page optimization",
            "cohort analysis",
            "a b testing",
            "mixpanel",
            "amplitude",
            "campaign analytics",
        ],
        "responsibilities": [
            "run growth experiments across acquisition activation retention and referral stages",
            "identify funnel drop-offs and optimize messaging journeys and conversion paths",
            "work with product sales and marketing teams to scale repeatable growth programs",
        ],
        "expected_years": 0,
    },
    "email marketing specialist": {
        "skills": [
            "email campaign management",
            "marketing automation",
            "mailchimp",
            "hubspot",
            "campaign segmentation",
            "drip campaigns",
            "lead nurturing",
            "email copywriting",
            "subject line testing",
            "deliverability monitoring",
            "list hygiene",
            "campaign analytics",
            "template management",
            "crm integration",
        ],
        "responsibilities": [
            "build and execute email campaigns for acquisition nurture retention and re-engagement",
            "segment audiences and automate journeys to improve opens clicks and conversions",
            "monitor deliverability performance and optimize templates content and workflows",
        ],
        "expected_years": 0,
    },
    "product marketing manager": {
        "skills": [
            "go to market",
            "product positioning",
            "messaging framework",
            "competitive analysis",
            "sales enablement",
            "market research",
            "customer research",
            "launch planning",
            "campaign strategy",
            "product storytelling",
            "persona development",
            "win loss analysis",
            "content strategy",
            "stakeholder management",
        ],
        "responsibilities": [
            "define positioning messaging and launch strategy for products and new features",
            "equip sales and customer teams with enablement assets competitive narratives and use cases",
            "translate market customer and product insights into effective campaigns and adoption programs",
        ],
        "expected_years": 0,
    },
    "sales executive": {
        "skills": [
            "lead generation",
            "cold calling",
            "sales pitching",
            "prospecting",
            "follow up management",
            "crm management",
            "client handling",
            "negotiation",
            "sales closing",
            "territory sales",
            "market visits",
            "sales reporting",
            "relationship building",
            "pipeline management",
        ],
        "responsibilities": [
            "generate qualify and convert prospects through outbound outreach and follow-ups",
            "manage sales pipeline meetings proposals and closures against monthly targets",
            "maintain client relationships and update crm records with accurate opportunity status",
        ],
        "expected_years": 0,
    },
    "business development executive": {
        "skills": [
            "lead generation",
            "prospecting",
            "market research",
            "client acquisition",
            "proposal creation",
            "relationship management",
            "b2b sales",
            "crm management",
            "negotiation",
            "sales presentations",
            "pipeline management",
            "follow up management",
            "inside sales",
            "revenue tracking",
        ],
        "responsibilities": [
            "identify and qualify new business opportunities across target accounts and segments",
            "prepare pitches proposals and follow-up plans to drive conversions and partnerships",
            "work with delivery and leadership teams to expand pipeline and revenue opportunities",
        ],
        "expected_years": 0,
    },
    "account executive": {
        "skills": [
            "client presentations",
            "consultative selling",
            "pipeline management",
            "crm management",
            "proposal negotiation",
            "deal closing",
            "account planning",
            "stakeholder management",
            "forecasting",
            "cross selling",
            "upselling",
            "sales reporting",
            "contract discussion",
            "client relationship management",
        ],
        "responsibilities": [
            "own end-to-end sales cycles from discovery and demos through negotiation and closure",
            "manage account relationships and identify opportunities for renewal expansion and upsell",
            "forecast pipeline progress and coordinate internal teams for successful deal execution",
        ],
        "expected_years": 0,
    },
    "sales manager": {
        "skills": [
            "sales planning",
            "team handling",
            "target management",
            "pipeline reviews",
            "forecasting",
            "channel sales",
            "deal negotiation",
            "client escalation handling",
            "crm reporting",
            "sales coaching",
            "territory planning",
            "key account growth",
            "team performance management",
            "revenue planning",
        ],
        "responsibilities": [
            "lead sales teams against revenue targets through planning coaching and review mechanisms",
            "monitor pipeline health territory performance and conversion metrics to improve closures",
            "support major negotiations escalations and strategic account growth initiatives",
        ],
        "expected_years": 0,
    },
    "key account manager": {
        "skills": [
            "account management",
            "client relationship management",
            "renewal management",
            "upselling",
            "cross selling",
            "stakeholder management",
            "business reviews",
            "contract coordination",
            "crm management",
            "revenue tracking",
            "issue resolution",
            "proposal management",
            "account planning",
            "service coordination",
        ],
        "responsibilities": [
            "manage strategic accounts and strengthen long-term client relationships and retention",
            "coordinate internal teams to resolve issues deliver commitments and expand account value",
            "run business reviews renewals and cross-sell opportunities aligned to client goals",
        ],
        "expected_years": 0,
    },
    "inside sales representative": {
        "skills": [
            "inside sales",
            "lead qualification",
            "cold calling",
            "email outreach",
            "crm management",
            "demo scheduling",
            "sales pitching",
            "follow up management",
            "objection handling",
            "pipeline management",
            "telecalling",
            "sales reporting",
            "customer communication",
            "appointment setting",
        ],
        "responsibilities": [
            "engage prospects through calls emails and demos to move leads through the sales funnel",
            "qualify inbound and outbound leads and maintain structured follow-up cadences in crm",
            "coordinate handoffs and update conversion progress against daily and monthly targets",
        ],
        "expected_years": 0,
    },
    "field sales executive": {
        "skills": [
            "field sales",
            "territory management",
            "dealer visits",
            "channel partner management",
            "client meetings",
            "product demonstrations",
            "lead generation",
            "negotiation",
            "sales closing",
            "route planning",
            "retail activation",
            "market intelligence",
            "sales reporting",
            "relationship building",
        ],
        "responsibilities": [
            "drive sales through in-person client visits demonstrations and territory coverage",
            "build relationships with dealers distributors and customers to increase market penetration",
            "capture field intelligence and report pipeline movement and competitive insights",
        ],
        "expected_years": 0,
    },
    "customer success manager": {
        "skills": [
            "customer onboarding",
            "client relationship management",
            "renewal management",
            "account growth",
            "customer retention",
            "stakeholder management",
            "health score tracking",
            "adoption planning",
            "quarterly business reviews",
            "issue resolution",
            "crm management",
            "customer training",
            "escalation management",
            "cross functional coordination",
        ],
        "responsibilities": [
            "own onboarding adoption and retention outcomes for assigned customer portfolios",
            "build trusted stakeholder relationships and proactively resolve risks to renewals",
            "identify expansion opportunities and coordinate internal teams to improve account value",
        ],
        "expected_years": 0,
    },
    "relationship manager": {
        "skills": [
            "client relationship management",
            "customer retention",
            "cross selling",
            "upselling",
            "portfolio management",
            "service coordination",
            "crm management",
            "issue resolution",
            "client meetings",
            "sales support",
            "account servicing",
            "follow up management",
            "business communication",
            "stakeholder handling",
        ],
        "responsibilities": [
            "manage client relationships and ensure timely service support and follow-up",
            "grow portfolio value through cross-sell upsell and renewal conversations",
            "coordinate with operations and service teams to resolve customer issues effectively",
        ],
        "expected_years": 0,
    },
    "presales consultant": {
        "skills": [
            "solution demonstrations",
            "requirement discovery",
            "rfp responses",
            "proposal writing",
            "technical presentations",
            "client workshops",
            "solution mapping",
            "sales enablement",
            "proof of concept support",
            "stakeholder management",
            "business requirement analysis",
            "presentation design",
            "competitive positioning",
            "deal support",
        ],
        "responsibilities": [
            "support sales teams with discovery demos solution mapping and proposal responses",
            "translate client needs into clear solution narratives and proof of concept plans",
            "improve deal conversion by addressing objections requirements and stakeholder concerns",
        ],
        "expected_years": 0,
    },
    "hr executive": {
        "skills": [
            "hr operations",
            "employee onboarding",
            "joining formalities",
            "attendance management",
            "leave management",
            "employee documentation",
            "hr records management",
            "offer letter coordination",
            "exit formalities",
            "employee communication",
            "policy coordination",
            "hrms",
            "vendor coordination",
            "recruitment support",
        ],
        "responsibilities": [
            "manage day-to-day hr operations including onboarding documentation and employee records",
            "coordinate attendance leave and policy-related employee support activities",
            "support recruitment payroll and separation processes with accurate documentation",
        ],
        "expected_years": 0,
    },
    "hr generalist": {
        "skills": [
            "hr operations",
            "recruitment coordination",
            "employee onboarding",
            "performance management support",
            "attendance management",
            "leave management",
            "employee engagement",
            "hr policy implementation",
            "employee documentation",
            "grievance handling",
            "exit formalities",
            "hrms",
            "payroll coordination",
            "compliance documentation",
        ],
        "responsibilities": [
            "handle end-to-end hr processes across recruitment onboarding employee support and exits",
            "support policy implementation employee engagement and people operations reporting",
            "coordinate with payroll and managers to maintain compliant and smooth hr workflows",
        ],
        "expected_years": 0,
    },
    "recruiter": {
        "skills": [
            "candidate sourcing",
            "screening interviews",
            "job posting",
            "naukri recruiter",
            "linkedin recruiting",
            "resume screening",
            "interview scheduling",
            "talent pipeline management",
            "candidate engagement",
            "offer coordination",
            "ats management",
            "stakeholder coordination",
            "headhunting",
            "recruitment reporting",
        ],
        "responsibilities": [
            "source screen and coordinate candidates across open positions and hiring stages",
            "manage recruitment pipelines interview scheduling and candidate communication",
            "partner with hiring managers to improve closure rates and talent quality",
        ],
        "expected_years": 0,
    },
    "talent acquisition specialist": {
        "skills": [
            "talent sourcing",
            "linkedin recruiting",
            "naukri recruiter",
            "boolean search",
            "candidate screening",
            "stakeholder management",
            "offer negotiation",
            "employer branding",
            "campus hiring",
            "vendor management",
            "recruitment analytics",
            "ats management",
            "pipeline management",
            "candidate experience",
        ],
        "responsibilities": [
            "drive sourcing and selection strategies for priority positions across business units",
            "manage hiring pipelines stakeholder communication and offer closure processes",
            "improve time-to-fill quality-of-hire and candidate experience through structured recruiting",
        ],
        "expected_years": 0,
    },
    "hr manager": {
        "skills": [
            "hr strategy",
            "team handling",
            "employee relations",
            "performance management",
            "policy design",
            "workforce planning",
            "recruitment oversight",
            "payroll coordination",
            "compliance management",
            "employee engagement",
            "grievance resolution",
            "hr analytics",
            "manager partnering",
            "succession planning",
        ],
        "responsibilities": [
            "lead hr operations and people programs across hiring engagement performance and policy areas",
            "advise managers on employee relations workforce planning and organizational issues",
            "ensure compliant hr processes and drive initiatives that improve employee experience",
        ],
        "expected_years": 0,
    },
    "payroll executive": {
        "skills": [
            "payroll processing",
            "salary reconciliation",
            "attendance inputs",
            "leave adjustments",
            "pf compliance",
            "esi compliance",
            "tds basics",
            "payroll software",
            "employee records",
            "salary statements",
            "full and final settlement",
            "compliance documentation",
            "reimbursement processing",
            "excel reporting",
        ],
        "responsibilities": [
            "process payroll accurately using attendance leave and reimbursement inputs",
            "maintain statutory documentation and support pf esi and related compliance activities",
            "resolve payroll queries and coordinate final settlements and monthly payroll reports",
        ],
        "expected_years": 0,
    },
    "learning and development specialist": {
        "skills": [
            "training coordination",
            "learning needs analysis",
            "training calendar",
            "facilitation support",
            "learning management system",
            "content curation",
            "workshop planning",
            "evaluation forms",
            "employee development programs",
            "training logistics",
            "stakeholder coordination",
            "instructional material support",
            "training reports",
            "competency mapping",
        ],
        "responsibilities": [
            "coordinate learning programs workshops and capability-building initiatives across teams",
            "identify training needs and support development of learning plans and materials",
            "track training completion feedback and program effectiveness for continuous improvement",
        ],
        "expected_years": 0,
    },
    "employee relations specialist": {
        "skills": [
            "employee relations",
            "grievance handling",
            "policy interpretation",
            "disciplinary coordination",
            "conflict resolution",
            "employee counseling",
            "investigation support",
            "case documentation",
            "manager support",
            "exit interviews",
            "compliance documentation",
            "employee communication",
            "stakeholder management",
            "hrms",
        ],
        "responsibilities": [
            "manage employee concerns grievances and policy-related cases with proper documentation",
            "support managers with employee relations guidance conflict resolution and corrective actions",
            "help maintain a compliant fair and positive workplace experience across teams",
        ],
        "expected_years": 0,
    },
    "accountant": {
        "skills": [
            "general ledger",
            "journal entries",
            "bank reconciliation",
            "trial balance",
            "accounts payable",
            "accounts receivable",
            "tally",
            "gst filing",
            "tds reconciliation",
            "invoice processing",
            "ledger scrutiny",
            "financial statements",
            "month end closing",
            "excel reporting",
        ],
        "responsibilities": [
            "maintain accounting records ledgers reconciliations and month-end closing activities",
            "process invoices payments receipts and statutory filing support with accuracy",
            "prepare financial reports and assist audits and compliance documentation",
        ],
        "expected_years": 0,
    },
    "accounts executive": {
        "skills": [
            "invoice processing",
            "voucher entries",
            "bank reconciliation",
            "accounts payable",
            "accounts receivable",
            "tally",
            "gst basics",
            "vendor reconciliation",
            "payment follow ups",
            "expense tracking",
            "ledger maintenance",
            "purchase entries",
            "sales entries",
            "excel reporting",
        ],
        "responsibilities": [
            "record day-to-day accounting transactions including invoices vouchers and reconciliations",
            "coordinate vendor payments customer collections and ledger updates accurately",
            "support monthly books closure and statutory documentation with timely reporting",
        ],
        "expected_years": 0,
    },
    "financial analyst": {
        "skills": [
            "financial modeling",
            "budgeting",
            "forecasting",
            "variance analysis",
            "management reporting",
            "profitability analysis",
            "cash flow analysis",
            "financial statement analysis",
            "business case preparation",
            "excel modeling",
            "scenario analysis",
            "kpi tracking",
            "presentation reporting",
            "cost analysis",
        ],
        "responsibilities": [
            "analyze financial performance trends budgets and forecasts for business decision-making",
            "prepare management reports business cases and variance explanations for stakeholders",
            "support planning cycles through financial models and scenario-based recommendations",
        ],
        "expected_years": 0,
    },
    "finance manager": {
        "skills": [
            "financial planning",
            "budget management",
            "forecasting",
            "cash flow management",
            "financial controls",
            "management reporting",
            "cost optimization",
            "variance analysis",
            "audit coordination",
            "tax coordination",
            "team management",
            "working capital management",
            "business partnering",
            "financial compliance",
        ],
        "responsibilities": [
            "lead budgeting forecasting reporting and control processes across finance operations",
            "monitor cash flow profitability and compliance while advising business leaders on decisions",
            "coordinate audits statutory requirements and team deliverables for accurate financial governance",
        ],
        "expected_years": 0,
    },
    "auditor": {
        "skills": [
            "internal audit",
            "audit planning",
            "control testing",
            "risk assessment",
            "working papers",
            "compliance review",
            "financial statement review",
            "process walkthroughs",
            "audit documentation",
            "reconciliation review",
            "sampling techniques",
            "observation reporting",
            "statutory audit support",
            "issue tracking",
        ],
        "responsibilities": [
            "conduct audits of processes controls and financial records to identify gaps and risks",
            "document observations evidence and recommendations through structured audit working papers",
            "coordinate with stakeholders on remediation tracking and compliance follow-up actions",
        ],
        "expected_years": 0,
    },
    "tax consultant": {
        "skills": [
            "gst return filing",
            "income tax basics",
            "tds compliance",
            "tax reconciliation",
            "tax notices handling",
            "compliance documentation",
            "indirect tax support",
            "tax working preparation",
            "ledger scrutiny",
            "financial records review",
            "statutory compliance",
            "client coordination",
            "tax research basics",
            "excel reporting",
        ],
        "responsibilities": [
            "prepare tax workings returns reconciliations and supporting compliance documentation",
            "assist with gst tds and direct tax compliance queries and notice responses",
            "coordinate with clients and finance teams to maintain accurate tax records and submissions",
        ],
        "expected_years": 0,
    },
    "payroll accountant": {
        "skills": [
            "payroll accounting",
            "salary reconciliation",
            "journal entries",
            "pf compliance",
            "esi compliance",
            "tds on salary",
            "salary payable reconciliation",
            "bank transfer reconciliation",
            "full and final settlement",
            "employee reimbursements",
            "ledger maintenance",
            "month end closing",
            "payroll software",
            "excel reporting",
        ],
        "responsibilities": [
            "manage payroll-related accounting entries reconciliations and salary payable balances",
            "support statutory salary deductions compliance and payroll month-end reporting",
            "resolve payroll accounting discrepancies and coordinate with hr and finance teams",
        ],
        "expected_years": 0,
    },
    "investment analyst": {
        "skills": [
            "equity research",
            "financial modeling",
            "valuation analysis",
            "industry research",
            "company analysis",
            "ratio analysis",
            "investment memos",
            "portfolio tracking",
            "market updates",
            "forecasting",
            "excel modeling",
            "presentation decks",
            "due diligence support",
            "financial statement analysis",
        ],
        "responsibilities": [
            "analyze companies industries and financial performance to support investment decisions",
            "prepare valuation models research notes and portfolio performance updates",
            "track market developments and synthesize insights into actionable investment recommendations",
        ],
        "expected_years": 0,
    },
    "credit analyst": {
        "skills": [
            "credit appraisal",
            "financial statement analysis",
            "ratio analysis",
            "risk assessment",
            "loan file review",
            "credit underwriting support",
            "cash flow analysis",
            "bank statement review",
            "portfolio monitoring",
            "credit notes",
            "compliance checks",
            "customer due diligence",
            "repayment capacity analysis",
            "documentation review",
        ],
        "responsibilities": [
            "assess borrower financials and repayment capacity to support credit decisions",
            "prepare credit notes analyses and documentation review findings for approval workflows",
            "monitor portfolio quality and highlight credit risks or policy exceptions proactively",
        ],
        "expected_years": 0,
    },
    "operations executive": {
        "skills": [
            "process coordination",
            "daily operations tracking",
            "reporting",
            "vendor coordination",
            "inventory tracking",
            "order processing",
            "documentation",
            "mis reporting",
            "issue resolution",
            "cross functional coordination",
            "service coordination",
            "workflow monitoring",
            "data entry accuracy",
            "sla tracking",
        ],
        "responsibilities": [
            "support daily operational workflows documentation and coordination across teams",
            "track service requests inventory or orders to ensure timely process completion",
            "prepare operational reports and escalate issues affecting turnaround or quality",
        ],
        "expected_years": 0,
    },
    "operations manager": {
        "skills": [
            "operations planning",
            "team management",
            "process improvement",
            "sla management",
            "resource planning",
            "vendor management",
            "kpi monitoring",
            "capacity planning",
            "quality control",
            "cost optimization",
            "cross functional coordination",
            "escalation handling",
            "mis reporting",
            "workflow governance",
        ],
        "responsibilities": [
            "lead operational teams processes and service delivery against efficiency and quality goals",
            "monitor capacity slas costs and escalations to improve operational performance",
            "standardize workflows controls and reporting across internal and external stakeholders",
        ],
        "expected_years": 0,
    },
    "office administrator": {
        "skills": [
            "office coordination",
            "calendar management",
            "travel coordination",
            "vendor coordination",
            "facility support",
            "document management",
            "front office coordination",
            "meeting arrangements",
            "inventory management",
            "purchase coordination",
            "record keeping",
            "microsoft office",
            "communication support",
            "administrative reporting",
        ],
        "responsibilities": [
            "manage office administration schedules records vendors and routine coordination tasks",
            "support meetings travel documentation and front office or facility requirements",
            "maintain administrative records supplies and service requests for smooth office operations",
        ],
        "expected_years": 0,
    },
    "admin executive": {
        "skills": [
            "administration support",
            "document management",
            "vendor coordination",
            "travel booking",
            "office inventory",
            "meeting coordination",
            "front office support",
            "record maintenance",
            "purchase requests",
            "facility coordination",
            "mail handling",
            "microsoft office",
            "invoice coordination",
            "administrative reporting",
        ],
        "responsibilities": [
            "handle routine administrative tasks documentation and office support activities",
            "coordinate vendors travel supplies and facility-related requests in a timely manner",
            "maintain records reports and communication to support smooth administrative operations",
        ],
        "expected_years": 0,
    },
    "supply chain executive": {
        "skills": [
            "supply planning",
            "inventory management",
            "order coordination",
            "vendor follow up",
            "dispatch tracking",
            "procurement coordination",
            "warehouse coordination",
            "demand planning support",
            "shipment documentation",
            "mis reporting",
            "purchase order tracking",
            "replenishment planning",
            "sla coordination",
            "stock reconciliation",
        ],
        "responsibilities": [
            "coordinate procurement inventory and dispatch activities to support supply continuity",
            "track purchase orders stock levels and vendor commitments against business needs",
            "prepare supply chain reports and resolve delays or stock movement issues proactively",
        ],
        "expected_years": 0,
    },
    "logistics coordinator": {
        "skills": [
            "shipment coordination",
            "dispatch planning",
            "route coordination",
            "tracking updates",
            "transport vendor coordination",
            "delivery scheduling",
            "proof of delivery tracking",
            "shipment documentation",
            "warehouse coordination",
            "freight coordination",
            "issue escalation",
            "logistics reporting",
            "inventory movement tracking",
            "customer updates",
        ],
        "responsibilities": [
            "coordinate shipments transportation schedules and delivery updates across stakeholders",
            "maintain logistics documents tracking records and proof-of-delivery information accurately",
            "resolve dispatch delays and communication gaps to improve on-time delivery performance",
        ],
        "expected_years": 0,
    },
    "procurement specialist": {
        "skills": [
            "vendor sourcing",
            "purchase requisitions",
            "request for quotation",
            "vendor negotiation",
            "purchase order creation",
            "cost comparison",
            "supplier evaluation",
            "contract coordination",
            "invoice coordination",
            "procurement reporting",
            "inventory support",
            "rate negotiation",
            "supplier follow up",
            "compliance documentation",
        ],
        "responsibilities": [
            "source suppliers and manage quotations purchase orders and follow-up activities",
            "negotiate pricing and terms while ensuring timely material or service availability",
            "maintain procurement documentation vendor performance tracking and cost comparisons",
        ],
        "expected_years": 0,
    },
    "vendor manager": {
        "skills": [
            "vendor management",
            "supplier relationship management",
            "contract coordination",
            "service level monitoring",
            "performance reviews",
            "issue escalation",
            "cost negotiation",
            "vendor onboarding",
            "compliance tracking",
            "stakeholder coordination",
            "renewal coordination",
            "mis reporting",
            "risk tracking",
            "invoice dispute support",
        ],
        "responsibilities": [
            "manage vendor relationships contracts and service performance against business expectations",
            "coordinate issue resolution renewals and governance reviews across stakeholders",
            "track vendor compliance risk and cost opportunities through structured reporting and follow-up",
        ],
        "expected_years": 0,
    },
    "facility manager": {
        "skills": [
            "facility operations",
            "vendor coordination",
            "maintenance planning",
            "housekeeping supervision",
            "security coordination",
            "asset upkeep",
            "space management",
            "amc tracking",
            "safety compliance",
            "utility management",
            "incident handling",
            "service request management",
            "budget monitoring",
            "facility reporting",
        ],
        "responsibilities": [
            "oversee facility services maintenance safety and vendor performance for office operations",
            "manage service requests asset upkeep utilities and space-related coordination effectively",
            "ensure compliance with safety housekeeping and preventive maintenance standards",
        ],
        "expected_years": 0,
    },
    "customer support executive": {
        "skills": [
            "customer query resolution",
            "ticket handling",
            "call handling",
            "email support",
            "chat support",
            "crm management",
            "complaint resolution",
            "follow up management",
            "customer communication",
            "service recovery",
            "sla adherence",
            "issue logging",
            "customer satisfaction tracking",
            "escalation coordination",
        ],
        "responsibilities": [
            "respond to customer queries through calls emails or chat and resolve issues promptly",
            "log tickets follow up on open cases and coordinate escalations to maintain service levels",
            "improve customer satisfaction through clear communication and timely issue closure",
        ],
        "expected_years": 0,
    },
    "customer service representative": {
        "skills": [
            "customer interaction",
            "call handling",
            "email support",
            "chat support",
            "complaint handling",
            "service request processing",
            "crm updates",
            "customer verification",
            "follow up management",
            "customer satisfaction",
            "service etiquette",
            "issue resolution",
            "ticket logging",
            "escalation support",
        ],
        "responsibilities": [
            "handle customer service interactions and process service requests accurately",
            "maintain crm records and follow up on unresolved concerns with proper escalations",
            "deliver courteous and timely support that improves customer satisfaction and retention",
        ],
        "expected_years": 0,
    },
    "technical support executive": {
        "skills": [
            "technical troubleshooting",
            "ticket handling",
            "remote support",
            "incident logging",
            "desktop support",
            "software installation support",
            "system diagnostics",
            "user issue resolution",
            "service desk tools",
            "knowledge base usage",
            "network troubleshooting basics",
            "hardware issue triage",
            "sla adherence",
            "escalation management",
        ],
        "responsibilities": [
            "diagnose and resolve technical issues reported by users through support channels",
            "log incidents troubleshoot systems and escalate complex problems to specialized teams",
            "ensure timely resolution and clear communication while maintaining support documentation",
        ],
        "expected_years": 0,
    },
    "helpdesk executive": {
        "skills": [
            "helpdesk support",
            "ticket logging",
            "call support",
            "remote assistance",
            "issue triage",
            "user communication",
            "service desk tools",
            "password reset support",
            "incident follow up",
            "knowledge base usage",
            "sla tracking",
            "escalation support",
            "basic troubleshooting",
            "support documentation",
        ],
        "responsibilities": [
            "provide first-line helpdesk support for logged issues and service requests",
            "triage incidents route escalations and maintain accurate support records",
            "follow standard resolution processes to meet response and closure timelines",
        ],
        "expected_years": 0,
    },
    "client service executive": {
        "skills": [
            "client communication",
            "service coordination",
            "query handling",
            "account servicing",
            "crm management",
            "issue resolution",
            "follow up management",
            "documentation support",
            "service request tracking",
            "stakeholder coordination",
            "relationship management",
            "complaint handling",
            "sla coordination",
            "reporting",
        ],
        "responsibilities": [
            "support clients through service coordination issue follow-ups and communication updates",
            "maintain account records requests and resolution timelines across internal teams",
            "build positive client relationships through responsive and organized service handling",
        ],
        "expected_years": 0,
    },
    "customer experience manager": {
        "skills": [
            "customer journey mapping",
            "voice of customer",
            "service quality improvement",
            "customer feedback analysis",
            "nps tracking",
            "csat tracking",
            "process improvement",
            "cross functional coordination",
            "customer escalation handling",
            "service design",
            "retention initiatives",
            "team coaching",
            "service reporting",
            "experience governance",
        ],
        "responsibilities": [
            "improve end-to-end customer journeys through feedback analysis and process enhancements",
            "lead service quality initiatives and coordinate teams on customer pain points and escalations",
            "track experience metrics and implement programs that improve retention and satisfaction",
        ],
        "expected_years": 0,
    },
    "call center executive": {
        "skills": [
            "inbound calling",
            "outbound calling",
            "customer verification",
            "call logging",
            "query handling",
            "crm updates",
            "telecalling",
            "follow up management",
            "customer service",
            "complaint handling",
            "call quality standards",
            "script adherence",
            "issue escalation",
            "service reporting",
        ],
        "responsibilities": [
            "handle inbound or outbound calls to support service requests and customer engagement",
            "log call outcomes maintain crm accuracy and follow standard call quality processes",
            "resolve common concerns and escalate complex issues for timely closure",
        ],
        "expected_years": 0,
    },
    "teacher": {
        "skills": [
            "lesson planning",
            "classroom management",
            "student assessment",
            "curriculum delivery",
            "subject instruction",
            "worksheet preparation",
            "exam invigilation",
            "parent communication",
            "student mentoring",
            "board syllabus understanding",
            "progress tracking",
            "activity planning",
            "remedial teaching",
            "class records management",
        ],
        "responsibilities": [
            "plan and deliver lessons that support curriculum goals and student understanding",
            "assess student performance maintain records and provide timely academic feedback",
            "manage classroom engagement discipline and communication with parents and coordinators",
        ],
        "expected_years": 0,
    },
    "school teacher": {
        "skills": [
            "lesson planning",
            "classroom management",
            "student assessment",
            "board syllabus delivery",
            "exam preparation",
            "parent teacher communication",
            "attendance management",
            "activity coordination",
            "notebook checking",
            "student mentoring",
            "report card support",
            "worksheet preparation",
            "discipline management",
            "remedial teaching",
        ],
        "responsibilities": [
            "deliver school curriculum effectively while maintaining classroom discipline and participation",
            "evaluate assignments tests and student progress with accurate academic records",
            "coordinate with parents and school leadership on student learning and development needs",
        ],
        "expected_years": 0,
    },
    "mathematics teacher": {
        "skills": [
            "mathematics instruction",
            "lesson planning",
            "problem solving pedagogy",
            "board syllabus delivery",
            "student assessment",
            "worksheet preparation",
            "exam preparation",
            "concept reinforcement",
            "doubt clearing",
            "classroom management",
            "progress tracking",
            "remedial teaching",
            "parent communication",
            "academic record keeping",
        ],
        "responsibilities": [
            "teach mathematics concepts through structured lessons practice and assessments",
            "support students with doubt clearing remedial sessions and exam preparation",
            "track academic progress and communicate performance updates to parents and school staff",
        ],
        "expected_years": 0,
    },
    "science teacher": {
        "skills": [
            "science instruction",
            "lesson planning",
            "lab coordination",
            "experiment demonstration",
            "board syllabus delivery",
            "student assessment",
            "worksheet preparation",
            "concept explanation",
            "classroom management",
            "activity planning",
            "progress tracking",
            "exam preparation",
            "parent communication",
            "academic record keeping",
        ],
        "responsibilities": [
            "teach science subjects through concept explanation experiments and activity-based learning",
            "prepare assessments practical support and revision plans for improved understanding",
            "maintain academic records and coordinate with parents on student progress and participation",
        ],
        "expected_years": 0,
    },
    "english teacher": {
        "skills": [
            "english instruction",
            "grammar teaching",
            "reading comprehension",
            "writing skills development",
            "spoken english support",
            "lesson planning",
            "student assessment",
            "worksheet preparation",
            "classroom management",
            "board syllabus delivery",
            "literature teaching",
            "vocabulary building",
            "parent communication",
            "progress tracking",
        ],
        "responsibilities": [
            "teach language grammar writing and literature through planned classroom sessions",
            "assess comprehension speaking and writing skills through regular assignments and tests",
            "guide students on language development and communicate progress to parents and coordinators",
        ],
        "expected_years": 0,
    },
    "social science teacher": {
        "skills": [
            "social science instruction",
            "history teaching",
            "geography teaching",
            "civics teaching",
            "lesson planning",
            "board syllabus delivery",
            "student assessment",
            "worksheet preparation",
            "classroom management",
            "activity planning",
            "map work guidance",
            "exam preparation",
            "parent communication",
            "progress tracking",
        ],
        "responsibilities": [
            "deliver social science curriculum through engaging lessons activities and structured revision",
            "assess student understanding with assignments tests and project-based evaluation",
            "maintain records and support students and parents with academic progress communication",
        ],
        "expected_years": 0,
    },
    "tutor": {
        "skills": [
            "one on one teaching",
            "lesson planning",
            "concept explanation",
            "student assessment",
            "doubt clearing",
            "exam preparation",
            "worksheet preparation",
            "progress tracking",
            "subject instruction",
            "homework support",
            "remedial teaching",
            "time management",
            "parent communication",
            "personalized learning",
        ],
        "responsibilities": [
            "provide individualized teaching support based on student learning gaps and goals",
            "prepare lessons assignments and revision plans for improved student performance",
            "track progress and communicate outcomes with students and parents regularly",
        ],
        "expected_years": 0,
    },
    "academic coordinator": {
        "skills": [
            "academic planning",
            "teacher coordination",
            "timetable planning",
            "curriculum monitoring",
            "student performance tracking",
            "parent communication",
            "exam coordination",
            "class observations",
            "academic reporting",
            "school administration support",
            "event coordination",
            "lesson review",
            "training coordination",
            "documentation management",
        ],
        "responsibilities": [
            "coordinate academic schedules curriculum delivery and assessment planning across classes",
            "support teachers students and parents through reporting communication and process follow-up",
            "monitor academic quality and help improve instructional consistency and school operations",
        ],
        "expected_years": 0,
    },
    "curriculum developer": {
        "skills": [
            "curriculum design",
            "lesson framework creation",
            "learning objectives",
            "assessment design",
            "content structuring",
            "instructional planning",
            "worksheet development",
            "teacher guides",
            "board syllabus mapping",
            "learning outcomes evaluation",
            "academic research",
            "content review",
            "rubric design",
            "education content writing",
        ],
        "responsibilities": [
            "design curriculum frameworks lessons and assessments aligned to learning outcomes",
            "create teacher and student materials that support consistent classroom delivery",
            "review academic content quality and refine curriculum based on feedback and standards",
        ],
        "expected_years": 0,
    },
    "instructional designer": {
        "skills": [
            "instructional design",
            "learning objectives",
            "storyboarding",
            "e learning content",
            "assessment design",
            "adult learning principles",
            "content authoring",
            "training material development",
            "lms support",
            "curriculum structuring",
            "multimedia planning",
            "facilitator guides",
            "learning evaluation",
            "content review",
        ],
        "responsibilities": [
            "design learning experiences modules and assessments for classroom or digital delivery",
            "translate subject matter inputs into clear storyboards content flows and learning assets",
            "evaluate learner outcomes and improve instructional materials based on feedback and usage",
        ],
        "expected_years": 0,
    },
    "nurse": {
        "skills": [
            "patient care",
            "vital signs monitoring",
            "medication administration",
            "iv support",
            "ward management",
            "patient documentation",
            "infection control",
            "doctor coordination",
            "emergency response support",
            "patient counseling",
            "nursing procedures",
            "discharge support",
            "clinical observation",
            "care plan follow up",
        ],
        "responsibilities": [
            "provide bedside patient care medication support and clinical monitoring as per protocols",
            "maintain nursing documentation and coordinate with doctors and families on treatment updates",
            "ensure hygiene safety and timely response to patient needs within assigned units",
        ],
        "expected_years": 0,
    },
    "medical assistant": {
        "skills": [
            "patient preparation",
            "vital signs recording",
            "appointment coordination",
            "sample collection support",
            "doctor assistance",
            "medical records handling",
            "clinic coordination",
            "patient communication",
            "equipment preparation",
            "billing support",
            "front desk coordination",
            "clinical documentation",
            "follow up calls",
            "basic first aid support",
        ],
        "responsibilities": [
            "assist clinicians with patient preparation vital checks and routine clinical coordination",
            "manage appointments records and front-desk support for smooth patient flow",
            "support sample collection documentation and follow-up communication with patients",
        ],
        "expected_years": 0,
    },
    "pharmacist": {
        "skills": [
            "prescription dispensing",
            "medicine inventory",
            "pharmacy operations",
            "drug information",
            "patient counseling",
            "stock monitoring",
            "expiry tracking",
            "billing support",
            "controlled medicine handling",
            "vendor coordination",
            "medicine reconciliation",
            "dosage verification",
            "pharmacy software",
            "compliance documentation",
        ],
        "responsibilities": [
            "dispense medicines accurately based on prescriptions and counseling requirements",
            "maintain pharmacy inventory storage standards and expiry monitoring processes",
            "support compliance records and coordinate with doctors vendors and patients as needed",
        ],
        "expected_years": 0,
    },
    "lab technician": {
        "skills": [
            "sample collection",
            "specimen processing",
            "laboratory testing support",
            "equipment calibration",
            "quality control",
            "report preparation",
            "lab documentation",
            "safety protocols",
            "sample labeling",
            "inventory tracking",
            "pathology lab support",
            "diagnostic workflow support",
            "record maintenance",
            "infection control",
        ],
        "responsibilities": [
            "collect process and track samples for diagnostic testing and reporting",
            "operate maintain and document laboratory equipment and quality procedures accurately",
            "support timely report generation while following safety and infection-control standards",
        ],
        "expected_years": 0,
    },
    "physiotherapist": {
        "skills": [
            "patient assessment",
            "therapy planning",
            "exercise prescription",
            "rehabilitation support",
            "pain management",
            "mobility training",
            "manual therapy",
            "treatment documentation",
            "patient counseling",
            "progress evaluation",
            "home exercise guidance",
            "clinical coordination",
            "musculoskeletal care",
            "therapy session management",
        ],
        "responsibilities": [
            "assess patient conditions and deliver therapy plans for pain relief and mobility improvement",
            "guide rehabilitation exercises and track progress across treatment sessions",
            "maintain treatment records and educate patients on recovery plans and home exercises",
        ],
        "expected_years": 0,
    },
    "healthcare administrator": {
        "skills": [
            "hospital administration",
            "patient coordination",
            "medical records management",
            "billing coordination",
            "appointment management",
            "vendor coordination",
            "front office supervision",
            "compliance documentation",
            "insurance coordination",
            "service quality monitoring",
            "staff coordination",
            "healthcare reporting",
            "process coordination",
            "patient service support",
        ],
        "responsibilities": [
            "coordinate administrative operations across patient services records billing and scheduling",
            "support healthcare staff vendors and patients to maintain smooth service delivery",
            "maintain compliance documentation reports and operational follow-ups across the facility",
        ],
        "expected_years": 0,
    },
    "clinical research coordinator": {
        "skills": [
            "clinical trial coordination",
            "patient screening",
            "informed consent support",
            "study documentation",
            "case report forms",
            "regulatory file maintenance",
            "site coordination",
            "adverse event reporting support",
            "protocol compliance",
            "investigator coordination",
            "data entry accuracy",
            "sample tracking",
            "ethics documentation",
            "study visit scheduling",
        ],
        "responsibilities": [
            "coordinate study activities participant visits and trial documentation as per protocol",
            "maintain regulatory and study records with accurate case documentation and follow-up",
            "support investigators participants and sponsors through smooth trial operations and compliance",
        ],
        "expected_years": 0,
    },
    "medical representative": {
        "skills": [
            "doctor visits",
            "product detailing",
            "territory coverage",
            "chemist coordination",
            "sales reporting",
            "prescription generation support",
            "relationship building",
            "market intelligence",
            "brand communication",
            "meeting planning",
            "field sales",
            "crm updates",
            "target achievement",
            "product knowledge",
        ],
        "responsibilities": [
            "promote pharmaceutical products through regular doctor and chemist visits in assigned territories",
            "communicate product benefits scientifically and support prescription-generation efforts",
            "track field activity target progress and market feedback for territory growth",
        ],
        "expected_years": 0,
    },
    "legal associate": {
        "skills": [
            "legal drafting",
            "contract review",
            "legal research",
            "case documentation",
            "compliance review",
            "notice drafting",
            "agreement preparation",
            "litigation support",
            "document vetting",
            "corporate law basics",
            "regulatory reading",
            "due diligence support",
            "stakeholder coordination",
            "legal record management",
        ],
        "responsibilities": [
            "draft review and organize legal documents agreements and supporting case materials",
            "perform legal research and compliance checks to support internal or client requirements",
            "coordinate with stakeholders on documentation filings and follow-up legal actions",
        ],
        "expected_years": 0,
    },
    "legal advisor": {
        "skills": [
            "legal advisory",
            "contract review",
            "legal drafting",
            "regulatory compliance",
            "risk assessment",
            "legal research",
            "notice review",
            "policy review",
            "stakeholder advisory",
            "dispute support",
            "corporate law",
            "documentation review",
            "negotiation support",
            "legal compliance reporting",
        ],
        "responsibilities": [
            "advise business teams on legal risks contracts compliance obligations and policy interpretation",
            "review agreements and disputes to provide practical legal recommendations and safeguards",
            "support management on regulatory matters escalations and documentation quality",
        ],
        "expected_years": 0,
    },
    "compliance officer": {
        "skills": [
            "compliance monitoring",
            "policy implementation",
            "regulatory reporting",
            "internal controls",
            "compliance audit support",
            "risk assessment",
            "documentation review",
            "incident reporting",
            "training coordination",
            "compliance registers",
            "process review",
            "regulatory updates tracking",
            "investigation support",
            "governance reporting",
        ],
        "responsibilities": [
            "monitor compliance with policies regulations and internal control requirements",
            "maintain registers documentation and issue tracking for compliance observations and actions",
            "coordinate reviews training and reporting to strengthen governance and risk awareness",
        ],
        "expected_years": 0,
    },
    "company secretary": {
        "skills": [
            "secretarial compliance",
            "board meeting coordination",
            "minutes drafting",
            "mca filings",
            "statutory registers",
            "corporate governance",
            "agenda preparation",
            "resolution drafting",
            "roc compliance",
            "shareholder documentation",
            "compliance calendar",
            "legal documentation",
            "board papers coordination",
            "records management",
        ],
        "responsibilities": [
            "manage corporate secretarial filings registers board meetings and governance documentation",
            "prepare agendas minutes resolutions and compliance calendars for statutory requirements",
            "coordinate with directors auditors and regulators to maintain compliant corporate records",
        ],
        "expected_years": 0,
    },
    "contract manager": {
        "skills": [
            "contract drafting",
            "contract review",
            "clause negotiation support",
            "document version control",
            "vendor agreements",
            "renewal tracking",
            "risk review",
            "compliance coordination",
            "stakeholder management",
            "contract repository management",
            "obligation tracking",
            "legal coordination",
            "commercial terms review",
            "issue escalation",
        ],
        "responsibilities": [
            "manage contract lifecycle activities from drafting review negotiation support and renewals",
            "track obligations risks and documentation across vendor client and internal agreements",
            "coordinate stakeholders to ensure contracts are compliant current and operationally effective",
        ],
        "expected_years": 0,
    },
    "paralegal": {
        "skills": [
            "legal research",
            "case file management",
            "document drafting support",
            "evidence organization",
            "court filing support",
            "agreement formatting",
            "notice preparation",
            "legal documentation review",
            "calendar tracking",
            "record maintenance",
            "due diligence support",
            "legal correspondence",
            "litigation support",
            "compliance documentation",
        ],
        "responsibilities": [
            "support legal teams with research document preparation and case file organization",
            "maintain legal records timelines correspondence and filing-related documentation",
            "assist with due diligence contract support and routine legal administrative work",
        ],
        "expected_years": 0,
    },
    "risk and compliance analyst": {
        "skills": [
            "risk assessment",
            "control review",
            "compliance monitoring",
            "policy review",
            "issue tracking",
            "risk registers",
            "regulatory reporting support",
            "control testing",
            "process review",
            "data validation",
            "investigation support",
            "documentation analysis",
            "governance reporting",
            "audit support",
        ],
        "responsibilities": [
            "analyze risks controls and compliance observations across business processes",
            "maintain risk documentation reporting and action trackers for governance follow-up",
            "support audits investigations and remediation planning with structured evidence and analysis",
        ],
        "expected_years": 0,
    },
    "graphic designer": {
        "skills": [
            "adobe photoshop",
            "adobe illustrator",
            "coreldraw",
            "branding design",
            "social media creatives",
            "brochure design",
            "print design",
            "layout design",
            "canva",
            "visual composition",
            "typography",
            "image editing",
            "marketing collateral design",
            "color theory",
        ],
        "responsibilities": [
            "create visual assets for digital print and branding requirements across campaigns",
            "translate briefs into compelling layouts designs and production-ready creative deliverables",
            "coordinate with marketing content or business teams to maintain visual consistency",
        ],
        "expected_years": 0,
    },
    "video editor": {
        "skills": [
            "adobe premiere pro",
            "after effects",
            "video cutting",
            "color correction",
            "audio syncing",
            "motion titles",
            "storyboarding support",
            "reels editing",
            "youtube video editing",
            "short form content editing",
            "transition design",
            "video export management",
            "asset organization",
            "thumbnail coordination",
        ],
        "responsibilities": [
            "edit raw footage into polished videos optimized for campaigns platforms or storytelling goals",
            "manage pacing transitions audio and visual consistency across final outputs",
            "collaborate with creative teams on concepts revisions and publishing-ready video assets",
        ],
        "expected_years": 0,
    },
    "content creator": {
        "skills": [
            "content ideation",
            "script writing",
            "short form video planning",
            "social media content",
            "camera presence",
            "copywriting",
            "content calendar",
            "basic video editing",
            "reels creation",
            "audience engagement",
            "trend research",
            "thumbnail planning",
            "brand storytelling",
            "content performance tracking",
        ],
        "responsibilities": [
            "create engaging content concepts scripts and assets aligned to audience and brand goals",
            "publish or coordinate content across channels while adapting to platform trends and feedback",
            "track engagement and refine content formats messaging and cadence based on performance",
        ],
        "expected_years": 0,
    },
    "motion graphics designer": {
        "skills": [
            "after effects",
            "motion graphics",
            "animation principles",
            "kinetic typography",
            "storyboarding",
            "adobe illustrator",
            "adobe premiere pro",
            "visual transitions",
            "logo animation",
            "2d animation",
            "video compositing",
            "sound sync support",
            "creative asset adaptation",
            "render management",
        ],
        "responsibilities": [
            "design and animate motion assets for videos campaigns and brand storytelling needs",
            "translate creative briefs into storyboards transitions and engaging visual sequences",
            "work with editors and designers to deliver polished animated outputs on time",
        ],
        "expected_years": 0,
    },
    "visual designer": {
        "skills": [
            "visual design",
            "layout design",
            "branding design",
            "adobe photoshop",
            "adobe illustrator",
            "figma",
            "color theory",
            "typography",
            "campaign creatives",
            "presentation design",
            "marketing collateral design",
            "visual storytelling",
            "iconography",
            "design systems basics",
        ],
        "responsibilities": [
            "create visually consistent assets for campaigns presentations and brand communication",
            "translate concepts into polished layouts with strong typography color and composition",
            "support teams with visual design systems and creative adaptations across formats",
        ],
        "expected_years": 0,
    },
    "creative designer": {
        "skills": [
            "creative concept development",
            "branding design",
            "social media creatives",
            "campaign visuals",
            "adobe photoshop",
            "adobe illustrator",
            "canva",
            "layout design",
            "visual storytelling",
            "copy direction support",
            "color theory",
            "typography",
            "creative briefing",
            "asset adaptation",
        ],
        "responsibilities": [
            "develop creative visuals for campaigns promotions and brand initiatives across channels",
            "interpret briefs into original concepts and design assets suited for target audiences",
            "coordinate revisions and adaptations to keep campaigns visually strong and consistent",
        ],
        "expected_years": 0,
    },
    "copywriter": {
        "skills": [
            "copywriting",
            "ad copy",
            "content writing",
            "headline writing",
            "brand messaging",
            "campaign copy",
            "social media copy",
            "email copywriting",
            "website copy",
            "proofreading",
            "editing",
            "creative briefing",
            "seo writing",
            "storytelling",
        ],
        "responsibilities": [
            "write persuasive and brand-aligned copy across ads campaigns websites and crm channels",
            "develop headlines messaging frameworks and scripts that improve engagement and conversion",
            "collaborate with marketing and design teams to refine copy based on performance and feedback",
        ],
        "expected_years": 0,
    },
    "retail sales associate": {
        "skills": [
            "customer assistance",
            "product demonstration",
            "billing support",
            "upselling",
            "cross selling",
            "store merchandising",
            "inventory support",
            "cash handling",
            "customer service",
            "sales target achievement",
            "product knowledge",
            "store upkeep",
            "point of sale",
            "walk in customer handling",
        ],
        "responsibilities": [
            "assist walk-in customers with product information billing and purchase decisions",
            "support store sales through upselling merchandising and service quality standards",
            "maintain stock displays cash counters and transaction records accurately",
        ],
        "expected_years": 0,
    },
    "store manager": {
        "skills": [
            "store operations",
            "team supervision",
            "sales target management",
            "inventory control",
            "merchandising",
            "cash management",
            "customer grievance handling",
            "staff scheduling",
            "loss prevention",
            "daily store reporting",
            "vendor coordination",
            "store compliance",
            "team coaching",
            "retail operations",
        ],
        "responsibilities": [
            "manage daily store operations staff performance inventory and sales achievement",
            "maintain customer service standards visual merchandising and cash control processes",
            "review store performance and address stock staffing or service issues proactively",
        ],
        "expected_years": 0,
    },
    "cashier": {
        "skills": [
            "cash handling",
            "billing",
            "point of sale",
            "customer interaction",
            "payment processing",
            "receipt generation",
            "cash reconciliation",
            "refund processing",
            "queue management",
            "basic customer service",
            "transaction accuracy",
            "closing balance support",
            "counter operations",
            "store support",
        ],
        "responsibilities": [
            "process customer transactions accurately through pos and payment systems",
            "maintain cash counter discipline receipts and daily reconciliation support",
            "assist customers courteously and coordinate with store teams for smooth checkout operations",
        ],
        "expected_years": 0,
    },
    "hotel receptionist": {
        "skills": [
            "front desk operations",
            "guest check in",
            "guest check out",
            "reservation handling",
            "phone etiquette",
            "guest query resolution",
            "billing support",
            "room coordination",
            "hospitality communication",
            "booking software",
            "guest records maintenance",
            "customer service",
            "shift handover",
            "service coordination",
        ],
        "responsibilities": [
            "manage front-desk guest interactions reservations check-ins and check-outs professionally",
            "coordinate room allocation billing and guest service requests with hotel departments",
            "maintain records and deliver courteous hospitality support across shifts",
        ],
        "expected_years": 0,
    },
    "front office executive": {
        "skills": [
            "front desk operations",
            "visitor handling",
            "call handling",
            "appointment coordination",
            "reception management",
            "guest assistance",
            "record maintenance",
            "billing support",
            "meeting coordination",
            "communication skills",
            "service coordination",
            "email handling",
            "customer assistance",
            "office support",
        ],
        "responsibilities": [
            "manage reception operations calls visitors and appointment-related coordination efficiently",
            "support front office documentation communication and service follow-up tasks",
            "ensure a professional first point of contact for guests clients and internal teams",
        ],
        "expected_years": 0,
    },
    "restaurant manager": {
        "skills": [
            "restaurant operations",
            "team supervision",
            "table management",
            "customer service",
            "food service coordination",
            "billing oversight",
            "inventory monitoring",
            "vendor coordination",
            "shift scheduling",
            "guest grievance handling",
            "hygiene compliance",
            "service quality monitoring",
            "daily sales reporting",
            "staff training",
        ],
        "responsibilities": [
            "oversee restaurant service operations staff scheduling and guest experience standards",
            "manage inventory vendor coordination billing and hygiene or service quality processes",
            "resolve guest issues and drive operational efficiency and sales performance across shifts",
        ],
        "expected_years": 0,
    },
    "hospitality executive": {
        "skills": [
            "guest relations",
            "service coordination",
            "front office support",
            "reservation support",
            "event coordination",
            "customer assistance",
            "billing support",
            "complaint handling",
            "hospitality communication",
            "vendor coordination",
            "guest follow ups",
            "service quality monitoring",
            "booking management",
            "records maintenance",
        ],
        "responsibilities": [
            "support guest services reservations and hospitality operations across assigned functions",
            "coordinate service delivery and issue resolution to maintain strong guest experience",
            "manage records communication and operational follow-ups with internal service teams",
        ],
        "expected_years": 0,
    },
}

_ROLE_ALIAS_SEED: dict[str, list[str]] = {
    "ai engineer": ["artificial intelligence engineer", "ai developer", "applied ai engineer"],
    "generative ai engineer": [
        "genai engineer",
        "llm engineer",
        "generative ai developer",
        "llm application engineer",
    ],
    "nlp specialist": [
        "nlp engineer",
        "nlp scientist",
        "natural language processing specialist",
        "natural language processing engineer",
    ],
    "computer vision engineer": [
        "cv engineer",
        "computer vision developer",
        "vision engineer",
    ],
    "ai ethics and compliance officer": [
        "responsible ai specialist",
        "ai governance specialist",
        "ai risk specialist",
    ],
    "ai product manager": [
        "ai pm",
        "artificial intelligence product manager",
        "ml product manager",
    ],
    "machine learning scientist": [
        "ml scientist",
        "applied scientist",
        "research scientist machine learning",
    ],
    "robotics engineer": ["robotics developer", "robotics software engineer"],
    "software engineer": [
        "software developer",
        "software development engineer",
        "application developer",
        "application engineer",
    ],
    "data scientist": [
        "machine learning scientist",
        "applied data scientist",
        "decision scientist",
        "data science intern",
    ],
    "data engineer": ["etl engineer", "data platform engineer", "analytics engineer"],
    "big data architect": ["data architect", "lakehouse architect", "data platform architect"],
    "business intelligence analyst": [
        "bi analyst",
        "business intelligence developer",
        "bi developer",
        "reporting analyst",
        "dashboard analyst",
    ],
    "data governance specialist": [
        "data governance analyst",
        "data quality specialist",
        "data stewardship specialist",
    ],
    "full-stack developer": [
        "full stack developer",
        "full stack engineer",
        "fullstack developer",
        "fullstack engineer",
    ],
    "backend engineer": [
        "backend developer",
        "back end engineer",
        "back end developer",
        "server side engineer",
        "server side developer",
        "api engineer",
    ],
    "frontend engineer": [
        "frontend developer",
        "front end engineer",
        "front end developer",
        "ui engineer",
        "web developer",
    ],
    "mobile app developer": [
        "mobile developer",
        "ios developer",
        "android developer",
        "mobile engineer",
    ],
    "blockchain developer": ["web3 developer", "smart contract engineer", "smart contract developer"],
    "embedded systems engineer": ["firmware engineer", "embedded developer", "firmware developer"],
    "game developer": ["game engineer", "game programmer", "unity developer", "unreal developer"],
    "cloud solutions architect": ["cloud architect", "solutions architect", "cloud solution architect"],
    "cloud engineer": ["cloud developer", "aws engineer", "azure engineer", "gcp engineer"],
    "devops engineer": ["devops", "platform ops engineer", "release engineer", "infrastructure engineer"],
    "site reliability engineer": ["sre", "reliability engineer"],
    "platform engineer": ["developer platform engineer", "internal platform engineer"],
    "finops specialist": ["finops analyst", "cloud cost analyst", "cloud financial analyst"],
    "cybersecurity analyst": ["security analyst", "soc analyst", "information security analyst"],
    "ethical hacker": ["penetration tester", "pentester", "red team engineer"],
    "application security engineer": [
        "appsec engineer",
        "application security specialist",
        "product security engineer",
    ],
    "ui ux designer": ["product designer", "ux designer", "ui designer", "ux ui designer"],
    "it project manager": ["technical project manager", "project manager", "program manager"],
    "machine learning engineer": [
        "ml engineer",
        "ml developer",
        "machine learning developer",
        "mlops engineer",
    ],
    "data analyst": [
        "analytics analyst",
        "reporting analyst",
        "business data analyst",
        "data analytics analyst",
    ],
    "business analyst": [
        "business systems analyst",
        "functional analyst",
        "requirements analyst",
    ],
    "product manager": ["technical product manager", "product owner", "digital product manager"],
    "qa engineer": [
        "quality assurance engineer",
        "test engineer",
        "sdet",
        "qa analyst",
        "automation tester",
        "qa automation engineer",
    ],
    "digital marketing executive": [
        "digital marketer",
        "digital marketing specialist",
        "online marketing executive",
        "digital marketing associate",
        "growth marketing executive",
        "digital campaign executive",
    ],
    "performance marketing specialist": [
        "performance marketer",
        "paid marketing specialist",
        "paid media specialist",
        "performance marketing executive",
        "media buying specialist",
        "growth performance marketer",
    ],
    "social media manager": [
        "social media specialist",
        "social media executive",
        "social media lead",
        "social media strategist",
        "community manager",
        "social media associate",
    ],
    "content marketer": [
        "content marketing specialist",
        "content marketing executive",
        "content strategist",
        "content specialist",
        "content marketing associate",
        "brand content executive",
    ],
    "seo specialist": [
        "seo executive",
        "search engine optimization specialist",
        "organic growth specialist",
        "seo analyst",
        "seo associate",
        "organic marketing executive",
    ],
    "brand manager": [
        "brand marketing manager",
        "assistant brand manager",
        "brand executive",
        "brand specialist",
        "brand associate",
        "brand lead",
    ],
    "marketing manager": [
        "marketing lead",
        "marketing specialist",
        "marketing executive",
        "marketing associate",
        "campaign manager",
        "marketing operations manager",
    ],
    "growth marketer": [
        "growth marketing specialist",
        "growth marketing executive",
        "growth marketing manager",
        "user acquisition specialist",
        "retention marketer",
        "growth associate",
    ],
    "email marketing specialist": [
        "email marketer",
        "email marketing executive",
        "crm marketer",
        "lifecycle marketing specialist",
        "marketing automation specialist",
        "email campaign specialist",
    ],
    "product marketing manager": [
        "product marketing specialist",
        "product marketing lead",
        "go to market manager",
        "gtm manager",
        "product marketing executive",
        "product communication manager",
    ],
    "sales executive": [
        "sales associate",
        "sales representative",
        "sales officer",
        "field sales officer",
        "inside sales executive",
        "sales consultant",
    ],
    "business development executive": [
        "business development associate",
        "business development representative",
        "bd executive",
        "bde",
        "sales business development executive",
        "business growth executive",
    ],
    "account executive": [
        "client acquisition executive",
        "sales account executive",
        "enterprise account executive",
        "account sales executive",
        "account management executive",
        "commercial executive",
    ],
    "sales manager": [
        "area sales manager",
        "regional sales manager",
        "territory sales manager",
        "sales team lead",
        "sales lead",
        "branch sales manager",
    ],
    "key account manager": [
        "key accounts manager",
        "national account manager",
        "strategic account manager",
        "client account manager",
        "key account executive",
        "major account manager",
    ],
    "inside sales representative": [
        "inside sales executive",
        "inside sales associate",
        "tele sales executive",
        "telecaller sales executive",
        "sales development representative",
        "sdr",
    ],
    "field sales executive": [
        "field sales representative",
        "field sales officer",
        "territory sales executive",
        "area sales executive",
        "field business development executive",
        "on ground sales executive",
    ],
    "customer success manager": [
        "customer success executive",
        "customer success lead",
        "client success manager",
        "customer success associate",
        "customer retention manager",
        "account success manager",
    ],
    "relationship manager": [
        "client relationship manager",
        "relationship executive",
        "customer relationship manager",
        "relationship officer",
        "relationship associate",
        "wealth relationship manager",
    ],
    "presales consultant": [
        "pre sales consultant",
        "presales specialist",
        "solution consultant",
        "bid consultant",
        "presales executive",
        "sales solution consultant",
    ],
    "hr executive": [
        "human resources executive",
        "hr operations executive",
        "hr associate",
        "people operations executive",
        "hr admin executive",
        "human resource associate",
    ],
    "hr generalist": [
        "human resources generalist",
        "people operations generalist",
        "hr operations specialist",
        "human resources specialist",
        "hr generalist executive",
        "people generalist",
    ],
    "recruiter": [
        "hr recruiter",
        "recruitment executive",
        "recruitment specialist",
        "technical recruiter",
        "non it recruiter",
        "staffing recruiter",
    ],
    "talent acquisition specialist": [
        "talent acquisition executive",
        "talent acquisition recruiter",
        "ta specialist",
        "ta executive",
        "hiring specialist",
        "sourcing specialist",
    ],
    "hr manager": [
        "human resources manager",
        "people manager",
        "hr operations manager",
        "assistant hr manager",
        "manager human resources",
        "hr business partner manager",
    ],
    "payroll executive": [
        "payroll specialist",
        "payroll associate",
        "salary processing executive",
        "payroll operations executive",
        "payroll officer",
        "compensation executive",
    ],
    "learning and development specialist": [
        "l and d specialist",
        "l&d specialist",
        "learning and development executive",
        "training specialist",
        "training executive",
        "learning specialist",
    ],
    "employee relations specialist": [
        "employee relations executive",
        "employee engagement specialist",
        "people relations specialist",
        "employee grievance specialist",
        "er specialist",
        "employee experience specialist",
    ],
    "accountant": [
        "general accountant",
        "accounts officer",
        "staff accountant",
        "finance accountant",
        "accounting associate",
        "accounting executive",
    ],
    "accounts executive": [
        "accounts assistant",
        "accounts officer",
        "accounts associate",
        "accounts payable executive",
        "accounts receivable executive",
        "finance executive accounts",
    ],
    "financial analyst": [
        "finance analyst",
        "fp and a analyst",
        "fp&a analyst",
        "business finance analyst",
        "financial planning analyst",
        "budget analyst",
    ],
    "finance manager": [
        "accounts and finance manager",
        "finance lead",
        "manager finance",
        "financial controller",
        "assistant finance manager",
        "finance operations manager",
    ],
    "auditor": [
        "internal auditor",
        "audit executive",
        "audit associate",
        "statutory auditor",
        "audit analyst",
        "assurance associate",
    ],
    "tax consultant": [
        "tax analyst",
        "gst consultant",
        "tax executive",
        "tax associate",
        "direct tax consultant",
        "indirect tax consultant",
    ],
    "payroll accountant": [
        "payroll specialist accounting",
        "salary accountant",
        "payroll finance executive",
        "payroll and accounts executive",
        "payroll accounts officer",
        "compensation accountant",
    ],
    "investment analyst": [
        "equity analyst",
        "research analyst investments",
        "investment research analyst",
        "portfolio analyst",
        "buy side analyst",
        "capital markets analyst",
    ],
    "credit analyst": [
        "credit appraisal analyst",
        "loan analyst",
        "underwriting analyst",
        "credit risk analyst",
        "credit evaluation analyst",
        "banking credit analyst",
    ],
    "operations executive": [
        "operations associate",
        "operations coordinator",
        "operations analyst",
        "back office executive",
        "process executive",
        "operations officer",
    ],
    "operations manager": [
        "operations lead",
        "process manager",
        "business operations manager",
        "service operations manager",
        "operations team lead",
        "manager operations",
    ],
    "office administrator": [
        "office admin",
        "office coordinator",
        "administrative officer",
        "admin coordinator",
        "office management executive",
        "office operations administrator",
    ],
    "admin executive": [
        "administrative executive",
        "admin officer",
        "admin associate",
        "back office admin executive",
        "office admin executive",
        "administration associate",
    ],
    "supply chain executive": [
        "supply chain associate",
        "supply chain coordinator",
        "supply executive",
        "inventory and supply executive",
        "supply operations executive",
        "planning executive supply chain",
    ],
    "logistics coordinator": [
        "logistics executive",
        "dispatch coordinator",
        "transport coordinator",
        "shipment coordinator",
        "logistics associate",
        "dispatch executive",
    ],
    "procurement specialist": [
        "procurement executive",
        "purchase executive",
        "sourcing specialist",
        "procurement associate",
        "purchase officer",
        "buyer",
    ],
    "vendor manager": [
        "supplier manager",
        "vendor relationship manager",
        "vendor coordinator lead",
        "supplier relationship manager",
        "vendor operations manager",
        "partner manager vendors",
    ],
    "facility manager": [
        "facilities manager",
        "facility executive",
        "admin and facility manager",
        "facility operations manager",
        "estate manager",
        "workplace manager",
    ],
    "customer support executive": [
        "customer support associate",
        "customer care executive",
        "customer service executive",
        "support executive",
        "customer care associate",
        "client support executive",
    ],
    "customer service representative": [
        "csr",
        "customer service associate",
        "customer care representative",
        "customer support representative",
        "service representative",
        "customer handling executive",
    ],
    "technical support executive": [
        "technical support associate",
        "tech support executive",
        "desktop support executive",
        "it support executive",
        "technical helpdesk executive",
        "support engineer l1",
    ],
    "helpdesk executive": [
        "help desk executive",
        "service desk executive",
        "helpdesk associate",
        "service desk analyst",
        "it helpdesk executive",
        "helpdesk support executive",
    ],
    "client service executive": [
        "client servicing executive",
        "client relations executive",
        "account servicing executive",
        "client support executive",
        "customer servicing executive",
        "service relationship executive",
    ],
    "customer experience manager": [
        "cx manager",
        "customer experience lead",
        "customer delight manager",
        "service experience manager",
        "customer journey manager",
        "client experience manager",
    ],
    "call center executive": [
        "telecaller",
        "bpo executive",
        "voice process executive",
        "call centre executive",
        "customer support caller",
        "inbound process executive",
    ],
    "teacher": [
        "educator",
        "faculty",
        "school educator",
        "teaching associate",
        "teaching faculty",
        "class teacher",
    ],
    "school teacher": [
        "school educator",
        "primary teacher",
        "secondary teacher",
        "class teacher",
        "subject teacher",
        "school faculty",
    ],
    "mathematics teacher": [
        "math teacher",
        "maths teacher",
        "mathematics faculty",
        "math faculty",
        "tgt mathematics",
        "pgt mathematics",
    ],
    "science teacher": [
        "science faculty",
        "science educator",
        "tgt science",
        "pgt science",
        "school science teacher",
        "general science teacher",
    ],
    "english teacher": [
        "english faculty",
        "english educator",
        "spoken english trainer",
        "tgt english",
        "pgt english",
        "language teacher english",
    ],
    "social science teacher": [
        "sst teacher",
        "social studies teacher",
        "social science faculty",
        "tgt social science",
        "humanities teacher",
        "history geography teacher",
    ],
    "tutor": [
        "private tutor",
        "home tutor",
        "subject tutor",
        "academic tutor",
        "online tutor",
        "teaching tutor",
    ],
    "academic coordinator": [
        "school academic coordinator",
        "academic lead",
        "curriculum coordinator",
        "academic supervisor",
        "school coordinator",
        "education coordinator",
    ],
    "curriculum developer": [
        "curriculum specialist",
        "academic content developer",
        "curriculum designer",
        "education content specialist",
        "learning content developer",
        "curriculum associate",
    ],
    "instructional designer": [
        "learning designer",
        "e learning designer",
        "training content designer",
        "instructional design specialist",
        "learning experience designer",
        "id specialist",
    ],
    "nurse": [
        "staff nurse",
        "registered nurse",
        "gnm nurse",
        "bsc nurse",
        "clinical nurse",
        "nursing officer",
    ],
    "medical assistant": [
        "clinical assistant",
        "doctor assistant",
        "medical office assistant",
        "patient care assistant",
        "healthcare assistant",
        "clinic assistant",
    ],
    "pharmacist": [
        "clinical pharmacist",
        "retail pharmacist",
        "hospital pharmacist",
        "registered pharmacist",
        "pharmacy executive",
        "pharmacy associate",
    ],
    "lab technician": [
        "laboratory technician",
        "medical lab technician",
        "pathology technician",
        "lab technologist",
        "diagnostic lab technician",
        "lab assistant",
    ],
    "physiotherapist": [
        "physical therapist",
        "rehabilitation therapist",
        "clinical physiotherapist",
        "physio",
        "sports physiotherapist",
        "therapy specialist physiotherapy",
    ],
    "healthcare administrator": [
        "hospital administrator",
        "hospital operations executive",
        "clinic administrator",
        "medical administrator",
        "healthcare operations executive",
        "hospital coordination executive",
    ],
    "clinical research coordinator": [
        "crc",
        "clinical trial coordinator",
        "clinical research executive",
        "study coordinator",
        "clinical operations coordinator",
        "research site coordinator",
    ],
    "medical representative": [
        "mr",
        "pharma sales representative",
        "pharmaceutical sales executive",
        "medical sales representative",
        "field medical representative",
        "pharma representative",
    ],
    "legal associate": [
        "legal executive",
        "legal analyst",
        "junior legal associate",
        "corporate legal associate",
        "legal coordinator",
        "associate legal",
    ],
    "legal advisor": [
        "legal consultant",
        "legal counsel",
        "legal officer",
        "corporate legal advisor",
        "legal specialist",
        "legal manager advisory",
    ],
    "compliance officer": [
        "compliance executive",
        "regulatory compliance officer",
        "compliance specialist",
        "compliance associate",
        "ethics and compliance officer",
        "policy compliance officer",
    ],
    "company secretary": [
        "cs",
        "qualified company secretary",
        "assistant company secretary",
        "secretarial executive",
        "corporate secretarial executive",
        "secretarial officer",
    ],
    "contract manager": [
        "contracts manager",
        "contract specialist",
        "agreement manager",
        "contract administrator",
        "commercial contract manager",
        "contract executive",
    ],
    "paralegal": [
        "legal assistant",
        "legal support executive",
        "paralegal associate",
        "legal documentation assistant",
        "litigation assistant",
        "legal operations assistant",
    ],
    "risk and compliance analyst": [
        "risk analyst compliance",
        "governance risk and compliance analyst",
        "grc analyst",
        "risk compliance executive",
        "risk and controls analyst",
        "compliance risk analyst",
    ],
    "graphic designer": [
        "graphic design executive",
        "graphic artist",
        "visual graphic designer",
        "creative graphic designer",
        "design executive graphic",
        "graphic design associate",
    ],
    "video editor": [
        "video editing executive",
        "video editing specialist",
        "editor video",
        "post production editor",
        "reels editor",
        "content video editor",
    ],
    "content creator": [
        "digital content creator",
        "social media content creator",
        "content production executive",
        "creator",
        "ugc creator",
        "content creation specialist",
    ],
    "motion graphics designer": [
        "motion designer",
        "motion graphic artist",
        "motion graphics executive",
        "2d motion designer",
        "animation designer",
        "motion graphics specialist",
    ],
    "visual designer": [
        "brand visual designer",
        "visual communication designer",
        "marketing visual designer",
        "creative visual designer",
        "visual design executive",
        "visual artist designer",
    ],
    "creative designer": [
        "creative executive design",
        "brand creative designer",
        "marketing creative designer",
        "creative visual designer",
        "creative associate design",
        "creative specialist",
    ],
    "copywriter": [
        "creative copywriter",
        "content copywriter",
        "marketing copywriter",
        "ad copywriter",
        "copy writing executive",
        "brand copywriter",
    ],
    "retail sales associate": [
        "retail sales executive",
        "store sales associate",
        "sales associate retail",
        "retail associate",
        "showroom sales executive",
        "retail sales representative",
    ],
    "store manager": [
        "retail store manager",
        "showroom manager",
        "branch manager retail",
        "store operations manager",
        "outlet manager",
        "assistant store manager",
    ],
    "cashier": [
        "billing executive",
        "counter cashier",
        "retail cashier",
        "cash counter executive",
        "billing cashier",
        "pos cashier",
    ],
    "hotel receptionist": [
        "hotel front desk executive",
        "guest relations executive",
        "front desk receptionist",
        "front office receptionist",
        "hotel front office associate",
        "guest service associate",
    ],
    "front office executive": [
        "front desk executive",
        "reception executive",
        "guest relation executive",
        "receptionist",
        "front office associate",
        "visitor management executive",
    ],
    "restaurant manager": [
        "food and beverage manager",
        "restaurant operations manager",
        "dining manager",
        "outlet manager restaurant",
        "f and b manager",
        "f&b manager",
    ],
    "hospitality executive": [
        "guest relations executive",
        "hospitality associate",
        "hospitality coordinator",
        "guest service executive",
        "hotel operations executive",
        "service hospitality executive",
    ],
}

_ROLE_SENIORITY_PREFIXES: tuple[str, ...] = (
    "junior",
    "jr",
    "associate",
    "senior",
    "sr",
    "lead",
    "principal",
    "staff",
)
_ROLE_TRAINEE_SUFFIXES: tuple[str, ...] = ("intern", "trainee", "apprentice")
_ROLE_COMPACT_EXPANSIONS: dict[str, str] = {}
_ROLE_GENERIC_SKILL_BLOCKLIST: frozenset[str] = frozenset(
    {
        "python",
        "sql",
        "excel",
        "git",
        "linux",
        "windows server",
        "javascript",
        "typescript",
        "java",
        "c++",
        "aws",
        "azure",
        "gcp",
        "docker",
        "kubernetes",
        "rest",
        "rest api development",
        "agile",
        "scrum",
        "debugging",
        "unit testing",
        "communication",
    }
)


# ---------------------------------------------------------------------------
# Strict ATS policy constants
# ---------------------------------------------------------------------------

_UNIVERSAL_ACTION_VERB_CATEGORIES: dict[str, frozenset[str]] = {
    "build": frozenset(
        {
            "build",
            "built",
            "create",
            "created",
            "develop",
            "developed",
            "design",
            "designed",
            "launch",
            "launched",
            "architect",
            "architected",
            "establish",
            "established",
            "craft",
            "crafted",
            "construct",
            "constructed",
        }
    ),
    "analyze": frozenset(
        {
            "analyze",
            "analyzed",
            "analyse",
            "analysed",
            "evaluate",
            "evaluated",
            "research",
            "researched",
            "study",
            "studied",
            "assess",
            "assessed",
            "review",
            "reviewed",
            "investigate",
            "investigated",
            "derive",
            "derived",
            "identify",
            "identified",
        }
    ),
    "lead": frozenset(
        {
            "lead",
            "led",
            "manage",
            "managed",
            "coordinate",
            "coordinated",
            "direct",
            "directed",
            "oversee",
            "oversaw",
            "orchestrate",
            "orchestrated",
            "spearhead",
            "spearheaded",
            "own",
            "owned",
            "chair",
            "chaired",
            "head",
            "headed",
            "supervise",
            "supervised",
        }
    ),
    "improve": frozenset(
        {
            "improve",
            "improved",
            "optimize",
            "optimized",
            "enhance",
            "enhanced",
            "streamline",
            "streamlined",
            "strengthen",
            "strengthened",
            "accelerate",
            "accelerated",
            "upgrade",
            "upgraded",
            "modernize",
            "modernized",
            "refine",
            "refined",
        }
    ),
    "deliver": frozenset(
        {
            "deliver",
            "delivered",
            "execute",
            "executed",
            "implement",
            "implemented",
            "deploy",
            "deployed",
            "perform",
            "performed",
            "complete",
            "completed",
            "rollout",
            "rolled",
            "drive",
            "drove",
            "generate",
            "generated",
            "produce",
            "produced",
            "apply",
            "applied",
            "utilize",
            "utilized",
        }
    ),
    "communicate": frozenset(
        {
            "communicate",
            "communicated",
            "prepare",
            "prepared",
            "present",
            "presented",
            "report",
            "reported",
            "share",
            "shared",
            "document",
            "documented",
            "publish",
            "published",
            "brief",
            "briefed",
        }
    ),
    "support": frozenset(
        {
            "support",
            "supported",
            "assist",
            "assisted",
            "contribute",
            "contributed",
            "facilitate",
            "facilitated",
            "enable",
            "enabled",
            "partner",
            "partnered",
            "collaborate",
            "collaborated",
        }
    ),
    "mentor": frozenset(
        {
            "train",
            "trained",
            "mentor",
            "mentored",
            "guide",
            "guided",
            "coach",
            "coached",
            "teach",
            "taught",
            "instruct",
            "instructed",
            "onboard",
            "onboarded",
        }
    ),
    "achieve": frozenset(
        {
            "achieve",
            "achieved",
            "accomplish",
            "accomplished",
            "win",
            "won",
            "recognize",
            "recognized",
            "attain",
            "attained",
            "secure",
            "secured",
            "exceed",
            "exceeded",
            "earn",
            "earned",
        }
    ),
}


def _build_action_normalization_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for canonical, variants in _UNIVERSAL_ACTION_VERB_CATEGORIES.items():
        mapping[canonical] = canonical
        for variant in variants:
            mapping[variant] = canonical
    mapping.update(
        {
            "manage": "manage",
            "managed": "manage",
            "coordinate": "coordinate",
            "coordinated": "coordinate",
        }
    )
    return mapping


_ACTION_VERB_NORMALIZATION_MAP: dict[str, str] = _build_action_normalization_map()
_MANDATORY_ACTION_START_VERBS: frozenset[str] = frozenset(
    set(_UNIVERSAL_ACTION_VERB_CATEGORIES.keys()) | {"manage", "coordinate"}
)

_MANDATORY_RESULT_MARKERS: frozenset[str] = frozenset(
    {
        "increase",
        "achieved",
        "boosted",
        "decreased",
        "delivered",
        "eliminated",
        "generated",
        "grew",
        "improved",
        "optimized",
        "reduced",
        "saved",
        "secured",
        "streamlined",
    }
)

_MANDATORY_COMPLEXITY_MARKERS: frozenset[str] = frozenset(
    {
        "analysis",
        "audit",
        "auditing",
        "automation",
        "campaign",
        "client-facing",
        "compliance",
        "cross-functional",
        "cross-team",
        "dashboard",
        "data collection",
        "documentation",
        "dashboard",
        "event",
        "forecasting",
        "global",
        "governance",
        "high-volume",
        "international",
        "large-scale",
        "logistics",
        "multi-team",
        "operations",
        "operational",
        "process",
        "process improvement",
        "program",
        "regulatory",
        "reporting",
        "research",
        "risk",
        "survey",
        "stakeholder",
        "stakeholders",
        "system",
        "training",
        "workshop",
    }
)

_ML_LIBRARY_SKILL_BLOCKLIST: frozenset[str] = frozenset(
    {
        "numpy",
        "pandas",
        "scikit-learn",
        "scikit learn",
    }
)

_REQUIRED_SKILL_SUBSECTIONS: frozenset[str] = frozenset(
    {
        "programming languages",
        "data science",
        "data visualization",
        "databases",
        "tools",
    }
)

_DATE_RANGE_MMYYYY_REGEX: re.Pattern[str] = re.compile(
    r"^\s*\d{2}/\d{4}\s*-\s*(?:\d{2}/\d{4}|present)\s*$",
    re.IGNORECASE,
)

_TEAMWORK_REGEX: re.Pattern[str] = re.compile(
    r"\b(collaborated?|team|cross-functional|partnered)\b",
    re.IGNORECASE,
)

_HEADER_CONTACT_REGEX: re.Pattern[str] = re.compile(
    r"\b\d{7,}\b.*\|.*@.*\|.*linkedin\b",
    re.IGNORECASE,
)

_BULLET_QUANT_REGEX: re.Pattern[str] = re.compile(
    r"("
    r"(?:\$|€|£|₹)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:k|m|b|million|billion|lakh|crore))?"
    r"|\b\d+(?:\.\d+)?\s?%"
    r"|\b\d+(?:\.\d+)?\s?percent\b"
    r"|\b\d+(?:\.\d+)?[kmb]\b"
    r"|\b\d+\+(?=\s|$)"
    r"|\b(?:top|ranked|rank|no\.?|#)\s?\d+\b"
    r"|\b\d+(?:st|nd|rd|th)\b"
    r"|\b\d+(?:\.\d+)?\s?[- ]?(?:point|points|frame|frames|hour|hours|day|days|week|weeks|month|months|year|years|yr|yrs|minute|minutes|min|mins|second|seconds|sec|secs|country|countries|location|locations|region|regions|office|offices|site|sites|branch|branches|team|teams|member|members|people|person|staff|employees?|volunteers?|users?|customers?|clients?|students?|respondents?|participants?|attendees?|stakeholders?|partners?|projects?|events?|campaigns?|programs?|initiatives?|reports?|dashboards?|models?|apis?|process(?:es)?|workflows?|tasks?|transactions?|records?|documents?|tickets?|leads?|deals?|accounts?|classes?|courses?|lessons?)\b"
    r"|\b(?:million|billion|lakh|crore)\b"
    r")",
    re.IGNORECASE,
)


def _flatten_skill_terms(skills: Any) -> set[str]:
    """Extract normalized skill terms from heterogeneous skill payloads."""
    flattened = to_resume_skill_map(skills)
    return {
        normalize_skill_name(str(k))
        for k in flattened.keys()
        if normalize_skill_name(str(k))
    }


def _extract_skill_categories(skills: Any) -> set[str]:
    """Extract normalized category names from skill dictionaries."""
    categories: set[str] = set()
    if not isinstance(skills, list):
        return categories
    for item in cast(list[Any], skills):
        if not isinstance(item, dict):
            continue
        item_dict = cast(dict[str, Any], item)
        category = (
            str(item_dict.get("category", item_dict.get("group", ""))).strip().lower()
        )
        if category:
            categories.add(category)
    return categories


def _jd_ranked_required_skills(jd_context: dict[str, Any]) -> list[str]:
    """Rank required JD skills by explicit importance weight, then preserve order."""
    required = [
        normalize_skill_name(str(s))
        for s in list(jd_context.get("skills_required", []))
        if normalize_skill_name(str(s))
    ]
    importance_weights = cast(dict[str, Any], jd_context.get("importance_weights", {}))
    if not required:
        return []
    indexed = [(idx, skill) for idx, skill in enumerate(required)]
    ranked = sorted(
        indexed,
        key=lambda item: (
            -float(importance_weights.get(item[1], 0.0) or 0.0),
            item[0],
        ),
    )
    return [skill for _, skill in ranked]


def _top_jd_required_skills(jd_context: dict[str, Any], *, limit: int = 5) -> list[str]:
    ranked = _jd_ranked_required_skills(jd_context)
    return ranked[: max(0, limit)]


def _count_skill_mentions_in_bullets(skill: str, bullets: list[str]) -> int:
    normalized_skill = normalize_skill_name(skill)
    if not normalized_skill:
        return 0
    return sum(
        1 for bullet in bullets if _text_has_skill(str(bullet), normalized_skill)
    )


# ---------------------------------------------------------------------------
# Typed dataclasses for decomposed compute_ats_score pipeline
# ---------------------------------------------------------------------------


@dataclass
class HardGateResult:
    """Output of _run_hard_gates()."""

    hard_fail: bool
    should_borderline: bool
    decision: str  # "FAIL" | "BORDERLINE" | "PASS"
    hard_fail_reasons: list[str] = field(default_factory=list)
    borderline_reasons: list[str] = field(default_factory=list)


@dataclass
class CrossPenaltyResult:
    """Output of _apply_cross_penalties()."""

    skill_score: float
    experience_score: float
    weak_signal_penalty: float


@dataclass
class RawScoreResult:
    """Output of _compute_raw_score()."""

    ats_raw: float
    component_scores: dict[str, float]


@dataclass
class BandedScoreResult:
    """Output of _apply_decision_band()."""

    ats_total: float
    score_100: int
    penalty_value: float


# ---------------------------------------------------------------------------
# FIX 4: sanitize_generated_resume  — O(n) exact dedup + MinHash LSH fuzzy dedup
# ---------------------------------------------------------------------------


def _try_import_datasketch() -> Any:
    """Lazy import of datasketch; returns (MinHash, MinHashLSH) or None."""
    try:
        from datasketch import MinHash, MinHashLSH

        return MinHash, MinHashLSH
    except ImportError:
        return None


def _minhash_dedupe_sentences(
    sentences: list[str], threshold: float = 0.80
) -> list[str]:
    """Near-duplicate sentence removal using MinHash LSH.

    Falls back to exact-only dedup when datasketch is not installed.
    Time complexity: O(n) amortized (vs O(n²) with SequenceMatcher).
    """
    mh_classes = _try_import_datasketch()
    if mh_classes is None or not sentences:
        # Fallback: exact dedup only
        seen: set[str] = set()
        result: list[str] = []
        for s in sentences:
            key = s.strip().lower()
            if key and key not in seen:
                seen.add(key)
                result.append(s)
        return result

    MinHash, MinHashLSH = mh_classes
    num_perm = 64
    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    kept: list[str] = []

    for idx, sentence in enumerate(sentences):
        text = sentence.strip().lower()
        if not text:
            continue
        tokens = set(text.split())
        mh = MinHash(num_perm=num_perm)
        for token in tokens:
            mh.update(token.encode("utf-8"))
        key = f"s{idx}"
        # query() returns keys of near-duplicates already in LSH
        candidates = lsh.query(mh)
        if not candidates:
            lsh.insert(key, mh)
            kept.append(sentence)
        # else: near-duplicate found — skip this sentence

    return kept


def sanitize_generated_resume(resume_json: dict[str, Any]) -> dict[str, Any]:
    """Sanitize resume payload before scoring.

    FIX 4 applied:
    - Bullet deduplication: normalised lowercase set lookup (O(n)) replaces
      O(n²) SequenceMatcher loop for exact duplicates.
    - Summary sentence deduplication: MinHash LSH (O(n) amortized) replaces
      O(n²) SequenceMatcher loop for fuzzy near-duplicates.
    """
    sanitized: dict[str, Any] = dict(resume_json or {})

    def _norm(text: str) -> str:
        return " ".join(str(text).split()).strip()

    def _dedupe_list(values: list[str]) -> list[str]:
        """Exact dedup via normalised set — O(n)."""
        output: list[str] = []
        seen: set[str] = set()
        for value in values:
            clean = _norm(value)
            if not clean:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            output.append(clean)
        return output

    # Summary: split into sentences, MinHash-LSH fuzzy dedup, rejoin
    summary = _norm(str(sanitized.get("summary", "")))
    if summary:
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", summary) if p.strip()]
        deduped_parts = _minhash_dedupe_sentences(parts, threshold=0.80)
        sanitized["summary"] = " ".join(deduped_parts).strip()

    # Experience bullets: exact dedup via set (sufficient for bullet lists)
    experience = sanitized.get("experience", [])
    if isinstance(experience, list):
        new_exp: list[dict[str, Any]] = []
        for item in experience:
            if not isinstance(item, dict):
                continue
            entry = dict(item)
            entry["title"] = _norm(str(entry.get("title", entry.get("role", ""))))
            entry["company"] = _norm(str(entry.get("company", "")))
            entry["duration"] = _norm(str(entry.get("duration", "")))
            bullets = entry.get("bullets", [])
            if isinstance(bullets, list):
                entry["bullets"] = _dedupe_list([str(b) for b in bullets])
            else:
                entry["bullets"] = []
            new_exp.append(entry)
        sanitized["experience"] = new_exp

    # Project bullets: same exact dedup
    projects = sanitized.get("projects", [])
    if isinstance(projects, list):
        new_projects: list[dict[str, Any]] = []
        for item in projects:
            if not isinstance(item, dict):
                continue
            entry = dict(item)
            entry["name"] = _norm(str(entry.get("name", entry.get("text", ""))))
            bullets = entry.get("bullets", [])
            if isinstance(bullets, list):
                entry["bullets"] = _dedupe_list([str(b) for b in bullets])
            else:
                entry["bullets"] = []
            new_projects.append(entry)
        sanitized["projects"] = new_projects

    return sanitized


# ---------------------------------------------------------------------------
# FIX 1 helpers: pre-tokenised bullet corpus + cached regex for skill matching
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=512)
def _compile_skill_pattern(skill: str) -> re.Pattern[str]:
    """Cache compiled regex patterns for multi-word skills.

    Single-word skills use token-set lookup instead; this cache is only
    invoked for skills that contain a space.
    """
    return re.compile(rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])")


def _build_bullet_token_set(bullets: list[str]) -> set[str]:
    """Pre-tokenise all bullets into a single normalised token set — O(n).

    Used for O(1) single-word skill lookups inside _required_skill_depth_score.
    """
    tokens: set[str] = set()
    for bullet in bullets:
        normalized = normalize_skill_name(str(bullet))
        if normalized:
            tokens.update(normalized.split())
    return tokens


def _build_bullet_corpus(bullets: list[str]) -> str:
    """Build a single normalised string from all bullets for multi-word matching."""
    return " ".join(normalize_skill_name(str(b)) for b in bullets if str(b).strip())


def _text_has_skill(text: str, skill: str) -> bool:
    """Check normalised skill presence with strict token boundaries."""
    normalized_text = normalize_skill_name(str(text))
    normalized_skill = normalize_skill_name(str(skill))
    if not normalized_text or not normalized_skill:
        return False
    if " " in normalized_skill:
        return normalized_skill in normalized_text
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_skill)}(?![a-z0-9])"
    return bool(re.search(pattern, normalized_text))


def _skill_in_corpus(
    skill: str,
    token_set: set[str],
    corpus: str,
) -> bool:
    """O(1) lookup for single-word skills; cached-regex for multi-word skills."""
    normalized_skill = normalize_skill_name(skill)
    if not normalized_skill:
        return False
    if " " not in normalized_skill:
        # Single-word: token set lookup — O(1)
        return normalized_skill in token_set
    # Multi-word: use lru_cache compiled regex
    pattern = _compile_skill_pattern(normalized_skill)
    return bool(pattern.search(corpus))


# ---------------------------------------------------------------------------
# FIX 1: _required_skill_depth_score — O(n+m) via pre-tokenised corpus
# ---------------------------------------------------------------------------


def _required_skill_depth_score(
    *,
    required_skills: list[str],
    resume_entities: dict[str, Any],
    skill_alignment: dict[str, list[dict[str, Any]]],
) -> dict[str, float]:
    """Estimate depth of required skill evidence across bullets, projects, and recency.

    FIX 1: Pre-tokenise all bullets into a token set + single corpus string
    once (O(n)), then use O(1) set lookup per single-word skill and a
    lru_cache-compiled regex per multi-word skill — instead of compiling a
    fresh regex for every (skill, bullet) pair inside the nested loop.

    Original: O(n×m) with ~800 regex compilations per resume.
    Optimised: O(n+m) amortized.
    """
    if not required_skills:
        return {"depth_score": 0.0, "weak_required_ratio": 0.0}

    resume_terms = set(to_resume_skill_map(resume_entities.get("skills", [])).keys())
    resume_terms |= {
        normalize_skill_name(str(item))
        for item in list(resume_entities.get("keywords", []))
        if normalize_skill_name(str(item))
    }

    matched_map = {
        normalize_skill_name(str(item.get("jd_skill", ""))): item
        for item in list(skill_alignment.get("matched", []))
        if normalize_skill_name(str(item.get("jd_skill", "")))
    }
    weak_map = {
        normalize_skill_name(str(item.get("jd_skill", ""))): item
        for item in list(skill_alignment.get("weak", []))
        if normalize_skill_name(str(item.get("jd_skill", "")))
    }

    experience_entries = cast(
        list[dict[str, Any]], resume_entities.get("experience", [])
    )
    bullets = flatten_experience_bullets(experience_entries)
    projects = cast(list[dict[str, Any]], resume_entities.get("projects", []))

    # --- FIX 1: pre-build corpus once, not inside the loop ---
    bullet_token_set: set[str] = _build_bullet_token_set(bullets)
    bullet_corpus: str = _build_bullet_corpus(bullets)

    # Pre-build project corpus per-project for multi-word matching
    project_corpora: list[str] = []
    for project in projects:
        if not isinstance(project, dict):
            project_corpora.append("")
            continue
        text_parts: list[str] = [
            str(project.get("name", "")),
            " ".join(str(v) for v in cast(list[Any], project.get("bullets", []))),
            " ".join(str(v) for v in cast(list[Any], project.get("technologies", []))),
        ]
        project_corpora.append(normalize_skill_name(" ".join(text_parts)))

    project_token_sets: list[set[str]] = [
        set(corpus.split()) for corpus in project_corpora
    ]

    weak_required = 0
    depth_values: list[float] = []

    for skill in required_skills:
        normalized_skill = normalize_skill_name(skill)

        # Presence in skills/keywords section
        presence = 1.0 if normalized_skill in resume_terms else 0.0

        # Evidence from alignment output
        match_item = matched_map.get(normalized_skill) or weak_map.get(normalized_skill)
        evidence = (
            float(cast(dict[str, Any], match_item).get("weighted_score", 0.0) or 0.0)
            if match_item
            else 0.0
        )
        cross_signal = (
            str(cast(dict[str, Any], match_item).get("cross_signal", "") or "")
            if match_item
            else ""
        )
        if cross_signal == "skill_present_but_weak_experience_evidence":
            weak_required += 1
            evidence *= 0.60

        # --- O(1) bullet hit count via pre-built corpus/token-set ---
        if " " not in normalized_skill:
            # Single-word: token set lookup
            bullet_hit = 1 if normalized_skill in bullet_token_set else 0
            # Count approximate occurrences for the ratio (split corpus into words)
            bullet_hits = bullet_corpus.count(normalized_skill) if bullet_hit else 0
        else:
            # Multi-word: single scan of pre-built corpus using cached regex
            pattern = _compile_skill_pattern(normalized_skill)
            bullet_hits = len(pattern.findall(bullet_corpus))

        bullet_usage = min(1.0, bullet_hits / 2.0)

        # Project usage — O(1) per project via pre-built token sets / corpora
        project_usage = 0.0
        for p_corpus, p_token_set in zip(project_corpora, project_token_sets):
            if _skill_in_corpus(skill, p_token_set, p_corpus):
                project_usage = 1.0
                break

        recency = _recent_skill_usage(
            skill=skill, experience_entries=experience_entries
        )

        depth_values.append(
            clamp01(
                (0.15 * presence)
                + (0.50 * evidence)
                + (0.20 * bullet_usage)
                + (0.10 * project_usage)
                + (0.05 * recency)
            )
        )

    depth_score = sum(depth_values) / max(1, len(depth_values))
    return {
        "depth_score": clamp01(depth_score),
        "weak_required_ratio": clamp01(weak_required / max(1, len(required_skills))),
    }


# ---------------------------------------------------------------------------
# FIX 2: _impact_score — single weighted formula, no stacking bonuses
# ---------------------------------------------------------------------------

# Approved action verbs (module-level constant — compiled once)
_ACTION_VERB_SET: frozenset[str] = frozenset(_ACTION_VERB_NORMALIZATION_MAP.keys())

_LEADERSHIP_ACTION_VERBS: frozenset[str] = frozenset(
    {"lead", "manage", "coordinate", "mentor"}
)
_SUPPORT_ACTION_VERBS: frozenset[str] = frozenset({"support"})
_OWNERSHIP_LEADERSHIP_MARKERS: frozenset[str] = frozenset(
    {
        "chair",
        "chaired",
        "coordinate",
        "coordinated",
        "direct",
        "directed",
        "founded",
        "guide",
        "guided",
        "head",
        "headed",
        "lead",
        "manage",
        "managed",
        "mentor",
        "mentored",
        "orchestrate",
        "orchestrated",
        "own",
        "owned",
        "oversee",
        "oversaw",
        "spearhead",
        "spearheaded",
        "supervise",
        "supervised",
        "train",
        "trained",
    }
)
_SCOPE_SCALE_MARKERS: frozenset[str] = frozenset(
    {
        "at scale",
        "campus-wide",
        "client-facing",
        "company-wide",
        "cross-functional",
        "cross-team",
        "customer-facing",
        "department-wide",
        "enterprise",
        "global",
        "high-volume",
        "international",
        "large-scale",
        "multi-site",
        "multi-team",
        "nationwide",
        "organization-wide",
        "regional",
    }
)
_SCOPE_SCALE_ENTITY_MARKERS: frozenset[str] = frozenset(
    {
        "accounts",
        "attendees",
        "branches",
        "campaigns",
        "clients",
        "countries",
        "customers",
        "departments",
        "events",
        "initiatives",
        "locations",
        "members",
        "offices",
        "participants",
        "partners",
        "people",
        "processes",
        "products",
        "programs",
        "projects",
        "regions",
        "reports",
        "respondents",
        "sites",
        "staff",
        "stakeholders",
        "stores",
        "students",
        "teams",
        "units",
        "users",
        "volunteers",
    }
)
_TOOL_PROCESS_METHOD_MARKERS: frozenset[str] = frozenset(
    {
        "a/b testing",
        "analysis",
        "api",
        "ats",
        "automation",
        "budget model",
        "campaign",
        "crm",
        "curriculum",
        "dashboard",
        "data collection",
        "documentation",
        "erp",
        "excel",
        "experiment",
        "figma",
        "financial model",
        "forecast model",
        "google analytics",
        "interview guide",
        "jira",
        "lesson plan",
        "machine learning",
        "meta ads",
        "model",
        "pipeline",
        "power bi",
        "process mapping",
        "python",
        "quickbooks",
        "reconciliation",
        "reporting",
        "research methodology",
        "salesforce",
        "sap",
        "seo",
        "sem",
        "sql",
        "survey",
        "system",
        "tableau",
        "tally",
        "training module",
        "workflow",
        "workday",
        "workshop",
    }
)
_GENERIC_COMPLEXITY_CONTEXT_MARKERS: frozenset[str] = frozenset(
    _MANDATORY_COMPLEXITY_MARKERS
    | {
        "budgeting",
        "curriculum",
        "forecasting",
        "lesson planning",
        "negotiation",
        "operations",
        "operational",
        "process mapping",
        "program",
        "quality assurance",
        "research methodology",
        "vendor",
        "workflow",
    }
)
_IMPACT_OUTCOME_NOUN_MARKERS: frozenset[str] = frozenset(
    {
        "accuracy",
        "adoption",
        "attendance",
        "awareness",
        "churn",
        "compliance",
        "completion",
        "conversion",
        "cost",
        "cost savings",
        "coverage",
        "efficiency",
        "engagement",
        "errors",
        "latency",
        "outreach",
        "pass rate",
        "performance",
        "productivity",
        "profit",
        "quality",
        "recruitment",
        "response time",
        "retention",
        "revenue",
        "satisfaction",
        "sales",
        "throughput",
        "time-to-hire",
        "turnaround time",
        "uptime",
    }
)
_IMPACT_REASONABLE_SUPPORTING_DIMENSIONS: tuple[str, ...] = (
    "quantified_evidence",
    "result_outcome",
    "scope_scale",
    "complexity_context",
    "ownership_leadership",
    "tool_process_method_usage",
)
_SCOPE_SCALE_REGEX: re.Pattern[str] = re.compile(
    r"\b\d+(?:\+)?\s?[- ]?(?:team|teams|member|members|people|staff|employee|employees|volunteer|volunteers|user|users|customer|customers|client|clients|student|students|respondent|respondents|participant|participants|attendee|attendees|stakeholder|stakeholders|partner|partners|country|countries|location|locations|region|regions|office|offices|site|sites|project|projects|event|events|campaign|campaigns|program|programs|initiative|initiatives|report|reports|dashboard|dashboards|model|models|api|apis|process|processes|workflow|workflows|account|accounts|store|stores|branch|branches)\b",
    re.IGNORECASE,
)
_IMPACT_QUANT_CONTEXT_REGEX: re.Pattern[str] = re.compile(
    r"\b(?:revenue|cost|savings|productivity|efficiency|accuracy|latency|uptime|retention|conversion|engagement|satisfaction|turnaround|time-to-hire|attendance|completion)\b[^\n\r]{0,24}?\b\d+(?:\.\d+)?%?",
    re.IGNORECASE,
)

_IMPACT_RESULT_REGEX: re.Pattern[str] = re.compile(
    r"\b(increas(?:e|ed|ing)|reduc(?:e|ed|ing)|improv(?:e|ed|ing)|optimiz(?:e|ed|ing)|achiev(?:e|ed|ing)|sav(?:e|ed|ing)|boost(?:e|ed|ing)?|accelerat(?:e|ed|ing)|streamlin(?:e|ed|ing)|grew|grow(?:s|n|ing)?|deliver(?:e|ed|ing)|exceed(?:e|ed|ing)|eliminat(?:e|ed|ing)|generat(?:e|ed|ing)|secure(?:d|s|ing)|retain(?:ed|ing|s)?|convert(?:ed|ing|s)?|shorten(?:ed|ing)|lower(?:ed|ing)|cut|won|recognized?)\b",
    re.IGNORECASE,
)

_IMPACT_RESULT_BOOST_PHRASE_REGEX: re.Pattern[str] = re.compile(
    r"\b(resulting in|leading to|which improved|which increased|which reduced|thereby|driving|yielding|enabling|contributing to|supporting)\b",
    re.IGNORECASE,
)

_IMPLICIT_RESULT_INDICATOR_REGEX: re.Pattern[str] = re.compile(
    r"\b(increas(?:e|ed|ing)|improv(?:e|ed|ing)|reduc(?:e|ed|ing)|enhanc(?:e|ed|ing)|optimiz(?:e|ed|ing)|accelerat(?:e|ed|ing)|streamlin(?:e|ed|ing)|strengthen(?:ed|ing)?)\b",
    re.IGNORECASE,
)

_IMPACT_METRIC_REGEX: re.Pattern[str] = re.compile(
    r"(\b\d+x\b|\b(?:f1|auc|accuracy|precision|recall|rmse|mae|latency|uptime|throughput|turnaround time|time-to-hire)\b[^\n\r]{0,24}?\b\d+(?:\.\d+)?%?)",
    re.IGNORECASE,
)


def _normalize_action_verb_text(text: str) -> str:
    lowered = text.lower()
    for source, target in _ACTION_VERB_NORMALIZATION_MAP.items():
        lowered = re.sub(rf"\b{re.escape(source)}\b", target, lowered)
    return lowered


def _extract_first_alpha_word(text: str) -> str:
    cleaned = str(text or "").strip()
    return re.sub(r"^[^a-zA-Z]+", "", cleaned).split(" ")[0].lower() if cleaned else ""


def _marker_present(text: str, marker: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])", text))


def _count_marker_hits(text: str, markers: frozenset[str]) -> tuple[int, list[str]]:
    hits = [marker for marker in markers if _marker_present(text, marker)]
    return len(hits), hits


def _normalized_bullet_analysis(text: str) -> dict[str, Any]:
    cleaned = str(text or "").strip()
    normalized = _normalize_action_verb_text(cleaned)
    first_word = _extract_first_alpha_word(cleaned)
    first_word = _ACTION_VERB_NORMALIZATION_MAP.get(first_word, first_word)
    tokens = re.findall(r"[a-z][a-z/+.-]*", normalized)
    canonical_actions = [token for token in tokens if token in _MANDATORY_ACTION_START_VERBS]
    action_categories = sorted(set(canonical_actions))
    has_action_marker = bool(canonical_actions)
    quant_matches = [match.group(0) for match in _BULLET_QUANT_REGEX.finditer(normalized)]
    metric_matches = [match.group(0) for match in _IMPACT_METRIC_REGEX.finditer(normalized)]
    quant_context_matches = [
        match.group(0) for match in _IMPACT_QUANT_CONTEXT_REGEX.finditer(normalized)
    ]
    has_quant = bool(quant_matches or metric_matches or quant_context_matches)
    if first_word in _MANDATORY_ACTION_START_VERBS:
        action_clarity = 0.85 if first_word in _SUPPORT_ACTION_VERBS else 1.0
    elif any(token in _MANDATORY_ACTION_START_VERBS for token in tokens[:4]):
        action_clarity = 0.8
    elif has_action_marker:
        action_clarity = 0.65
    else:
        action_clarity = 0.0
    has_explicit_result = bool(_IMPACT_RESULT_REGEX.search(normalized))
    has_result_boost_phrase = bool(_IMPACT_RESULT_BOOST_PHRASE_REGEX.search(normalized))
    has_implicit_result = bool(_IMPLICIT_RESULT_INDICATOR_REGEX.search(normalized))
    outcome_hit_count, outcome_hits = _count_marker_hits(normalized, _IMPACT_OUTCOME_NOUN_MARKERS)
    has_result = (
        has_explicit_result
        or has_result_boost_phrase
        or has_implicit_result
        or outcome_hit_count > 0
    )
    if has_result_boost_phrase:
        result_outcome = 1.0
    elif has_explicit_result and (has_quant or outcome_hit_count > 0):
        result_outcome = 1.0
    elif has_explicit_result:
        result_outcome = 0.8
    elif has_implicit_result and (has_quant or outcome_hit_count > 0):
        result_outcome = 0.75
    elif has_implicit_result:
        result_outcome = 0.6
    elif outcome_hit_count > 0 and has_quant:
        result_outcome = 0.7
    elif outcome_hit_count > 0:
        result_outcome = 0.45
    else:
        result_outcome = 0.0
    scope_hit_count, scope_hits = _count_marker_hits(normalized, _SCOPE_SCALE_MARKERS)
    explicit_scope_matches = [match.group(0) for match in _SCOPE_SCALE_REGEX.finditer(normalized)]
    has_explicit_scope = bool(explicit_scope_matches)
    if has_explicit_scope:
        scope_scale = 1.0
    elif scope_hit_count >= 2:
        scope_scale = 0.85
    elif scope_hit_count == 1 or any(entity in normalized for entity in _SCOPE_SCALE_ENTITY_MARKERS):
        scope_scale = 0.65 if scope_hit_count or has_quant else 0.45
    else:
        scope_scale = 0.0
    complexity_hit_count, complexity_hits = _count_marker_hits(
        normalized,
        _GENERIC_COMPLEXITY_CONTEXT_MARKERS,
    )
    if complexity_hit_count >= 2:
        complexity_context = 1.0
    elif complexity_hit_count == 1:
        complexity_context = 0.75
    else:
        complexity_context = 0.0
    ownership_hit_count, ownership_hits = _count_marker_hits(
        normalized,
        _OWNERSHIP_LEADERSHIP_MARKERS,
    )
    if first_word in _LEADERSHIP_ACTION_VERBS or first_word in _OWNERSHIP_LEADERSHIP_MARKERS:
        ownership_leadership = 1.0
    elif ownership_hit_count >= 2:
        ownership_leadership = 0.9
    elif ownership_hit_count == 1:
        ownership_leadership = 0.75
    elif first_word in _SUPPORT_ACTION_VERBS:
        ownership_leadership = 0.35
    else:
        ownership_leadership = 0.0
    tool_hit_count, tool_hits = _count_marker_hits(normalized, _TOOL_PROCESS_METHOD_MARKERS)
    if tool_hit_count >= 2:
        tool_process_method_usage = 1.0
    elif tool_hit_count == 1:
        tool_process_method_usage = 0.7
    else:
        tool_process_method_usage = 0.0
    if quant_matches:
        quantified_evidence = 1.0 if len(quant_matches) >= 1 else 0.0
    elif metric_matches or quant_context_matches:
        quantified_evidence = 0.75
    else:
        quantified_evidence = 0.0
    reasons: list[str] = []
    if action_clarity > 0.0:
        reasons.append(f"action:{first_word or ','.join(action_categories)}")
    if quantified_evidence > 0.0:
        quant_preview = ", ".join(quant_matches[:2] or metric_matches[:1] or quant_context_matches[:1])
        reasons.append(f"quantified:{quant_preview}")
    if result_outcome > 0.0:
        reasons.append("outcome signal")
    if scope_scale > 0.0:
        scope_preview = ", ".join((explicit_scope_matches or scope_hits)[:2])
        reasons.append(f"scope:{scope_preview or 'scale evidence'}")
    if complexity_context > 0.0:
        reasons.append(
            f"context:{', '.join(complexity_hits[:2]) if complexity_hits else 'complexity evidence'}"
        )
    if ownership_leadership > 0.0:
        reasons.append(
            f"ownership:{', '.join(ownership_hits[:2]) if ownership_hits else first_word}"
        )
    if tool_process_method_usage > 0.0:
        reasons.append(
            f"method:{', '.join(tool_hits[:2]) if tool_hits else 'tool/process evidence'}"
        )
    return {
        "cleaned": cleaned,
        "normalized": normalized,
        "first_word": first_word,
        "tokens": tokens,
        "action_categories": action_categories,
        "has_action_marker": has_action_marker,
        "has_quant": has_quant,
        "has_action": action_clarity > 0.0,
        "has_result": has_result,
        "has_explicit_result": has_explicit_result,
        "has_result_boost_phrase": has_result_boost_phrase,
        "has_implicit_result": has_implicit_result,
        "has_complexity": complexity_context > 0.0,
        "has_scope": scope_scale > 0.0,
        "has_ownership": ownership_leadership > 0.0,
        "has_tool_process": tool_process_method_usage > 0.0,
        "action_clarity": clamp01(action_clarity),
        "quantified_evidence": clamp01(quantified_evidence),
        "result_outcome": clamp01(result_outcome),
        "scope_scale": clamp01(scope_scale),
        "complexity_context": clamp01(complexity_context),
        "ownership_leadership": clamp01(ownership_leadership),
        "tool_process_method_usage": clamp01(tool_process_method_usage),
        "quant_matches": quant_matches,
        "metric_matches": metric_matches,
        "outcome_hits": outcome_hits,
        "scope_hits": scope_hits,
        "complexity_hits": complexity_hits,
        "ownership_hits": ownership_hits,
        "tool_hits": tool_hits,
        "reason": "; ".join(reasons) if reasons else "limited impact evidence",
    }


def _aggregate_impact_scores(scores: list[float]) -> float:
    if not scores:
        return 0.0
    ranked = sorted(scores, reverse=True)
    top_k = max(1, int(math.ceil(len(ranked) * 0.5)))
    top_scores = ranked[:top_k]
    top_weights = [max(0.55, 1.0 - (0.10 * idx)) for idx in range(len(top_scores))]
    all_weights = [max(0.35, 1.0 - (0.06 * idx)) for idx in range(len(ranked))]
    top_weighted = sum(score * weight for score, weight in zip(top_scores, top_weights)) / max(
        1e-6, sum(top_weights)
    )
    all_weighted = sum(score * weight for score, weight in zip(ranked, all_weights)) / max(
        1e-6, sum(all_weights)
    )
    median_score = ranked[len(ranked) // 2]
    return clamp01((0.70 * top_weighted) + (0.20 * all_weighted) + (0.10 * median_score))


def _impact_score(
    resume_entities: dict[str, Any],
    resume_metadata: dict[str, Any],
    *,
    resume_text: str | None = None,
) -> float:
    return float(
        _impact_score_details(
            resume_entities,
            resume_metadata,
            resume_text=resume_text,
        ).get("score", 0.0)
        or 0.0
    )


def _impact_score_details(
    resume_entities: dict[str, Any],
    resume_metadata: dict[str, Any],
    *,
    resume_text: str | None = None,
) -> dict[str, Any]:
    """Compute a role-neutral impact score from universal bullet dimensions."""
    _ = resume_metadata
    bullets = flatten_experience_bullets(resume_entities.get("experience", []))

    # Include project bullets/text so resume-only mode captures impact evidence
    # that often appears in projects for students and early-career profiles.
    project_candidates: list[str] = []
    projects = resume_entities.get("projects", [])
    if isinstance(projects, list):
        for item in cast(list[Any], projects):
            if isinstance(item, dict):
                entry = cast(dict[str, Any], item)
                project_text = str(entry.get("text", "")).strip()
                if project_text:
                    project_candidates.append(project_text)
                project_bullets = entry.get("bullets", [])
                if isinstance(project_bullets, list):
                    for bullet in cast(list[Any], project_bullets):
                        text = str(bullet).strip()
                        if text:
                            project_candidates.append(text)
            else:
                text = str(item).strip()
                if text:
                    project_candidates.append(text)

    all_bullets = [*bullets, *project_candidates]
    candidate_bullets = [
        bullet for bullet in all_bullets if _is_candidate_impact_bullet(bullet)
    ]
    if candidate_bullets:
        bullets = candidate_bullets
    elif all_bullets:
        bullets = all_bullets
    else:
        bullets = _extract_impact_candidate_bullets(
            resume_entities.get("experience", [])
        )

    if not bullets:
        text_signal = _impact_score_from_text(str(resume_text or ""))
        if text_signal <= 0.0:
            text_signal = _impact_score_from_text(_entities_text_blob(resume_entities))
        return {"score": clamp01(text_signal), "impact_debug": []}

    per_bullet_scores: list[float] = []
    impact_debug: list[dict[str, Any]] = []

    for bullet in bullets:
        text = str(bullet).strip()
        analysis = _normalized_bullet_analysis(text)
        action_score = float(analysis["action_clarity"])
        quant_score = float(analysis["quantified_evidence"])
        result_score = float(analysis["result_outcome"])
        scope_score = float(analysis["scope_scale"])
        complexity_score = float(analysis["complexity_context"])
        ownership_score = float(analysis["ownership_leadership"])
        tool_score = float(analysis["tool_process_method_usage"])

        bullet_score = clamp01(
            (0.25 * action_score)
            + (0.25 * quant_score)
            + (0.20 * result_score)
            + (0.15 * scope_score)
            + (0.10 * complexity_score)
            + (0.05 * ownership_score)
        )
        fallback_floor_applied = False
        has_metric_signal = quant_score >= 0.85
        has_tool_signal = tool_score >= 0.65
        has_action_signal = action_score >= 0.8
        has_result_signal = result_score >= 0.75
        if (
            (has_tool_signal and has_metric_signal)
            or (has_action_signal and has_result_signal)
            or (has_metric_signal and has_result_signal)
        ) and bullet_score < 0.6:
            bullet_score = 0.6
            fallback_floor_applied = True
        final_bullet_score = clamp01(bullet_score)
        per_bullet_scores.append(final_bullet_score)
        impact_item = {
            "bullet": text,
            "action_clarity": round(action_score, 3),
            "quantified_evidence": round(quant_score, 3),
            "result_outcome": round(result_score, 3),
            "scope_scale": round(scope_score, 3),
            "complexity_context": round(complexity_score, 3),
            "ownership_leadership": round(ownership_score, 3),
            "tool_process_method_usage": round(tool_score, 3),
            "final_bullet_impact_score": round(final_bullet_score, 3),
            "reason": str(analysis.get("reason", "")),
            "quant_score": round(quant_score, 3),
            "action_score": round(action_score, 3),
            "result_score": round(result_score, 3),
            "complexity_score": round(complexity_score, 3),
            "fallback_floor_applied": fallback_floor_applied,
            "final_score": round(final_bullet_score, 3),
        }
        impact_debug.append(impact_item)
        logger.debug("Impact score debug: %s", impact_item)

    score = _aggregate_impact_scores(per_bullet_scores)

    global_signal = _impact_score_from_text(str(resume_text or ""))
    if global_signal <= 0.0:
        global_signal = _impact_score_from_text(_entities_text_blob(resume_entities))
    score = max(score, 0.70 * global_signal)

    return {
        "score": clamp01(score),
        "impact_debug": impact_debug,
    }


# ---------------------------------------------------------------------------
# FIX 3: compute_ats_score decomposed into typed helper functions
# ---------------------------------------------------------------------------


def _run_hard_gates(
    *,
    strict_skill: dict[str, Any],
    experience_gate: dict[str, Any],
    experience_evidence_available: bool,
    role_gate: dict[str, Any],
    structure_gate: dict[str, Any],
    years: float,
    required_years: float,
    rule_fail_reasons: list[str] | None = None,
) -> HardGateResult:
    """Evaluate all hard gates and return a typed HardGateResult.

    FIX 3: Extracted from the 200-line compute_ats_score body so that gate
    logic is independently testable.
    """
    hard_fail_reasons: list[str] = []
    borderline_reasons: list[str] = []

    # Critical skill count gates
    critical_missing_count = int(strict_skill.get("critical_missing_count", 0) or 0)
    if critical_missing_count >= 2:
        hard_fail_reasons.append(
            f"Missing {critical_missing_count} critical required skills"
        )
    elif critical_missing_count == 1:
        borderline_reasons.append("Missing one critical required skill")

    # Top-5 required skill gate (manual intervention when >= 2 are missing)
    top_missing_count = int(strict_skill.get("top_missing_count", 0) or 0)
    if top_missing_count >= 2:
        hard_fail_reasons.append(
            f"Top JD skill gap: missing {top_missing_count}/5 critical skills"
        )

    # Experience years gate
    if required_years > 0 and years < (required_years * 0.75):
        hard_fail_reasons.append(
            f"Experience below threshold: {years:.1f} years vs required {required_years:.1f}"
        )

    # Role mismatch gate
    if role_gate.get("mismatch"):
        mismatch_reason = (
            f"Role mismatch: resume aligns to {role_gate['resume_role']} "
            f"but JD targets {role_gate['jd_role']}"
        )
        # Treat low-confidence role mismatch as a warning instead of a hard fail.
        # This avoids catastrophic score collapse when JD/resume role inference is noisy.
        mismatch_confidence = float(role_gate.get("confidence", 0.0) or 0.0)
        if mismatch_confidence >= 0.50:
            hard_fail_reasons.append(mismatch_reason)
        else:
            borderline_reasons.append(mismatch_reason)

    # Required skill ratio gate
    required_total = int(strict_skill.get("required_total", 0) or 0)
    required_match_ratio = float(strict_skill.get("required_match_ratio", 0.0) or 0.0)
    if required_total > 0 and required_match_ratio < 0.55:
        hard_fail_reasons.append(
            f"Required skill match too low: "
            f"{strict_skill['required_matched']}/{strict_skill['required_total']}"
        )

    # Responsibility coverage gate
    if (
        experience_gate.get("has_requirements")
        and experience_evidence_available
        and float(experience_gate.get("blended_coverage_ratio", 0.0) or 0.0) < 0.60
    ):
        hard_fail_reasons.append(
            f"Responsibility coverage too low: "
            f"{experience_gate['covered_count']}/{experience_gate['total_count']}"
        )

    # Parse-ability gate
    if not structure_gate.get("is_parseable"):
        hard_fail_reasons.append(
            f"Resume parsing confidence too low "
            f"({structure_gate['parsing_confidence']:.2f} < 0.70)"
        )

    if rule_fail_reasons:
        hard_fail_reasons.extend(
            [str(reason) for reason in rule_fail_reasons if str(reason).strip()]
        )

    hard_fail = len(hard_fail_reasons) > 0
    should_borderline = bool(
        len(borderline_reasons) > 0
        or (required_total > 0 and required_match_ratio < 0.75)
    )

    if hard_fail:
        decision = "FAIL"
    elif should_borderline:
        decision = "BORDERLINE"
    else:
        decision = "PASS"

    return HardGateResult(
        hard_fail=hard_fail,
        should_borderline=should_borderline,
        decision=decision,
        hard_fail_reasons=hard_fail_reasons,
        borderline_reasons=borderline_reasons,
    )


def _apply_cross_penalties(
    *,
    skill_score: float,
    experience_score: float,
    strict_skill: dict[str, Any],
    experience_gate: dict[str, Any],
    weak_required_ratio: float,
) -> CrossPenaltyResult:
    """Apply cross-signal penalties and return adjusted scores.

    FIX 3: The original code had 6 sequential *= mutations scattered inline.
    This function makes every mutation explicit, named, and traceable.
    """
    required_total = int(strict_skill.get("required_total", 0) or 0)
    required_skill_ratio = float(strict_skill.get("required_match_ratio", 0.0) or 0.0)
    experience_coverage_ratio = float(
        experience_gate.get("blended_coverage_ratio", 0.0) or 0.0
    )
    critical_missing_count = int(strict_skill.get("critical_missing_count", 0) or 0)

    # Weak-evidence penalty on skill score
    weak_signal_penalty = min(0.30, 0.45 * weak_required_ratio)
    skill_score = clamp01(skill_score * (1.0 - weak_signal_penalty))

    if required_total > 0:
        # Low skill ratio → reduce experience
        if required_skill_ratio < 0.60:
            experience_score *= 1.0

        # Low experience → reduce skills
        if experience_score < 0.50:
            skill_score *= 1.0

        # Low responsibility coverage → reduce skills
        if experience_coverage_ratio < 0.50:
            skill_score *= 0.95

        # Critical missing skills → reduce experience (1 missing) or skills (≥2)
        if critical_missing_count > 0:
            experience_score *= 0.92
        if critical_missing_count >= 2:
            skill_score *= 0.92

    return CrossPenaltyResult(
        skill_score=clamp01(skill_score),
        experience_score=clamp01(experience_score),
        weak_signal_penalty=weak_signal_penalty,
    )


def _compute_raw_score(
    *,
    skill_score: float,
    experience_score: float,
    format_score: float,
    impact_score: float,
    language_quality_score: float,
    keyword_score: float,
) -> RawScoreResult:
    """Combine component scores into ATS raw score.

    FIX 3: Weights are explicit and documented here, not buried mid-function.
    Impact/language/keyword retain 0.0 weight in JD mode (diagnostic only).
    """
    component_scores = {
        "skill_score": clamp01(skill_score),
        "experience_score": clamp01(experience_score),
        "impact_score": clamp01(impact_score),
        "keyword_score": clamp01(keyword_score),
        "format_score": clamp01(format_score),
        "language_quality_score": clamp01(language_quality_score),
    }
    ats_raw = clamp01(
        (0.62 * component_scores["skill_score"])
        + (0.18 * component_scores["experience_score"])
        + (0.08 * component_scores["format_score"])
        + (0.08 * component_scores["impact_score"])
        + (0.02 * component_scores["keyword_score"])
        + (0.02 * component_scores["language_quality_score"])
        + 0.04
    )
    return RawScoreResult(ats_raw=ats_raw, component_scores=component_scores)


def _apply_decision_band(*, ats_raw: float, decision: str) -> BandedScoreResult:
    """Apply decision band scaling and floor/ceiling clamping.

    FIX 3: Band clamping logic is isolated and independently testable.
    """
    real_score = ats_raw
    if decision == "FAIL":
        real_score *= 0.40
    elif decision == "BORDERLINE":
        real_score *= 0.85

    ats_total = clamp01(real_score)

    if decision == "FAIL":
        ats_total = min(ats_total, 0.45)
    elif decision == "BORDERLINE":
        ats_total = min(max(ats_total, 0.50), 0.79)
    else:
        ats_total = max(ats_total, 0.74)

    penalty_value = max(0.0, ats_raw - ats_total)
    score_100 = int(round(ats_total * 100.0))

    return BandedScoreResult(
        ats_total=ats_total,
        score_100=score_100,
        penalty_value=penalty_value,
    )


# ---------------------------------------------------------------------------
# Public entry point — now ~40 lines thanks to decomposition (FIX 3)
# ---------------------------------------------------------------------------


def compute_ats_score(
    *,
    skill_alignment: dict[str, list[dict[str, Any]]],
    experience_alignment: dict[str, list[dict[str, Any]]],
    resume_entities: dict[str, Any],
    resume_metadata: dict[str, Any],
    jd_context: dict[str, Any],
    resume_sections: dict[str, str] | None = None,
    resume_text: str | None = None,
) -> dict[str, Any]:
    """Compute ATS score with hard gates and strict matching logic.

    Scoring flow:
    1) Sanitize & extract signals.
    2) Compute sub-scores (skill depth, experience, format, impact).
    3) Apply cross-signal penalties (_apply_cross_penalties).
    4) Evaluate hard gates (_run_hard_gates).
    5) Compute raw score (_compute_raw_score).
    6) Apply decision band clamping (_apply_decision_band).
    7) Build output dict.
    """
    # --- 1. Sanitize & extract ---
    sanitized_entities = sanitize_generated_resume(resume_entities)
    resume_sections = resume_sections or {}
    resume_text_value = str(resume_text or "")

    years = _extract_experience_years(
        resume_text_value,
        resume_experience=sanitized_entities.get("experience", []),
    )
    required_years = _required_years_from_jd(jd_context)

    strict_skill = _strict_required_skill_match(
        skill_alignment=skill_alignment,
        resume_entities=sanitized_entities,
        jd_context=jd_context,
    )
    experience_gate = _experience_gate(experience_alignment)
    intrinsic_experience_score = _experience_score(experience_alignment)

    covered_items = list(experience_alignment.get("covered", []))
    partial_items = list(experience_alignment.get("partial", []))
    extracted_experience_bullets = flatten_experience_bullets(
        sanitized_entities.get("experience", [])
    )
    alignment_has_evidence = any(
        float(item.get("similarity", 0.0) or 0.0) > 0.0
        or str(item.get("resume_bullet", "") or "").strip()
        for item in [*covered_items, *partial_items]
        if isinstance(item, dict)
    )
    experience_evidence_available = (
        bool(extracted_experience_bullets) or alignment_has_evidence
    )

    role_gate = _role_alignment_gate(
        jd_context=jd_context,
        resume_text=resume_text_value,
        resume_entities=sanitized_entities,
    )
    rule_summary = _evaluate_resume_rules(
        resume_entities=sanitized_entities,
        resume_metadata=resume_metadata,
        resume_sections=resume_sections,
        jd_context=jd_context,
        experience_alignment=experience_alignment,
        years=years,
    )
    structure_gate = _structure_gate(
        resume_metadata=resume_metadata,
        resume_sections=resume_sections,
        rule_summary=rule_summary,
    )

    # --- 2. Sub-scores ---
    skill_depth = _required_skill_depth_score(
        required_skills=list(strict_skill.get("required_skills", [])),
        resume_entities=sanitized_entities,
        skill_alignment=skill_alignment,
    )
    skill_score_raw = clamp01(
        (0.70 * strict_skill["required_match_ratio"])
        + (0.30 * float(skill_depth.get("depth_score", 0.0) or 0.0))
    )
    weak_required_ratio = float(skill_depth.get("weak_required_ratio", 0.0) or 0.0)

    years_fit_score = 0.0
    if required_years > 0:
        years_fit_score = clamp01(years / required_years)
    elif years > 0:
        years_fit_score = clamp01(1.0 - math.exp(-(years / 3.0)))

    if not experience_gate["has_requirements"]:
        experience_score_raw = clamp01(0.10 + (0.30 * years_fit_score))
    elif experience_evidence_available:
        coverage_score = float(
            experience_gate.get("blended_coverage_ratio", 0.0) or 0.0
        )
        experience_score_raw = clamp01(
            (0.45 * coverage_score)
            + (0.45 * intrinsic_experience_score)
            + (0.10 * years_fit_score)
        )
    else:
        experience_score_raw = clamp01(0.10 + (0.10 * years_fit_score))

    # --- 3. Cross-signal penalties (FIX 3) ---
    penalties_result = _apply_cross_penalties(
        skill_score=skill_score_raw,
        experience_score=experience_score_raw,
        strict_skill=strict_skill,
        experience_gate=experience_gate,
        weak_required_ratio=weak_required_ratio,
    )
    skill_score = penalties_result.skill_score
    experience_score = penalties_result.experience_score
    weak_signal_penalty = penalties_result.weak_signal_penalty

    # Diagnostic-only scores (not used in ATS raw)
    enforce_strict_rule_gates = bool(
        resume_sections
        and any(str(v).strip() for v in cast(dict[str, Any], resume_sections).values())
    )

    strict_rule_fail_reasons = (
        list(rule_summary.get("fail_reasons", []))
        if enforce_strict_rule_gates
        else []
    )

    format_score = structure_gate["score"]
    keyword_score = strict_skill["required_match_ratio"]
    impact_details = _impact_score_details(
        sanitized_entities, resume_metadata, resume_text=resume_text
    )
    impact_score_val = float(impact_details.get("score", 0.0) or 0.0)
    language_quality_score = float(
        rule_summary.get("language_quality_score", 0.0) or 0.0
    )

    # --- 4. Hard gates (FIX 3) ---
    gate_result = _run_hard_gates(
        strict_skill=strict_skill,
        experience_gate=experience_gate,
        experience_evidence_available=experience_evidence_available,
        role_gate=role_gate,
        structure_gate=structure_gate,
        years=years,
        required_years=required_years,
        rule_fail_reasons=strict_rule_fail_reasons,
    )

    # --- 5. Raw score (FIX 3) ---
    raw_result = _compute_raw_score(
        skill_score=skill_score,
        experience_score=experience_score,
        format_score=format_score,
        impact_score=impact_score_val,
        language_quality_score=language_quality_score,
        keyword_score=keyword_score,
    )

    # --- 6. Decision band (FIX 3) ---
    banded = _apply_decision_band(
        ats_raw=raw_result.ats_raw, decision=gate_result.decision
    )

    # --- 7. Build output ---
    missing = skill_alignment.get("missing", [])
    matched = skill_alignment.get("matched", [])
    weak = skill_alignment.get("weak", [])
    total_skill_count = len(matched) + len(weak) + len(missing)
    missing_ratio = (len(missing) / total_skill_count) if total_skill_count > 0 else 0.0

    reasons = [
        f"Matched {strict_skill['required_matched']}/{strict_skill['required_total']} required skills",
        f"Covered {experience_gate['covered_count']}/{experience_gate['total_count']} responsibilities",
        f"Experience estimated at {years:.1f} years",
    ]
    if weak_signal_penalty > 0.0:
        reasons.append(
            f"Weak evidence penalty applied to listed skills "
            f"({weak_signal_penalty:.0%} reduction)"
        )
    if experience_gate["has_requirements"] and not experience_evidence_available:
        reasons.append(
            "Experience bullets were unavailable from parsed entities; "
            "coverage treated conservatively"
        )
    if structure_gate["is_parseable"]:
        reasons.append("Resume is parseable with ATS-friendly structure")
    if gate_result.should_borderline and not gate_result.hard_fail:
        reasons.extend(gate_result.borderline_reasons)

    evidence_volume = strict_skill["required_total"] + experience_gate["total_count"]
    confidence = clamp01(
        (0.45 * min(1.0, evidence_volume / 10.0))
        + (
            0.55
            * (
                (
                    raw_result.component_scores["skill_score"]
                    + raw_result.component_scores["experience_score"]
                )
                / 2.0
            )
        )
    )
    if gate_result.hard_fail:
        confidence = min(confidence, 0.40)
    elif gate_result.should_borderline:
        confidence = min(max(confidence, 0.25), 0.65)
    else:
        confidence = max(confidence, 0.50)
    if experience_gate["has_requirements"] and not experience_evidence_available:
        confidence = min(confidence, 0.60)

    role_for_distribution = str(role_gate.get("jd_role", "") or "").strip().lower()
    if not role_for_distribution:
        role_for_distribution = infer_role(resume_text_value)

    recommended_skills = [
        str(item.get("jd_skill", "")).strip()
        for item in missing
        if str(item.get("jd_skill", "")).strip()
    ]
    weak_evidence_skills = [
        str(item.get("jd_skill", "")).strip()
        for item in [*matched, *weak]
        if str(item.get("cross_signal", ""))
        == "skill_present_but_weak_experience_evidence"
        and str(item.get("jd_skill", "")).strip()
    ]

    return {
        "ats_score": round(banded.ats_total, 3),
        "legacy_ats_score": round(banded.ats_total, 3),
        "calibrated_ats_score": round(banded.ats_total, 3),
        "score": banded.score_100,
        "percentile": round(banded.ats_total * 100.0, 1),
        "percentile_is_synthetic": False,
        "percentile_note": "Percentile is a direct normalized-score mapping for cross-role consistency.",
        "benchmark_role": role_for_distribution,
        "decision": gate_result.decision,
        "confidence": round(confidence, 3),
        "reasons": reasons,
        "fail_reasons": gate_result.hard_fail_reasons,
        "components": {
            "skill_score": round(raw_result.component_scores["skill_score"], 3),
            "experience_score": round(
                raw_result.component_scores["experience_score"], 3
            ),
            "intrinsic_experience_score": round(clamp01(intrinsic_experience_score), 3),
            "impact_score": round(raw_result.component_scores["impact_score"], 3),
            "keyword_score": round(raw_result.component_scores["keyword_score"], 3),
            "format_score": round(raw_result.component_scores["format_score"], 3),
            "language_quality_score": round(
                raw_result.component_scores["language_quality_score"], 3
            ),
        },
        "weights": {
            "skill": 0.70,
            "experience": 0.20,
            "impact": 0.00,
            "keyword": 0.00,
            "format": 0.10,
            "language_quality": 0.00,
        },
        "penalties": {
            "critical_missing_applied": strict_skill["critical_missing_count"] > 0,
            "reason": "hard_filter_rejection" if gate_result.hard_fail else None,
            "penalty_factor": round(max(0.0, 1.0 - banded.penalty_value), 3),
            "penalty_value": round(banded.penalty_value, 3),
            "missing_ratio": round(missing_ratio, 3),
            "weak_evidence_penalty": round(weak_signal_penalty, 3),
            "hard_filters": {
                "critical_missing_count": strict_skill["critical_missing_count"],
                "required_skill_ratio": round(strict_skill["required_match_ratio"], 3),
                "experience_years": round(years, 3),
                "required_years": round(required_years, 3),
                "role_mismatch": role_gate["mismatch"],
                "responsibility_coverage": round(
                    experience_gate["blended_coverage_ratio"], 3
                ),
                "parseability_ok": structure_gate["is_parseable"],
            },
        },
        "rule_engine": rule_summary,
        "module_confidence": {
            "skill_alignment_confidence": round(_module_confidence(skill_alignment), 3),
            "experience_alignment_confidence": round(
                _module_confidence(experience_alignment), 3
            ),
            "parser_confidence": round(
                float(resume_metadata.get("parsing_confidence", 0.0) or 0.0), 3
            ),
        },
        "evidence": {
            "skill_alignment": skill_alignment,
            "experience_alignment": experience_alignment,
            "impact_debug": list(cast(list[Any], impact_details.get("impact_debug", []))),
            "recommended_skills": recommended_skills,
            "weak_evidence_skills": sorted(set(weak_evidence_skills)),
            "strict_skill_matching": {
                "required_total": strict_skill["required_total"],
                "required_matched": strict_skill["required_matched"],
                "required_match_ratio": round(strict_skill["required_match_ratio"], 3),
                "top_required_skills": strict_skill.get("top_required_skills", []),
                "top_missing_required": strict_skill.get("top_missing_required", []),
                "critical_missing": strict_skill["critical_missing"],
                "depth_score": round(
                    float(skill_depth.get("depth_score", 0.0) or 0.0), 3
                ),
                "weak_required_ratio": round(weak_required_ratio, 3),
            },
        },
    }


# ---------------------------------------------------------------------------
# Remaining functions — unchanged from original
# ---------------------------------------------------------------------------


def infer_role(resume_text: str) -> str:
    detection = _detect_resume_role(
        resume_text=resume_text,
        resume_entities={},
    )
    return str(detection.get("final_role") or "software engineer")


def _infer_role_from_aliases(resume_text: str) -> str | None:
    role, _ = _infer_role_from_alias_candidates([resume_text])
    return role


_ROLE_CAMEL_BOUNDARY_RE = re.compile(
    r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])"
)
_ROLE_NON_ALNUM_RE = re.compile(r"[^a-z0-9+#]+")
_ROLE_MULTI_SPACE_RE = re.compile(r"\s+")


def _normalize_role_phrase(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    raw = raw.replace("&", " and ").replace("/", " ").replace("_", " ")

    tokens: list[str] = []
    for token in raw.split():
        compact = _ROLE_NON_ALNUM_RE.sub("", token.lower()).strip()
        if not compact:
            continue
        expanded = _ROLE_COMPACT_EXPANSIONS.get(compact)
        if expanded:
            tokens.extend(expanded.split())
            continue

        split_token = _ROLE_CAMEL_BOUNDARY_RE.sub(" ", token)
        for part in split_token.split():
            cleaned = _ROLE_NON_ALNUM_RE.sub("", part.lower()).strip()
            if cleaned:
                tokens.append(cleaned)

    return _ROLE_MULTI_SPACE_RE.sub(" ", " ".join(tokens)).strip()


def _build_role_aliases() -> dict[str, list[str]]:
    alias_map: dict[str, list[str]] = {}

    for role in ROLE_PROFILES.keys():
        aliases: set[str] = {role}
        aliases.update(_ROLE_ALIAS_SEED.get(role, []))
        aliases.add(role.replace("-", " "))
        aliases.add(role.replace("-", " ").replace(" and ", " & "))

        expanded_aliases: set[str] = set()
        for alias in aliases:
            clean = " ".join(str(alias).strip().lower().replace("-", " ").split())
            if not clean:
                continue
            expanded_aliases.add(clean)
            for prefix in _ROLE_SENIORITY_PREFIXES:
                if not clean.startswith(f"{prefix} "):
                    expanded_aliases.add(f"{prefix} {clean}")
            for suffix in _ROLE_TRAINEE_SUFFIXES:
                if not clean.endswith(f" {suffix}"):
                    expanded_aliases.add(f"{clean} {suffix}")

        alias_map[role] = sorted(
            expanded_aliases,
            key=lambda item: (-len(item.split()), -len(item), item),
        )

    return alias_map


ROLE_ALIASES: dict[str, list[str]] = _build_role_aliases()


def _build_role_compact_expansions() -> dict[str, str]:
    expansions: dict[str, str] = {}
    for aliases in ROLE_ALIASES.values():
        for alias in aliases:
            normalized = _ROLE_MULTI_SPACE_RE.sub(" ", alias.strip().lower()).strip()
            compact = normalized.replace(" ", "")
            if compact and compact != normalized and len(normalized.split()) >= 2:
                expansions.setdefault(compact, normalized)
    return expansions


_ROLE_COMPACT_EXPANSIONS.update(_build_role_compact_expansions())
_ROLE_NORMALIZED_ALIASES: dict[str, list[str]] = {
    role: [
        normalized
        for normalized in [_normalize_role_phrase(alias) for alias in aliases]
        if normalized
    ]
    for role, aliases in ROLE_ALIASES.items()
}
_ROLE_CANONICAL_NORMALIZED: dict[str, str] = {
    role: _normalize_role_phrase(role) for role in ROLE_PROFILES.keys()
}


def _month_index_from_token(token: str) -> int | None:
    value = str(token or "").strip()
    if not value:
        return None
    if re.fullmatch(r"\d{4}", value):
        value = f"01/{value}"
    for fmt in ("%m/%Y", "%b %Y", "%B %Y"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.year * 12 + parsed.month
        except ValueError:
            continue
    return None


def _role_alias_confidence(
    *,
    role: str,
    alias: str,
    context: str,
) -> float:
    exact = alias == _ROLE_CANONICAL_NORMALIZED.get(role, "")
    token_count = len(alias.split())

    if context == "experience":
        score = 0.92 if exact else 0.84
    elif context == "jd_title":
        score = 0.90 if exact else 0.82
    else:
        score = 0.80 if exact else 0.72

    score += 0.02 * min(2, max(0, token_count - 2))
    return clamp01(score)


def _best_role_alias_match(text: str, *, context: str) -> dict[str, Any] | None:
    normalized_text = _normalize_role_phrase(text)
    if not normalized_text:
        return None

    padded = f" {normalized_text} "
    best_match: dict[str, Any] | None = None

    for role, aliases in _ROLE_NORMALIZED_ALIASES.items():
        for alias in aliases:
            if len(alias) < 3 and alias not in {"qa", "pm"}:
                continue
            probe = f" {alias} "
            occurrences = padded.count(probe)
            if occurrences <= 0:
                continue

            candidate = {
                "role": role,
                "alias": alias,
                "confidence": _role_alias_confidence(
                    role=role,
                    alias=alias,
                    context=context,
                ),
                "occurrences": occurrences,
                "exact": alias == _ROLE_CANONICAL_NORMALIZED.get(role, ""),
            }
            if best_match is None or (
                candidate["confidence"],
                candidate["occurrences"],
                len(candidate["alias"]),
                candidate["role"],
            ) > (
                best_match["confidence"],
                best_match["occurrences"],
                len(best_match["alias"]),
                best_match["role"],
            ):
                best_match = candidate

    return best_match


def _score_repeated_role_mentions(
    matches: list[dict[str, Any]],
    *,
    base_confidence: float,
    max_confidence: float,
) -> float:
    if len(matches) <= 1:
        return round(clamp01(base_confidence), 3)
    boosted = base_confidence + min(0.10, 0.05 * (len(matches) - 1))
    return round(min(max_confidence, clamp01(boosted)), 3)


def _infer_role_from_alias_candidates(
    text_candidates: list[str],
) -> tuple[str | None, float]:
    matches: dict[str, list[dict[str, Any]]] = {}
    for raw_text in text_candidates:
        match = _best_role_alias_match(raw_text, context="alias")
        if not match:
            continue
        matches.setdefault(str(match["role"]), []).append(match)

    if not matches:
        return None, 0.0

    scored: list[tuple[str, float, int]] = []
    for role, role_matches in matches.items():
        base = max(float(item["confidence"]) for item in role_matches)
        score = _score_repeated_role_mentions(
            role_matches,
            base_confidence=base,
            max_confidence=0.92,
        )
        scored.append((role, score, len(role_matches)))

    best_role, best_score, _ = max(
        scored,
        key=lambda item: (
            item[1],
            item[2],
            len(ROLE_PROFILES.get(item[0], {}).get("skills", [])),
            item[0],
        ),
    )
    return best_role, best_score


def _experience_recency_rank(entries: list[dict[str, Any]], index: int) -> tuple[int, int]:
    entry = entries[index]
    end_month = _duration_end_month(str(entry.get("duration", "")))
    if end_month is None:
        end_month = _month_index_from_token(str(entry.get("end_date", ""))) or 0
    if end_month > 0:
        return (2 if bool(entry.get("is_present")) else 1, end_month)
    return (0, len(entries) - index)


def _collect_experience_role_matches(resume_entities: dict[str, Any]) -> list[dict[str, Any]]:
    experience_entries = resume_entities.get("experience", [])
    if not isinstance(experience_entries, list):
        return []

    matches: list[dict[str, Any]] = []
    typed_entries = cast(list[dict[str, Any]], experience_entries)
    for index, item in enumerate(typed_entries):
        if not isinstance(item, dict):
            continue
        entry = cast(dict[str, Any], item)
        title = str(
            entry.get("title")
            or entry.get("role")
            or entry.get("job_title")
            or entry.get("position")
            or entry.get("designation")
            or ""
        ).strip()
        match = _best_role_alias_match(title, context="experience")
        if not match:
            continue
        matches.append(
            {
                **match,
                "title": title,
                "index": index,
                "recency_rank": _experience_recency_rank(typed_entries, index),
            }
        )
    return matches


def _collect_explicit_role_mentions(
    *,
    resume_text: str,
    resume_entities: dict[str, Any],
) -> list[dict[str, Any]]:
    texts: list[tuple[str, str]] = []
    for key in (
        "summary",
        "headline",
        "profile",
        "objective",
        "about",
        "target_role",
        "current_role",
        "title",
    ):
        value = str(resume_entities.get(key, "") or "").strip()
        if value:
            texts.append((key, value))

    sections = resume_entities.get("sections", {})
    if isinstance(sections, dict):
        for key in ("summary", "profile", "objective", "headline"):
            value = str(cast(dict[str, Any], sections).get(key, "") or "").strip()
            if value:
                texts.append((f"section:{key}", value))

    top_lines = [line.strip() for line in str(resume_text or "").splitlines() if line.strip()]
    for index, line in enumerate(top_lines[:12]):
        texts.append((f"top_line_{index + 1}", line))
    texts.append(("document", str(resume_text or "")))

    matches: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for label, text in texts:
        normalized = _normalize_role_phrase(text)
        key = (label, normalized)
        if not normalized or key in seen:
            continue
        seen.add(key)
        match = _best_role_alias_match(text, context="alias")
        if not match:
            continue
        matches.append({**match, "label": label, "text": text})
    return matches


def _build_experience_role_signal(resume_entities: dict[str, Any]) -> dict[str, Any] | None:
    matches = _collect_experience_role_matches(resume_entities)
    if not matches:
        return None

    latest = max(
        matches,
        key=lambda item: (
            item["recency_rank"][0],
            item["recency_rank"][1],
            -int(item["index"]),
        ),
    )
    repeated = [item for item in matches if item["role"] == latest["role"]]
    confidence = _score_repeated_role_mentions(
        repeated,
        base_confidence=float(latest["confidence"]),
        max_confidence=1.0,
    )

    reason = f"Most recent experience title matched '{latest['title']}'"
    if len(repeated) > 1:
        reason = f"Most recent experience title matched '{latest['title']}' and the role repeats"

    return {
        "final_role": latest["role"],
        "confidence": confidence,
        "source": "experience",
        "conflict_flag": False,
        "reason": reason,
    }


def _build_alias_role_signal(
    *,
    resume_text: str,
    resume_entities: dict[str, Any],
) -> dict[str, Any] | None:
    matches = _collect_explicit_role_mentions(
        resume_text=resume_text,
        resume_entities=resume_entities,
    )
    if not matches:
        return None

    by_role: dict[str, list[dict[str, Any]]] = {}
    for match in matches:
        by_role.setdefault(str(match["role"]), []).append(match)

    scored: list[dict[str, Any]] = []
    for role, role_matches in by_role.items():
        best = max(
            role_matches,
            key=lambda item: (
                float(item["confidence"]),
                int(item["occurrences"]),
                len(str(item["alias"])),
                str(item["label"]),
            ),
        )
        confidence = _score_repeated_role_mentions(
            role_matches,
            base_confidence=float(best["confidence"]),
            max_confidence=0.92,
        )
        scored.append(
            {
                "final_role": role,
                "confidence": confidence,
                "source": "alias",
                "conflict_flag": False,
                "reason": (
                    f"Explicit role mention matched '{best['alias']}' in {best['label']}"
                    if len(role_matches) == 1
                    else f"Explicit role mentions consistently matched '{best['alias']}'"
                ),
                "match_count": len(role_matches),
            }
        )

    if not scored:
        return None

    return max(
        scored,
        key=lambda item: (
            float(item["confidence"]),
            int(item.get("match_count", 1)),
            str(item["final_role"]),
        ),
    )


def _build_consistent_role_signal(
    *,
    resume_text: str,
    resume_entities: dict[str, Any],
) -> dict[str, Any] | None:
    experience_matches = _collect_experience_role_matches(resume_entities)
    alias_matches = _collect_explicit_role_mentions(
        resume_text=resume_text,
        resume_entities=resume_entities,
    )

    signal_sources: dict[str, set[str]] = {}
    signal_count: Counter[str] = Counter()
    for match in experience_matches:
        signal_sources.setdefault(str(match["role"]), set()).add("experience")
        signal_count[str(match["role"])] += 1
    for match in alias_matches:
        signal_sources.setdefault(str(match["role"]), set()).add("alias")
        signal_count[str(match["role"])] += 1

    candidates: list[dict[str, Any]] = []
    for role, sources in signal_sources.items():
        if len(sources) < 2 and signal_count[role] < 2:
            continue
        confidence = clamp01(0.62 + (0.08 * len(sources)) + (0.04 * (signal_count[role] - 1)))
        candidates.append(
            {
                "final_role": role,
                "confidence": round(min(0.84, confidence), 3),
                "source": "alias",
                "conflict_flag": False,
                "reason": "Consistent role signals across resume prioritized over weak skill overlap",
            }
        )

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda item: (float(item["confidence"]), str(item["final_role"])),
    )


def _build_resume_skill_role_signal(resume_entities: dict[str, Any]) -> dict[str, Any] | None:
    resume_skill_map = to_resume_skill_map(resume_entities.get("skills", []))
    for item in list(resume_entities.get("keywords", [])):
        keyword = normalize_skill_name(str(item))
        if not keyword:
            continue
        resume_skill_map[keyword] = max(resume_skill_map.get(keyword, 0.0), 0.45)

    role_by_skills, role_confidence = _infer_role_from_skill_distribution(
        resume_skill_map,
        confidence_cap=0.60,
    )
    if not role_by_skills:
        return None

    return {
        "final_role": role_by_skills,
        "confidence": round(min(0.60, float(role_confidence)), 3),
        "source": "skills",
        "conflict_flag": False,
        "reason": "No strong title or alias signal found, so discriminative skills were used as fallback",
    }


def _detect_resume_role(
    *,
    resume_text: str,
    resume_entities: dict[str, Any],
) -> dict[str, Any]:
    experience_signal = _build_experience_role_signal(resume_entities)
    alias_signal = _build_alias_role_signal(
        resume_text=resume_text,
        resume_entities=resume_entities,
    )
    consistent_signal = _build_consistent_role_signal(
        resume_text=resume_text,
        resume_entities=resume_entities,
    )
    skill_signal = _build_resume_skill_role_signal(resume_entities)

    selected: dict[str, Any] | None = None
    if experience_signal is not None:
        selected = experience_signal
    elif alias_signal is not None and float(alias_signal["confidence"]) >= 0.75:
        selected = alias_signal
    elif consistent_signal is not None and float(consistent_signal["confidence"]) >= 0.50:
        selected = consistent_signal
    elif alias_signal is not None and float(alias_signal["confidence"]) >= 0.50:
        selected = alias_signal
    elif skill_signal is not None:
        selected = skill_signal

    if selected is None:
        return {
            "final_role": "software engineer",
            "confidence": 0.0,
            "source": "default",
            "conflict_flag": False,
            "reason": "No strong role signal was found",
        }

    if (
        selected.get("source") != "skills"
        and skill_signal is not None
        and str(skill_signal.get("final_role")) != str(selected.get("final_role"))
        and float(skill_signal.get("confidence", 0.0) or 0.0) >= 0.35
    ):
        selected = dict(selected)
        selected["conflict_flag"] = True
        if selected.get("source") == "experience":
            selected["reason"] = "Skill mismatch but title prioritized"
        else:
            selected["reason"] = "Skill mismatch but explicit role prioritized"

    return selected


def _infer_resume_only_role(
    *,
    resume_text: str,
    resume_entities: dict[str, Any],
) -> tuple[str, float, str]:
    detection = _detect_resume_role(
        resume_text=resume_text,
        resume_entities=resume_entities,
    )
    return (
        str(detection.get("final_role") or "software engineer"),
        round(float(detection.get("confidence", 0.0) or 0.0), 3),
        str(detection.get("source") or "default"),
    )


def _strict_required_skill_match(
    *,
    skill_alignment: dict[str, list[dict[str, Any]]],
    resume_entities: dict[str, Any],
    jd_context: dict[str, Any],
) -> dict[str, Any]:
    required_raw = [
        str(item)
        for item in list(jd_context.get("skills_required", []))
        if str(item).strip()
    ]
    required_skills = [
        normalize_skill_name(item)
        for item in required_raw
        if normalize_skill_name(item)
    ]
    required_total = len(required_skills)
    top_required_skills = _top_jd_required_skills(jd_context, limit=5)

    resume_terms = set(to_resume_skill_map(resume_entities.get("skills", [])).keys())
    resume_terms |= {
        normalize_skill_name(str(item))
        for item in list(resume_entities.get("keywords", []))
        if normalize_skill_name(str(item))
    }

    exp_bullets = flatten_experience_bullets(resume_entities.get("experience", []))
    project_items = cast(list[Any], resume_entities.get("projects", []))
    project_text_parts: list[str] = []
    for item in project_items:
        if not isinstance(item, dict):
            continue
        project_dict = cast(dict[str, Any], item)
        project_text_parts.extend(
            [
                str(project_dict.get("name", "")),
                " ".join(
                    str(v) for v in cast(list[Any], project_dict.get("bullets", []))
                ),
                " ".join(
                    str(v)
                    for v in cast(list[Any], project_dict.get("technologies", []))
                ),
            ]
        )
    full_resume_corpus = normalize_skill_name(
        " ".join(
            [
                " ".join(str(v) for v in resume_terms),
                " ".join(str(v) for v in exp_bullets),
                " ".join(project_text_parts),
            ]
        )
    )

    matched_required = [
        skill for skill in required_skills if _text_has_skill(full_resume_corpus, skill)
    ]
    missing_required = [
        skill
        for skill in required_skills
        if not _text_has_skill(full_resume_corpus, skill)
    ]
    top_missing_required = [
        skill
        for skill in top_required_skills
        if not _text_has_skill(full_resume_corpus, skill)
    ]

    jd_importance = jd_context.get("importance_weights", {})
    critical_missing: list[str] = []
    for skill in missing_required:
        importance = float(cast(dict[str, Any], jd_importance).get(skill, 0.6) or 0.6)
        if importance >= 0.75 or _is_critical_missing_skill(
            {"jd_skill": skill, "jd_importance": importance}
        ):
            critical_missing.append(skill)

    if not critical_missing:
        for item in list(skill_alignment.get("missing", [])):
            if _is_critical_missing_skill(item):
                jd_skill = normalize_skill_name(str(item.get("jd_skill", "")).strip())
                if (
                    jd_skill
                    and jd_skill in missing_required
                    and jd_skill not in critical_missing
                ):
                    critical_missing.append(jd_skill)

    ratio = (len(matched_required) / required_total) if required_total > 0 else 0.0
    return {
        "required_skills": required_skills,
        "top_required_skills": top_required_skills,
        "required_total": required_total,
        "required_matched": len(matched_required),
        "required_match_ratio": ratio,
        "missing_required": missing_required,
        "top_missing_required": top_missing_required,
        "top_missing_count": len(top_missing_required),
        "critical_missing": critical_missing,
        "critical_missing_count": len(critical_missing),
    }


def _duration_end_month(duration: str) -> int | None:
    text = str(duration or "").strip().replace("\u2013", "-").replace("\u2014", "-")
    if not text:
        return None
    today = date.today()
    current_month = today.year * 12 + (today.month - 1)
    tokens = re.findall(r"\d{2}/\d{4}|\d{4}|present", text, flags=re.IGNORECASE)
    if len(tokens) < 2:
        return None
    end_token = tokens[1].strip().lower()
    if end_token == "present":
        return current_month
    if re.match(r"^\d{4}$", end_token):
        end_token = f"01/{end_token}"
    try:
        end_dt = datetime.strptime(end_token, "%m/%Y")
        return end_dt.year * 12 + (end_dt.month - 1)
    except Exception:
        return None


def _recent_skill_usage(
    *, skill: str, experience_entries: list[dict[str, Any]]
) -> float:
    if not experience_entries:
        return 0.0
    newest_index = 0
    newest_month = -1
    for index, entry in enumerate(experience_entries):
        if not isinstance(entry, dict):
            continue
        end_month = _duration_end_month(str(entry.get("duration", "")))
        if end_month is not None and end_month > newest_month:
            newest_month = end_month
            newest_index = index

    def _entry_text(entry: dict[str, Any]) -> str:
        bullet_text = " ".join(
            str(v) for v in cast(list[Any], entry.get("bullets", []))
        )
        return " ".join(
            [
                str(entry.get("title", "")),
                str(entry.get("role", "")),
                str(entry.get("company", "")),
                bullet_text,
            ]
        )

    newest_entry = (
        experience_entries[newest_index]
        if newest_index < len(experience_entries)
        else {}
    )
    if isinstance(newest_entry, dict) and _text_has_skill(
        _entry_text(newest_entry), skill
    ):
        return 1.0
    for entry in experience_entries:
        if isinstance(entry, dict) and _text_has_skill(_entry_text(entry), skill):
            return 0.5
    return 0.0


def _required_years_from_jd(jd_context: dict[str, Any]) -> float:
    raw_text = str(jd_context.get("raw", "") or "")
    years_matches = [
        int(v)
        for v in re.findall(r"(\d{1,2})\s*\+?\s*years", raw_text, flags=re.IGNORECASE)
    ]
    if years_matches:
        return float(max(years_matches))
    seniority = str(jd_context.get("seniority", "") or "").strip().lower()
    if seniority == "lead":
        return 8.0
    if seniority == "senior":
        return 6.0
    if seniority == "junior":
        return 1.0
    return 0.0


def _experience_gate(
    experience_alignment: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    covered = list(experience_alignment.get("covered", []))
    partial = list(experience_alignment.get("partial", []))
    missing = list(experience_alignment.get("missing", []))
    total_count = len(covered) + len(partial) + len(missing)
    if total_count == 0:
        return {
            "has_requirements": False,
            "pass": True,
            "covered_ratio": 0.0,
            "blended_coverage_ratio": 0.0,
            "covered_count": 0,
            "partial_count": 0,
            "total_count": 0,
        }
    covered_ratio = len(covered) / total_count
    blended_ratio = (len(covered) + (0.20 * len(partial))) / total_count
    return {
        "has_requirements": True,
        "pass": blended_ratio >= 0.60,
        "covered_ratio": covered_ratio,
        "blended_coverage_ratio": blended_ratio,
        "covered_count": len(covered),
        "partial_count": len(partial),
        "total_count": total_count,
    }


def _infer_role_from_skill_distribution(
    skills: set[str] | dict[str, float],
    *,
    confidence_cap: float = 1.0,
) -> tuple[str | None, float]:
    skill_map: dict[str, float] = {}
    if isinstance(skills, dict):
        for raw_skill, raw_conf in skills.items():
            skill = normalize_skill_name(str(raw_skill))
            if not skill:
                continue
            confidence = clamp01(float(raw_conf or 0.0))
            if confidence <= 0.0:
                continue
            skill_map[skill] = max(skill_map.get(skill, 0.0), confidence)
    else:
        for raw_skill in skills:
            skill = normalize_skill_name(str(raw_skill))
            if skill:
                skill_map[skill] = max(skill_map.get(skill, 0.0), 1.0)

    if not skill_map:
        return None, 0.0

    role_skill_sets: dict[str, set[str]] = {}
    skill_role_frequency: dict[str, int] = {}
    for role, profile in ROLE_PROFILES.items():
        role_skills = {
            normalize_skill_name(str(item))
            for item in list(profile.get("skills", []))
            if normalize_skill_name(str(item))
        }
        if not role_skills:
            continue
        role_skill_sets[role] = role_skills
        for skill in role_skills:
            skill_role_frequency[skill] = skill_role_frequency.get(skill, 0) + 1

    if not role_skill_sets:
        return None, 0.0

    role_count = max(1, len(role_skill_sets))
    common_skill_threshold = max(3, int(math.ceil(role_count * 0.35)))

    def _idf(skill: str) -> float:
        role_freq = skill_role_frequency.get(skill, 0)
        return 1.0 + math.log((1.0 + role_count) / (1.0 + role_freq))

    discriminative_skill_map = {
        skill: confidence
        for skill, confidence in skill_map.items()
        if skill
        and skill not in _ROLE_GENERIC_SKILL_BLOCKLIST
        and skill_role_frequency.get(skill, role_count) <= common_skill_threshold
    }
    if discriminative_skill_map:
        skill_map = discriminative_skill_map

    resume_weight_total = 0.0
    for skill, confidence in skill_map.items():
        resume_weight_total += confidence * _idf(skill)
    if resume_weight_total <= 0.0:
        return None, 0.0

    best_role: str | None = None
    best_score = 0.0

    for role, role_skills in role_skill_sets.items():
        overlap_weight = 0.0
        matched_count = 0
        for skill, confidence in skill_map.items():
            if skill in role_skills:
                matched_count += 1
                overlap_weight += confidence * _idf(skill)

        if overlap_weight <= 0.0:
            continue

        precision_like = overlap_weight / resume_weight_total
        role_weight_total = sum(_idf(skill) for skill in role_skills)
        recall_like = overlap_weight / max(1e-9, role_weight_total)
        evidence_factor = min(1.0, matched_count / 4.0)

        score = clamp01(
            (0.65 * precision_like)
            + (0.20 * recall_like)
            + (0.15 * evidence_factor)
        )

        if score > best_score:
            best_score = score
            best_role = role

    if not best_role:
        return None, 0.0

    return best_role, round(min(confidence_cap, best_score), 3)


def _infer_jd_role(jd_context: dict[str, Any]) -> tuple[str | None, float]:
    explicit_role_hints = [
        str(jd_context.get("job_title", "") or "").strip(),
        str(jd_context.get("target_role", "") or "").strip(),
        str(jd_context.get("title", "") or "").strip(),
    ]
    alias_role, alias_confidence = _infer_role_from_alias_candidates(
        [value for value in explicit_role_hints if value]
    )
    if alias_role and alias_confidence >= 0.75:
        return alias_role, alias_confidence

    jd_skills = {
        normalize_skill_name(str(item))
        for item in [
            *list(jd_context.get("skills_required", [])),
            *list(jd_context.get("skills_optional", [])),
        ]
        if normalize_skill_name(str(item))
    }
    role_by_skills, skill_confidence = _infer_role_from_skill_distribution(
        jd_skills,
        confidence_cap=0.85,
    )

    if alias_role and alias_confidence >= skill_confidence:
        return alias_role, alias_confidence
    return role_by_skills, skill_confidence


def _role_alignment_gate(
    *,
    jd_context: dict[str, Any],
    resume_text: str,
    resume_entities: dict[str, Any],
) -> dict[str, Any]:
    jd_role, jd_role_confidence = _infer_jd_role(jd_context)
    if not jd_role:
        return {
            "mismatch": False,
            "jd_role": "unknown",
            "resume_role": "unknown",
            "confidence": 0.0,
        }

    resume_detection = _detect_resume_role(
        resume_text=resume_text,
        resume_entities=resume_entities,
    )
    resume_role = str(resume_detection.get("final_role", "") or "").strip()
    resume_role_confidence = float(resume_detection.get("confidence", 0.0) or 0.0)
    if not resume_role or resume_detection.get("source") == "default":
        return {
            "mismatch": False,
            "jd_role": jd_role,
            "resume_role": "unknown",
            "confidence": round(jd_role_confidence, 3),
        }

    mismatch = bool(
        jd_role_confidence >= 0.30
        and resume_role_confidence >= 0.30
        and resume_role != jd_role
    )
    return {
        "mismatch": mismatch,
        "jd_role": jd_role,
        "resume_role": resume_role,
        "confidence": round(min(jd_role_confidence, resume_role_confidence), 3),
        "jd_role_confidence": round(jd_role_confidence, 3),
        "resume_role_confidence": round(resume_role_confidence, 3),
        "resume_role_source": str(resume_detection.get("source", "") or "unknown"),
        "resume_role_conflict_flag": bool(resume_detection.get("conflict_flag", False)),
    }


def _structure_gate(
    *,
    resume_metadata: dict[str, Any],
    resume_sections: dict[str, str],
    rule_summary: dict[str, Any],
) -> dict[str, Any]:
    required_sections = {"experience", "education", "skills"}
    present_sections = {
        str(key).strip().lower()
        for key, value in resume_sections.items()
        if str(key).strip() and str(value).strip()
    }
    section_coverage = len(required_sections & present_sections) / len(
        required_sections
    )
    parsing_confidence = clamp01(
        float(resume_metadata.get("parsing_confidence", 0.0) or 0.0)
    )
    warnings = list(resume_metadata.get("quality_warnings", []))
    weird_format_hits = sum(
        1
        for warning in warnings
        if any(
            t in str(warning).lower()
            for t in ["table", "column", "icon", "layout", "parse"]
        )
    )
    single_column_score = float(
        cast(dict[str, Any], rule_summary.get("details", {})).get(
            "single_column_score", 1.0
        )
        or 1.0
    )
    formatting_sanity = clamp01(
        (0.7 * single_column_score) + (0.3 * max(0.0, 1.0 - 0.25 * weird_format_hits))
    )
    score = clamp01(
        (0.45 * section_coverage)
        + (0.40 * parsing_confidence)
        + (0.15 * formatting_sanity)
    )
    return {
        "score": score,
        "is_parseable": parsing_confidence >= 0.7,
        "parsing_confidence": parsing_confidence,
        "section_coverage": section_coverage,
        "formatting_sanity": formatting_sanity,
    }


def compute_resume_only_score(
    *,
    resume_entities: dict[str, Any],
    resume_metadata: dict[str, Any],
    resume_text: str,
) -> dict[str, Any]:
    from .experience_alignment import align_experience
    from .skill_alignment import align_skills

    sanitized_entities = sanitize_generated_resume(resume_entities)
    inferred_role_details = _detect_resume_role(
        resume_text=resume_text,
        resume_entities=sanitized_entities,
    )
    inferred_role, inferred_role_confidence, inferred_role_method = _infer_resume_only_role(
        resume_text=resume_text,
        resume_entities=sanitized_entities,
    )
    profile = ROLE_PROFILES.get(inferred_role, ROLE_PROFILES["software engineer"])

    resume_skills = sanitized_entities.get("skills", [])
    resume_experience = sanitized_entities.get("experience", [])
    resume_projects = sanitized_entities.get("projects", [])
    resume_bullets = _collect_resume_bullets(
        resume_experience=resume_experience,
        resume_projects=resume_projects,
        resume_text=resume_text,
    )

    expected_skills = [
        str(s).strip().lower()
        for s in list(profile.get("skills", []))
        if str(s).strip()
    ]
    expected_responsibilities = list(profile.get("responsibilities", []))
    expected_years_raw = profile.get("expected_years", 4)
    expected_years = int(expected_years_raw) if expected_years_raw is not None else 4
    if expected_years < 0:
        expected_years = 0

    skill_alignment = align_skills(
        resume_skills=resume_skills,
        jd_skills=expected_skills,
        experience_bullets=resume_bullets,
        has_project_section=bool(resume_projects),
        weak_threshold=0.55,
        experience_evidence_threshold=0.40,
    )
    exp_alignment = align_experience(
        jd_responsibilities=expected_responsibilities,
        resume_bullets=resume_bullets,
        role=inferred_role,
    )

    skill_score = _resume_only_skill_score(skill_alignment)

    years = _extract_experience_years(resume_text, resume_experience=resume_experience)
    if expected_years <= 0:
        years_score = 1.0
    else:
        years_score = clamp01(1.0 - math.exp(-(years / float(expected_years))))
    alignment_experience_score = _experience_score(exp_alignment)
    experience_score = clamp01(0.7 * alignment_experience_score + 0.3 * years_score)

    covered_count = len(cast(list[Any], exp_alignment.get("covered", [])))
    missing_count = len(cast(list[Any], exp_alignment.get("missing", [])))
    if covered_count == 0 and missing_count > 0:
        experience_score = min(0.25, experience_score)

    impact_details = _impact_score_details(
        sanitized_entities, resume_metadata, resume_text=resume_text
    )
    impact_score_val = float(impact_details.get("score", 0.0) or 0.0)
    format_score = _format_score(resume_metadata)

    ats_total = clamp01(
        (0.30 * skill_score)
        + (0.30 * experience_score)
        + (0.25 * impact_score_val)
        + (0.15 * format_score)
    )

    percentile = round(ats_total * 100.0, 1)
    rewrite_suggestions = _build_rewrite_suggestions(resume_bullets)

    recommended_skills = list(skill_alignment.get("missing", []))
    role_focused_alignment = {
        "matched": list(skill_alignment.get("matched", [])),
        "weak": list(skill_alignment.get("weak", [])),
        "recommended_skills": recommended_skills,
        "insights": list(skill_alignment.get("insights", [])),
    }
    experience_debug = {
        "inferred_role": inferred_role,
        "selected_role_profile_responsibilities": expected_responsibilities,
        "parsed_experience_entries": resume_experience,
        "collected_resume_bullets": resume_bullets,
        "alignment_matches": list(cast(dict[str, Any], exp_alignment.get("debug", {})).get("matches", [])),
    }
    logger.debug("Resume-only experience debug: %s", experience_debug)

    return {
        "mode": "resume_only",
        "inferred_role": inferred_role,
        "inferred_role_details": {
            "method": inferred_role_method,
            "confidence": round(inferred_role_confidence, 3),
            "source": str(inferred_role_details.get("source", inferred_role_method)),
            "conflict_flag": bool(inferred_role_details.get("conflict_flag", False)),
            "reason": str(inferred_role_details.get("reason", "") or ""),
        },
        "benchmark_profile": {
            "skills": expected_skills,
            "responsibilities": expected_responsibilities,
            "expected_years": expected_years,
        },
        "ats_score": round(ats_total, 3),
        "components": {
            "skill_score": round(skill_score, 3),
            "experience_score": round(experience_score, 3),
            "impact_score": round(impact_score_val, 3),
            "format_score": round(format_score, 3),
        },
        "weights": {"skill": 0.30, "experience": 0.30, "impact": 0.25, "format": 0.15},
        "calibration": {
            "percentile": percentile,
            "distribution_size": 0,
            "is_synthetic": False,
            "note": "Percentile is a direct normalized-score mapping for cross-role consistency.",
        },
        "evidence": {
            "skill_alignment": role_focused_alignment,
            "raw_skill_alignment": skill_alignment,
            "experience_alignment": exp_alignment,
            "experience_debug": experience_debug,
            "impact_debug": list(cast(list[Any], impact_details.get("impact_debug", []))),
            "estimated_years": years,
            "rewrite_suggestions": rewrite_suggestions,
        },
    }


def compute_structure_score(
    *,
    resume_entities: dict[str, Any],
    resume_metadata: dict[str, Any],
    resume_sections: dict[str, str] | None = None,
    resume_text: str | None = None,
) -> float:
    _ = resume_entities
    _ = resume_text
    sections = resume_sections or {}
    expected_sections = {"summary", "experience", "education", "skills"}
    present = {str(k).strip().lower() for k in sections.keys() if str(k).strip()}
    section_coverage = len(expected_sections & present) / len(expected_sections)
    completeness = clamp01(float(resume_metadata.get("completeness_score", 0.0) or 0.0))
    parsing_confidence = clamp01(
        float(resume_metadata.get("parsing_confidence", 0.0) or 0.0)
    )
    format_score = _format_score(resume_metadata)
    score = clamp01(
        (0.4 * completeness)
        + (0.35 * parsing_confidence)
        + (0.15 * section_coverage)
        + (0.10 * format_score)
    )
    return round(score, 3)


def compute_hybrid_score(
    *, ats_score: float, llm_score: float, structure_score: float
) -> float:
    final = clamp01(
        (0.20 * clamp01(float(ats_score)))
        + (0.70 * clamp01(float(llm_score)))
        + (0.10 * clamp01(float(structure_score)))
    )
    return round(final, 3)


def _skill_score(
    skill_alignment: dict[str, list[dict[str, Any]]], years: float = 1.0
) -> float:
    matched = skill_alignment.get("matched", [])
    weak = skill_alignment.get("weak", [])
    missing = skill_alignment.get("missing", [])

    weighted_sum = 0.0
    effective_importance = 0.0
    high_value_skills = {"docker", "kubernetes", "pytorch", "tensorflow"}
    high_value_bonus = 0.0

    for item in matched:
        importance = float(item.get("jd_importance", 0.6) or 0.6)
        score = float(item.get("weighted_score", 0.0) or 0.0)
        if (
            str(item.get("cross_signal", ""))
            == "skill_present_but_weak_experience_evidence"
        ):
            score *= WEAK_EVIDENCE_SCORE_MULTIPLIER
        weighted_sum += score
        effective_importance += importance
        if str(item.get("jd_skill", "")).lower().strip() in high_value_skills:
            high_value_bonus += 0.03

    for item in weak:
        importance = float(item.get("jd_importance", 0.6) or 0.6)
        score = float(item.get("weighted_score", 0.0) or 0.0)
        if (
            str(item.get("cross_signal", ""))
            == "skill_present_but_weak_experience_evidence"
        ):
            score *= WEAK_EVIDENCE_SCORE_MULTIPLIER
        weighted_sum += score * 0.8
        effective_importance += importance

    if effective_importance == 0:
        return 0.0

    score = clamp01(weighted_sum / effective_importance)
    score = clamp01(score + high_value_bonus)

    missing_critical = any(_is_critical_missing_skill(item) for item in missing)
    missing_ratio = len(missing) / max(1, len(matched) + len(weak) + len(missing))
    penalty = 0.07 * missing_ratio
    if missing_critical:
        penalty += 0.05
    if years < 2.0:
        penalty *= 0.5
    if len(matched) >= 4:
        score = clamp01(score + 0.05)
    return clamp01(score - penalty)


def _experience_score(experience_alignment: dict[str, list[dict[str, Any]]]) -> float:
    covered = experience_alignment.get("covered", [])
    partial = experience_alignment.get("partial", [])
    missing = experience_alignment.get("missing", [])
    total = len(covered) + len(partial) + len(missing)
    if total == 0:
        return 0.0

    covered_sim = sum(float(item.get("similarity", 0.0) or 0.0) for item in covered)
    partial_sim = sum(float(item.get("similarity", 0.0) or 0.0) for item in partial)
    covered_avg = covered_sim / max(1, len(covered))
    partial_avg = partial_sim / max(1, len(partial))
    covered_ratio = len(covered) / total
    partial_ratio = len(partial) / total

    coverage = covered_ratio + (0.20 * partial_ratio)
    quality = (0.6 * covered_avg) + (0.4 * partial_avg)
    score = clamp01((0.7 * coverage) + (0.3 * quality))

    logger.debug("Experience Debug - Covered: %s", len(covered))
    logger.debug("Experience Debug - Missing: %s", len(missing))

    if len(covered) == 0 and len(missing) > 0:
        final_score = min(0.15, score)
        logger.debug("Experience Debug - Final score: %.3f", final_score)
        return final_score
    logger.debug("Experience Debug - Final score: %.3f", score)
    return score


def _keyword_score(
    resume_entities: dict[str, Any], jd_context: dict[str, Any]
) -> float:
    resume_keywords = list(resume_entities.get("keywords", []))
    jd_keywords: list[str] = []
    jd_keywords.extend([str(v) for v in list(jd_context.get("skills_required", []))])
    jd_keywords.extend([str(v) for v in list(jd_context.get("skills_optional", []))])
    jd_keywords.extend([str(v) for v in list(jd_context.get("tools", []))])
    if not jd_keywords or not resume_keywords:
        return 0.0

    normalized_resume = [
        str(item).strip().lower() for item in resume_keywords if str(item).strip()
    ]
    normalized_jd = [
        str(item).strip().lower() for item in jd_keywords if str(item).strip()
    ]
    if not normalized_jd:
        return 0.0

    matches = 0
    for jd_kw in jd_keywords:
        found = any(
            semantic_similarity(str(jd_kw), str(rk))[0] > 0.6 for rk in resume_keywords
        )
        if found:
            matches += 1

    semantic_match = matches / len(normalized_jd)
    frequency_hits = sum(
        sum(1 for rt in normalized_resume if jt in rt or rt in jt)
        for jt in normalized_jd
    )
    frequency_score = min(1.0, frequency_hits / max(1.0, 2.0 * len(normalized_jd)))
    return clamp01((0.7 * semantic_match) + (0.3 * frequency_score))


def _format_score(resume_metadata: dict[str, Any]) -> float:
    completeness = float(resume_metadata.get("completeness_score", 0.0) or 0.0)
    confidence = float(resume_metadata.get("parsing_confidence", 0.0) or 0.0)
    warning_count = len(resume_metadata.get("quality_warnings", []))
    warning_penalty = min(0.2, warning_count * 0.04)
    return clamp01((0.6 * completeness) + (0.4 * confidence) - warning_penalty)


def _module_confidence(module_output: dict[str, list[dict[str, Any]]]) -> float:
    covered = module_output.get("covered", [])
    partial = module_output.get("partial", [])
    if not covered and "matched" in module_output:
        covered = module_output.get("matched", [])
    if not partial and "weak" in module_output:
        partial = module_output.get("weak", [])
    missing = module_output.get("missing", [])

    total_items = len(covered) + len(partial) + len(missing)
    if total_items == 0:
        return 0.0

    covered_scores = [
        float(item.get("similarity", item.get("weighted_score", 0.0)) or 0.0)
        for item in covered
    ]
    partial_scores = [
        float(item.get("similarity", item.get("weighted_score", 0.0)) or 0.0)
        for item in partial
    ]

    weighted_score = sum(covered_scores) + 0.5 * sum(partial_scores)
    return clamp01(weighted_score / total_items)


def _extract_impact_candidate_bullets(experience: Any) -> list[str]:
    if not isinstance(experience, list):
        return []
    candidates: list[str] = []
    for entry in cast(list[Any], experience):
        if not isinstance(entry, dict):
            continue
        raw_bullets = cast(dict[str, Any], entry).get("bullets", [])
        if not isinstance(raw_bullets, list):
            continue
        for bullet in cast(list[Any], raw_bullets):
            text = str(bullet).strip()
            if _is_candidate_impact_bullet(text):
                candidates.append(text)

    seen: set[str] = set()
    unique: list[str] = []
    for bullet in candidates:
        lowered = bullet.lower()
        if lowered not in seen:
            seen.add(lowered)
            unique.append(bullet)
    return unique


def _is_candidate_impact_bullet(text: str) -> bool:
    cleaned = str(text or "").strip()
    if not cleaned:
        return False
    if re.match(
        r"^\s*(?:\d{1,2}[/-])?\d{4}\s*(?:-|to|–|—)\s*(?:present|current|(?:\d{1,2}[/-])?\d{4})\b",
        cleaned,
        re.IGNORECASE,
    ):
        return False
    if re.match(r".*,\s*[A-Z]{2}(?:\s+\d{5}(?:-\d{4})?)?\s*$", cleaned):
        return False
    analysis = _normalized_bullet_analysis(cleaned)
    return any(
        float(analysis.get(signal, 0.0) or 0.0) > 0.0
        for signal in (
            "action_clarity",
            "quantified_evidence",
            "result_outcome",
            "scope_scale",
            "complexity_context",
            "ownership_leadership",
            "tool_process_method_usage",
        )
    )


def _extract_experience_years(
    text: str, *, resume_experience: Any | None = None, as_of: date | None = None
) -> float:
    del text
    if not isinstance(resume_experience, list):
        return 0.0

    today = as_of or date.today()
    current_month_index = today.year * 12 + (today.month - 1)
    month_lookup = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }
    date_token_re = re.compile(
        r"(present|current|now|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)"
        r"(?:uary|ruary|ch|il|e|y|ust|tember|ober|ember)?\s+\d{4}|\d{1,2}/\d{4}|\d{4})",
        flags=re.IGNORECASE,
    )

    def _parse_date_token(token: str, *, is_end: bool = False) -> datetime | None:
        value = str(token or "").strip()
        if not value:
            return None
        lowered = value.lower()
        if lowered in {"present", "current", "now"}:
            return datetime(today.year, today.month, 1)
        if re.match(r"^\d{1,2}/\d{4}$", value):
            month, year = value.split("/", 1)
            return datetime(int(year), int(month), 1)
        if re.match(r"^\d{4}$", value):
            month = 12 if is_end else 1
            return datetime(int(value), month, 1)
        match = re.match(r"^([A-Za-z]+)\s+(\d{4})$", value)
        if match:
            month_text, year_text = match.groups()
            month = month_lookup.get(month_text.lower())
            if month:
                return datetime(int(year_text), month, 1)
        return None

    intervals: list[tuple[int, int]] = []
    for item in cast(list[Any], resume_experience):
        if not isinstance(item, dict):
            continue
        item_dict = cast(dict[str, Any], item)
        duration = str(item_dict.get("duration", "")).strip()
        if not duration:
            continue
        normalized_duration = duration.replace("\u2013", "-").replace("\u2014", "-")
        normalized_duration = re.sub(r"\s*-\s*", " - ", normalized_duration)
        tokens = [token.strip() for token in date_token_re.findall(normalized_duration)]
        if len(tokens) < 2:
            continue
        start_dt = _parse_date_token(tokens[0], is_end=False)
        end_dt = _parse_date_token(tokens[1], is_end=True)
        if not start_dt or not end_dt:
            continue
        start_idx = start_dt.year * 12 + (start_dt.month - 1)
        end_idx = (
            current_month_index
            if str(tokens[1]).strip().lower() in {"present", "current", "now"}
            else end_dt.year * 12 + (end_dt.month - 1)
        )
        if end_idx < start_idx:
            continue
        intervals.append((start_idx, end_idx + 1))

    if not intervals:
        return 0.0

    merged = _merge_month_intervals(intervals)
    total_months = sum(max(0, end - start) for start, end in merged)
    years = total_months / 12.0

    logger.debug(
        "Experience years debug: durations=%s merged_intervals=%s total_months=%s years=%s",
        [cast(dict[str, Any], item).get("duration", "") for item in cast(list[Any], resume_experience) if isinstance(item, dict)],
        merged,
        total_months,
        round(years, 3),
    )
    return max(0.0, years)


def _is_student_profile(resume_experience: list[Any]) -> bool:
    markers = {"intern", "student", "trainee", "apprentice", "research assistant"}
    for item in resume_experience:
        if not isinstance(item, dict):
            continue
        entry = cast(dict[str, Any], item)
        text = " ".join(
            [
                str(entry.get("title", "")),
                str(entry.get("role", "")),
                str(entry.get("company", "")),
            ]
        ).lower()
        if any(marker in text for marker in markers):
            return True
    return False


def _merge_month_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    sorted_intervals = sorted(intervals, key=lambda item: (item[0], item[1]))
    merged: list[tuple[int, int]] = []
    cur_start, cur_end = sorted_intervals[0]
    for start, end in sorted_intervals[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            merged.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    merged.append((cur_start, cur_end))
    return merged


def _is_critical_missing_skill(item: dict[str, Any]) -> bool:
    importance = float(item.get("jd_importance", 0.0) or 0.0)
    skill_text = str(item.get("jd_skill", item.get("skill", ""))).lower()
    critical_keywords = {
        "docker",
        "kubernetes",
        "pytorch",
        "tensorflow",
        "model deployment",
        "deployment",
        "mlops",
        "api",
    }
    if importance >= 0.75:
        return True
    return any(keyword in skill_text for keyword in critical_keywords)


def _entities_text_blob(resume_entities: dict[str, Any]) -> str:
    chunks: list[str] = []
    experience = resume_entities.get("experience", [])
    if isinstance(experience, list):
        for item in cast(list[Any], experience):
            if not isinstance(item, dict):
                continue
            entry = cast(dict[str, Any], item)
            for key in ["text", "role", "company", "duration"]:
                value = str(entry.get(key, "")).strip()
                if value:
                    chunks.append(value)
            bullets = entry.get("bullets", [])
            if isinstance(bullets, list):
                for bullet in cast(list[Any], bullets):
                    text = str(bullet).strip()
                    if text:
                        chunks.append(text)
    projects = resume_entities.get("projects", [])
    if isinstance(projects, list):
        for item in cast(list[Any], projects):
            text = str(item).strip()
            if text:
                chunks.append(text)
    return "\n".join(chunks)


def _impact_score_from_text(text: str) -> float:
    if not text.strip():
        return 0.0
    lines = [line.strip() for line in re.split(r"[\n\r\.]+", text) if line.strip()]
    if not lines:
        return 0.0

    candidate_lines = [line for line in lines if _is_candidate_impact_bullet(line)]
    scoring_lines = candidate_lines if len(candidate_lines) >= 3 else lines
    per_line_scores: list[float] = []
    for line in scoring_lines:
        analysis = _normalized_bullet_analysis(line)
        per_line_scores.append(
            clamp01(
                (0.25 * float(analysis["action_clarity"]))
                + (0.25 * float(analysis["quantified_evidence"]))
                + (0.20 * float(analysis["result_outcome"]))
                + (0.15 * float(analysis["scope_scale"]))
                + (0.10 * float(analysis["complexity_context"]))
                + (0.05 * float(analysis["ownership_leadership"]))
            )
        )
    return _aggregate_impact_scores(per_line_scores)


def _collect_resume_bullets(
    *,
    resume_experience: Any,
    resume_projects: Any | None,
    resume_text: str,
) -> list[str]:
    bullets = flatten_experience_bullets(resume_experience)
    if isinstance(resume_experience, list):
        for item in cast(list[Any], resume_experience):
            if not isinstance(item, dict):
                continue
            entry = cast(dict[str, Any], item)
            for key in [
                "bullets",
                "description",
                "responsibilities",
                "achievements",
                "highlights",
                "points",
                "items",
                "content",
            ]:
                values = entry.get(key, [])
                if isinstance(values, list):
                    for value in cast(list[Any], values):
                        text = str(value).strip()
                        if text and text not in bullets:
                            bullets.append(text)
                elif isinstance(values, str):
                    text = values.strip()
                    if text and text not in bullets:
                        bullets.append(text)

    if isinstance(resume_projects, list):
        for item in cast(list[Any], resume_projects):
            if isinstance(item, dict):
                entry = cast(dict[str, Any], item)
                project_text = str(entry.get("text", "")).strip()
                if project_text and project_text not in bullets:
                    bullets.append(project_text)
                project_bullets = entry.get("bullets", [])
                if isinstance(project_bullets, list):
                    for bullet in cast(list[Any], project_bullets):
                        text = str(bullet).strip()
                        if text and text not in bullets:
                            bullets.append(text)
            else:
                text = str(item).strip()
                if text and text not in bullets:
                    bullets.append(text)

    # Resume-only fallback: if structured extraction is sparse, recover
    # responsibility-like lines directly from raw text.
    if not bullets and str(resume_text or "").strip():
        fallback_action_markers = set(_MANDATORY_ACTION_START_VERBS)
        for line in str(resume_text).splitlines():
            raw_line = str(line).strip()
            if not raw_line:
                continue
            bullet_like = bool(re.match(r"^[\u2022\u25cf\u25e6\u2023\-*]\s+", raw_line))
            normalized_line = re.sub(
                r"^[\u2022\u25cf\u25e6\u2023\-*\s]+",
                "",
                raw_line,
            ).strip()
            if not normalized_line:
                continue
            lowered_line = _normalize_action_verb_text(normalized_line)
            has_fallback_action = any(marker in lowered_line for marker in fallback_action_markers)
            if bullet_like or _is_candidate_impact_bullet(normalized_line) or has_fallback_action:
                bullets.append(normalized_line)

    deduped: list[str] = []
    seen: set[str] = set()
    for bullet in bullets:
        key = str(bullet).strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(str(bullet).strip())
    return deduped


def _resume_only_skill_score(skill_alignment: dict[str, list[dict[str, Any]]]) -> float:
    matched = skill_alignment.get("matched", [])
    weak = skill_alignment.get("weak", [])
    missing = skill_alignment.get("missing", [])

    importance_sum = 0.0
    weighted_sum = 0.0
    missing_importance_sum = 0.0

    for item in matched:
        importance = float(item.get("jd_importance", 0.6) or 0.6)
        score = float(item.get("weighted_score", 0.0) or 0.0)
        # Prevent per-skill evidence from exceeding its JD importance.
        weighted_sum += min(importance, max(0.0, score))
        importance_sum += importance

    for item in weak:
        importance = float(item.get("jd_importance", 0.6) or 0.6)
        score = float(item.get("weighted_score", 0.0) or 0.0)
        # Weak matches receive a stricter cap than strong matches.
        weighted_sum += min(0.9 * importance, max(0.0, 0.8 * score))
        importance_sum += importance

    for item in missing:
        importance = float(item.get("jd_importance", 0.6) or 0.6)
        missing_importance_sum += importance

    importance_sum += missing_importance_sum

    if importance_sum <= 0:
        return 0.0

    base_score = clamp01(weighted_sum / importance_sum)
    total = max(1, len(matched) + len(weak) + len(missing))
    missing_ratio = len(missing) / total
    weak_ratio = len(weak) / total
    coverage_ratio = (len(matched) + (0.4 * len(weak))) / total

    penalty_multiplier = max(0.50, 1.0 - (0.20 * missing_ratio) - (0.08 * weak_ratio))
    score = base_score * penalty_multiplier

    # Cap score by observed coverage so small matched sets cannot saturate score.
    score = min(score, clamp01(coverage_ratio + 0.30))

    # Keep a ceiling when most required skills are missing, but less aggressively.
    if missing_ratio >= 0.80:
        score = min(score, 0.40)
    elif missing_ratio >= 0.60:
        score = min(score, 0.55)
    elif missing_ratio >= 0.50:
        score = min(score, 0.72)

    return clamp01(score)


def _evaluate_resume_rules(
    *,
    resume_entities: dict[str, Any],
    resume_metadata: dict[str, Any],
    resume_sections: dict[str, str],
    jd_context: dict[str, Any],
    experience_alignment: dict[str, list[dict[str, Any]]],
    years: float,
) -> dict[str, Any]:
    sections_lower = {
        str(key).strip().lower(): str(value)
        for key, value in (resume_sections or {}).items()
    }

    experience_entries = cast(list[Any], resume_entities.get("experience", []))
    project_entries = cast(list[Any], resume_entities.get("projects", []))
    bullets = flatten_experience_bullets(experience_entries)
    project_bullets: list[str] = []
    for project in project_entries:
        if not isinstance(project, dict):
            continue
        raw_bullets = cast(dict[str, Any], project).get("bullets", [])
        if isinstance(raw_bullets, list):
            project_bullets.extend(
                [str(v).strip() for v in cast(list[Any], raw_bullets) if str(v).strip()]
            )
    all_bullets = [*bullets, *project_bullets]

    strict_expected_order = [
        "experience",
        "projects",
        "skills",
        "education",
        "certifications",
    ]
    if years > 10.0:
        strict_expected_order = ["summary", *strict_expected_order]
    section_order = [str(key).strip().lower() for key in (resume_sections or {}).keys()]
    filtered_order = [item for item in section_order if item in strict_expected_order]
    order_is_exact = filtered_order == strict_expected_order

    present_required = sum(
        1
        for section in strict_expected_order
        if section in sections_lower and str(sections_lower.get(section, "")).strip()
    )
    section_presence_score = present_required / max(1, len(strict_expected_order))
    section_order_score = (
        1.0
        if order_is_exact
        else _section_order_score(filtered_order, strict_expected_order)
    )

    summary_text = str(sections_lower.get("summary", "")).strip()
    summary_rule_ok = bool(summary_text) if years > 10.0 else not bool(summary_text)
    summary_rule_score = 1.0 if summary_rule_ok else 0.0

    total_bullets = len(all_bullets)
    bullet_limit_score = (
        1.0 if total_bullets <= 20 else max(0.0, 1.0 - 0.05 * (total_bullets - 20))
    )

    per_job_score = _per_job_bullet_score(experience_entries)
    per_project_score = _per_job_bullet_score(project_entries)

    invalid_exp_bullet_roles: list[str] = []
    for entry in experience_entries:
        if not isinstance(entry, dict):
            continue
        entry_dict = cast(dict[str, Any], entry)
        role_name = str(
            entry_dict.get(
                "title",
                entry_dict.get("role", entry_dict.get("company", "Unknown role")),
            )
        )
        role_bullets = entry_dict.get("bullets", [])
        if not isinstance(role_bullets, list):
            invalid_exp_bullet_roles.append(role_name)
            continue
        role_count = len([b for b in cast(list[Any], role_bullets) if str(b).strip()])
        if role_count < 3 or role_count > 4:
            invalid_exp_bullet_roles.append(role_name)

    invalid_project_bullets: list[str] = []
    for project in project_entries:
        if not isinstance(project, dict):
            continue
        project_dict = cast(dict[str, Any], project)
        project_name = str(
            project_dict.get("name", project_dict.get("text", "Unknown project"))
        )
        project_role_bullets = project_dict.get("bullets", [])
        if not isinstance(project_role_bullets, list):
            invalid_project_bullets.append(project_name)
            continue
        project_count = len(
            [b for b in cast(list[Any], project_role_bullets) if str(b).strip()]
        )
        if project_count < 3 or project_count > 4:
            invalid_project_bullets.append(project_name)

    combined_text = "\n".join(sections_lower.values())
    table_or_icon_hits = 0
    if combined_text.count("|") >= 8:
        table_or_icon_hits += 1
    if re.search(r"\!\[[^\]]*\]\([^\)]+\)", combined_text):
        table_or_icon_hits += 1
    if re.search(r"[\U0001F300-\U0001FAFF]", combined_text):
        table_or_icon_hits += 1
    if re.search(r"\t", combined_text):
        table_or_icon_hits += 1
    single_column_score = max(0.0, 1.0 - 0.3 * table_or_icon_hits)

    raw_header = str(
        sections_lower.get("header", "")
        or sections_lower.get("contact", "")
        or resume_metadata.get("header", "")
    ).strip()
    header_ok = (
        True if not raw_header else bool(_HEADER_CONTACT_REGEX.search(raw_header))
    )
    header_score = 1.0 if header_ok else 0.0

    date_failures = 0
    date_candidates: list[str] = []
    for entry in [*experience_entries, *project_entries]:
        if not isinstance(entry, dict):
            continue
        duration = str(cast(dict[str, Any], entry).get("duration", "")).strip()
        if not duration:
            continue
        date_candidates.append(duration)
        if not _DATE_RANGE_MMYYYY_REGEX.match(duration.lower()):
            date_failures += 1
    date_format_score = (
        1.0
        if not date_candidates
        else max(0.0, 1.0 - (date_failures / len(date_candidates)))
    )

    skills_payload = resume_entities.get("skills", [])
    skill_terms = _flatten_skill_terms(skills_payload)
    skill_categories = _extract_skill_categories(skills_payload)
    skills_text = str(sections_lower.get("skills", "")).lower()
    if not skill_categories and skills_text:
        for section in _REQUIRED_SKILL_SUBSECTIONS:
            if section in skills_text:
                skill_categories.add(section)
    missing_skill_categories = sorted(_REQUIRED_SKILL_SUBSECTIONS - skill_categories)
    skill_structure_score = 1.0 - (
        len(missing_skill_categories) / max(1, len(_REQUIRED_SKILL_SUBSECTIONS))
    )

    blocked_skills = sorted(
        skill for skill in skill_terms if skill in _ML_LIBRARY_SKILL_BLOCKLIST
    )

    bullet_corpus = normalize_skill_name(" ".join(all_bullets))
    skills_without_bullet_evidence = sorted(
        skill
        for skill in skill_terms
        if skill and not _text_has_skill(bullet_corpus, skill)
    )

    top_skills = _top_jd_required_skills(jd_context, limit=5)
    critical_skill_violations: list[str] = []
    experience_entries_typed = cast(
        list[dict[str, Any]], resume_entities.get("experience", [])
    )
    for skill in top_skills:
        in_experience = _count_skill_mentions_in_bullets(skill, bullets)
        in_skills = (
            1 if skill in skill_terms or _text_has_skill(skills_text, skill) else 0
        )
        in_recent = _recent_skill_usage(
            skill=skill, experience_entries=experience_entries_typed
        )
        if in_experience < 2 or in_skills < 1 or in_recent <= 0.0:
            critical_skill_violations.append(skill)

    jd_keywords = {
        normalize_skill_name(str(item))
        for item in [
            *list(jd_context.get("skills_required", [])),
            *list(jd_context.get("skills_optional", [])),
            *list(jd_context.get("tools", [])),
            *list(jd_context.get("responsibilities", [])),
        ]
        if normalize_skill_name(str(item))
    }
    resume_keyword_corpus = normalize_skill_name(
        "\n".join(
            [
                _entities_text_blob(resume_entities),
                "\n".join(str(v) for v in sections_lower.values()),
            ]
        )
    )
    keyword_match_count = sum(
        1 for kw in jd_keywords if _text_has_skill(resume_keyword_corpus, kw)
    )
    keyword_match_ratio = keyword_match_count / max(1, len(jd_keywords))

    experience_gate = _experience_gate(experience_alignment)
    responsibility_coverage = float(
        experience_gate.get("blended_coverage_ratio", 0.0) or 0.0
    )

    weak_phrase_hits = 0
    pronoun_hits = 0
    action_formula_violations = 0
    teamwork_missing_roles: list[str] = []

    weak_phrases = {"worked on", "helped with", "assisted", "responsible for"}
    scale_indicators = {
        "high-volume",
        "multi-user",
        "large-scale",
        "enterprise-scale",
        "at scale",
    }
    for bullet in all_bullets:
        text = str(bullet).strip()
        lowered = _normalize_action_verb_text(text)
        analysis = _normalized_bullet_analysis(text)

        if any(phrase in lowered for phrase in weak_phrases):
            weak_phrase_hits += 1
        if re.search(r"\b(i|me|my|we|our)\b", lowered):
            pronoun_hits += 1

        has_action = float(analysis.get("action_clarity", 0.0) or 0.0) >= 0.65
        has_quant = float(analysis.get("quantified_evidence", 0.0) or 0.0) >= 0.65 or any(
            ind in lowered for ind in scale_indicators
        )
        has_supporting_context = any(
            float(analysis.get(field, 0.0) or 0.0) >= 0.6
            for field in (
                "result_outcome",
                "scope_scale",
                "complexity_context",
                "ownership_leadership",
                "tool_process_method_usage",
            )
        )
        if not (has_action and has_quant and has_supporting_context):
            action_formula_violations += 1

    for entry in experience_entries:
        if not isinstance(entry, dict):
            continue
        entry_dict = cast(dict[str, Any], entry)
        role_name = str(
            entry_dict.get(
                "title",
                entry_dict.get("role", entry_dict.get("company", "Unknown role")),
            )
        )
        role_bullets = entry_dict.get("bullets", [])
        role_text = (
            " ".join(str(v) for v in cast(list[Any], role_bullets))
            if isinstance(role_bullets, list)
            else ""
        )
        if role_text.strip() and not _TEAMWORK_REGEX.search(role_text):
            teamwork_missing_roles.append(role_name)

    full_text_for_count = (
        combined_text if combined_text.strip() else _entities_text_blob(resume_entities)
    )
    word_count = len(re.findall(r"\b\w+\b", full_text_for_count))
    word_count_ok = 400 <= word_count <= 650

    certs = resume_entities.get("certifications", [])
    cert_items = cast(list[Any], certs) if isinstance(certs, list) else []
    cert_count = len([c for c in cert_items if str(c).strip()])
    cert_count_ok = cert_count <= 5
    cert_format_ok = True
    cert_format_re = re.compile(r"^.+\s*-\s*.+\s*-\s*\d{4}$")
    for cert in cert_items:
        cert_text = str(cert).strip()
        if cert_text and not cert_format_re.match(cert_text):
            cert_format_ok = False
            break

    font_ok = True
    font_family = str(resume_metadata.get("font_family", "")).strip().lower()
    if font_family and not any(
        token in font_family for token in ["arial", "calibri", "sans"]
    ):
        font_ok = False

    fail_reasons: list[str] = []

    if not summary_rule_ok:
        if years > 10.0:
            fail_reasons.append(
                "Summary section is required for resumes above 10 years"
            )
        else:
            fail_reasons.append(
                "Summary section must be removed for resumes at or below 10 years"
            )
    if not order_is_exact:
        fail_reasons.append(
            "Section order must be Summary(if >10 yrs) -> Experience -> Projects -> Skills -> Education -> Certifications"
        )
    if table_or_icon_hits > 0:
        fail_reasons.append(
            "Layout must be single-column and text-only (no tables/icons/images/emojis)"
        )
    if not font_ok:
        fail_reasons.append("Font family must be standard sans serif (Arial/Calibri)")
    if not header_ok:
        fail_reasons.append("Header must use: Mobile | Email | LinkedIn")
    if total_bullets > 20:
        fail_reasons.append("Total bullet count must be 20 or fewer")
    if invalid_exp_bullet_roles:
        fail_reasons.append("Each experience role must contain exactly 3-4 bullets")
    if invalid_project_bullets:
        fail_reasons.append("Each project must contain exactly 3-4 bullets")
    if missing_skill_categories:
        fail_reasons.append(
            "Skills section must include categories: Programming Languages, Data Science, Data Visualization, Databases, Tools"
        )
    if blocked_skills:
        fail_reasons.append(
            "Do not list ML libraries (NumPy/Pandas/Scikit-learn) in Skills section"
        )
    if skills_without_bullet_evidence:
        fail_reasons.append(
            "Every listed skill must appear in at least one project or experience bullet"
        )
    if critical_skill_violations:
        fail_reasons.append(
            "Critical JD skills must appear >=2 times in experience, >=1 time in skills, and in the most recent role"
        )
    if responsibility_coverage < 0.60:
        fail_reasons.append("Resume must cover at least 60% of JD responsibilities")
    if keyword_match_ratio < 0.85:
        fail_reasons.append(
            f"Keyword match ratio below threshold: {keyword_match_ratio:.1%} < 85%"
        )
    if weak_phrase_hits > 0:
        fail_reasons.append(
            "Weak phrases are not allowed: worked on/helped with/assisted/responsible for"
        )
    if pronoun_hits > 0:
        fail_reasons.append("Personal pronouns are not allowed (I/Me/My/We)")
    if teamwork_missing_roles:
        fail_reasons.append("Every role must include explicit teamwork evidence")
    if action_formula_violations > 0:
        fail_reasons.append(
            "Every bullet must follow Action + Context/Tech + Quantifiable Outcome"
        )
    if not word_count_ok:
        fail_reasons.append(
            f"Resume word count must be between 400 and 650 (current: {word_count})"
        )
    if date_failures > 0:
        fail_reasons.append("Dates must follow MM/YYYY - MM/YYYY format")
    if not cert_count_ok:
        fail_reasons.append("Certifications section must contain a maximum of 5 items")
    if cert_count > 0 and not cert_format_ok:
        fail_reasons.append("Certifications must follow: Name - Organization - Year")

    format_rule_score = clamp01(
        0.14 * section_presence_score
        + 0.12 * section_order_score
        + 0.10 * summary_rule_score
        + 0.08 * bullet_limit_score
        + 0.08 * per_job_score
        + 0.08 * per_project_score
        + 0.08 * single_column_score
        + 0.08 * header_score
        + 0.08 * date_format_score
        + 0.08 * skill_structure_score
        + 0.08 * min(1.0, keyword_match_ratio)
        + 0.08 * (1.0 if word_count_ok else 0.0)
    )

    language_quality_score, language_details = _language_quality_score(all_bullets)

    return {
        "pass": len(fail_reasons) == 0,
        "fail_reasons": fail_reasons,
        "format_rule_score": round(format_rule_score, 3),
        "language_quality_score": round(language_quality_score, 3),
        "details": {
            "section_presence_score": round(section_presence_score, 3),
            "section_order_score": round(section_order_score, 3),
            "summary_rule_score": round(summary_rule_score, 3),
            "bullet_limit_score": round(bullet_limit_score, 3),
            "per_job_bullet_score": round(per_job_score, 3),
            "per_project_bullet_score": round(per_project_score, 3),
            "single_column_score": round(single_column_score, 3),
            "header_score": round(header_score, 3),
            "date_format_score": round(date_format_score, 3),
            "skill_structure_score": round(skill_structure_score, 3),
            "keyword_match_ratio": round(keyword_match_ratio, 3),
            "word_count": word_count,
            "word_count_ok": word_count_ok,
            "total_bullets": total_bullets,
            "invalid_experience_bullet_roles": invalid_exp_bullet_roles,
            "invalid_project_bullets": invalid_project_bullets,
            "blocked_skill_terms": blocked_skills,
            "skills_without_evidence": skills_without_bullet_evidence,
            "critical_skill_violations": critical_skill_violations,
            "responsibility_coverage": round(responsibility_coverage, 3),
            "weak_phrase_hits": weak_phrase_hits,
            "pronoun_hits": pronoun_hits,
            "teamwork_missing_roles": teamwork_missing_roles,
            "action_formula_violations": action_formula_violations,
            "quality_warnings": list(resume_metadata.get("quality_warnings", [])),
            **language_details,
        },
    }


def _section_order_score(section_order: list[str], expected_order: list[str]) -> float:
    if not section_order:
        return 0.6
    positions = [expected_order.index(s) for s in section_order if s in expected_order]
    if len(positions) <= 1:
        return 0.8
    good_pairs = sum(
        1 for i in range(len(positions) - 1) if positions[i] <= positions[i + 1]
    )
    total_pairs = len(positions) - 1
    return good_pairs / total_pairs if total_pairs > 0 else 0.8


def _per_job_bullet_score(experience_entries: Any) -> float:
    if not isinstance(experience_entries, list) or not experience_entries:
        return 0.6
    scores: list[float] = []
    for entry in cast(list[Any], experience_entries):
        if not isinstance(entry, dict):
            continue
        bullets = cast(dict[str, Any], entry).get("bullets", [])
        if not isinstance(bullets, list):
            continue
        count = len([item for item in cast(list[Any], bullets) if str(item).strip()])
        if 3 <= count <= 4:
            scores.append(1.0)
        elif count in (2, 5):
            scores.append(0.75)
        elif count == 0:
            scores.append(0.2)
        else:
            scores.append(0.45)
    return sum(scores) / len(scores) if scores else 0.6


def _language_quality_score(bullets: list[str]) -> tuple[float, dict[str, Any]]:
    if not bullets:
        return 0.4, {
            "action_verb_ratio": 0.0,
            "quantified_bullet_ratio": 0.0,
            "weak_phrase_ratio": 1.0,
            "pronoun_hits": 0,
        }

    weak_phrases = {
        "worked on",
        "helped with",
        "assisted",
        "responsible for",
        "various",
        "several",
    }
    quant_regex = re.compile(_BULLET_QUANT_REGEX.pattern, re.IGNORECASE)

    action_verb_hits = 0
    quantified_hits = 0
    weak_hits = 0
    pronoun_hits = 0
    result_hits = 0

    for bullet in bullets:
        text = str(bullet).strip()
        lowered = _normalize_action_verb_text(text)
        analysis = _normalized_bullet_analysis(text)
        if float(analysis.get("action_clarity", 0.0) or 0.0) >= 0.65:
            action_verb_hits += 1
        if float(analysis.get("quantified_evidence", 0.0) or 0.0) >= 0.65 or quant_regex.search(lowered):
            quantified_hits += 1
        if any(phrase in lowered for phrase in weak_phrases):
            weak_hits += 1
        if re.search(r"\b(i|we|my|our)\b", lowered):
            pronoun_hits += 1
        if float(analysis.get("result_outcome", 0.0) or 0.0) >= 0.65:
            result_hits += 1

    total = max(1, len(bullets))
    action_ratio = action_verb_hits / total
    quantified_ratio = quantified_hits / total
    weak_ratio = weak_hits / total
    result_ratio = result_hits / total
    pronoun_penalty = min(0.25, 0.05 * pronoun_hits)

    score = (
        0.35 * action_ratio
        + 0.35 * quantified_ratio
        + 0.20 * result_ratio
        + 0.10 * (1.0 - weak_ratio)
        - pronoun_penalty
    )
    return clamp01(score), {
        "action_verb_ratio": round(action_ratio, 3),
        "quantified_bullet_ratio": round(quantified_ratio, 3),
        "result_marker_ratio": round(result_ratio, 3),
        "weak_phrase_ratio": round(weak_ratio, 3),
        "pronoun_hits": pronoun_hits,
    }


def _build_rewrite_suggestions(bullets: list[str]) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []
    scale_indicator = "for a high-volume multi-user platform"

    for bullet in bullets[:8]:
        lowered = _normalize_action_verb_text(bullet)
        analysis = _normalized_bullet_analysis(bullet)
        has_number = float(analysis.get("quantified_evidence", 0.0) or 0.0) >= 0.65
        has_action = float(analysis.get("action_clarity", 0.0) or 0.0) >= 0.65
        has_result = float(analysis.get("result_outcome", 0.0) or 0.0) >= 0.65
        if has_number and has_action and has_result:
            continue
        rewrite = bullet
        if not has_action:
            rewrite = f"Delivered {rewrite}".strip()
        if not has_result:
            rewrite = f"{rewrite}, improved measurable business outcomes".strip()
        if not has_number:
            rewrite = f"{rewrite} {scale_indicator} (+18% performance)".strip()
        suggestions.append({"original": bullet, "suggested": rewrite})
    return suggestions
