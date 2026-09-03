-- =====================================================================
-- National Vocational Certification and Exam Slot-Booking System
-- Relational Schema (portable to MySQL 8 / PostgreSQL 15 / SQLite)
-- =====================================================================

DROP TABLE IF EXISTS Result;
DROP TABLE IF EXISTS Booking;
DROP TABLE IF EXISTS Slot;
DROP TABLE IF EXISTS ExamAttempt;
DROP TABLE IF EXISTS Candidate;
DROP TABLE IF EXISTS Center;

-- ---------------------------------------------------------------------
-- Master entities
-- ---------------------------------------------------------------------
CREATE TABLE Candidate (
    candidate_id    INTEGER PRIMARY KEY,
    full_name       TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    phone           TEXT,
    registered_on   TEXT NOT NULL DEFAULT (date('now'))
);

CREATE TABLE Center (
    center_id       INTEGER PRIMARY KEY,
    center_name     TEXT NOT NULL,
    city            TEXT NOT NULL,
    total_seats     INTEGER NOT NULL
);

-- ---------------------------------------------------------------------
-- Exam-attempt archive (the "large, ever-growing" file).
-- Physically clustered on (center_id, exam_date) to emulate an
-- indexed-sequential file organization: records for the same center
-- and date are stored contiguously, so a center/date audit scan is a
-- single contiguous range read instead of a full-file scan.
-- ---------------------------------------------------------------------
CREATE TABLE ExamAttempt (
    attempt_id      INTEGER NOT NULL,
    candidate_id    INTEGER NOT NULL,
    center_id       INTEGER NOT NULL,
    exam_date       TEXT NOT NULL,
    slot_time       TEXT NOT NULL,
    responses_json  TEXT,              -- question-wise responses
    time_taken_sec  INTEGER,
    raw_score       REAL,
    PRIMARY KEY (center_id, exam_date, attempt_id),   -- clustering key
    FOREIGN KEY (candidate_id) REFERENCES Candidate(candidate_id),
    FOREIGN KEY (center_id)    REFERENCES Center(center_id)
) WITHOUT ROWID;   -- forces physical storage order = clustering key order (SQLite)
-- MySQL/InnoDB equivalent: PRIMARY KEY (center_id, exam_date, attempt_id)
-- already clusters the table physically (InnoDB clusters on the PK).

-- Secondary non-clustering B+-tree index for candidate-wise point/history
-- lookups that do NOT go through center_id/exam_date.
CREATE INDEX idx_attempt_candidate ON ExamAttempt(candidate_id);

-- Secondary index to accelerate pure date-range audits across centers.
CREATE INDEX idx_attempt_date ON ExamAttempt(exam_date);

-- ---------------------------------------------------------------------
-- Slot booking (capacity-bounded, high write-contention table)
-- ---------------------------------------------------------------------
CREATE TABLE Slot (
    slot_id         INTEGER PRIMARY KEY,
    center_id       INTEGER NOT NULL,
    exam_date       TEXT NOT NULL,
    slot_time       TEXT NOT NULL,
    capacity        INTEGER NOT NULL,
    booked_count    INTEGER NOT NULL DEFAULT 0,
    UNIQUE (center_id, exam_date, slot_time),
    CHECK (booked_count <= capacity),
    FOREIGN KEY (center_id) REFERENCES Center(center_id)
);
CREATE INDEX idx_slot_center_date ON Slot(center_id, exam_date);

CREATE TABLE Booking (
    booking_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER NOT NULL,
    slot_id         INTEGER NOT NULL,
    booking_time    TEXT NOT NULL DEFAULT (datetime('now')),
    status          TEXT NOT NULL CHECK (status IN ('CONFIRMED','CANCELLED')),
    UNIQUE (candidate_id, slot_id),
    FOREIGN KEY (candidate_id) REFERENCES Candidate(candidate_id),
    FOREIGN KEY (slot_id)      REFERENCES Slot(slot_id)
);
CREATE INDEX idx_booking_slot ON Booking(slot_id);

-- ---------------------------------------------------------------------
-- Result publishing (concurrent-write hotspot)
-- ---------------------------------------------------------------------
CREATE TABLE Result (
    result_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id      INTEGER NOT NULL,
    candidate_id    INTEGER NOT NULL,
    center_id       INTEGER NOT NULL,
    exam_date       TEXT NOT NULL,
    final_score     REAL NOT NULL,
    grade           TEXT,
    published_by    TEXT NOT NULL,
    published_on    TEXT NOT NULL DEFAULT (datetime('now')),
    version         INTEGER NOT NULL DEFAULT 1,   -- optimistic-lock counter
    FOREIGN KEY (candidate_id) REFERENCES Candidate(candidate_id)
);
CREATE INDEX idx_result_candidate ON Result(candidate_id);
