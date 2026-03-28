# ReviewHub v2 — Architecture Document

## Overview

ReviewHub v2 is an AI-powered code review teaching platform that transforms automated code reviews into structured learning experiences for developers. The system analyzes commits, identifies patterns, tracks skills, and provides personalized feedback.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Vue 3 + TypeScript + Tailwind | SPA Dashboard |
| **Backend API** | Django + DRF | REST API, Auth, ORM |
| **AI Engine** | FastAPI + Python | LLM integration, Learning Algorithm |
| **Database** | PostgreSQL | Persistent storage |
| **Queue** | Redis + RQ | Background job processing |
| **Cache** | Redis | Session cache, rate limiting |
| **Git Integration** | GitHub API | Webhooks, commit fetching |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                    │
│                         Vue 3 + TypeScript                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ Login/   │ │Dashboard │ │ Skills   │ │Findings  │ │ Settings │      │
│  │ Onboard  │ │          │ │          │ │          │ │          │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ HTTP/REST
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         DJANGO BACKEND (:8000)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │  Auth    │ │  Users   │ │ Projects │ │Evaluations│ │  Skills  │      │
│  │  JWT     │ │          │ │          │ │          │ │          │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│  ┌──────────┐ ┌──────────┐                                              │
│  │Notifications│ │ Onboard │                                            │
│  └──────────┘ └──────────┘                                              │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ Internal API
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       FASTAPI AI ENGINE (:8001)                         │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐        │
│  │  Commit Analyzer │ │ Learning Engine  │ │  Profile Builder │        │
│  │                  │ │                  │ │                  │        │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘        │
│  ┌──────────────────┐ ┌──────────────────┐                              │
│  │ Batch Processor  │ │  LLM Integration │                              │
│  │    (Phase 6)     │ │  (OpenAI/Claude) │                              │
│  └──────────────────┘ └──────────────────┘                              │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   PostgreSQL     │  │      Redis       │  │    GitHub API    │
│   (Database)     │  │  (Queue/Cache)   │  │   (Webhooks)     │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## Development Phases

### Phase 1: Foundation ✅
- Django project setup
- JWT authentication
- User model with roles (admin, developer, viewer)
- Project model with GitHub integration
- Basic API structure

### Phase 2: Core Dashboard ✅
- Evaluations system (code reviews)
- Findings model (individual issues)
- Dashboard API endpoints
- Frontend: Calendar, findings list, filters

### Phase 3: Skills System ✅
- Skill categories and skills models
- UserSkill tracking
- FindingSkill associations
- Skill scoring algorithm
- Frontend: Skills dashboard, progress tracking

### Phase 4: Notifications & Recommendations ✅
- Notification model and API
- Auto-notifications on new findings (signals)
- Learning recommendations engine
- Frontend: Notification bell, recommendations widget

### Phase 5: Polish & QA 🔄 (Current)
- User onboarding flow (first-time password setup)
- Bug fixes and UI polish
- Performance optimization
- Testing and QA
- Documentation

### Phase 6: Batch Commit Review 📋 (Planned)
**Goal:** Process historical commits to bootstrap developer profiles

See detailed specification below.

---

## Phase 6: Batch Commit Review — Detailed Specification

### Overview

A batch processing system that:
1. Takes a repository URL
2. Fetches commit history
3. Replays commits through the learning engine
4. Builds a comprehensive developer profile
5. Stores it for future personalization

**Why This Matters:**
- ✅ Solves cold start problem
- ✅ Deep developer understanding from day 1
- ✅ Historical intelligence for personalization
- ✅ Makes the system proactively personalized, not just reactive

### Architecture

```
User submits repo
       ↓
FastAPI creates job
       ↓
Redis Queue stores job
       ↓
Worker processes:
   → fetch commits
   → replay commits
   → update learning
       ↓
Build developer profile
       ↓
Store profile
       ↓
Future commits become personalized
```

### Data Flow

```
Current System:
  Webhook → process_commit → learning

New Addition (Batch Pipeline):
  Repo URL → Batch Processor → process_commit (loop) → learning → profile

👉 Same engine, different entry point
```

### Components

