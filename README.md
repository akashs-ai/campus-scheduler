# Orbit Campus Scheduler

Orbit is a polished, dependency-light prototype for campus timetable operations: schedule visibility, room discovery, booking decisions, exam assignments, and disruption review. It is designed around the official problem statement and keeps deterministic policy decisions separate from the optional AI assistance layer.

## Run locally

```bash
npm start
```

Open the local URL printed by `serve`. The app works without a database or third-party provider in demo mode.

The heavy version also includes a standard-library API with SQLite persistence:

```bash
python server.py
```

The API listens on `http://localhost:8080`. Demo credentials are `admin@orbit.demo` / `admin-demo`, `coordinator@orbit.demo` / `coordinator-demo`, `faculty@orbit.demo` / `faculty-demo`, and `club@orbit.demo` / `club-demo`. These are demo-only credentials; production deployments must replace them and terminate TLS at the edge.

Core endpoints are `GET /api/health`, `POST /api/auth/login`, `GET /api/me`, `GET /api/rooms`, `GET /api/timetable`, `GET /api/bookings`, `POST /api/bookings`, `POST /api/bookings/:id/decision`, and `POST /api/admin/reset`. Authorization is checked on the server, sessions are bearer tokens with expiry, passwords are scrypt-hashed, SQLite foreign keys are enabled, and booking mutations write audit events.

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

The included UI still uses a compact fixture dataset and does not yet include a real OTP provider, hosted deployment, or the complete 189-row official starter dataset/validator package. The API and schema are ready for the official dataset adapter; the included export files are explicitly marked as a prototype slice rather than a claim that the official validator has been run.
