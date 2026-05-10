# 5-Hour Solo AI Hackathon Playbook

## Before Start

1. Confirm `python app.py` opens on `http://localhost:7860`.
2. Confirm the Dockerfile starts `app.py` and exposes `7860`.
3. Confirm GitHub and ModelScope remotes are available.
4. Prepare one API key path: `OPENAI_API_KEY` for DeepSeek V4 Pro.

## 0:00-0:30 Scope

1. Rewrite the directed challenge into one sentence.
2. Define one target user and one painful workflow.
3. Choose a single input and a single output for the MVP.
4. Write the demo success criterion in `TASK_BRIEF.md`.

## 0:30-2:00 Core Build

1. Implement only the happy path first.
2. Use sample data that makes the value obvious.
3. Keep the AI prompt visible and easy to edit.
4. Commit once the first end-to-end path works.

## 2:00-3:30 Productization

1. Add input validation and useful empty states.
2. Add examples and default values.
3. Save generated outputs for demo recovery.
4. Improve result formatting for judges.

## 3:30-4:30 Deployment

1. Run the app locally.
2. Push to GitHub.
3. Push or sync to ModelScope Studio.
4. Test the public deployment link.

## 4:30-5:00 Demo

1. Stop adding features.
2. Prepare a two-minute script.
3. Capture backup screenshots or a short recording.
4. Keep terminal, app, repository, and deployment link ready.
