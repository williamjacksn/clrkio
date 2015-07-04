CREATE TABLE IF NOT EXISTS members (
  baptism_date TEXT,
  baptism_ratified INTEGER,
  birth_country TEXT,
  birth_place TEXT,
  birthdate TEXT,
  born_in_covenant INTEGER,
  confirmation_date TEXT,
  confirmation_ratified INTEGER,
  email TEXT,
  enabled INTEGER,
  endowment_date TEXT,
  endowment_ratified INTEGER,
  endowment_temple INTEGER,
  fathers_birth_date TEXT,
  fathers_name TEXT,
  from_address_unknown INTEGER,
  full_name TEXT,
  gender TEXT,
  given_name TEXT,
  individual_id INTEGER PRIMARY KEY,
  is_spouse_member INTEGER,
  maiden_name TEXT,
  marriage_date TEXT,
  marriage_place TEXT,
  member_id TEXT UNIQUE,
  mission_country TEXT,
  mission_language TEXT,
  mothers_birth_date TEXT,
  mothers_name TEXT,
  moved_in_date TEXT,
  not_accountable INTEGER,
  phone TEXT,
  preferred_name TEXT,
  prior_unit INTEGER,
  prior_unit_move_date TEXT,
  prior_unit_name TEXT,
  recommend_expiration_date TEXT,
  recommend_status TEXT,
  sealed_parents_date TEXT,
  sealed_spouse_date TEXT,
  sealed_spouse_temple TEXT,
  sealed_to_parents_temple TEXT,
  sealing_to_parents_ratified INTEGER,
  sealing_to_spouse_ratified INTEGER,
  spouse_birth_date TEXT,
  spouse_deceased INTEGER,
  spouse_member INTEGER,
  spouse_member_id TEXT,
  spouse_name TEXT,
  surname TEXT
);

CREATE TABLE IF NOT EXISTS priesthood_office_codes (
  priesthood_office_code INTEGER PRIMARY KEY,
  priesthood_office_name TEXT
);

INSERT INTO priesthood_office_codes (
  priesthood_office_code, priesthood_office_name
) VALUES
  (1, 'Deacon'),
  (2, 'Teacher'),
  (3, 'Priest'),
  (4, 'Elder'),
  (5, 'Seventy'),
  (6, 'High Priest');

CREATE TABLE IF NOT EXISTS priesthood_offices (
  individual_id INTEGER REFERENCES members(individual_id) ON DELETE CASCADE,
  ordination_date TEXT,
  performed_by TEXT,
  performed_by_mrn TEXT,
  priesthood_office_code INTEGER REFERENCES priesthood_office_codes(priesthood_office_code),
  ratified INTEGER,
  PRIMARY KEY (individual_id, priesthood_office_code)
);

CREATE TABLE IF NOT EXISTS households (
  couple_name TEXT,
  description_1 TEXT,
  description_2 TEXT,
  description_3 TEXT,
  email_address TEXT,
  enabled INTEGER,
  head_of_house INTEGER PRIMARY KEY REFERENCES members(individual_id) ON DELETE CASCADE,
  household_name TEXT,
  include_lat_long INTEGER,
  latitude REAL,
  longitude REAL,
  phone TEXT,
  spouse INTEGER REFERENCES members(individual_id) ON DELETE SET NULL,
  state TEXT
);

CREATE TABLE IF NOT EXISTS household_children (
  head_of_house INTEGER REFERENCES members(individual_id) ON DELETE CASCADE,
  child INTEGER REFERENCES members(individual_id) ON DELETE CASCADE,
  PRIMARY KEY (head_of_house, child)
);
