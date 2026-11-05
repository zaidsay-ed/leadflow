# LeadFlow

A backend service for managing sales contacts, built to learn backend fundamentals: REST APIs, MongoDB, Redis, and Docker.

## Tech stack
Python, FastAPI, MongoDB, Docker Compose

## Features
- REST API to create, search, update, and delete contacts
- Email normalization and deduplication (unique index, returns 409 on duplicates)
- Case-insensitive search on company and title using a MongoDB collation (index-backed, no regex scans)
- Pagination

## Run it
```bash
docker compose up --build
```
Then open http://localhost:8000/docs

## Roadmap
- [X] Redis caching for search
- [X] Rate limiting
- [X] Background enrichment jobs
- [X] Multi-step outreach sequences
