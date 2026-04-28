# Screenshot capture for the Leera pitch video

`capture-screenshots.mjs` drives a headless Chromium against the running
Vite dev server, walks the canonical demo routes as authenticated users
(teacher / two students), and writes 1920×1080 PNGs into
`../../leera-pitch-video/public/screenshots/`.

## When to run

- **Now (preview):** validate the script + framing against `localhost:5173`
  while the demo data is fresh.
- **Post-J2 deploy:** re-run against the prod URL so the URL bar reads
  `app.leera.app` (or whatever the prod host ends up being). Drop the
  refreshed PNGs into the same path; Remotion picks them up via
  `<Img src={staticFile('screenshots/01-teacher-dashboard.png')} />`.
- **After any UI change** that affects a captured surface — the script
  is deterministic and idempotent.

## Prerequisites

- Vite dev server running on `:5173` (frontend `npm run dev`)
- Django + ai_engine running with seeded dogfood data
- Playwright + Chromium installed (one-time):

  ```bash
  cd frontend
  npm i -D playwright
  npx playwright install chromium
  ```

- Demo students have `dev_profile_completed=True` so they don't get
  redirected to the profile setup wizard. One-shot fix:

  ```bash
  cd django_backend
  ./venv/Scripts/python.exe manage.py shell -c "
  from django.contrib.auth import get_user_model
  U = get_user_model()
  U.objects.filter(role='developer').update(dev_profile_completed=True)
  "
  ```

## Run

JWTs are minted inline so they're always fresh:

```bash
cd django_backend
TEACHER_JWT=$(./venv/Scripts/python.exe -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reviewhub.settings')
django.setup()
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
print(RefreshToken.for_user(get_user_model().objects.get(email='yanick007.dev@gmail.com')).access_token)
")
STUDENT_JWT=$(./venv/Scripts/python.exe -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reviewhub.settings')
django.setup()
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
print(RefreshToken.for_user(get_user_model().objects.get(email='tester@reviewhub.com')).access_token)
")
JAN_JWT=$(./venv/Scripts/python.exe -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reviewhub.settings')
django.setup()
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
print(RefreshToken.for_user(get_user_model().objects.get(email='jan.deboer@student.mediacollege.nl')).access_token)
")
cd ../frontend
TEACHER_JWT="$TEACHER_JWT" STUDENT_JWT="$STUDENT_JWT" JAN_JWT="$JAN_JWT" \
  node scripts/capture-screenshots.mjs
```

## Flags

- `--headed` — visible browser (debug captures)
- `--base=URL` — override frontend base (default `http://localhost:5173`)
- `--only=NAME` — capture a single shot by name
- `--slow=MS` — slow each step by N ms

## Captured shots (11)

| File | Account | Path | Pitch scene |
|------|---------|------|-------------|
| `01-teacher-dashboard.png` | teacher | `/` | Teacher front-door |
| `02-teacher-inbox-drafted.png` | teacher | `/grading?state=drafted` | Inbox |
| `03-teacher-session-detail-drafted.png` | teacher | `/grading/sessions/56` | Rubric + AI draft (hero) |
| `06-teacher-student-profile-jan.png` | teacher | `/grading/students/12` | Student profile |
| `07-student-dashboard-tester.png` | tester | `/` | Student front-door |
| `07b-student-dashboard-jan.png` | jan | `/` | Confident dashboard variant |
| `08-student-my-feedback.png` | tester | `/my/prs` | My Feedback |
| `09-student-session-readonly.png` | tester | `/grading/sessions/71` | Read-only feedback view |
| `10-student-code-review.png` | tester | `/timeline` | Per-commit AI auto-review |
| `13-teacher-cohort-overview.png` | teacher | `/grading/cohorts/5/overview` | Klas-overzicht |
| `14-student-skills-dashboard.png` | jan | `/skills` | Skills drill-down |

## Wiring into Remotion

```tsx
import {Img, staticFile} from 'remotion';
<Img src={staticFile('screenshots/03-teacher-session-detail-drafted.png')} />
```

Three FeatureScenes in `src/compositions/LeeraPitch.tsx` already wired:
- `Feedback op elke commit` → `10-student-code-review.png`
- `Jouw nakijk-werkplek` → `03-teacher-session-detail-drafted.png`
- `Eén blik per student` → `06-teacher-student-profile-jan.png`

The fourth scene (`Past in jouw stack`) shows the GitHub PR with posted
comments — that one's a manual screenshot of `inno8/codelens-test#4` on
github.com.
