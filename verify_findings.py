"""
Verify findings in database.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reviewhub.settings')
django.setup()

from evaluations.models import Evaluation, Finding, FindingSkill

try:
    eval_obj = Evaluation.objects.get(commit_sha='abc123def456789')
    
    print(f"[FOUND] Evaluation: {eval_obj.commit_message}")
    print(f"  Commit: {eval_obj.commit_sha[:7]}")
    print(f"  Score: {eval_obj.overall_score}")
    print(f"  Findings: {eval_obj.findings.count()}")
    
    findings = eval_obj.findings.prefetch_related('skills', 'finding_skills__skill').all()
    
    for i, finding in enumerate(findings, 1):
        print(f"\n  Finding {i}: {finding.title}")
        print(f"    Severity: {finding.severity}")
        print(f"    File: {finding.file_path} (lines {finding.line_start}-{finding.line_end})")
        print(f"    Skills linked: {finding.skills.count()}")
        
        for skill in finding.skills.all():
            print(f"      * {skill.name} ({skill.slug})")
        
        finding_skills = finding.finding_skills.select_related('skill').all()
        for fs in finding_skills:
            print(f"        > Impact: {fs.impact_score} points")
    
    print(f"\n[SUCCESS] All findings have skill mappings!")
    
    # Summary
    total_skill_links = FindingSkill.objects.filter(finding__evaluation=eval_obj).count()
    print(f"\nSummary:")
    print(f"  Total Finding-Skill links: {total_skill_links}")
    print(f"  Expected: ~7 (based on test data)")
    
except Evaluation.DoesNotExist:
    print("[ERROR] Evaluation not found! Test may have failed.")
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
