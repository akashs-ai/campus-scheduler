# Orbit Campus Scheduler

Orbit is a polished, dependency-light prototype for campus timetable operations: schedule visibility, room discovery, booking decisions, exam assignments, and disruption review. It is designed around the official problem statement and keeps deterministic policy decisions separate from the optional AI assistance layer.

## Run locally

```bash
npm start
```

Open the local URL printed by `serve`. The app works without a database or third-party provider in demo mode.

Validate the included generated exports:

```bash
npm run validate
```

## Demo walkthrough

Choose any role on the sign-in page. Admin exposes the Rescheduling studio and policy controls; every other role receives a focused workspace. The demo shows the official priority order (exams, classes, institute events, guest lectures, department events, clubs), explainable booking decisions, and the sample disruption comparison.

Demo identities are role-scoped UI fixtures only. Production credentials must be supplied through environment variables or a managed secret store; never commit them. See `.env.example`.

## Architecture

The current submission is a static vertical slice so judges can run it immediately: `index.html` provides the shell, `app.js` contains the role-aware view model and deterministic demo rules, `styles.css` provides the responsive design system, and `exports/` contains the app-produced export contract. A production deployment should move the same services behind a relational API with migrations, secure sessions, transactions, and server-side authorization.

## Known limitations

This prototype does not yet include a persistent database, real OTP provider, server-side sessions, live deployment, or the full 189-row official dataset. The included export files and UI fixtures are intentionally limited to the visible vertical slice and are not a claim that the full official validator has been run.
