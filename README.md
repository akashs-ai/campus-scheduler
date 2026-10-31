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

The API listens on `http://localhost:8080` in development. Demo credentials are available only in development mode. Production mode refuses to auto-seed accounts, requires an explicit external bootstrap, and requires HTTPS at the proxy boundary.

Core endpoints are `GET /api/health`, `POST /api/auth/login`, `POST /api/auth/signup`, `POST /api/auth/logout`, `GET /api/me`, `GET /api/rooms`, `GET /api/timetable`, `GET /api/bookings`, `POST /api/bookings`, `POST /api/bookings/:id/decision`, `POST /api/bookings/:id/cancel`, `GET /api/admin/users`, `POST /api/admin/users/:id/approve`, and `POST /api/admin/reset`. Authorization is checked on the server, sessions are persistent, hashed, expiring, and revocable, passwords are scrypt-hashed, SQLite foreign keys are enabled, login attempts are throttled, and booking mutations write audit events.

Validate the included generated exports:

```bash
npm run validate
```

## Demo walkthrough

Sign in through the authenticated form. The role selector is only a visual hint; the server derives the actual role from the account. Non-admin signup creates a pending account that cannot sign in until an Admin approves it. Admin exposes the Rescheduling studio and policy controls; every other role receives a focused workspace.

Demo identities are role-scoped UI fixtures only. Production credentials must be supplied through environment variables or a managed secret store; never commit them. See `.env.example`.

## Architecture

The submission combines a responsive frontend with a standard-library API, SQLite schema, persistent sessions, strict authorization, deterministic booking rules, audit events, and export validation. The frontend is served separately and uses a bearer token in `sessionStorage`; production should place both behind an HTTPS reverse proxy and configure a real verified identity/OTP provider.

## Known limitations

The included UI still uses a compact fixture dataset and does not yet include a real OTP provider, hosted deployment, or the complete 189-row official starter dataset/validator package. The API and schema are ready for the official dataset adapter; the included export files are explicitly marked as a prototype slice rather than a claim that the official validator has been run.
