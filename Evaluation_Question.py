import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import sqlite3, random, time, threading, unittest, heapq
from datetime import datetime

# ── Colour Theme (warm green + charcoal) ──────────
BG, PANEL, CARD = "#1c271b", "#352923", "#2a3444"
A1, A2 = "#2ecc71", "#e67e22"          # green accent, orange
RED, YLW = "#e74c3c", "#f1c40f"
TXT, DIM = "#ecf0f1", "#7f8c9a"
FH = ("Consolas", 13, "bold")          # font head
FL = ("Consolas", 10)                  # font label
FM = ("Consolas", 9)                   # font mono/small

def btn(parent, text, cmd, color=A1, **kw):
    return tk.Button(parent, text=text, command=cmd,
                     bg=CARD, fg=color, font=FL, relief="flat",
                     activebackground=PANEL, activeforeground=color,
                     padx=10, pady=5, cursor="hand2",
                     highlightthickness=1, highlightbackground=color, **kw)

# ── Database ──────────────────────────────────────
class DB:
    def __init__(self, path="pk_traffic.db"):
        self.path = path
        c = sqlite3.connect(path, check_same_thread=False) if path == ":memory:" else None
        self._mem = c
        cx = self._cx()
        for sql in [
            "CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY,loc TEXT,cong INT,ts TEXT,status TEXT)",
            "CREATE TABLE IF NOT EXISTS accidents(id INTEGER PRIMARY KEY,loc TEXT,desc TEXT,sev TEXT,ts TEXT,resolved INT DEFAULT 0)",
            "CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY,msg TEXT,kind TEXT,ts TEXT)",
        ]: cx.execute(sql)
        cx.commit()

    def _cx(self):
        return self._mem or sqlite3.connect(self.path)

    def log(self, loc, cong, status="normal"):
        if not loc or not loc.strip(): raise ValueError("Location cannot be empty")
        if not 0 <= cong <= 100: raise ValueError("Congestion must be 0–100")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cx = self._cx(); cx.execute("INSERT INTO records VALUES(NULL,?,?,?,?)",(loc.strip(),cong,ts,status)); cx.commit()
        return ts

    def accident(self, loc, desc, sev):
        if not loc or not loc.strip(): raise ValueError("Location cannot be empty")
        if sev not in {"low","medium","high","critical"}: raise ValueError("Bad severity")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cx = self._cx(); cx.execute("INSERT INTO accidents VALUES(NULL,?,?,?,?,0)",(loc.strip(),desc,sev,ts)); cx.commit()
        return ts

    def alert(self, msg, kind):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cx = self._cx(); cx.execute("INSERT INTO alerts VALUES(NULL,?,?,?)",(msg,kind,ts)); cx.commit()

    def recent(self, n=40):
        return self._cx().execute("SELECT loc,cong,ts,status FROM records ORDER BY id DESC LIMIT ?",(n,)).fetchall()

    def active_accidents(self):
        return self._cx().execute("SELECT id,loc,desc,sev,ts FROM accidents WHERE resolved=0 ORDER BY id DESC").fetchall()

    def get_alerts(self, n=15):
        return self._cx().execute("SELECT msg,kind,ts FROM alerts ORDER BY id DESC LIMIT ?",(n,)).fetchall()

    def resolve(self, aid):
        cx = self._cx(); cx.execute("UPDATE accidents SET resolved=1 WHERE id=?",(aid,)); cx.commit()

    def analytics(self):
        return self._cx().execute("SELECT loc,AVG(cong),MAX(cong),COUNT(*) FROM records GROUP BY loc").fetchall()

