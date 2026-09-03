import sqlite3, random, json, datetime, os

DB = "exam_system.db"
if os.path.exists(DB):
    os.remove(DB)

conn = sqlite3.connect(DB)
conn.executescript(open("schema.sql").read())
cur = conn.cursor()

random.seed(42)

# ---- Centers ----
CITIES = ["Chennai", "Coimbatore", "Madurai", "Trichy", "Salem"]
centers = []
for cid in range(1, 21):
    centers.append((cid, f"Center-{cid:03d}", random.choice(CITIES), 200))
cur.executemany("INSERT INTO Center VALUES (?,?,?,?)", centers)

# ---- Candidates ----
candidates = []
for cid in range(1, 5001):
    candidates.append((cid, f"Candidate_{cid}", f"cand{cid}@vocexam.org",
                        f"9{random.randint(100000000,999999999)}",
                        "2026-01-01"))
cur.executemany("INSERT INTO Candidate VALUES (?,?,?,?,?)", candidates)

# ---- Exam attempts (the big archive) ----
dates = [f"2026-0{m}-{d:02d}" for m in range(1, 7) for d in (10, 20)]
attempts = []
attempt_seq = {}   # per (center,date) running attempt_id, matches clustering key style
for i in range(1, 50001):
    center_id = random.randint(1, 20)
    exam_date = random.choice(dates)
    key = (center_id, exam_date)
    attempt_seq[key] = attempt_seq.get(key, 0) + 1
    attempt_id = attempt_seq[key]
    candidate_id = random.randint(1, 5000)
    slot_time = random.choice(["09:00", "13:00", "16:00"])
    responses = json.dumps({f"q{j}": random.choice(["A","B","C","D"]) for j in range(1, 6)})
    time_taken = random.randint(1800, 5400)
    score = round(random.uniform(0, 100), 2)
    attempts.append((attempt_id, candidate_id, center_id, exam_date, slot_time,
                      responses, time_taken, score))

cur.executemany("""INSERT INTO ExamAttempt
    (attempt_id, candidate_id, center_id, exam_date, slot_time,
     responses_json, time_taken_sec, raw_score) VALUES (?,?,?,?,?,?,?,?)""",
    attempts)

# ---- Slots (capacity-bounded) ----
slot_rows = []
sid = 1
for c in range(1, 21):
    for d in dates:
        for t in ["09:00", "13:00", "16:00"]:
            slot_rows.append((sid, c, d, t, 30, 0))
            sid += 1
cur.executemany("INSERT INTO Slot VALUES (?,?,?,?,?,?)", slot_rows)

conn.commit()
print("Rows inserted:")
for t in ["Center", "Candidate", "ExamAttempt", "Slot"]:
    n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t:12s}: {n}")
conn.close()