#### 1. BatchJob Model
```python
class BatchJob(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    repo_url = models.URLField()
    status = models.CharField(choices=[
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ])
    progress = models.IntegerField(default=0)  # 0-100
    total_commits = models.IntegerField(default=0)
    processed_commits = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)
    error_message = models.TextField(blank=True)
```

#### 2. BatchCommitResult Model
```python
class BatchCommitResult(models.Model):
    job = models.ForeignKey(BatchJob, on_delete=models.CASCADE)
    commit_sha = models.CharField(max_length=40)
    commit_date = models.DateTimeField()
    score = models.FloatField()
    skills_snapshot = models.JSONField()  # Skills at this point
    patterns_snapshot = models.JSONField()  # Patterns identified
    created_at = models.DateTimeField(auto_now_add=True)
```

Enables:
- Timeline visualization
- Progress graphs
- Historical insights

#### 3. UserProfile Model
```python
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    level = models.CharField(max_length=20)  # beginner, intermediate, advanced
    strengths = models.JSONField(default=list)  # ["readability", "naming"]
    weaknesses = models.JSONField(default=list)  # ["testing", "error_handling"]
    top_patterns = models.JSONField(default=list)  # Most common issues
    trend = models.CharField(max_length=20)  # improving, stable, declining
    last_updated = models.DateTimeField(auto_now=True)
```

Used in ALL future analysis for personalization.

### API Endpoints

#### FastAPI (AI Engine)

```python
@app.post("/analyze-repo")
def analyze_repo(repo_url: str, user_id: int):
    """
    Trigger batch analysis of a repository.
    Returns immediately with job_id.
    Processing happens in background.
    """
    job = create_job(repo_url, user_id)
    queue.enqueue("process_repo_job", job.id)
    return {"job_id": job.id}

@app.get("/jobs/{job_id}")
def get_job_status(job_id: int):
    """Get job progress and status."""
    return {
        "status": job.status,
        "progress": job.progress,
        "total_commits": job.total_commits,
        "processed_commits": job.processed_commits
    }

@app.get("/jobs/{job_id}/results")
def get_job_results(job_id: int):
    """Get batch processing results and timeline."""
    return {
        "commits": [...],
        "profile": {...},
        "insights": {...}
    }
```

### Worker Implementation

```python
def process_repo_job(job_id):
    job = get_job(job_id)
    update_status(job, "running")
    
    try:
        # Fetch commits (oldest → newest)
        commits = fetch_commits(job.repo_url)
        commits = sorted(commits, key=lambda x: x["date"])
        
        # Limit for performance
        commits = commits[-100:]  # Last 100 commits
        
        job.total_commits = len(commits)
        job.save()
        
        # Process each commit
        for i, commit in enumerate(commits):
            process_commit(commit, job.user_id, mode="batch")
            
            # Store intermediate result
            BatchCommitResult.objects.create(
                job=job,
                commit_sha=commit["sha"],
                commit_date=commit["date"],
                score=...,
                skills_snapshot=...,
                patterns_snapshot=...
            )
            
            # Update progress
            job.processed_commits = i + 1
            job.progress = int((i + 1) / len(commits) * 100)
            job.save()
        
        # Build final profile
        build_final_profile(job.user)
        
        update_status(job, "done")
        
    except Exception as e:
        job.error_message = str(e)
        update_status(job, "failed")
```

### process_commit() Extension

```python
def process_commit(commit, user, mode="realtime"):
    """
    Process a single commit.
    
    Args:
        mode: "realtime" (webhook) or "batch" (historical)
    """
    if mode == "batch":
        # Skip notifications for batch processing
        skip_notifications = True
        # Store intermediate results
        store_intermediate = True
    else:
        skip_notifications = False
        store_intermediate = False
    
    # ... existing processing logic ...
```

### Profile Builder

