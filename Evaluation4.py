"""
╔══════════════════════════════════════════════════════════════════╗
║        SMART HEALTH APPOINTMENT MANAGEMENT SYSTEM               ║
║        Built with Python (tkinter) + SQLite                     ╚══════════════════════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import datetime
import re
import sys
import unittest
import io
from typing import Optional, List

# ──────────────────────────────────────────────
#  DATABASE LAYER
# ──────────────────────────────────────────────
class DatabaseManager:
    def __init__(self, db_path: str = "health_system.db"):
        self.db_path = db_path
        self.init_database()

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_database(self):
        with self.get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS patients (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL,
                    email       TEXT    UNIQUE NOT NULL,
                    phone       TEXT    NOT NULL,
                    dob         TEXT    NOT NULL,
                    blood_group TEXT,
                    address     TEXT,
                    created_at  TEXT    DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS doctors (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    name           TEXT NOT NULL,
                    specialization TEXT NOT NULL,
                    email          TEXT UNIQUE NOT NULL,
                    phone          TEXT NOT NULL,
                    available_days TEXT NOT NULL,
                    slot_duration  INTEGER DEFAULT 30,
                    start_time     TEXT DEFAULT '09:00',
                    end_time       TEXT DEFAULT '17:00'
                );

                CREATE TABLE IF NOT EXISTS appointments (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id   INTEGER NOT NULL REFERENCES patients(id),
                    doctor_id    INTEGER NOT NULL REFERENCES doctors(id),
                    date         TEXT NOT NULL,
                    time_slot    TEXT NOT NULL,
                    status       TEXT DEFAULT 'Scheduled',
                    reason       TEXT,
                    notes        TEXT,
                    created_at   TEXT DEFAULT (datetime('now')),
                    UNIQUE(doctor_id, date, time_slot)
                );

                CREATE TABLE IF NOT EXISTS notifications (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id     INTEGER REFERENCES patients(id),
                    message        TEXT NOT NULL,
                    is_read        INTEGER DEFAULT 0,
                    created_at     TEXT DEFAULT (datetime('now'))
                );
            """)
            self._seed_doctors(conn)

    def _seed_doctors(self, conn):
        existing = conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]
        if existing == 0:
            doctors = [
                ("Dr. Aisha Khan",       "Cardiology",       "aisha.khan@hospital.pk",   "0300-1234567", "Mon,Tue,Wed,Thu,Fri", 30, "09:00", "17:00"),
                ("Dr. Hamza Malik",      "Neurology",        "hamza.malik@hospital.pk",  "0301-2345678", "Mon,Wed,Fri",         30, "10:00", "16:00"),
                ("Dr. Sara Ahmed",       "Pediatrics",       "sara.ahmed@hospital.pk",   "0302-3456789", "Tue,Thu,Sat",         20, "09:00", "15:00"),
                ("Dr. Omar Farooq",      "Orthopedics",      "omar.farooq@hospital.pk",  "0303-4567890", "Mon,Tue,Wed,Thu,Fri", 30, "08:00", "14:00"),
                ("Dr. Fatima Siddiqui",  "Dermatology",      "fatima.s@hospital.pk",     "0304-5678901", "Mon,Wed,Fri",         20, "11:00", "18:00"),
                ("Dr. Bilal Hussain",    "General Practice", "bilal.h@hospital.pk",      "0305-6789012", "Mon,Tue,Wed,Thu,Fri", 15, "08:00", "18:00"),
                ("Dr. Nadia Iqbal",      "Gynecology",       "nadia.iqbal@hospital.pk",  "0306-7890123", "Tue,Thu",             30, "09:00", "15:00"),
                ("Dr. Zubair Sheikh",    "Ophthalmology",    "zubair.s@hospital.pk",     "0307-8901234", "Mon,Wed,Thu,Sat",     20, "10:00", "17:00"),
                ("Dr. Mehwish Raza",     "ENT",              "mehwish.r@hospital.pk",    "0308-9012345", "Mon,Tue,Thu,Fri",     25, "09:00", "16:00"),
                ("Dr. Asad Rehman",      "Psychiatry",       "asad.r@hospital.pk",       "0309-0123456", "Tue,Wed,Fri",         45, "10:00", "17:00"),
            ]
            conn.executemany(
                "INSERT INTO doctors (name,specialization,email,phone,available_days,slot_duration,start_time,end_time) VALUES (?,?,?,?,?,?,?,?)",
                doctors
            )

    # ── Patients ──────────────────────────────
    def register_patient(self, name, email, phone, dob, blood_group, address):
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO patients (name,email,phone,dob,blood_group,address) VALUES (?,?,?,?,?,?)",
                (name, email, phone, dob, blood_group, address)
            )
        return True

    def get_patient_by_email(self, email):
        with self.get_conn() as conn:
            return conn.execute("SELECT * FROM patients WHERE email=?", (email,)).fetchone()

    def get_all_patients(self):
        with self.get_conn() as conn:
            return conn.execute("SELECT * FROM patients ORDER BY name").fetchall()

    def update_patient(self, pid, name, phone, blood_group, address):
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE patients SET name=?,phone=?,blood_group=?,address=? WHERE id=?",
                (name, phone, blood_group, address, pid)
            )

    # ── Doctors ───────────────────────────────
    def get_all_doctors(self):
        with self.get_conn() as conn:
            return conn.execute("SELECT * FROM doctors ORDER BY name").fetchall()

    def get_doctors_by_specialization(self, spec):
        with self.get_conn() as conn:
            return conn.execute(
                "SELECT * FROM doctors WHERE specialization LIKE ? ORDER BY name",
                (f"%{spec}%",)
            ).fetchall()

    def get_doctor_by_id(self, did):
        with self.get_conn() as conn:
            return conn.execute("SELECT * FROM doctors WHERE id=?", (did,)).fetchone()

    def get_specializations(self):
        with self.get_conn() as conn:
            rows = conn.execute("SELECT DISTINCT specialization FROM doctors ORDER BY specialization").fetchall()
            return [r[0] for r in rows]

    # ── Slots ─────────────────────────────────
    def get_available_slots(self, doctor_id: int, date: str) -> List[str]:
        doc = self.get_doctor_by_id(doctor_id)
        if not doc:
            return []
        day_name = datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%a")
        available_days = [d[:3] for d in doc["available_days"].split(",")]
        if day_name not in available_days:
            return []
        start    = datetime.datetime.strptime(doc["start_time"], "%H:%M")
        end      = datetime.datetime.strptime(doc["end_time"],   "%H:%M")
        duration = doc["slot_duration"]
        all_slots = []
        current = start
        while current + datetime.timedelta(minutes=duration) <= end:
            all_slots.append(current.strftime("%H:%M"))
            current += datetime.timedelta(minutes=duration)
        with self.get_conn() as conn:
            booked = [
                r[0] for r in conn.execute(
                    "SELECT time_slot FROM appointments WHERE doctor_id=? AND date=? AND status!='Cancelled'",
                    (doctor_id, date)
                ).fetchall()
            ]
        return [s for s in all_slots if s not in booked]

    def is_slot_available(self, doctor_id: int, date: str, time_slot: str) -> bool:
        return time_slot in self.get_available_slots(doctor_id, date)

    # ── Appointments ──────────────────────────
    def book_appointment(self, patient_id, doctor_id, date, time_slot, reason):
        if not self.is_slot_available(doctor_id, date, time_slot):
            raise ValueError("Selected time slot is not available.")
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO appointments (patient_id,doctor_id,date,time_slot,reason) VALUES (?,?,?,?,?)",
                (patient_id, doctor_id, date, time_slot, reason)
            )
            doctor = conn.execute("SELECT name FROM doctors WHERE id=?", (doctor_id,)).fetchone()
            msg = f"Appointment confirmed with {doctor['name']} on {date} at {time_slot}."
            conn.execute(
                "INSERT INTO notifications (patient_id, message) VALUES (?,?)",
                (patient_id, msg)
            )
        return True

    def reschedule_appointment(self, appt_id, new_date, new_time_slot):
        with self.get_conn() as conn:
            appt = conn.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
            if not appt:
                raise ValueError("Appointment not found.")
            if appt["status"] == "Cancelled":
                raise ValueError("Cannot reschedule a cancelled appointment.")
            if not self.is_slot_available(appt["doctor_id"], new_date, new_time_slot):
                raise ValueError("New time slot is not available.")
            conn.execute(
                "UPDATE appointments SET date=?,time_slot=?,status='Scheduled' WHERE id=?",
                (new_date, new_time_slot, appt_id)
            )
            msg = f"Appointment #{appt_id} rescheduled to {new_date} at {new_time_slot}."
            conn.execute(
                "INSERT INTO notifications (patient_id,message) VALUES (?,?)",
                (appt["patient_id"], msg)
            )
        return True

    def cancel_appointment(self, appt_id):
        with self.get_conn() as conn:
            appt = conn.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
            if not appt:
                raise ValueError("Appointment not found.")
            conn.execute("UPDATE appointments SET status='Cancelled' WHERE id=?", (appt_id,))
            msg = f"Appointment #{appt_id} has been cancelled."
            conn.execute(
                "INSERT INTO notifications (patient_id,message) VALUES (?,?)",
                (appt["patient_id"], msg)
            )
        return True

    def get_patient_appointments(self, patient_id):
        with self.get_conn() as conn:
            return conn.execute("""
                SELECT a.*, d.name AS doctor_name, d.specialization,
                       p.name AS patient_name
                FROM appointments a
                JOIN doctors  d ON a.doctor_id  = d.id
                JOIN patients p ON a.patient_id = p.id
                WHERE a.patient_id = ?
                ORDER BY a.date DESC, a.time_slot DESC
            """, (patient_id,)).fetchall()

    def get_all_appointments(self):
        with self.get_conn() as conn:
            return conn.execute("""
                SELECT a.*, d.name AS doctor_name, d.specialization,
                       p.name AS patient_name
                FROM appointments a
                JOIN doctors  d ON a.doctor_id  = d.id
                JOIN patients p ON a.patient_id = p.id
                ORDER BY a.date DESC, a.time_slot DESC
            """).fetchall()

    def get_upcoming_appointments(self, patient_id):
        today = datetime.date.today().isoformat()
        with self.get_conn() as conn:
            return conn.execute("""
                SELECT a.*, d.name AS doctor_name, d.specialization
                FROM appointments a
                JOIN doctors d ON a.doctor_id = d.id
                WHERE a.patient_id=? AND a.date >= ? AND a.status='Scheduled'
                ORDER BY a.date, a.time_slot
            """, (patient_id, today)).fetchall()

    # ── Notifications ─────────────────────────
    def get_unread_notifications(self, patient_id):
        with self.get_conn() as conn:
            return conn.execute(
                "SELECT * FROM notifications WHERE patient_id=? AND is_read=0 ORDER BY created_at DESC",
                (patient_id,)
            ).fetchall()

    def mark_notifications_read(self, patient_id):
        with self.get_conn() as conn:
            conn.execute("UPDATE notifications SET is_read=1 WHERE patient_id=?", (patient_id,))


