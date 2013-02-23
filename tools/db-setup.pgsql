--
-- This is the required schema for PostgreSQL. Load this into the database
-- from the postgres user:
--
--    $ createuser -d -S -R -P pyicqt
--    $ createdb -O pyicqt pyicqt
--    $ psql -U pyicqt pyicqt -f db-setup.pgsql 
--
-- You will need to enter this information
-- into your PyICQt config file.
--
--
-- registration table
--
DROP TABLE IF EXISTS register CASCADE;

CREATE TABLE register (
    owner TEXT NOT NULL,
    username TEXT,
    password TEXT,
    encryptedpassword TEXT
);

--
-- settings table
--
DROP TABLE IF EXISTS settings CASCADE;

CREATE TABLE settings (
    owner TEXT NOT NULL,
    variable TEXT,
    value TEXT
);

--
-- lists table
--
DROP TABLE IF EXISTS lists CASCADE;

CREATE TABLE lists (
    owner TEXT NOT NULL,
    type TEXT NOT NULL,
    jid TEXT
);

--
-- list attributes table
--
DROP TABLE IF EXISTS list_attributes CASCADE;

CREATE TABLE list_attributes (
    owner TEXT NOT NULL,
    type TEXT NOT NULL,
    jid TEXT,
    attribute TEXT,
    value TEXT
);

--
-- custom settings table
--
DROP TABLE IF EXISTS csettings CASCADE;

CREATE TABLE csettings (
    owner TEXT NOT NULL,
    variable TEXT,
    value TEXT
);

--
-- x-statuses table
--
DROP TABLE IF EXISTS xstatuses CASCADE;

CREATE TABLE xstatuses (
    owner TEXT NOT NULL,
    number TEXT,
    title TEXT,
    value TEXT
);