```python
def build_final_profile(user):
    """
    Aggregate all batch results into a developer profile.
    Called after batch processing completes.
    """
    results = BatchCommitResult.objects.filter(
        job__user=user
    ).order_by('commit_date')
    
    # Analyze patterns
    all_patterns = []
    skill_scores = defaultdict(list)
    
    for result in results:
        all_patterns.extend(result.patterns_snapshot)
        for skill, score in result.skills_snapshot.items():
            skill_scores[skill].append(score)
    
    # Calculate strengths/weaknesses
    strengths = [s for s, scores in skill_scores.items() 
                 if statistics.mean(scores) >= 75]
    weaknesses = [s for s, scores in skill_scores.items() 
                  if statistics.mean(scores) < 50]
    
    # Detect trend
    if len(results) >= 10:
        early_avg = statistics.mean([r.score for r in results[:5]])
        late_avg = statistics.mean([r.score for r in results[-5:]])
        if late_avg > early_avg + 5:
            trend = "improving"
        elif late_avg < early_avg - 5:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "unknown"
    
    # Save profile
    UserProfile.objects.update_or_create(
        user=user,
        defaults={
            "level": calculate_level(skill_scores),
            "strengths": strengths,
            "weaknesses": weaknesses,
            "top_patterns": Counter(all_patterns).most_common(5),
            "trend": trend,
        }
    )
```

### Using Profile in Real-time Analysis

```python
# When user pushes new code:
# Webhook → process_commit()

def process_commit(commit, user, mode="realtime"):
    # Load profile
    profile = UserProfile.objects.filter(user=user).first()
    
    if profile:
        # Adapt LLM prompt based on profile
        context = f"""
        Developer Profile:
        - Level: {profile.level}
        - Known weaknesses: {profile.weaknesses}
        - Common patterns: {profile.top_patterns}
        
        Pay special attention to: {profile.weaknesses}
        """
        
        # Now your system says:
        # "You often miss edge cases based on past projects."
```

### Queue System

**Start Simple:**
- Redis + RQ (Python RQ)

**Later Scale:**
- Celery + Redis
- or Kafka (advanced)

### Failure Handling

```python
def process_repo_job(job_id):
    try:
        # ... processing ...
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        job.save()
        
        # Optional: retry logic
        if job.retry_count < 3:
            job.retry_count += 1
            queue.enqueue_in(
                timedelta(minutes=5),
                "process_repo_job",
                job_id
            )
```

### Performance Optimization

**Problem:** Large repos = slow

**Solutions:**
1. **Limit commits:** Process last 100 commits
2. **Parallelize:** Multiple workers (later)
3. **Cache diffs:** Store GitHub API responses
4. **Skip merge commits:** Focus on actual code changes
5. **Rate limiting:** Respect GitHub API limits

### Frontend Integration

#### Repository Analysis Page
- Input: Repository URL
- Start Analysis button
- Progress bar with real-time updates
- Results view with:
  - Timeline graph (score over time)
  - Skills evolution chart
  - Top patterns identified
  - Final profile summary

#### Profile Card (Dashboard)
- Developer level badge
- Strengths tags (green)
- Weaknesses tags (orange)
- Trend indicator (↑ improving, → stable, ↓ declining)
- "Analyze Repository" button

### Implementation Steps

| Step | Description | Priority |
|------|-------------|----------|
| 1 | Add BatchJob model | High |
| 2 | Create FastAPI `/analyze-repo` endpoint | High |
| 3 | Setup Redis + RQ worker | High |
| 4 | Implement commit fetcher | High |
| 5 | Add `mode` parameter to process_commit | High |
| 6 | Add BatchCommitResult model | Medium |
| 7 | Implement Profile Builder | High |
| 8 | Add UserProfile model | High |
| 9 | Create frontend analysis page | Medium |
| 10 | Integrate profile into real-time analysis | High |

---

## Database Schema (Summary)

### Django Backend

```
users
├── id, username, email, password, role
├── onboard_completed, created_at, updated_at
└── llm_provider, llm_api_key, llm_model

onboard_codes
├── id, user_id, code, expires_at, used, created_at

projects
├── id, name, github_url, default_branch
└── created_at, updated_at

evaluations
├── id, project_id, commit_sha, author_name
├── score, summary, created_at

findings
├── id, evaluation_id, file_path, line_start, line_end
├── category, severity, title, description
├── original_code, suggested_code, explanation

skills (categories)
├── id, name, display_name, description, icon

user_skills
├── id, user_id, skill_id, score, level

finding_skills
├── id, finding_id, skill_id, impact_score

notifications
├── id, user_id, type, title, message, data
├── read, created_at

batch_jobs (Phase 6)
├── id, user_id, repo_url, status, progress
├── total_commits, processed_commits
├── created_at, completed_at, error_message

batch_commit_results (Phase 6)
├── id, job_id, commit_sha, commit_date
├── score, skills_snapshot, patterns_snapshot

user_profiles (Phase 6)
├── id, user_id, level, strengths, weaknesses
├── top_patterns, trend, last_updated
```

