-- ===================================================================
-- AI-First CRM - HCP Interaction Logging
-- Raw PostgreSQL DDL (matches backend/app/models.py SQLAlchemy models)
-- ===================================================================

CREATE TYPE material_type_enum AS ENUM ('material', 'sample');

-- ---------------------------------------------------------------
-- 1. hcp_profiles
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hcp_profiles (
    hcp_id      SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    specialty   VARCHAR(255)
);

-- ---------------------------------------------------------------
-- 2. interactions
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS interactions (
    id                  SERIAL PRIMARY KEY,
    hcp_id              INTEGER REFERENCES hcp_profiles(hcp_id) ON DELETE SET NULL,
    interaction_type    VARCHAR(100),
    date                DATE,
    time                TIME,
    attendees           TEXT,
    topics              TEXT,
    sentiment           VARCHAR(50),
    outcomes            TEXT,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------
-- 3. materials
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS materials (
    material_id SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    type        material_type_enum NOT NULL
);

-- ---------------------------------------------------------------
-- Join table: which materials/samples were shared in which interaction.
-- (Not explicitly listed in the assignment brief, but required to model
--  a many-to-many relationship between interactions and materials without
--  denormalizing the interactions table. See README "Design Notes".)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS interaction_materials (
    id              SERIAL PRIMARY KEY,
    interaction_id  INTEGER NOT NULL REFERENCES interactions(id) ON DELETE CASCADE,
    material_id     INTEGER NOT NULL REFERENCES materials(material_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------
-- 4. tasks
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tasks (
    task_id         SERIAL PRIMARY KEY,
    hcp_id          INTEGER REFERENCES hcp_profiles(hcp_id) ON DELETE SET NULL,
    interaction_id  INTEGER REFERENCES interactions(id) ON DELETE SET NULL,
    description     TEXT NOT NULL,
    due_date        DATE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ===================================================================
-- Seed data - a few HCPs and materials so Fetch_HCP_Context and
-- Lookup_Items have real records to resolve on a fresh database.
-- ===================================================================

INSERT INTO hcp_profiles (name, specialty) VALUES
    ('Dr. Smith', 'Cardiology'),
    ('Dr. John', 'Oncology'),
    ('Dr. Sarah Lee', 'Endocrinology'),
    ('Dr. Rajesh Mehta', 'Neurology')
ON CONFLICT DO NOTHING;

INSERT INTO materials (name, type) VALUES
    ('Prodo-X Brochure', 'material'),
    ('Efficacy Study Handout', 'material'),
    ('Prodo-X Sample Pack', 'sample'),
    ('Starter Sample Kit', 'sample')
ON CONFLICT DO NOTHING;