# ── Traffic Engine ────────────────────────────────
class Engine:
    GRAPH = {
        "Karachi":   [("Hyderabad",6),("Sukkur",10),("Hub",4)],
        "Lahore":    [("Islamabad",7),("Faisalabad",5),("Multan",6)],
        "Islamabad": [("Lahore",7),("Peshawar",4),("Rawalpindi",2)],
        "Rawalpindi":[("Islamabad",2),("Peshawar",5),("Lahore",7)],
        "Faisalabad":[("Lahore",5),("Multan",4),("Sargodha",3)],
        "Multan":    [("Lahore",6),("Faisalabad",4),("Bahawalpur",5)],
        "Peshawar":  [("Islamabad",4),("Rawalpindi",5)],
        "Hyderabad": [("Karachi",6),("Sukkur",7)],
        "Sukkur":    [("Karachi",10),("Hyderabad",7),("Multan",8)],
        "Quetta":    [("Hub",9),("Multan",11)],
        "Hub":       [("Karachi",4),("Quetta",9)],
        "Sargodha":  [("Faisalabad",3),("Rawalpindi",4)],
        "Bahawalpur":[("Multan",5),("Sukkur",6)],
    }
    ZONES = list(GRAPH.keys())

    def __init__(self):
        self.cong = {z: random.randint(5,45) for z in self.ZONES}
        self.accident_zones = set()

    def update(self):
        for z in self.ZONES:
            d = random.randint(-7,10)
            v = self.cong[z] + d + (random.randint(8,18) if z in self.accident_zones else 0)
            self.cong[z] = max(0, min(100, v))

    def level(self, v):
        if v < 25: return "LOW", A1
        if v < 50: return "MODERATE", YLW
        if v < 75: return "HIGH", A2
        return "CRITICAL", RED

    def predict(self, zone, hrs=1):
        if zone not in self.cong: raise ValueError(f"Unknown zone: {zone}")
        if hrs < 0: raise ValueError("hrs must be >= 0")
        h = (datetime.now().hour + hrs) % 24
        f = 1.4 if 8<=h<=10 else 1.5 if 17<=h<=19 else 0.5 if h<=5 else 1.0
        return int(min(100, self.cong[zone] * f))

    def route(self, src, dst):
        if src not in self.GRAPH: raise ValueError(f"Unknown: {src}")
        if dst not in self.GRAPH: raise ValueError(f"Unknown: {dst}")
        if src == dst: return [src], 0.0
        dist = {z: float("inf") for z in self.GRAPH}; dist[src] = 0.0
        prev = {z: None for z in self.GRAPH}; heap = [(0.0, src)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]: continue
            for v, w in self.GRAPH[u]:
                nd = d + w * (1 + self.cong.get(v,0)/100)
                if nd < dist[v]: dist[v]=nd; prev[v]=u; heapq.heappush(heap,(nd,v))
        path, n = [], dst
        while n: path.append(n); n = prev[n]
        path.reverse()
        if path[0] != src: raise RuntimeError("No path found")
        return path, round(dist[dst], 2)

    def alt_routes(self, src, dst, n=3):
        saved = dict(self.cong); routes = []; seen = set()
        for _ in range(n*4):
            try:
                p, c = self.route(src, dst)
                k = tuple(p)
                if k not in seen:
                    seen.add(k); routes.append((p,c))
                    if len(routes)==n: break
                for z in p[1:-1]: self.cong[z] = min(100, self.cong[z]+30)
            except: break
        self.cong = saved; return routes

# ── Unit Tests ────────────────────────────────────
class Tests(unittest.TestCase):
    def setUp(self): self.e=Engine(); self.db=DB(":memory:")

    def test_predict_valid(self): self.assertIn(self.e.predict("Karachi",0), range(101))
    def test_predict_bad_zone(self):
        with self.assertRaises(ValueError): self.e.predict("Moon")
    def test_predict_neg_hrs(self):
        with self.assertRaises(ValueError): self.e.predict("Karachi",-1)
    def test_route_valid(self):
        p,c = self.e.route("Lahore","Karachi"); self.assertEqual(p[0],"Lahore"); self.assertGreater(c,0)
    def test_route_same(self):
        p,c = self.e.route("Lahore","Lahore"); self.assertEqual(c,0.0)
    def test_route_bad_src(self):
        with self.assertRaises(ValueError): self.e.route("Mars","Karachi")
    def test_route_bad_dst(self):
        with self.assertRaises(ValueError): self.e.route("Lahore","Mars")
    def test_level_low(self): self.assertEqual(self.e.level(10)[0],"LOW")
    def test_level_critical(self): self.assertEqual(self.e.level(90)[0],"CRITICAL")
    def test_db_log_valid(self): self.assertIsNotNone(self.db.log("Karachi",55))
    def test_db_log_empty(self):
        with self.assertRaises(ValueError): self.db.log("",50)
    def test_db_log_high(self):
        with self.assertRaises(ValueError): self.db.log("Karachi",150)
    def test_db_log_neg(self):
        with self.assertRaises(ValueError): self.db.log("Karachi",-1)
    def test_accident_valid(self): self.assertIsNotNone(self.db.accident("Lahore","crash","high"))
    def test_accident_bad_sev(self):
        with self.assertRaises(ValueError): self.db.accident("Lahore","x","extreme")
    def test_accident_empty_loc(self):
        with self.assertRaises(ValueError): self.db.accident("","x","low")
    def test_recent_records(self): self.db.log("Islamabad",40); self.assertGreater(len(self.db.recent()),0)
    def test_active_accidents(self): self.db.accident("Peshawar","fire","critical"); self.assertGreater(len(self.db.active_accidents()),0)