# ──────────────────────────────────────────────
#  VALIDATION HELPERS
# ──────────────────────────────────────────────
class Validator:
    @staticmethod
    def validate_email(email: str) -> bool:
        return bool(re.match(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$", email))

    @staticmethod
    def validate_phone(phone: str) -> bool:
        return bool(re.match(r"^[0-9\-\+\s]{10,15}$", phone))

    @staticmethod
    def validate_date(date_str: str) -> bool:
        try:
            datetime.datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    @staticmethod
    def validate_future_date(date_str: str) -> bool:
        if not Validator.validate_date(date_str):
            return False
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").date() >= datetime.date.today()

    @staticmethod
    def validate_dob(dob: str) -> bool:
        if not Validator.validate_date(dob):
            return False
        return datetime.datetime.strptime(dob, "%Y-%m-%d").date() < datetime.date.today()

    @staticmethod
    def validate_name(name: str) -> bool:
        return len(name.strip()) >= 2


# ──────────────────────────────────────────────
#  COLOUR / STYLE CONSTANTS
# ──────────────────────────────────────────────
P = {
    "bg":       "#0F1923",
    "panel":    "#162030",
    "card":     "#1E2D40",
    "acc1":     "#00C9A7",
    "acc2":     "#4F8EF7",
    "acc3":     "#F76C6C",
    "acc4":     "#FFB347",
    "text":     "#E8EDF2",
    "dim":      "#7A8FA6",
    "border":   "#2A3F5A",
    "success":  "#2ECC71",
    "warning":  "#F39C12",
    "error":    "#E74C3C",
}

FT = {
    "title":   ("Segoe UI", 22, "bold"),
    "heading": ("Segoe UI", 14, "bold"),
    "sub":     ("Segoe UI", 11, "bold"),
    "body":    ("Segoe UI", 10),
    "small":   ("Segoe UI", 9),
    "mono":    ("Courier New", 10),
}


# ── Widget helpers ──────────────────────────
def btn(parent, text, cmd, color=None, width=14, **kw):
    return tk.Button(parent, text=text, command=cmd,
                     bg=color or P["acc1"], fg=P["bg"],
                     font=FT["sub"], relief="flat", cursor="hand2",
                     padx=12, pady=6, width=width,
                     activebackground=P["text"], activeforeground=P["bg"], **kw)

def card(parent, **kw):
    return tk.Frame(parent, bg=P["card"],
                    highlightbackground=P["border"], highlightthickness=1, **kw)

def lbl(parent, text, fk="body", fg=None, bg=None, **kw):
    return tk.Label(parent, text=text, bg=bg or P["card"],
                    fg=fg or P["text"], font=FT[fk], **kw)

def entry(parent, var=None, width=30, show=""):
    return tk.Entry(parent, textvariable=var, width=width,
                    bg=P["bg"], fg=P["text"], insertbackground=P["acc1"],
                    relief="flat", font=FT["body"],
                    highlightbackground=P["border"], highlightthickness=1,
                    show=show)

def style_tree():
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("Treeview", background=P["card"], foreground=P["text"],
                 fieldbackground=P["card"], rowheight=28)
    s.configure("Treeview.Heading", background=P["bg"],
                 foreground=P["acc1"], font=FT["small"])
    s.map("Treeview", background=[("selected", P["acc2"])])


# ──────────────────────────────────────────────
#  MAIN APPLICATION
# ──────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.current_patient = None
        self.title("Smart Health Appointment Management System")
        self.geometry("1280x800")
        self.minsize(1100, 700)
        self.configure(bg=P["bg"])
        style_tree()
        self._login()

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _login(self):              self._clear(); LoginScreen(self)
    def _register_screen(self):   self._clear(); RegisterScreen(self)   # FIX: renamed from _register
    def _dashboard(self):         self._clear(); Dashboard(self)
    def _book(self):              self._clear(); BookScreen(self)
    def _appointments(self):      self._clear(); AppointmentsScreen(self)
    def _doctors(self):           self._clear(); DoctorsScreen(self)
    def _admin(self):             self._clear(); AdminScreen(self)


# ══════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════
def sidebar(parent, app, active=""):
    sb = tk.Frame(parent, bg=P["panel"], width=225)
    sb.pack(side="left", fill="y")
    sb.pack_propagate(False)

    tk.Label(sb, text="🏥  HealthCare+", font=("Segoe UI", 14, "bold"),
             bg=P["panel"], fg=P["acc1"]).pack(pady=(25, 2), padx=18, anchor="w")
    if app.current_patient:
        tk.Label(sb, text=f"  👤 {app.current_patient['name']}",
                 font=FT["small"], bg=P["panel"], fg=P["dim"]).pack(anchor="w", padx=18)
    tk.Frame(sb, bg=P["border"], height=1).pack(fill="x", padx=18, pady=14)

    items = [
        ("🏠  Dashboard",       "dashboard",    app._dashboard),
        ("📅  Book Appointment", "book",         app._book),
        ("📋  My Appointments",  "appointments", app._appointments),
        ("👨‍⚕️  Our Doctors",       "doctors",      app._doctors),
    ]
    for text, key, cmd in items:
        is_a = key == active
        tk.Button(sb, text=text, command=cmd,
                  bg=P["acc1"] if is_a else P["panel"],
                  fg=P["bg"]   if is_a else P["text"],
                  font=FT["body"], relief="flat", anchor="w",
                  padx=20, pady=10, cursor="hand2",
                  activebackground=P["border"], activeforeground=P["text"]
                  ).pack(fill="x", padx=5, pady=2)

    tk.Frame(sb, bg=P["border"], height=1).pack(fill="x", padx=18, pady=14, side="bottom")
    tk.Button(sb, text="⬅  Logout", command=app._login,
              bg=P["panel"], fg=P["error"], font=FT["body"],
              relief="flat", anchor="w", padx=20, pady=10, cursor="hand2"
              ).pack(fill="x", padx=5, pady=2, side="bottom")
    return sb


# ══════════════════════════════════════════════
#  LOGIN SCREEN
# ══════════════════════════════════════════════
class LoginScreen:
    def __init__(self, app: App):
        self.app = app

        outer = tk.Frame(app, bg=P["bg"])
        outer.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Left decorative panel
        left = tk.Frame(outer, bg=P["acc1"], width=430)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="🏥", font=("Segoe UI", 72), bg=P["acc1"], fg=P["bg"]).pack(pady=(90, 8))
        tk.Label(left, text="HealthCare+", font=("Segoe UI", 30, "bold"), bg=P["acc1"], fg=P["bg"]).pack()
        tk.Label(left, text="Smart Appointment Management", font=FT["sub"], bg=P["acc1"], fg=P["bg"]).pack(pady=4)
        tk.Label(left, text="Your health. Our priority.", font=FT["body"], bg=P["acc1"], fg=P["bg"]).pack(pady=(18, 0))
        for feat in ["✔  Easy appointment booking", "✔  Real-time slot availability", "✔  Instant notifications"]:
            tk.Label(left, text=feat, font=FT["small"], bg=P["acc1"], fg=P["bg"]).pack(anchor="w", padx=60, pady=3)

        # Right form
        right = tk.Frame(outer, bg=P["bg"])
        right.pack(side="right", fill="both", expand=True)

        form = tk.Frame(right, bg=P["panel"], padx=55, pady=50)
        form.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(form, text="Welcome Back", font=FT["title"], bg=P["panel"], fg=P["text"]).pack(anchor="w")
        tk.Label(form, text="Sign in to manage your appointments",
                 font=FT["body"], bg=P["panel"], fg=P["dim"]).pack(anchor="w", pady=(0, 22))

        tk.Label(form, text="Email Address", font=FT["small"], bg=P["panel"], fg=P["dim"]).pack(anchor="w")
        self.ev = tk.StringVar()
        entry(form, var=self.ev, width=36).pack(anchor="w", pady=(2, 14))

        tk.Label(form, text="Password  (admin: admin123)", font=FT["small"], bg=P["panel"], fg=P["dim"]).pack(anchor="w")
        self.pv = tk.StringVar()
        entry(form, var=self.pv, width=36, show="●").pack(anchor="w", pady=(2, 22))

        row = tk.Frame(form, bg=P["panel"])
        row.pack(fill="x")
        btn(row, "Sign In",    self._login,       color=P["acc1"], width=14).pack(side="left")
        btn(row, "Admin Login", self._admin_login, color=P["acc2"], width=14).pack(side="left", padx=8)

        reg_lbl = tk.Label(form, text="New patient? Register here →",
                           font=FT["body"], bg=P["panel"], fg=P["acc2"], cursor="hand2")
        reg_lbl.pack(anchor="w", pady=(18, 0))
        # FIX: was app._register(), now app._register_screen()
        reg_lbl.bind("<Button-1>", lambda _: app._register_screen())

    def _login(self):
        email = self.ev.get().strip()
        if not email:
            messagebox.showerror("Error", "Please enter your email.")
            return
        patient = self.app.db.get_patient_by_email(email)
        if not patient:
            messagebox.showerror("Login Failed",
                                 "No account found for that email.\nPlease register first.")
            return
        self.app.current_patient = patient
        self.app._dashboard()

    def _admin_login(self):
        if self.pv.get().strip() == "admin123":
            self.app.current_patient = None
            self.app._admin()
        else:
            messagebox.showerror("Admin Login", "Wrong password.\nHint: admin123")


# ══════════════════════════════════════════════
#  REGISTER SCREEN
# ══════════════════════════════════════════════
class RegisterScreen:
    def __init__(self, app: App):
        self.app = app

        outer = tk.Frame(app, bg=P["bg"])
        outer.place(relx=0, rely=0, relwidth=1, relheight=1)

        hdr = tk.Frame(outer, bg=P["acc1"], height=62)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="  🏥  Patient Registration",
                 font=FT["heading"], bg=P["acc1"], fg=P["bg"]).pack(side="left", padx=22)
        btn(hdr, "← Back to Login", app._login, color=P["bg"], width=18).pack(side="right", padx=18, pady=8)

        wrap = tk.Frame(outer, bg=P["bg"])
        wrap.pack(fill="both", expand=True)

        form = tk.Frame(wrap, bg=P["card"], padx=45, pady=35)
        form.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(form, text="Create Your Patient Profile", font=FT["title"],
                 bg=P["card"], fg=P["acc1"]).grid(row=0, column=0, columnspan=4,
                                                   pady=(0, 22), sticky="w")

        fields = [
            ("Full Name *",                     "name"),
            ("Email Address *",                 "email"),
            ("Phone Number *",                  "phone"),
            ("Date of Birth * (YYYY-MM-DD)",    "dob"),
            ("Blood Group (e.g. O+)",           "blood"),
            ("Address",                         "address"),
        ]
        self.vars = {}
        for i, (label_text, key) in enumerate(fields):
            col = (i % 2) * 2
            row = (i // 2) * 2 + 1
            tk.Label(form, text=label_text, font=FT["small"],
                     bg=P["card"], fg=P["dim"]).grid(row=row, column=col, sticky="w", padx=(0, 10))
            v = tk.StringVar()
            self.vars[key] = v
            entry(form, var=v, width=28).grid(row=row+1, column=col, sticky="w",
                                               pady=(2, 14), padx=(0, 22))

        br = tk.Frame(form, bg=P["card"])
        br.grid(row=20, column=0, columnspan=4, pady=8, sticky="w")
        btn(br, "✅  Register",  self._register,   color=P["acc1"], width=18).pack(side="left")
        btn(br, "🗑  Clear",     self._clear_form, color=P["dim"],  width=10).pack(side="left", padx=10)

    def _clear_form(self):
        for v in self.vars.values():
            v.set("")

    def _register(self):
        d = {k: v.get().strip() for k, v in self.vars.items()}
        errs = []
        if not Validator.validate_name(d["name"]):
            errs.append("• Full name must be at least 2 characters.")
        if not Validator.validate_email(d["email"]):
            errs.append("• Invalid email address.")
        if not Validator.validate_phone(d["phone"]):
            errs.append("• Phone must be 10–15 digits.")
        if not Validator.validate_dob(d["dob"]):
            errs.append("• Date of birth must be a past date (YYYY-MM-DD).")
        if errs:
            messagebox.showerror("Validation Errors", "\n".join(errs))
            return
        if self.app.db.get_patient_by_email(d["email"]):
            messagebox.showerror("Error", "Email already registered. Please login.")
            return
        try:
            self.app.db.register_patient(d["name"], d["email"], d["phone"],
                                          d["dob"], d["blood"], d["address"])
            messagebox.showinfo("Success", f"Welcome, {d['name']}!\nAccount created. You can now login.")
            self.app._login()
        except Exception as ex:
            messagebox.showerror("Error", str(ex))


# ══════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════
class Dashboard:
    def __init__(self, app: App):
        self.app = app

        outer = tk.Frame(app, bg=P["bg"])
        outer.place(relx=0, rely=0, relwidth=1, relheight=1)
        sidebar(outer, app, "dashboard")

        main = tk.Frame(outer, bg=P["bg"])
        main.pack(side="right", fill="both", expand=True)

        # Top bar
        top = tk.Frame(main, bg=P["panel"], height=65)
        top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top, text=f"  Good day, {app.current_patient['name']} 👋",
                 font=FT["heading"], bg=P["panel"], fg=P["text"]).pack(side="left", padx=22, pady=14)
        tk.Label(top, text=datetime.datetime.now().strftime("  📅 %A, %d %B %Y"),
                 font=FT["body"], bg=P["panel"], fg=P["dim"]).pack(side="right", padx=22)

        body = tk.Frame(main, bg=P["bg"])
        body.pack(fill="both", expand=True, padx=22, pady=18)

        pid   = app.current_patient["id"]
        all_a = app.db.get_patient_appointments(pid)
        up    = app.db.get_upcoming_appointments(pid)
        notifs = app.db.get_unread_notifications(pid)
        completed = sum(1 for a in all_a if a["status"] == "Completed")

        # Stat cards
        sr = tk.Frame(body, bg=P["bg"])
        sr.pack(fill="x", pady=(0, 16))
        for icon, title, val, col in [
            ("📅", "Total Appointments", len(all_a),     P["acc2"]),
            ("⏰", "Upcoming",           len(up),        P["acc1"]),
            ("✅", "Completed",          completed,      P["success"]),
            ("🔔", "Notifications",      len(notifs),    P["acc4"]),
        ]:
            c = tk.Frame(sr, bg=P["card"],
                         highlightbackground=col, highlightthickness=2)
            c.pack(side="left", fill="y", expand=True, padx=6, ipady=14, ipadx=10)
            tk.Label(c, text=icon, font=("Segoe UI", 28), bg=P["card"], fg=col).pack(pady=(10, 0))
            tk.Label(c, text=str(val), font=("Segoe UI", 26, "bold"), bg=P["card"], fg=col).pack()
            tk.Label(c, text=title, font=FT["small"], bg=P["card"], fg=P["dim"]).pack(pady=(0, 10))

        # Quick actions
        qa = card(body)
        qa.pack(fill="x", pady=(0, 14), ipady=8)
        lbl(qa, "Quick Actions", "sub", fg=P["acc1"]).pack(anchor="w", padx=20, pady=(12, 8))
        qr = tk.Frame(qa, bg=P["card"]); qr.pack(padx=20, pady=(0, 10))
        btn(qr, "📅 Book Appointment",     app._book,         color=P["acc1"],   width=22).pack(side="left", padx=5)
        btn(qr, "📋 View Appointments",    app._appointments, color=P["acc2"],   width=22).pack(side="left", padx=5)
        btn(qr, "👨‍⚕️ Browse Doctors",       app._doctors,      color=P["acc4"],   width=18).pack(side="left", padx=5)

        # Upcoming table
        uf = card(body); uf.pack(fill="both", expand=True, pady=(0, 8))
        lbl(uf, "Upcoming Appointments", "sub", fg=P["acc1"]).pack(anchor="w", padx=20, pady=(12, 8))

        cols = ("Date", "Time", "Doctor", "Specialization", "Status")
        tree = ttk.Treeview(uf, columns=cols, show="headings", height=6)
        for c, w in zip(cols, [110, 80, 200, 160, 110]):
            tree.heading(c, text=c); tree.column(c, width=w, anchor="center")
        for a in (up or []):
            tree.insert("", "end", values=(a["date"], a["time_slot"],
                                           a["doctor_name"], a["specialization"], a["status"]))
        if not up:
            tree.insert("", "end", values=("No upcoming appointments", "", "", "", ""))
        tree.pack(fill="both", expand=True, padx=20, pady=(0, 14))

        # Notification banner
        if notifs:
            nf = card(body); nf.pack(fill="x", pady=(0, 8), ipady=8)
            lbl(nf, f"🔔  {len(notifs)} Unread Notification(s)", "sub",
                fg=P["acc4"]).pack(anchor="w", padx=20, pady=(10, 4))
            for n in notifs[:3]:
                nb = tk.Frame(nf, bg=P["bg"],
                              highlightbackground=P["acc4"], highlightthickness=1)
                nb.pack(fill="x", padx=20, pady=3)
                tk.Label(nb, text=f"  {n['message']}", font=FT["small"],
                         bg=P["bg"], fg=P["text"], anchor="w").pack(side="left", pady=6)
            btn(nf, "Mark All Read",
                lambda: [app.db.mark_notifications_read(pid), app._dashboard()],
                color=P["dim"], width=14).pack(anchor="e", padx=20, pady=6)


