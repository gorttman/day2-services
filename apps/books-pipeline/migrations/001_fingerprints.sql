-- Run manually against the `books` database (see README - this is not
-- applied automatically by anything in this proposal). CREATE EXTENSION
-- requires superuser privilege; the `books` app role created alongside
-- this database does not have it, per Phase 1 findings.

CREATE TABLE fingerprints (
  id           bigserial PRIMARY KEY,
  title_norm   text NOT NULL,
  author_norm  text NOT NULL,
  isbn13       text,
  format       text NOT NULL,
  path         text NOT NULL UNIQUE,
  added_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON fingerprints (title_norm);
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ON fingerprints USING gin (title_norm gin_trgm_ops);