---

## API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/token/` | Login (returns JWT) |
| POST | `/api/auth/token/refresh/` | Refresh token |

### Onboarding
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/onboard/check-email/` | Check if user exists |
| POST | `/api/onboard/verify-code/` | Verify OTP code |
| POST | `/api/onboard/set-password/` | Set initial password |

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/` | List users |
| GET | `/api/users/me/` | Current user |
| POST | `/api/users/` | Create user |
| PATCH | `/api/users/{id}/` | Update user |

### Projects
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/` | List projects |
| GET | `/api/projects/{id}/` | Get project |
| POST | `/api/projects/` | Create project |

### Evaluations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/evaluations/` | List evaluations |
| GET | `/api/evaluations/{id}/` | Get evaluation |
| GET | `/api/evaluations/dashboard/` | Dashboard stats |
| GET | `/api/evaluations/findings/` | List findings |
| GET | `/api/evaluations/findings/{id}/` | Get finding |
| POST | `/api/evaluations/findings/{id}/fix/` | Mark as fixed |

### Skills
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/skills/categories/` | List skill categories |
| GET | `/api/skills/user/{id}/` | User's skills |
| GET | `/api/skills/recommendations/` | Learning recommendations |
| GET | `/api/skills/dashboard/overview/` | Skills overview |
| GET | `/api/skills/dashboard/progress/` | Progress over time |

### Notifications
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/notifications/` | List notifications |
| PATCH | `/api/notifications/{id}/read/` | Mark as read |
| POST | `/api/notifications/mark-all-read/` | Mark all read |
| GET | `/api/notifications/unread-count/` | Unread count |

### Batch Processing (Phase 6)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/analyze-repo` | Start batch analysis |
| GET | `/api/jobs/{id}` | Get job status |
| GET | `/api/jobs/{id}/results` | Get job results |

---

## Environment Variables

```env
# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://user:pass@localhost:5432/reviewhub

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-jwt-secret
JWT_ACCESS_TOKEN_LIFETIME=60  # minutes
JWT_REFRESH_TOKEN_LIFETIME=1440  # minutes (1 day)

# GitHub
GITHUB_TOKEN=ghp_xxxx
GITHUB_WEBHOOK_SECRET=your-webhook-secret

# LLM
OPENAI_API_KEY=sk-xxxx
ANTHROPIC_API_KEY=sk-ant-xxxx

# Encryption (for user API keys)
ENCRYPTION_KEY=your-fernet-key
```

---

## Deployment

### Development
```bash
# Backend
cd django_backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8000

# AI Engine
cd fastapi_engine
pip install -r requirements.txt
uvicorn main:app --port 8001

# Frontend
cd frontend
npm install
npm run dev

# Redis (for queue)
redis-server

# Worker (Phase 6)
rq worker
```

### Production
- **Hosting:** DigitalOcean App Platform or Droplet
- **Database:** Managed PostgreSQL
- **Cache:** Managed Redis
- **CI/CD:** GitHub Actions
- **SSL:** Let's Encrypt

---

## Security Considerations

1. **JWT tokens** with short expiry + refresh
2. **CORS** restricted to frontend domain
3. **Rate limiting** on API endpoints
4. **Input validation** on all endpoints
5. **SQL injection prevention** via ORM
6. **XSS prevention** via Vue's auto-escaping
7. **Secrets encryption** for user LLM API keys
8. **Webhook signature verification** for GitHub

---

## Monitoring & Logging

- **Application logs:** Django + FastAPI logging
- **Error tracking:** Sentry (recommended)
- **Metrics:** Prometheus + Grafana (optional)
- **Uptime:** UptimeRobot or similar

---

*Last Updated: March 28, 2026*
*Version: 2.0*