# ══════════════════════════════════════════════
#  BOOK APPOINTMENT SCREEN
# ══════════════════════════════════════════════
class BookScreen:
    def __init__(self, app: App):
        self.app = app
        self.sel_doctor = None
        self.sel_slot   = None

        outer = tk.Frame(app, bg=P["bg"])
        outer.place(relx=0, rely=0, relwidth=1, relheight=1)
        sidebar(outer, app, "book")

        main = tk.Frame(outer, bg=P["bg"])
        main.pack(side="right", fill="both", expand=True)

        top = tk.Frame(main, bg=P["panel"], height=65)
        top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top, text="  📅  Book New Appointment",
                 font=FT["heading"], bg=P["panel"], fg=P["text"]).pack(side="left", padx=22, pady=14)

        body = tk.Frame(main, bg=P["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=18)

        # ── Left: doctor search ─────────────────
        left = card(body)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        lbl(left, "Find a Doctor", "sub", fg=P["acc1"]).pack(anchor="w", padx=16, pady=(14, 8))

        sr = tk.Frame(left, bg=P["card"]); sr.pack(fill="x", padx=16, pady=(0, 8))
        specs = ["All Specializations"] + app.db.get_specializations()
        self.spec_v = tk.StringVar(value=specs[0])
        cb = ttk.Combobox(sr, textvariable=self.spec_v, values=specs, width=24, state="readonly")
        cb.pack(side="left", padx=(0, 8))
        btn(sr, "Filter", self._search, color=P["acc2"], width=10).pack(side="left")

        dcols = ("ID", "Name", "Specialization", "Days", "Hours")
        self.dtree = ttk.Treeview(left, columns=dcols, show="headings", height=14, selectmode="browse")
        for c, w in zip(dcols, [40, 180, 140, 170, 120]):
            self.dtree.heading(c, text=c); self.dtree.column(c, width=w, anchor="center")
        self.dtree.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self.dtree.bind("<<TreeviewSelect>>", self._pick_doctor)
        self._load_doctors()

        # ── Right: booking form ─────────────────
        right = card(body)
        right.pack(side="right", fill="y", ipadx=12)

        lbl(right, "Appointment Details", "sub", fg=P["acc1"]).pack(anchor="w", padx=16, pady=(14, 8))

        self.doc_info = tk.Label(right, text="← Select a doctor",
                                 font=FT["small"], bg=P["card"], fg=P["dim"], wraplength=270)
        self.doc_info.pack(padx=16, pady=(0, 10), anchor="w")

        tk.Label(right, text="Date (YYYY-MM-DD)", font=FT["small"],
                 bg=P["card"], fg=P["dim"]).pack(anchor="w", padx=16)
        self.date_v = tk.StringVar(value=datetime.date.today().strftime("%Y-%m-%d"))
        entry(right, var=self.date_v, width=28).pack(anchor="w", padx=16, pady=(2, 8))

        btn(right, "🔍 Load Available Slots", self._load_slots,
            color=P["acc2"], width=24).pack(padx=16, pady=(0, 10))

        tk.Label(right, text="Available Slots", font=FT["small"],
                 bg=P["card"], fg=P["dim"]).pack(anchor="w", padx=16)
        self.slots_f = tk.Frame(right, bg=P["card"])
        self.slots_f.pack(fill="x", padx=16, pady=(4, 10))

        self.sel_lbl = tk.Label(right, text="No slot selected",
                                font=FT["small"], bg=P["card"], fg=P["acc4"])
        self.sel_lbl.pack(padx=16, pady=(0, 8))

        tk.Label(right, text="Reason for Visit", font=FT["small"],
                 bg=P["card"], fg=P["dim"]).pack(anchor="w", padx=16)
        self.reason_v = tk.StringVar()
        entry(right, var=self.reason_v, width=28).pack(anchor="w", padx=16, pady=(2, 14))

        btn(right, "✅ Confirm Booking", self._confirm,
            color=P["acc1"], width=24).pack(padx=16, pady=8)

    def _load_doctors(self, doctors=None):
        self.dtree.delete(*self.dtree.get_children())
        for d in (doctors or self.app.db.get_all_doctors()):
            self.dtree.insert("", "end", values=(
                d["id"], d["name"], d["specialization"],
                d["available_days"], f"{d['start_time']}–{d['end_time']}"
            ))

    def _search(self):
        s = self.spec_v.get()
        self._load_doctors(None if s == "All Specializations"
                           else self.app.db.get_doctors_by_specialization(s))

    def _pick_doctor(self, _=None):
        sel = self.dtree.selection()
        if sel:
            v = self.dtree.item(sel[0])["values"]
            self.sel_doctor = self.app.db.get_doctor_by_id(v[0])
            self.doc_info.config(
                text=f"✔ {v[1]}\n{v[2]}\nDays: {v[3]}  |  {v[4]}",
                fg=P["acc1"])
            self.sel_slot = None
            self.sel_lbl.config(text="No slot selected")

    def _load_slots(self):
        for w in self.slots_f.winfo_children():
            w.destroy()
        if not self.sel_doctor:
            messagebox.showwarning("Select Doctor", "Please select a doctor first.")
            return
        date = self.date_v.get().strip()
        if not Validator.validate_future_date(date):
            messagebox.showerror("Invalid Date", "Enter a valid future date (YYYY-MM-DD).")
            return
        slots = self.app.db.get_available_slots(self.sel_doctor["id"], date)
        if not slots:
            tk.Label(self.slots_f, text="No slots available on this day.",
                     font=FT["small"], bg=P["card"], fg=P["error"]).pack()
            return
        for i, s in enumerate(slots):
            tk.Button(self.slots_f, text=s, font=FT["small"],
                      bg=P["bg"], fg=P["text"], relief="flat",
                      padx=7, pady=4, cursor="hand2",
                      highlightbackground=P["acc1"], highlightthickness=1,
                      command=lambda x=s: self._pick_slot(x)
                      ).grid(row=i // 4, column=i % 4, padx=3, pady=3)

    def _pick_slot(self, s):
        self.sel_slot = s
        self.sel_lbl.config(text=f"Selected: {s}", fg=P["acc1"])

    def _confirm(self):
        if not self.sel_doctor:
            messagebox.showwarning("Missing", "Select a doctor."); return
        if not self.sel_slot:
            messagebox.showwarning("Missing", "Select a time slot."); return
        reason = self.reason_v.get().strip()
        if not reason:
            messagebox.showwarning("Missing", "Enter a reason for visit."); return
        try:
            self.app.db.book_appointment(
                self.app.current_patient["id"],
                self.sel_doctor["id"],
                self.date_v.get().strip(),
                self.sel_slot, reason
            )
            messagebox.showinfo("Confirmed",
                                f"✅ Appointment booked!\n\nDoctor : {self.sel_doctor['name']}"
                                f"\nDate   : {self.date_v.get()}\nTime   : {self.sel_slot}")
            self.app._appointments()
        except ValueError as e:
            messagebox.showerror("Booking Failed", str(e))


# ══════════════════════════════════════════════
#  MY APPOINTMENTS SCREEN
# ══════════════════════════════════════════════
class AppointmentsScreen:
    def __init__(self, app: App):
        self.app = app

        outer = tk.Frame(app, bg=P["bg"])
        outer.place(relx=0, rely=0, relwidth=1, relheight=1)
        sidebar(outer, app, "appointments")

        main = tk.Frame(outer, bg=P["bg"])
        main.pack(side="right", fill="both", expand=True)

        top = tk.Frame(main, bg=P["panel"], height=65)
        top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top, text="  📋  My Appointments",
                 font=FT["heading"], bg=P["panel"], fg=P["text"]).pack(side="left", padx=22, pady=14)

        body = tk.Frame(main, bg=P["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=18)

        tf = card(body); tf.pack(fill="both", expand=True, pady=(0, 10))
        lbl(tf, "Appointment History", "sub", fg=P["acc1"]).pack(anchor="w", padx=16, pady=(12, 8))

        cols = ("ID", "Date", "Time", "Doctor", "Specialization", "Reason", "Status")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", height=14, selectmode="browse")
        for c, w in zip(cols, [40, 100, 70, 180, 150, 200, 100]):
            self.tree.heading(c, text=c); self.tree.column(c, width=w, anchor="center")
        sb2 = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb2.set)
        sb2.pack(side="right", fill="y", padx=(0, 8), pady=(0, 10))
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self._load()

        # Actions
        af = card(body); af.pack(fill="x", ipady=10)
        lbl(af, "Actions", "sub", fg=P["acc1"]).pack(anchor="w", padx=16, pady=(12, 8))
        ar = tk.Frame(af, bg=P["card"]); ar.pack(padx=16, pady=(0, 8))
        btn(ar, "❌ Cancel",       self._cancel,          color=P["error"],  width=14).pack(side="left", padx=5)
        btn(ar, "🔄 Reschedule",   self._show_reschedule, color=P["acc4"],   width=16).pack(side="left", padx=5)

        self.resf = tk.Frame(af, bg=P["card"]); self.resf.pack(fill="x", padx=16, pady=(0, 10))
        tk.Label(self.resf, text="New Date:", font=FT["small"], bg=P["card"], fg=P["dim"]).pack(side="left")
        self.nd_v = tk.StringVar()
        entry(self.resf, var=self.nd_v, width=13).pack(side="left", padx=5)
        tk.Label(self.resf, text="New Time (HH:MM):", font=FT["small"], bg=P["card"], fg=P["dim"]).pack(side="left", padx=(10, 0))
        self.nt_v = tk.StringVar()
        entry(self.resf, var=self.nt_v, width=8).pack(side="left", padx=5)
        btn(self.resf, "Confirm Reschedule", self._confirm_reschedule,
            color=P["acc1"], width=20).pack(side="left", padx=10)
        self.resf.pack_forget()

    def _load(self):
        self.tree.delete(*self.tree.get_children())
        for a in self.app.db.get_patient_appointments(self.app.current_patient["id"]):
            self.tree.insert("", "end", tags=(a["status"],), values=(
                a["id"], a["date"], a["time_slot"],
                a["doctor_name"], a["specialization"],
                a["reason"] or "–", a["status"]
            ))
        self.tree.tag_configure("Cancelled", foreground=P["error"])
        self.tree.tag_configure("Scheduled", foreground=P["acc1"])
        self.tree.tag_configure("Completed", foreground=P["success"])

    def _sel_id(self):
        s = self.tree.selection()
        if not s:
            messagebox.showwarning("Select", "Please select an appointment."); return None
        return self.tree.item(s[0])["values"][0]

    def _cancel(self):
        aid = self._sel_id()
        if aid and messagebox.askyesno("Confirm", f"Cancel appointment #{aid}?"):
            try:
                self.app.db.cancel_appointment(aid)
                messagebox.showinfo("Done", "Appointment cancelled.")
                self._load()
            except ValueError as e:
                messagebox.showerror("Error", str(e))

    def _show_reschedule(self):
        if self._sel_id():
            self.resf.pack(fill="x", padx=16, pady=(0, 10))

    def _confirm_reschedule(self):
        aid = self._sel_id()
        nd  = self.nd_v.get().strip()
        nt  = self.nt_v.get().strip()
        if not aid: return
        if not Validator.validate_future_date(nd):
            messagebox.showerror("Invalid Date", "Enter a valid future date (YYYY-MM-DD)."); return
        try:
            self.app.db.reschedule_appointment(aid, nd, nt)
            messagebox.showinfo("Success", f"Rescheduled to {nd} at {nt}.")
            self.resf.pack_forget()
            self._load()
        except ValueError as e:
            messagebox.showerror("Error", str(e))


# ══════════════════════════════════════════════
#  DOCTORS SCREEN
# ══════════════════════════════════════════════
class DoctorsScreen:
    def __init__(self, app: App):
        self.app = app

        outer = tk.Frame(app, bg=P["bg"])
        outer.place(relx=0, rely=0, relwidth=1, relheight=1)
        sidebar(outer, app, "doctors")

        main = tk.Frame(outer, bg=P["bg"])
        main.pack(side="right", fill="both", expand=True)

        top = tk.Frame(main, bg=P["panel"], height=65)
        top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top, text="  👨‍⚕️  Our Specialist Doctors",
                 font=FT["heading"], bg=P["panel"], fg=P["text"]).pack(side="left", padx=22, pady=14)

        body = tk.Frame(main, bg=P["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=18)

        sf = card(body); sf.pack(fill="x", pady=(0, 10), ipady=8)
        sr = tk.Frame(sf, bg=P["card"]); sr.pack(padx=16, pady=4)
        tk.Label(sr, text="Filter by Specialization:",
                 font=FT["small"], bg=P["card"], fg=P["dim"]).pack(side="left")
        specs = ["All"] + app.db.get_specializations()
        self.spec_v = tk.StringVar(value="All")
        cb = ttk.Combobox(sr, textvariable=self.spec_v, values=specs, width=24, state="readonly")
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda _: self._load())

        # Scrollable canvas for doctor cards
        self.cf = tk.Frame(body, bg=P["bg"])
        self.cf.pack(fill="both", expand=True)
        self._load()

    def _load(self):
        for w in self.cf.winfo_children():
            w.destroy()
        s = self.spec_v.get()
        docs = (self.app.db.get_all_doctors() if s == "All"
                else self.app.db.get_doctors_by_specialization(s))
        cols = 3
        for i, d in enumerate(docs):
            c = tk.Frame(self.cf, bg=P["card"],
                         highlightbackground=P["acc2"], highlightthickness=1)
            c.grid(row=i // cols, column=i % cols, padx=8, pady=8,
                   sticky="nsew", ipadx=14, ipady=12)
            self.cf.columnconfigure(i % cols, weight=1)
            tk.Label(c, text="👨‍⚕️", font=("Segoe UI", 32),
                     bg=P["card"]).grid(row=0, column=0, rowspan=2, padx=10)
            tk.Label(c, text=d["name"], font=FT["sub"],
                     bg=P["card"], fg=P["text"]).grid(row=0, column=1, sticky="w")
            tk.Label(c, text=d["specialization"], font=FT["small"],
                     bg=P["card"], fg=P["acc1"]).grid(row=1, column=1, sticky="w")
            for row_n, ico, val in [
                (2, "📞", d["phone"]),
                (3, "🗓", d["available_days"]),
                (4, "⏱", f"{d['start_time']}–{d['end_time']}  ({d['slot_duration']} min/slot)"),
            ]:
                tk.Label(c, text=f"{ico}  {val}", font=FT["small"],
                         bg=P["card"], fg=P["dim"]).grid(
                             row=row_n, column=0, columnspan=2,
                             sticky="w", padx=10, pady=(0, 4))


# ══════════════════════════════════════════════
#  ADMIN SCREEN
# ══════════════════════════════════════════════
class AdminScreen:
    def __init__(self, app: App):
        self.app = app

        outer = tk.Frame(app, bg=P["bg"])
        outer.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Admin sidebar
        sb = tk.Frame(outer, bg=P["panel"], width=225)
        sb.pack(side="left", fill="y"); sb.pack_propagate(False)
        tk.Label(sb, text="🏥  Admin Panel", font=("Segoe UI", 14, "bold"),
                 bg=P["panel"], fg=P["acc3"]).pack(pady=(25, 2), padx=18, anchor="w")
        tk.Label(sb, text="  Administrator", font=FT["small"],
                 bg=P["panel"], fg=P["dim"]).pack(anchor="w", padx=18)
        tk.Frame(sb, bg=P["border"], height=1).pack(fill="x", padx=18, pady=14)

        self.main = tk.Frame(outer, bg=P["bg"])
        self.main.pack(side="right", fill="both", expand=True)

        for text, key in [("📋 All Appointments", "appts"),
                           ("👥 All Patients",      "patients"),
                           ("🧪 Unit Test Runner",  "tests")]:
            tk.Button(sb, text=text, font=FT["body"],
                      bg=P["panel"], fg=P["text"],
                      relief="flat", anchor="w", padx=20, pady=10, cursor="hand2",
                      command=lambda k=key: self._switch(k)
                      ).pack(fill="x", padx=5, pady=2)

        tk.Frame(sb, bg=P["border"], height=1).pack(fill="x", padx=18, pady=14, side="bottom")
        tk.Button(sb, text="⬅  Logout", command=app._login,
                  bg=P["panel"], fg=P["error"], font=FT["body"],
                  relief="flat", anchor="w", padx=20, pady=10, cursor="hand2"
                  ).pack(fill="x", padx=5, pady=2, side="bottom")

        self._show_appointments()

    def _switch(self, k):
        for w in self.main.winfo_children():
            w.destroy()
        {"appts": self._show_appointments, "patients": self._show_patients,
         "tests": self._show_tests}[k]()

    def _topbar(self, title):
        t = tk.Frame(self.main, bg=P["panel"], height=65)
        t.pack(fill="x"); t.pack_propagate(False)
        tk.Label(t, text=f"  {title}", font=FT["heading"],
                 bg=P["panel"], fg=P["text"]).pack(side="left", padx=22, pady=14)

    def _show_appointments(self):
        self._topbar("📋  All Appointments")
        body = tk.Frame(self.main, bg=P["bg"]); body.pack(fill="both", expand=True, padx=20, pady=18)
        tf = card(body); tf.pack(fill="both", expand=True)
        cols = ("ID", "Patient", "Doctor", "Specialization", "Date", "Time", "Reason", "Status")
        tree = ttk.Treeview(tf, columns=cols, show="headings", height=18)
        for c, w in zip(cols, [40, 150, 160, 140, 100, 70, 190, 100]):
            tree.heading(c, text=c); tree.column(c, width=w, anchor="center")
        sb2 = ttk.Scrollbar(tf, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb2.set)
        sb2.pack(side="right", fill="y", padx=(0, 8), pady=10)
        tree.pack(fill="both", expand=True, padx=16, pady=10)
        for a in self.app.db.get_all_appointments():
            tree.insert("", "end", tags=(a["status"],), values=(
                a["id"], a["patient_name"], a["doctor_name"], a["specialization"],
                a["date"], a["time_slot"], a["reason"] or "–", a["status"]
            ))
        tree.tag_configure("Cancelled", foreground=P["error"])
        tree.tag_configure("Scheduled", foreground=P["acc1"])
        tree.tag_configure("Completed", foreground=P["success"])

    def _show_patients(self):
        self._topbar("👥  All Patients")
        body = tk.Frame(self.main, bg=P["bg"]); body.pack(fill="both", expand=True, padx=20, pady=18)
        tf = card(body); tf.pack(fill="both", expand=True)
        cols = ("ID", "Name", "Email", "Phone", "DOB", "Blood Group", "Registered")
        tree = ttk.Treeview(tf, columns=cols, show="headings", height=18)
        for c, w in zip(cols, [40, 160, 220, 120, 100, 90, 140]):
            tree.heading(c, text=c); tree.column(c, width=w, anchor="center")
        sb2 = ttk.Scrollbar(tf, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb2.set)
        sb2.pack(side="right", fill="y", padx=(0, 8), pady=10)
        tree.pack(fill="both", expand=True, padx=16, pady=10)
        for p in self.app.db.get_all_patients():
            tree.insert("", "end", values=(
                p["id"], p["name"], p["email"], p["phone"],
                p["dob"], p["blood_group"] or "–", p["created_at"][:10]
            ))

    def _show_tests(self):
        self._topbar("🧪  Unit Test Runner")
        body = tk.Frame(self.main, bg=P["bg"]); body.pack(fill="both", expand=True, padx=20, pady=18)

        tr = tk.Frame(body, bg=P["bg"]); tr.pack(fill="x", pady=(0, 10))
        btn(tr, "▶  Run All Tests", self._run_tests, color=P["acc1"], width=20).pack(side="left")
        self.tstatus = tk.Label(tr, text="", font=FT["sub"], bg=P["bg"], fg=P["text"])
        self.tstatus.pack(side="left", padx=16)

        out_f = card(body); out_f.pack(fill="both", expand=True)
        lbl(out_f, "Test Output", "sub", fg=P["acc2"]).pack(anchor="w", padx=16, pady=(12, 4))
        self.tout = tk.Text(out_f, bg=P["bg"], fg=P["text"], font=FT["mono"],
                            relief="flat", insertbackground=P["acc1"])
        sb2 = ttk.Scrollbar(out_f, orient="vertical", command=self.tout.yview)
        self.tout.configure(yscrollcommand=sb2.set)
        sb2.pack(side="right", fill="y", padx=(0, 8), pady=10)
        self.tout.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.tout.insert("1.0", "Click '▶ Run All Tests' to execute the unit test suite.\n\n"
                         "Tests cover:\n"
                         "  • Email / phone / date / name validation\n"
                         "  • Patient registration & duplicate detection\n"
                         "  • Doctor seeding & specialization queries\n"
                         "  • Slot generation & availability logic\n"
                         "  • Appointment booking, cancellation, rescheduling\n"
                         "  • Overlap / double-booking prevention\n"
                         "  • Notification creation & mark-as-read\n")

    def _run_tests(self):
        self.tout.delete("1.0", "end")
        self.tstatus.config(text="⏳ Running...", fg=P["acc4"])
        self.main.update()
        stream = io.StringIO()
        loader = unittest.TestLoader()
        suite  = loader.loadTestsFromTestCase(TestHealthSystem)
        runner = unittest.TextTestRunner(stream=stream, verbosity=2)
        result = runner.run(suite)
        self.tout.insert("1.0", stream.getvalue())
        passed = result.testsRun - len(result.failures) - len(result.errors)
        if result.wasSuccessful():
            self.tstatus.config(text=f"✅ All {result.testsRun} tests passed!", fg=P["success"])
        else:
            self.tstatus.config(
                text=f"❌ {len(result.failures)+len(result.errors)} failed / {result.testsRun} total",
                fg=P["error"])


# ══════════════════════════════════════════════
#  UNIT TEST SUITE
# ══════════════════════════════════════════════
class TestHealthSystem(unittest.TestCase):
    """
    Comprehensive unit tests for the Smart Health Appointment
    Management System.  Uses an in-memory SQLite database so
    no on-disk state is modified.
    """

    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseManager(":memory:")
        cls.db.register_patient(
            "Test Patient", "test@test.com", "0300-1111111",
            "1990-05-15", "O+", "123 Test Street"
        )
        cls.patient = cls.db.get_patient_by_email("test@test.com")
        cls.doctor  = cls.db.get_all_doctors()[0]

    # ── Validator Tests ──────────────────────
    def test_valid_email_standard(self):
        self.assertTrue(Validator.validate_email("user@example.com"))

    def test_valid_email_complex(self):
        self.assertTrue(Validator.validate_email("user.name+tag@domain.co.uk"))

    def test_invalid_email_no_at(self):
        self.assertFalse(Validator.validate_email("notanemail"))

    def test_invalid_email_no_user(self):
        self.assertFalse(Validator.validate_email("@domain.com"))

    def test_invalid_email_no_domain(self):
        self.assertFalse(Validator.validate_email("user@"))

    def test_valid_phone_plain(self):
        self.assertTrue(Validator.validate_phone("03001234567"))

    def test_valid_phone_dashes(self):
        self.assertTrue(Validator.validate_phone("0300-123-4567"))

    def test_valid_phone_plus(self):
        self.assertTrue(Validator.validate_phone("+923001234567"))

    def test_invalid_phone_too_short(self):
        self.assertFalse(Validator.validate_phone("123"))

    def test_invalid_phone_letters(self):
        self.assertFalse(Validator.validate_phone("abcdefghij"))

    def test_valid_date_normal(self):
        self.assertTrue(Validator.validate_date("2025-06-15"))

    def test_valid_date_year_end(self):
        self.assertTrue(Validator.validate_date("2026-12-31"))

    def test_invalid_date_format(self):
        self.assertFalse(Validator.validate_date("15-06-2025"))

    def test_invalid_date_string(self):
        self.assertFalse(Validator.validate_date("not-a-date"))

    def test_invalid_date_month_13(self):
        self.assertFalse(Validator.validate_date("2025-13-01"))

    def test_future_date_is_valid(self):
        future = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
        self.assertTrue(Validator.validate_future_date(future))

    def test_past_date_not_future(self):
        self.assertFalse(Validator.validate_future_date("2020-01-01"))

    def test_today_is_not_past(self):
        self.assertTrue(Validator.validate_future_date(datetime.date.today().isoformat()))

    def test_valid_dob(self):
        self.assertTrue(Validator.validate_dob("1990-05-15"))

    def test_invalid_dob_future(self):
        future = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        self.assertFalse(Validator.validate_dob(future))

    def test_valid_name_two_chars(self):
        self.assertTrue(Validator.validate_name("Al"))

    def test_valid_name_full(self):
        self.assertTrue(Validator.validate_name("Muhammad Ali Khan"))

    def test_invalid_name_one_char(self):
        self.assertFalse(Validator.validate_name("A"))

    def test_invalid_name_spaces(self):
        self.assertFalse(Validator.validate_name("  "))

    # ── Patient Tests ────────────────────────
    def test_patient_registration_succeeds(self):
        self.db.register_patient(
            "Jane Doe", "jane@test.com", "0301-2222222",
            "1985-03-20", "A+", "456 Oak Ave"
        )
        p = self.db.get_patient_by_email("jane@test.com")
        self.assertIsNotNone(p)
        self.assertEqual(p["name"], "Jane Doe")

    def test_duplicate_email_raises(self):
        with self.assertRaises(Exception):
            self.db.register_patient(
                "Duplicate", "test@test.com", "0300-9999999",
                "1990-01-01", "B+", "Somewhere"
            )

    def test_get_all_patients_returns_records(self):
        patients = self.db.get_all_patients()
        self.assertGreater(len(patients), 0)

    def test_patient_has_required_fields(self):
        p = self.db.get_patient_by_email("test@test.com")
        for field in ["id", "name", "email", "phone", "dob"]:
            self.assertIn(field, p.keys())

    # ── Doctor Tests ─────────────────────────
    def test_doctors_seeded_at_least_10(self):
        self.assertGreaterEqual(len(self.db.get_all_doctors()), 10)

    def test_get_doctors_by_specialization(self):
        cards = self.db.get_doctors_by_specialization("Cardiology")
        self.assertGreater(len(cards), 0)
        for d in cards:
            self.assertIn("Cardiology", d["specialization"])

    def test_doctor_has_required_fields(self):
        d = self.db.get_all_doctors()[0]
        for f in ["name", "specialization", "available_days", "slot_duration"]:
            self.assertIn(f, d.keys())

    def test_get_specializations_includes_cardiology(self):
        self.assertIn("Cardiology", self.db.get_specializations())

    def test_get_doctor_by_id(self):
        d  = self.db.get_all_doctors()[0]
        d2 = self.db.get_doctor_by_id(d["id"])
        self.assertEqual(d["name"], d2["name"])

    # ── Slot Tests ───────────────────────────
    def _next_weekday(self, weekday: int, weeks_ahead: int = 0) -> str:
        """Return next occurrence of 'weekday' (0=Mon) as YYYY-MM-DD."""
        day = datetime.date.today() + datetime.timedelta(days=1)
        while day.weekday() != weekday:
            day += datetime.timedelta(days=1)
        day += datetime.timedelta(weeks=weeks_ahead)
        return day.isoformat()

    def test_no_slots_on_sunday(self):
        doc = self.db.get_doctors_by_specialization("Neurology")[0]
        sunday = self._next_weekday(6)  # 6 = Sunday
        self.assertEqual(self.db.get_available_slots(doc["id"], sunday), [])

    def test_slots_on_working_monday(self):
        doc = next(d for d in self.db.get_all_doctors() if "Mon" in d["available_days"])
        monday = self._next_weekday(0)
        slots = self.db.get_available_slots(doc["id"], monday)
        self.assertGreater(len(slots), 0)

    def test_slots_are_strings(self):
        doc = next(d for d in self.db.get_all_doctors() if "Mon" in d["available_days"])
        slots = self.db.get_available_slots(doc["id"], self._next_weekday(0))
        for s in slots:
            self.assertRegex(s, r"^\d{2}:\d{2}$")

    def test_slot_count_for_15min_doctor(self):
        """8:00–18:00 with 15-min slots = 40 slots max."""
        doc = next(d for d in self.db.get_all_doctors()
                   if d["slot_duration"] == 15 and "Mon" in d["available_days"])
        slots = self.db.get_available_slots(doc["id"], self._next_weekday(0))
        self.assertEqual(len(slots), 40)

    def test_is_slot_available_true(self):
        doc = next(d for d in self.db.get_all_doctors() if "Fri" in d["available_days"])
        friday = self._next_weekday(4)
        slots = self.db.get_available_slots(doc["id"], friday)
        if slots:
            self.assertTrue(self.db.is_slot_available(doc["id"], friday, slots[-1]))

    # ── Appointment Tests ────────────────────
    def test_book_appointment_success(self):
        doc  = next(d for d in self.db.get_all_doctors() if "Mon" in d["available_days"])
        date = self._next_weekday(0)
        slots = self.db.get_available_slots(doc["id"], date)
        self.assertTrue(
            self.db.book_appointment(self.patient["id"], doc["id"], date, slots[0], "Test visit")
        )

    def test_double_booking_raises_value_error(self):
        doc  = next(d for d in self.db.get_all_doctors() if "Tue" in d["available_days"])
        date = self._next_weekday(1)
        slots = self.db.get_available_slots(doc["id"], date)
        self.assertGreater(len(slots), 1)
        slot = slots[1]
        self.db.book_appointment(self.patient["id"], doc["id"], date, slot, "First")
        with self.assertRaises(ValueError):
            self.db.book_appointment(self.patient["id"], doc["id"], date, slot, "Duplicate")

    def test_slot_unavailable_after_booking(self):
        doc  = next(d for d in self.db.get_all_doctors() if "Wed" in d["available_days"])
        date = self._next_weekday(2)
        slots = self.db.get_available_slots(doc["id"], date)
        if len(slots) >= 2:
            slot = slots[2]
            self.db.book_appointment(self.patient["id"], doc["id"], date, slot, "Block slot")
            self.assertFalse(self.db.is_slot_available(doc["id"], date, slot))

    def test_cancel_appointment(self):
        doc  = next(d for d in self.db.get_all_doctors() if "Thu" in d["available_days"])
        date = self._next_weekday(3)
        slots = self.db.get_available_slots(doc["id"], date)
        if slots:
            self.db.book_appointment(self.patient["id"], doc["id"], date, slots[0], "To cancel")
            appts  = self.db.get_patient_appointments(self.patient["id"])
            aid    = [a["id"] for a in appts if a["status"] == "Scheduled"][-1]
            self.assertTrue(self.db.cancel_appointment(aid))
            appts2 = self.db.get_patient_appointments(self.patient["id"])
            record = next(a for a in appts2 if a["id"] == aid)
            self.assertEqual(record["status"], "Cancelled")

    def test_cancel_nonexistent_raises(self):
        with self.assertRaises(ValueError):
            self.db.cancel_appointment(999999)

    def test_reschedule_cancelled_appointment_raises(self):
        doc  = next(d for d in self.db.get_all_doctors() if "Fri" in d["available_days"])
        d1   = self._next_weekday(4)
        d2   = self._next_weekday(4, weeks_ahead=1)
        sl1  = self.db.get_available_slots(doc["id"], d1)
        sl2  = self.db.get_available_slots(doc["id"], d2)
        if sl1 and sl2:
            self.db.book_appointment(self.patient["id"], doc["id"], d1, sl1[-1], "Reschedule test")
            appts = self.db.get_patient_appointments(self.patient["id"])
            aid   = [a["id"] for a in appts if a["status"] == "Scheduled"][-1]
            self.db.cancel_appointment(aid)
            with self.assertRaises(ValueError):
                self.db.reschedule_appointment(aid, d2, sl2[0])

    def test_upcoming_appointments_all_future(self):
        today = datetime.date.today().isoformat()
        for a in self.db.get_upcoming_appointments(self.patient["id"]):
            self.assertGreaterEqual(a["date"], today)
            self.assertEqual(a["status"], "Scheduled")

    def test_get_all_appointments(self):
        appts = self.db.get_all_appointments()
        self.assertIsInstance(appts, list)

    # ── Notification Tests ───────────────────
    def test_booking_creates_notification(self):
        doc   = next(d for d in self.db.get_all_doctors() if "Mon" in d["available_days"])
        date  = self._next_weekday(0, weeks_ahead=2)
        slots = self.db.get_available_slots(doc["id"], date)
        before = len(self.db.get_unread_notifications(self.patient["id"]))
        if slots:
            self.db.book_appointment(self.patient["id"], doc["id"], date, slots[0], "Notif test")
            after = len(self.db.get_unread_notifications(self.patient["id"]))
            self.assertGreater(after, before)

    def test_mark_notifications_read(self):
        self.db.mark_notifications_read(self.patient["id"])
        self.assertEqual(len(self.db.get_unread_notifications(self.patient["id"])), 0)

    def test_cancellation_creates_notification(self):
        doc   = next(d for d in self.db.get_all_doctors() if "Tue" in d["available_days"])
        date  = self._next_weekday(1, weeks_ahead=3)
        slots = self.db.get_available_slots(doc["id"], date)
        if slots:
            self.db.book_appointment(self.patient["id"], doc["id"], date, slots[0], "Notif cancel")
            self.db.mark_notifications_read(self.patient["id"])
            appts = self.db.get_patient_appointments(self.patient["id"])
            aid   = [a["id"] for a in appts if a["status"] == "Scheduled"][-1]
            self.db.cancel_appointment(aid)
            notifs = self.db.get_unread_notifications(self.patient["id"])
            self.assertGreater(len(notifs), 0)


# ──────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────
if __name__ == "__main__":
    if "--test" in sys.argv:
        print("=" * 70)
        print("   SMART HEALTH APPOINTMENT SYSTEM  —  UNIT TEST SUITE")
        print("=" * 70)
        loader = unittest.TestLoader()
        suite  = loader.loadTestsFromTestCase(TestHealthSystem)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        print("\n" + "=" * 70)
        print(f"  RESULT: {'PASSED ✅' if result.wasSuccessful() else 'FAILED ❌'}")
        print(f"  Tests run : {result.testsRun}")
        print(f"  Failures  : {len(result.failures)}")
        print(f"  Errors    : {len(result.errors)}")
        print("=" * 70)
        sys.exit(0 if result.wasSuccessful() else 1)
    else:
        app = App()
        app.mainloop()