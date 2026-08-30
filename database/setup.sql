
-- ============================================================
-- MASTER SETUP SCRIPT
-- Run this file to create all database objects:
--   sqlplus username/password@localhost:1521/XEPDB1 @database/setup.sql
-- ============================================================

PROMPT ================================================
PROMPT Running schema.sql ...
PROMPT ================================================
@@schema.sql

PROMPT ================================================
PROMPT Running procedures.sql ...
PROMPT ================================================
@@procedures.sql

PROMPT ================================================
PROMPT Running triggers.sql ...
PROMPT ================================================
@@triggers.sql

PROMPT ================================================
PROMPT Running seed.sql ...
PROMPT ================================================
@@seed.sql

PROMPT ================================================
PROMPT Setup complete! Tables, procedures, triggers,
PROMPT and reference data created successfully.
PROMPT ================================================
