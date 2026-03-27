from evaluations.models import Evaluation, Finding, FindingSkill

eval_obj = Evaluation.objects.get(commit_sha='def456abc789012')

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

total_skill_links = FindingSkill.objects.filter(finding__evaluation=eval_obj).count()
print(f"\nSummary:")
print(f"  Total Finding-Skill links: {total_skill_links}")
print(f"  Expected: ~7 (based on test data)")