# ── Main Application ──────────────────────────────
class App(tk.Tk):
    # Node positions on canvas (relative 0-1)
    POS = {
        "Karachi":   (0.15,0.85), "Hyderabad": (0.25,0.72), "Sukkur":    (0.30,0.55),
        "Hub":       (0.08,0.72), "Quetta":    (0.10,0.48), "Multan":    (0.45,0.45),
        "Bahawalpur":(0.52,0.60), "Faisalabad":(0.55,0.30), "Sargodha":  (0.62,0.22),
        "Lahore":    (0.65,0.35), "Islamabad": (0.70,0.18), "Rawalpindi":(0.72,0.26),
        "Peshawar":  (0.78,0.10),
    }

    def __init__(self):
        super().__init__()
        self.title("🇵🇰 Pakistan Traffic Management System")
        self.geometry("1240x760"); self.configure(bg=BG); self.resizable(True,True)
        self.engine = Engine(); self.db = DB(); self._running = True; self._alerted = False
        self._seed()
        self._ui(); self._live()

    def _seed(self):
        for z in Engine.ZONES:
            try: self.db.log(z, self.engine.cong[z])
            except: pass

    def _ui(self):
        # Header
        hdr = tk.Frame(self, bg=BG); hdr.pack(fill="x", padx=14, pady=6)
        tk.Label(hdr, text="🇵🇰  PAKISTAN SMART TRAFFIC SYSTEM",
                 font=("Consolas",17,"bold"), fg=A1, bg=BG).pack(side="left")
        self.clk = tk.Label(hdr, text="", font=FL, fg=DIM, bg=BG); self.clk.pack(side="right")
        self._tick()

        # Alert banner (hidden)
        self.banner = tk.Label(self, text="", font=FL, bg=RED, fg="white", pady=3)

        # Tabs
        style = ttk.Style(self); style.theme_use("default")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=DIM,
                        font=FL, padding=[12,5])
        style.map("TNotebook.Tab", background=[("selected",CARD)], foreground=[("selected",A1)])

        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=8, pady=(0,6))
        tabs = {}
        for name in ["📊 Dashboard","🗺 Map","🚨 Incidents","🧭 Routes","📈 Analytics","🧪 Tests"]:
            f = tk.Frame(nb, bg=BG); nb.add(f, text=f"  {name}  "); tabs[name] = f

        self._dashboard(tabs["📊 Dashboard"])
        self._map(tabs["🗺 Map"])
        self._incidents(tabs["🚨 Incidents"])
        self._routes(tabs["🧭 Routes"])
        self._analytics(tabs["📈 Analytics"])
        self._tests(tabs["🧪 Tests"])
        nb.bind("<<NotebookTabChanged>>", lambda e: self._on_tab(nb))
        self.nb = nb

    def _tick(self):
        self.clk.config(text=datetime.now().strftime("📅 %d %b %Y   🕐 %H:%M:%S"))
        self.after(1000, self._tick)

    # ── Dashboard ──────────────────────────────────
    def _dashboard(self, p):
        tk.Label(p, text="LIVE CONGESTION — MAJOR CITIES", font=FH, fg=A1, bg=BG).pack(anchor="w", padx=12, pady=(8,4))
        grid = tk.Frame(p, bg=BG); grid.pack(fill="both", expand=True, padx=10)
        self.cards = {}
        for i, z in enumerate(Engine.ZONES):
            r, c = divmod(i, 5)
            card = tk.Frame(grid, bg=CARD, padx=10, pady=8,
                            highlightthickness=1, highlightbackground=A2)
            card.grid(row=r, column=c, padx=5, pady=5, sticky="nsew")
            grid.columnconfigure(c, weight=1); grid.rowconfigure(r, weight=1)
            tk.Label(card, text=z, font=("Consolas",10,"bold"), fg=TXT, bg=CARD).pack(anchor="w")
            bb = tk.Frame(card, bg="#1a2030", height=8); bb.pack(fill="x", pady=3)
            bf = tk.Frame(bb, bg=A1, height=8); bf.place(x=0,y=0,relheight=1)
            vl = tk.Label(card, text="--", font=("Consolas",18,"bold"), fg=A1, bg=CARD); vl.pack(anchor="w")
            sl = tk.Label(card, text="LOW", font=FM, fg=A1, bg=CARD); sl.pack(anchor="w")
            pl = tk.Label(card, text="forecast: --", font=FM, fg=DIM, bg=CARD); pl.pack(anchor="w")
            self.cards[z] = (bb, bf, vl, sl, pl)

        btns = tk.Frame(p, bg=BG); btns.pack(fill="x", padx=12, pady=4)
        btn(btns,"🔄 Refresh",self._refresh).pack(side="left")
        btn(btns,"⚡ Spike Traffic",self._spike,A2).pack(side="left",padx=8)

        tk.Label(p, text="ALERTS", font=FH, fg=YLW, bg=BG).pack(anchor="w", padx=12)
        self.alerts_box = scrolledtext.ScrolledText(p, height=4, bg=PANEL, fg=YLW,
                                                    font=FM, state="disabled", bd=0)
        self.alerts_box.pack(fill="x", padx=12, pady=(0,6))

    def _update_cards(self):
        for z, (bb, bf, vl, sl, pl) in self.cards.items():
            v = self.engine.cong[z]; lbl, col = self.engine.level(v)
            vl.config(text=f"{v}%", fg=col); sl.config(text=lbl, fg=col)
            pl.config(text=f"1h: {self.engine.predict(z,1)}%")
            bb.update_idletasks()
            w = max(4, int((bb.winfo_width() or 180) * v/100))
            bf.config(bg=col, width=w)

    def _refresh(self):
        self.engine.update(); self._update_cards(); self._refresh_alerts()
        for z in Engine.ZONES:
            try:
                v = self.engine.cong[z]; lbl, _ = self.engine.level(v)
                self.db.log(z, v, lbl.lower())
                if v >= 75: self.db.alert(f"HIGH at {z}: {v}%","congestion")
            except: pass

    def _spike(self):
        zz = random.sample(Engine.ZONES, 3)
        for z in zz: self.engine.cong[z] = random.randint(80,100)
        self._refresh()
        messagebox.showinfo("Spike","High traffic simulated on:\n"+", ".join(zz))

    def _refresh_alerts(self):
        rows = self.db.get_alerts()
        self.alerts_box.config(state="normal"); self.alerts_box.delete("1.0","end")
        for msg,kind,ts in rows:
            icon = "🚨" if kind=="accident" else "⚠️"
            self.alerts_box.insert("end",f"{icon} [{ts[-8:]}] {msg}\n")
        self.alerts_box.config(state="disabled")

    # ── Map ────────────────────────────────────────
    def _map(self, p):
        tk.Label(p, text="PAKISTAN CITY TRAFFIC MAP", font=FH, fg=A1, bg=BG).pack(anchor="w",padx=12,pady=(8,2))
        tk.Label(p, text="Node size = congestion  |  Edge colour = avg flow", font=FM, fg=DIM, bg=BG).pack(anchor="w",padx=12)
        self.mc = tk.Canvas(p, bg="#0d1117", bd=0, highlightthickness=0)
        self.mc.pack(fill="both",expand=True,padx=10,pady=4)
        btn(p,"🔄 Refresh Map",self._draw_map).pack(anchor="w",padx=12,pady=(0,6))
        self.mc.bind("<Configure>", lambda e: self._draw_map())

    def _draw_map(self):
        c = self.mc; c.delete("all"); c.update_idletasks()
        W, H = c.winfo_width() or 800, c.winfo_height() or 480
        def px(z): rx,ry=self.POS[z]; return int(rx*W), int(ry*H)
        drawn = set()
        for z, nbrs in Engine.GRAPH.items():
            for nb, _ in nbrs:
                e = tuple(sorted([z,nb]))
                if e in drawn: continue
                drawn.add(e)
                avg = (self.engine.cong[z]+self.engine.cong[nb])//2
                _, col = self.engine.level(avg)
                x1,y1=px(z); x2,y2=px(nb)
                c.create_line(x1,y1,x2,y2,fill=col,width=2)
        for z in Engine.ZONES:
            x,y = px(z); v=self.engine.cong[z]; _,col=self.engine.level(v)
            r = 14+v//9
            for i in (3,2,1): c.create_oval(x-r-i*3,y-r-i*3,x+r+i*3,y+r+i*3,fill="",outline=col,width=1)
            c.create_oval(x-r,y-r,x+r,y+r,fill=col,outline="white",width=1)
            if z in self.engine.accident_zones: c.create_text(x,y-r-8,text="⚠",fill=RED,font=("Arial",11,"bold"))
            c.create_text(x,y,text=str(v),fill="white",font=FM)
            c.create_text(x,y+r+11,text=z,fill=TXT,font=FM)
        # Legend
        for i,(t,col) in enumerate([("LOW",A1),("MOD",YLW),("HIGH",A2),("CRIT",RED)]):
            lx=16+i*100; c.create_oval(lx,H-18,lx+10,H-8,fill=col,outline="")
            c.create_text(lx+14,H-13,anchor="w",text=t,fill=col,font=FM)

    # ── Incidents ──────────────────────────────────
    def _incidents(self, p):
        left=tk.Frame(p,bg=BG); left.pack(side="left",fill="both",expand=True,padx=(12,4),pady=8)
        right=tk.Frame(p,bg=BG); right.pack(side="left",fill="both",expand=True,padx=(4,12),pady=8)

        tk.Label(left,text="🚨 REPORT INCIDENT",font=FH,fg=RED,bg=BG).pack(anchor="w",pady=(0,6))
        tk.Label(left,text="City:",font=FL,fg=DIM,bg=BG).pack(anchor="w")
        self.rep_z=tk.StringVar(value=Engine.ZONES[0])
        ttk.Combobox(left,textvariable=self.rep_z,values=Engine.ZONES,state="readonly",font=FL).pack(fill="x",pady=(0,6))
        tk.Label(left,text="Severity:",font=FL,fg=DIM,bg=BG).pack(anchor="w")
        self.rep_s=tk.StringVar(value="medium")
        sf=tk.Frame(left,bg=BG); sf.pack(anchor="w",pady=(0,6))
        for s,c in [("low",A1),("medium",YLW),("high",A2),("critical",RED)]:
            tk.Radiobutton(sf,text=s.upper(),variable=self.rep_s,value=s,fg=c,bg=BG,
                           selectcolor=CARD,activebackground=BG,font=FM).pack(side="left",padx=3)
        tk.Label(left,text="Description:",font=FL,fg=DIM,bg=BG).pack(anchor="w")
        self.rep_d=tk.Text(left,height=4,bg=CARD,fg=TXT,font=FM,insertbackground=A1,bd=0,
                           highlightthickness=1,highlightbackground=A2)
        self.rep_d.pack(fill="x",pady=(0,8))
        rf=tk.Frame(left,bg=BG); rf.pack(fill="x")
        btn(rf,"🚨 Submit",self._submit,RED).pack(side="left")
        btn(rf,"🧹 Clear",lambda:self.rep_d.delete("1.0","end"),DIM).pack(side="left",padx=6)

        tk.Label(left,text="─"*38,fg=A2,bg=BG).pack(pady=6)
        tk.Label(left,text="📡 MANUAL UPDATE",font=FH,fg=A1,bg=BG).pack(anchor="w")
        tk.Label(left,text="City:",font=FL,fg=DIM,bg=BG).pack(anchor="w")
        self.upd_z=tk.StringVar(value=Engine.ZONES[0])
        ttk.Combobox(left,textvariable=self.upd_z,values=Engine.ZONES,state="readonly",font=FL).pack(fill="x",pady=(0,4))
        tk.Label(left,text="Congestion (0–100):",font=FL,fg=DIM,bg=BG).pack(anchor="w")
        self.upd_v=tk.StringVar(value="50")
        tk.Entry(left,textvariable=self.upd_v,bg=CARD,fg=TXT,font=FL,insertbackground=A1).pack(fill="x",pady=(0,6))
        btn(left,"📡 Update",self._manual_update,A1).pack(anchor="w")

        tk.Label(right,text="⚡ ACTIVE INCIDENTS",font=FH,fg=YLW,bg=BG).pack(anchor="w",pady=(0,4))
        cols=("ID","City","Severity","Time")
        s=ttk.Style(); s.configure("Treeview",background=CARD,foreground=TXT,
                                   fieldbackground=CARD,font=FM,rowheight=22)
        s.configure("Treeview.Heading",background=PANEL,foreground=A1,font=FL)
        self.tree=ttk.Treeview(right,columns=cols,show="headings",height=12)
        for c in cols: self.tree.heading(c,text=c); self.tree.column(c,width=90)
        self.tree.pack(fill="both",expand=True)
        bf2=tk.Frame(right,bg=BG); bf2.pack(fill="x",pady=4)
        btn(bf2,"✅ Resolve",self._resolve,A1).pack(side="left")
        btn(bf2,"🔄 Refresh",self._load_incidents,A1).pack(side="left",padx=6)
        self._load_incidents()

    def _submit(self):
        z,s,d = self.rep_z.get(), self.rep_s.get(), self.rep_d.get("1.0","end").strip()
        if not z: return messagebox.showerror("Error","Select a city.")
        try:
            self.db.accident(z, d or "No description", s)
            self.engine.accident_zones.add(z)
            self.engine.cong[z] = min(100, self.engine.cong[z]+25)
            msg=f"ACCIDENT at {z} ({s.upper()})"
            self.db.alert(msg,"accident"); self._show_banner(msg)
            self._load_incidents(); self._update_cards()
            self.rep_d.delete("1.0","end")
            messagebox.showinfo("Done",f"Incident reported at {z}.")
        except ValueError as e: messagebox.showerror("Error",str(e))

    def _resolve(self):
        sel = self.tree.selection()
        if not sel: return messagebox.showwarning("None","Select an incident.")
        for item in sel:
            aid,zone = int(self.tree.item(item,"values")[0]), self.tree.item(item,"values")[1]
            self.db.resolve(aid); self.engine.accident_zones.discard(zone)
        self._load_incidents()

    def _load_incidents(self):
        for r in self.tree.get_children(): self.tree.delete(r)
        for aid,loc,desc,sev,ts in self.db.active_accidents():
            self.tree.insert("","end",values=(aid,loc,sev.upper(),ts[-8:]))

    def _manual_update(self):
        z = self.upd_z.get()
        try:
            v = int(self.upd_v.get())
            if not 0<=v<=100: raise ValueError
        except ValueError: return messagebox.showerror("Error","Enter a number 0–100.")
        try:
            self.engine.cong[z] = v; lbl,_ = self.engine.level(v)
            self.db.log(z, v, lbl.lower()); self._update_cards()
            messagebox.showinfo("Updated",f"{z} → {v}% ({lbl})")
        except Exception as e: messagebox.showerror("Error",str(e))

    # ── Routes ─────────────────────────────────────
    def _routes(self, p):
        tk.Label(p,text="🧭 SMART ROUTE PLANNER",font=FH,fg=A1,bg=BG).pack(anchor="w",padx=12,pady=(8,4))
        rf=tk.Frame(p,bg=BG); rf.pack(fill="x",padx=12,pady=(0,6))
        for label, attr, default in [("From:","rt_src","Lahore"),("To:","rt_dst","Karachi")]:
            tk.Label(rf,text=label,font=FL,fg=DIM,bg=BG).pack(side="left")
            var=tk.StringVar(value=default); setattr(self,attr,var)
            ttk.Combobox(rf,textvariable=var,values=Engine.ZONES,state="readonly",
                         font=FL,width=14).pack(side="left",padx=(2,14))
        btn(rf,"🔍 Best Route",self._find_route,A1).pack(side="left")
        btn(rf,"🔀 Alternatives",self._find_alts,A2).pack(side="left",padx=6)

        self.route_out=scrolledtext.ScrolledText(p,height=22,bg=CARD,fg=TXT,
                                                  font=FM,bd=0,state="disabled")
        self.route_out.pack(fill="both",expand=True,padx=12,pady=(0,8))

    def _show_routes(self, title, routes):
        self.route_out.config(state="normal"); self.route_out.delete("1.0","end")
        self.route_out.insert("end",f"{title}\n{'─'*58}\n\n")
        for i,(path,cost) in enumerate(routes,1):
            avg = sum(self.engine.cong[z] for z in path)//len(path)
            lbl,_ = self.engine.level(avg)
            self.route_out.insert("end",f"  Route {i}: {' → '.join(path)}\n")
            self.route_out.insert("end",f"  Cost: {cost:.2f}   Avg: {avg}% [{lbl}]\n")
            for z in path:
                v=self.engine.cong[z]; bar="█"*(v//10)+"░"*(10-v//10)
                self.route_out.insert("end",f"    {z:<14} {bar} {v:3d}%\n")
            self.route_out.insert("end","\n")
        self.route_out.config(state="disabled")

    def _find_route(self):
        s,d=self.rt_src.get(),self.rt_dst.get()
        if s==d: return messagebox.showinfo("Same","Origin = Destination")
        try: self._show_routes(f"OPTIMAL: {s} → {d}",[self.engine.route(s,d)])
        except Exception as e: messagebox.showerror("Error",str(e))

    def _find_alts(self):
        s,d=self.rt_src.get(),self.rt_dst.get()
        if s==d: return messagebox.showinfo("Same","Origin = Destination")
        try:
            routes=self.engine.alt_routes(s,d,3)
            self._show_routes(f"ALTERNATIVES: {s} → {d}",routes)
        except Exception as e: messagebox.showerror("Error",str(e))

    # ── Analytics ──────────────────────────────────
    def _analytics(self, p):
        tk.Label(p,text="📈 TRAFFIC ANALYTICS",font=FH,fg=A1,bg=BG).pack(anchor="w",padx=12,pady=(8,4))
        bf=tk.Frame(p,bg=BG); bf.pack(fill="x",padx=12,pady=(0,6))
        btn(bf,"📊 Load Stats",self._load_stats,A1).pack(side="left")
        btn(bf,"📋 Recent Records",self._load_recent,A2).pack(side="left",padx=6)
        self.ac=tk.Canvas(p,bg="#0d1117",height=180,bd=0,highlightthickness=0)
        self.ac.pack(fill="x",padx=12,pady=(0,6))
        self.at=scrolledtext.ScrolledText(p,height=14,bg=CARD,fg=TXT,
                                          font=FM,bd=0,state="disabled")
        self.at.pack(fill="both",expand=True,padx=12,pady=(0,8))
        self._load_stats()

    def _load_stats(self):
        rows=self.db.analytics()
        self.at.config(state="normal"); self.at.delete("1.0","end")
        self.at.insert("end",f"{'CITY':<15}{'AVG':>7}{'MAX':>7}{'COUNT':>8}\n"+"─"*38+"\n")
        data=[]
        for loc,avg,mx,cnt in rows:
            self.at.insert("end",f"{loc:<15}{avg:>6.1f}%{mx:>6d}%{cnt:>8d}\n")
            data.append((loc,avg))
        self.at.config(state="disabled")
        self._bar_chart(data)

    def _bar_chart(self, data):
        c=self.ac; c.delete("all"); c.update_idletasks()
        W,H=c.winfo_width() or 800,c.winfo_height() or 180
        if not data: return
        pl,pr,pt,pb=10,10,18,28; bw=(W-pl-pr)/max(len(data),1); mv=max(v for _,v in data) or 1
        for i,(lbl,v) in enumerate(data):
            x1=pl+i*bw+bw*.1; x2=x1+bw*.8
            bh=(v/mv)*(H-pt-pb); y1=H-pb-bh; y2=H-pb
            _,col=self.engine.level(int(v))
            c.create_rectangle(x1,y1,x2,y2,fill=col,outline="")
            c.create_text((x1+x2)/2,y1-4,text=f"{v:.0f}",fill=col,font=FM)
            c.create_text((x1+x2)/2,y2+10,text=lbl[:5],fill=DIM,font=FM)

    def _load_recent(self):
        self.at.config(state="normal"); self.at.delete("1.0","end")
        self.at.insert("end",f"{'CITY':<15}{'CONG':>6}  {'STATUS':<10}{'TIME'}\n"+"─"*50+"\n")
        for loc,cong,ts,status in self.db.recent(30):
            self.at.insert("end",f"{loc:<15}{cong:>5}%  {status:<10}{ts}\n")
        self.at.config(state="disabled")

    # ── Unit Tests ─────────────────────────────────
    def _tests(self, p):
        tk.Label(p,text="🧪 UNIT TEST RUNNER",font=FH,fg=A1,bg=BG).pack(anchor="w",padx=12,pady=(8,4))
        tk.Label(p,text="Tests: prediction · routing · validation · database operations",
                 font=FM,fg=DIM,bg=BG).pack(anchor="w",padx=12)
        bf=tk.Frame(p,bg=BG); bf.pack(fill="x",padx=12,pady=6)
        btn(bf,"▶  Run All Tests",self._run_tests,A1).pack(side="left")
        btn(bf,"🗑 Clear",lambda:self._clear_tests(),DIM).pack(side="left",padx=8)
        self.tsumm=tk.Label(p,text="",font=FH,bg=BG,fg=TXT); self.tsumm.pack(anchor="w",padx=12)
        self.tout=scrolledtext.ScrolledText(p,height=24,bg="#0d1117",fg=TXT,
                                            font=FM,bd=0,state="disabled")
        self.tout.pack(fill="both",expand=True,padx=12,pady=(0,8))
        self.tout.tag_config("ok",foreground=A1); self.tout.tag_config("fail",foreground=RED)
        self.tout.tag_config("head",foreground=A1); self.tout.tag_config("dim",foreground=DIM)

    def _run_tests(self):
        self.tout.config(state="normal"); self.tout.delete("1.0","end")
        suite=unittest.TestLoader().loadTestsFromTestCase(Tests)
        total=suite.countTestCases(); passed=0
        self.tout.insert("end",f"Running {total} tests…\n\n","head")
        self.update()
        for test in suite:
            r=unittest.TestResult(); test.run(r)
            name=test._testMethodName
            if r.wasSuccessful():
                passed+=1; self.tout.insert("end",f"  ✅ PASS  {name}\n","ok")
            else:
                self.tout.insert("end",f"  ❌ FAIL  {name}\n","fail")
                for _,tb in r.failures+r.errors:
                    for ln in tb.strip().split("\n")[-3:]:
                        self.tout.insert("end",f"         {ln}\n","dim")
            self.update()
        failed=total-passed
        self.tout.insert("end",f"\n{'─'*50}\n{passed}/{total} passed  |  {failed} failed\n","head")
        self.tsumm.config(text=f"✅ {passed} Passed   ❌ {failed} Failed",
                          fg=A1 if not failed else RED)
        self.tout.config(state="disabled")

    def _clear_tests(self):
        self.tout.config(state="normal"); self.tout.delete("1.0","end"); self.tout.config(state="disabled")
        self.tsumm.config(text="")

    # ── Helpers ────────────────────────────────────
    def _show_banner(self, msg):
        if self._alerted: return
        self.banner.config(text=f"🚨  {msg}  🚨"); self.banner.pack(fill="x")
        self._alerted=True; self.after(5000, self._hide_banner)

    def _hide_banner(self):
        self.banner.pack_forget(); self._alerted=False

    def _on_tab(self, nb):
        idx=nb.index(nb.select())
        if idx==1: self._draw_map()
        elif idx==4: self._load_stats()

    def _live(self):
        def worker():
            while self._running:
                time.sleep(10)
                if self._running:
                    self.engine.update()
                    self.after(0, self._on_live)
        threading.Thread(target=worker, daemon=True).start()

    def _on_live(self):
        self._update_cards(); self._refresh_alerts()
        for z,v in self.engine.cong.items():
            if v>=80 and not self._alerted:
                self.db.alert(f"HIGH at {z}: {v}%","auto")
                self._show_banner(f"HIGH CONGESTION at {z}: {v}%")
                break
        if self.nb.index(self.nb.select())==1: self._draw_map()

    def destroy(self):
        self._running=False; super().destroy()

if __name__ == "__main__":
    App().mainloop()