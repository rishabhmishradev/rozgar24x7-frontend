"""Command-line interface for resume parsing."""

import argparse
import json
import sys
from pathlib import Path

from .parsing.resume_parser import ResumeParser
from .parsing.jd_parser import parse_job_description


def parse_command(args: argparse.Namespace) -> None:
    """Parse a resume file and output results."""
    try:
        parser = ResumeParser()
        result = parser.parse_file(args.resume_file)
        
        output = result.to_dict()
        
        if args.format == "json":
            if args.output:
                output_path = Path(args.output)
                output_path.write_text(json.dumps(output, indent=2))
                print(f"✓ Results saved to {output_path}")
            else:
                print(json.dumps(output, indent=2))
        
        elif args.format == "summary":
            print("\n" + "="*60)
            print("RESUME PARSING SUMMARY")
            print("="*60)
            
            metadata = output["metadata"]
            print(f"\nCompleteness Score: {metadata.get('completeness_score', 'N/A'):.2f}")
            print(f"Parsing Confidence: {metadata.get('parsing_confidence', 'N/A'):.2f}")
            
            entities = output.get("entities", {})
            
            if entities.get("contact"):
                print(f"\n📧 Contact Information:")
                contact = entities["contact"]
                if contact.get("email"):
                    print(f"   Email: {contact['email']}")
                if contact.get("phone"):
                    print(f"   Phone: {contact['phone']}")
                if contact.get("linkedin"):
                    print(f"   LinkedIn: {contact['linkedin']}")
            
            if entities.get("experience"):
                print(f"\n💼 Experience ({len(entities['experience'])} entries):")
                for exp in entities["experience"][:3]:
                    print(f"   • {exp.get('role', 'N/A')} at {exp.get('company', 'N/A')} ({exp.get('duration', 'N/A')})")
                if len(entities['experience']) > 3:
                    print(f"   ... and {len(entities['experience']) - 3} more")
            
            if entities.get("skills"):
                skills_list = entities["skills"]
                top_skills = sorted(
                    skills_list,
                    key=lambda s: s.get("score", 0),
                    reverse=True
                )[:10]
                print(f"\n🎯 Top Skills ({len(skills_list)} total):")
                for skill in top_skills:
                    confidence = skill.get("confidence", 0)
                    print(f"   • {skill.get('name', 'N/A')}: {confidence:.2f}")
            
            if entities.get("education"):
                print(f"\n🎓 Education ({len(entities['education'])} entries):")
                for edu in entities["education"]:
                    print(f"   • {edu.get('degree', 'N/A')} in {edu.get('field', 'N/A')}")
            
            print("\n" + "="*60 + "\n")
    
    except FileNotFoundError:
        print(f"❌ Error: File '{args.resume_file}' not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def parse_jd_command(args: argparse.Namespace) -> None:
    """Parse a job description and output structured data."""
    try:
        jd_text = Path(args.jd_file).read_text()
        result = parse_job_description(jd_text)
        
        if args.format == "json":
            if args.output:
                output_path = Path(args.output)
                output_path.write_text(json.dumps(result, indent=2))
                print(f"✓ JD parsing results saved to {output_path}")
            else:
                print(json.dumps(result, indent=2))
        
        elif args.format == "summary":
            print("\n" + "="*60)
            print("JOB DESCRIPTION ANALYSIS")
            print("="*60)
            
            print(f"\n📋 Seniority Level: {result.get('seniority', 'N/A')}")
            
            if result.get("skills_required"):
                print(f"\n🔴 Required Skills ({len(result['skills_required'])}):")
                for skill in result["skills_required"][:10]:
                    print(f"   • {skill}")
                if len(result["skills_required"]) > 10:
                    print(f"   ... and {len(result['skills_required']) - 10} more")
            
            if result.get("skills_optional"):
                print(f"\n🟡 Optional Skills ({len(result['skills_optional'])}):")
                for skill in result["skills_optional"][:5]:
                    print(f"   • {skill}")
                if len(result["skills_optional"]) > 5:
                    print(f"   ... and {len(result['skills_optional']) - 5} more")
            
            if result.get("responsibilities"):
                print(f"\n✅ Key Responsibilities ({len(result['responsibilities'])}):")
                for resp in result["responsibilities"][:5]:
                    print(f"   • {resp}")
                if len(result["responsibilities"]) > 5:
                    print(f"   ... and {len(result['responsibilities']) - 5} more")
            
            print("\n" + "="*60 + "\n")
    
    except FileNotFoundError:
        print(f"❌ Error: File '{args.jd_file}' not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Resume and Job Description Parser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Parse a resume and show summary
  python -m app.cli parse resume.pdf --format summary
  
  # Parse a resume and save full JSON output
  python -m app.cli parse resume.pdf --output result.json
  
  # Parse job description
  python -m app.cli parse-jd job_description.txt --format summary
  
  # Compare resume with job description
  python -m app.cli parse resume.pdf --jd job_description.txt --format summary
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Parse command
    parse_parser = subparsers.add_parser(
        "parse",
        help="Parse a resume file"
    )
    parse_parser.add_argument(
        "resume_file",
        type=str,
        help="Path to resume file (PDF, DOCX, TXT, etc.)"
    )
    parse_parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="summary",
        help="Output format (default: summary)"
    )
    parse_parser.add_argument(
        "--output",
        type=str,
        help="Output file path (optional)"
    )
    parse_parser.add_argument(
        "--jd",
        dest="jd_file",
        type=str,
        help="Job description file for context-aware parsing"
    )
    parse_parser.set_defaults(func=parse_command)
    
    # Parse JD command
    jd_parser = subparsers.add_parser(
        "parse-jd",
        help="Parse a job description"
    )
    jd_parser.add_argument(
        "jd_file",
        type=str,
        help="Path to job description file (TXT)"
    )
    jd_parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="summary",
        help="Output format (default: summary)"
    )
    jd_parser.add_argument(
        "--output",
        type=str,
        help="Output file path (optional)"
    )
    jd_parser.set_defaults(func=parse_jd_command)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
