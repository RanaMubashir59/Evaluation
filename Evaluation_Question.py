import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import sqlite3, random, time, threading, unittest, heapq
from datetime import datetime
# if we want to call Test from next file instead
# suite=unittest.TestLoader().loadTestsFromTestCase(Tests)
# use this
# from test_cases import Tests
# suite = unittest.TestLoader().loadTestsFromTestCase(Tests)
# ══════════════════════════════════════════════
#  THEME  — white/slate professional light mode
# ══════════════════════════════════════════════
BG      = "#F0F4F8"   # page background
SIDEBAR = "#1E2A3A"   # deep navy sidebar
SB_SEL  = "#2E4057"   # sidebar selected item
SB_HOV  = "#263547"
CARD    = "#FFFFFF"
BORDER  = "#DDE3EA"
TXT     = "#1A2332"
DIM     = "#6B7A8D"
GREEN   = "#00B074"
AMBER   = "#F59E0B"
ORANGE  = "#EF6C00"
RED     = "#E53E3E"
BLUE    = "#3B82F6"
PURPLE  = "#7C3AED"

FT  = ("Segoe UI", 14, "bold")
FH  = ("Segoe UI", 11, "bold")
FL  = ("Segoe UI", 10)
FM  = ("Segoe UI", 9)
FBig= ("Segoe UI", 22, "bold")

def mk_btn(parent, text, cmd, bg=GREEN, fg="white", **kw):
    return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                     font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
                     activebackground=bg, activeforeground=fg,
                     padx=14, pady=7, cursor="hand2", **kw)

def card_frame(parent, **kw):
    return tk.Frame(parent, bg=CARD, bd=0,
                    highlightthickness=1, highlightbackground=BORDER, **kw)

# ══════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════
class DB:
    def __init__(self, path="pk_traffic.db"):
        self.path = path
        self._mem = sqlite3.connect(":memory:", check_same_thread=False) if path==":memory:" else None
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

# ══════════════════════════════════════════════
#  ENGINE
# ══════════════════════════════════════════════
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
            v = self.cong[z] + random.randint(-7,10)
            if z in self.accident_zones: v += random.randint(8,18)
            self.cong[z] = max(0, min(100, v))

    def level(self, v):
        if v < 25: return "LOW", GREEN
        if v < 50: return "MODERATE", AMBER
        if v < 75: return "HIGH", ORANGE
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
        dist={z:float("inf") for z in self.GRAPH}; dist[src]=0.0
        prev={z:None for z in self.GRAPH}; heap=[(0.0,src)]
        while heap:
            d,u=heapq.heappop(heap)
            if d>dist[u]: continue
            for v,w in self.GRAPH[u]:
                nd=d+w*(1+self.cong.get(v,0)/100)
                if nd<dist[v]: dist[v]=nd; prev[v]=u; heapq.heappush(heap,(nd,v))
        path,n=[],dst
        while n: path.append(n); n=prev[n]
        path.reverse()
        if path[0]!=src: raise RuntimeError("No path found")
        return path, round(dist[dst],2)

    def alt_routes(self, src, dst, n=3):
        saved=dict(self.cong); routes=[]; seen=set()
        for _ in range(n*4):
            try:
                p,c=self.route(src,dst); k=tuple(p)
                if k not in seen:
                    seen.add(k); routes.append((p,c))
                    if len(routes)==n: break
                for z in p[1:-1]: self.cong[z]=min(100,self.cong[z]+30)
            except: break
        self.cong=saved; return routes

# ══════════════════════════════════════════════
#  UNIT TESTS
# ══════════════════════════════════════════════
class Tests(unittest.TestCase):
    def setUp(self): self.e=Engine(); self.db=DB(":memory:")
    def test_predict_valid(self): self.assertIn(self.e.predict("Karachi",0), range(101))
    def test_predict_bad_zone(self):
        with self.assertRaises(ValueError): self.e.predict("Moon")
    def test_predict_neg_hrs(self):
        with self.assertRaises(ValueError): self.e.predict("Karachi",-1)
    def test_route_valid(self):
        p,c=self.e.route("Lahore","Karachi"); self.assertEqual(p[0],"Lahore"); self.assertGreater(c,0)
    def test_route_same(self):
        p,c=self.e.route("Lahore","Lahore"); self.assertEqual(c,0.0)
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

# ══════════════════════════════════════════════
#  APPLICATION
# ══════════════════════════════════════════════
class App(tk.Tk):
    NAV = [
        ("📊","Dashboard"),("🗺","Map"),("🚨","Incidents"),
        ("🧭","Routes"),("📈","Analytics"),("🧪","Tests"),
    ]
    POS = {
        "Karachi":   (0.15,0.88), "Hyderabad":(0.26,0.75), "Sukkur":    (0.32,0.58),
        "Hub":       (0.07,0.76), "Quetta":   (0.09,0.50), "Multan":    (0.46,0.47),
        "Bahawalpur":(0.53,0.62), "Faisalabad":(0.56,0.32),"Sargodha":  (0.63,0.22),
        "Lahore":    (0.66,0.36), "Islamabad": (0.71,0.18),"Rawalpindi":(0.73,0.27),
        "Peshawar":  (0.80,0.10),
    }

    def __init__(self):
        super().__init__()
        self.title("Pakistan Traffic Management System")
        self.geometry("1280x780"); self.configure(bg=BG); self.resizable(True,True)
        self.engine=Engine(); self.db=DB(); self._running=True; self._alerted=False
        self._active_tab=0
        for z in Engine.ZONES:
            try: self.db.log(z, self.engine.cong[z])
            except: pass
        self._build(); self._live()

    # ── Shell ──────────────────────────────────
    def _build(self):
        # Sidebar
        self.sidebar = tk.Frame(self, bg=SIDEBAR, width=200)
        self.sidebar.pack(side="left", fill="y"); self.sidebar.pack_propagate(False)

        # Logo area
        logo = tk.Frame(self.sidebar, bg=SIDEBAR, pady=20)
        logo.pack(fill="x")
        tk.Label(logo, text="🚦", font=("Segoe UI",28), bg=SIDEBAR).pack()
        tk.Label(logo, text="PK TRAFFIC", font=("Segoe UI",11,"bold"), fg="white", bg=SIDEBAR).pack()
        tk.Label(logo, text="Management System", font=("Segoe UI",8), fg="#8899AA", bg=SIDEBAR).pack()

        tk.Frame(self.sidebar, bg="#2E3F52", height=1).pack(fill="x", padx=16, pady=8)

        # Nav buttons
        self.nav_btns = []
        for icon, label in self.NAV:
            f = tk.Frame(self.sidebar, bg=SIDEBAR, cursor="hand2")
            f.pack(fill="x", padx=8, pady=2)
            lbl = tk.Label(f, text=f"  {icon}  {label}", font=("Segoe UI",10),
                           fg="#B0BEC5", bg=SIDEBAR, anchor="w", pady=8, padx=8)
            lbl.pack(fill="x")
            idx = len(self.nav_btns)
            for w in (f, lbl):
                w.bind("<Button-1>", lambda e, i=idx: self._switch(i))
                w.bind("<Enter>",    lambda e, fw=f, lw=lbl: (fw.config(bg=SB_HOV), lw.config(bg=SB_HOV)))
                w.bind("<Leave>",    lambda e, fw=f, lw=lbl, i=idx: self._nav_leave(fw,lw,i))
            self.nav_btns.append((f, lbl))

        # Clock at bottom of sidebar
        tk.Frame(self.sidebar, bg="#2E3F52", height=1).pack(fill="x", padx=16, pady=(20,8))
        self.clk = tk.Label(self.sidebar, text="", font=("Segoe UI",8), fg="#607080", bg=SIDEBAR)
        self.clk.pack(); self._tick()

        # Main content area
        self.content = tk.Frame(self, bg=BG); self.content.pack(fill="both", expand=True)

        # Top bar
        topbar = tk.Frame(self.content, bg=CARD, pady=10,
                          highlightthickness=1, highlightbackground=BORDER)
        topbar.pack(fill="x", padx=0, pady=0)
        self.page_title = tk.Label(topbar, text="Dashboard", font=FT, fg=TXT, bg=CARD)
        self.page_title.pack(side="left", padx=20)
        self.banner = tk.Label(topbar, text="", font=("Segoe UI",9,"bold"),
                               bg=RED, fg="white", padx=12, pady=4)

        # Page container
        self.pages_frame = tk.Frame(self.content, bg=BG)
        self.pages_frame.pack(fill="both", expand=True, padx=16, pady=12)

        # Build pages
        self.pages = []
        builders = [self._pg_dashboard, self._pg_map, self._pg_incidents,
                    self._pg_routes, self._pg_analytics, self._pg_tests]
        for build in builders:
            pg = tk.Frame(self.pages_frame, bg=BG)
            build(pg); self.pages.append(pg)

        self._switch(0)

    def _switch(self, idx):
        self._active_tab = idx
        for i,(f,lbl) in enumerate(self.nav_btns):
            if i==idx:
                f.config(bg=SB_SEL); lbl.config(bg=SB_SEL, fg="white")
            else:
                f.config(bg=SIDEBAR); lbl.config(bg=SIDEBAR, fg="#B0BEC5")
        for i,pg in enumerate(self.pages):
            if i==idx: pg.pack(fill="both",expand=True)
            else: pg.pack_forget()
        self.page_title.config(text=self.NAV[idx][1])
        if idx==1: self._draw_map()
        if idx==4: self._load_stats()

    def _nav_leave(self, f, lbl, i):
        if i != self._active_tab:
            f.config(bg=SIDEBAR); lbl.config(bg=SIDEBAR)

    def _tick(self):
        self.clk.config(text=datetime.now().strftime("%d %b %Y\n%H:%M:%S"))
        self.after(1000, self._tick)

    # ── Stat card helper ──────────────────────
    def _stat_card(self, parent, title, value, sub, color=GREEN, col=0, row=0):
        c = card_frame(parent, padx=16, pady=14)
        c.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        tk.Label(c, text=title, font=FM, fg=DIM, bg=CARD).pack(anchor="w")
        tk.Label(c, text=value, font=FBig, fg=color, bg=CARD).pack(anchor="w")
        tk.Label(c, text=sub, font=FM, fg=DIM, bg=CARD).pack(anchor="w")
        return c

    # ══════════════════════════════════════════
    #  DASHBOARD PAGE
    # ══════════════════════════════════════════
    def _pg_dashboard(self, p):
        # Top KPI row
        kpi = tk.Frame(p, bg=BG); kpi.pack(fill="x", pady=(0,10))
        for c in range(4): kpi.columnconfigure(c, weight=1)
        self._stat_card(kpi,"Total Zones","13","Cities monitored", BLUE, 0,0)
        self.kpi_avg  = self._stat_card(kpi,"Avg Congestion","--","Across all zones", GREEN,1,0)
        self.kpi_crit = self._stat_card(kpi,"Critical Zones","0","Congestion > 75%", RED,  2,0)
        self.kpi_inc  = self._stat_card(kpi,"Active Incidents","0","Open reports", AMBER, 3,0)

        # Zone grid
        mid = tk.Frame(p, bg=BG); mid.pack(fill="both", expand=True)
        left = tk.Frame(mid, bg=BG); left.pack(side="left", fill="both", expand=True)
        right_panel = tk.Frame(mid, bg=BG, width=260); right_panel.pack(side="right", fill="y", padx=(8,0))
        right_panel.pack_propagate(False)

        # Zone cards
        zf = card_frame(left); zf.pack(fill="both", expand=True, pady=(0,8))
        tk.Label(zf, text="CITY CONGESTION LEVELS", font=("Segoe UI",10,"bold"),
                 fg=DIM, bg=CARD).pack(anchor="w", padx=14, pady=(10,6))
        grid = tk.Frame(zf, bg=CARD); grid.pack(fill="both", expand=True, padx=10, pady=(0,10))
        self.zone_widgets = {}
        for i, z in enumerate(Engine.ZONES):
            r, c = divmod(i, 5); grid.columnconfigure(c, weight=1)
            zc = tk.Frame(grid, bg=BG, padx=10, pady=8,
                          highlightthickness=1, highlightbackground=BORDER)
            zc.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")
            tk.Label(zc, text=z, font=("Segoe UI",9,"bold"), fg=TXT, bg=BG).pack(anchor="w")
            # bar track
            track = tk.Frame(zc, bg=BORDER, height=6); track.pack(fill="x", pady=3)
            fill  = tk.Frame(track, bg=GREEN, height=6); fill.place(x=0,y=0,relheight=1)
            pct   = tk.Label(zc, text="--", font=("Segoe UI",16,"bold"), fg=GREEN, bg=BG)
            pct.pack(anchor="w")
            tag   = tk.Label(zc, text="LOW", font=("Segoe UI",8), fg=DIM, bg=BG)
            tag.pack(anchor="w")
            self.zone_widgets[z] = (track, fill, pct, tag)

        # Button row
        bf = tk.Frame(left, bg=BG); bf.pack(fill="x", pady=(0,4))
        mk_btn(bf,"↻  Refresh",self._refresh, GREEN).pack(side="left")
        mk_btn(bf,"⚡ Spike Traffic",self._spike, ORANGE).pack(side="left",padx=8)

        # Right: alerts feed
        af = card_frame(right_panel); af.pack(fill="both", expand=True)
        tk.Label(af, text="LIVE ALERTS", font=("Segoe UI",10,"bold"), fg=DIM, bg=CARD).pack(anchor="w",padx=12,pady=(10,4))
        self.alerts_box = scrolledtext.ScrolledText(af, bg=BG, fg=TXT, font=("Segoe UI",9),
                                                    state="disabled", bd=0, wrap="word")
        self.alerts_box.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.alerts_box.tag_config("red",  foreground=RED)
        self.alerts_box.tag_config("amb",  foreground=AMBER)
        self.alerts_box.tag_config("dim",  foreground=DIM)

    def _update_cards(self):
        vals = list(self.engine.cong.values())
        avg  = sum(vals)//len(vals)
        crit = sum(1 for v in vals if v>=75)
        inc  = len(self.db.active_accidents())
        # update KPI labels (dig into card children)
        for card_frame_widget, val, col in [
            (self.kpi_avg,  f"{avg}%", GREEN if avg<50 else ORANGE),
            (self.kpi_crit, str(crit), RED if crit>0 else GREEN),
            (self.kpi_inc,  str(inc),  AMBER if inc>0 else GREEN),
        ]:
            widgets = card_frame_widget.winfo_children()
            if len(widgets)>=2: widgets[1].config(text=val, fg=col)

        for z,(track,fill,pct,tag) in self.zone_widgets.items():
            v=self.engine.cong[z]; lbl,col=self.engine.level(v)
            pct.config(text=f"{v}%",fg=col); tag.config(text=lbl,fg=col)
            track.update_idletasks()
            w=max(3,int((track.winfo_width() or 160)*v/100))
            fill.config(bg=col,width=w)

    def _refresh(self):
        self.engine.update(); self._update_cards(); self._refresh_alerts()
        for z in Engine.ZONES:
            try:
                v=self.engine.cong[z]; lbl,_=self.engine.level(v)
                self.db.log(z,v,lbl.lower())
                if v>=75: self.db.alert(f"HIGH congestion at {z}: {v}%","congestion")
            except: pass

    def _spike(self):
        zz=random.sample(Engine.ZONES,3)
        for z in zz: self.engine.cong[z]=random.randint(80,100)
        self._refresh()
        messagebox.showinfo("Simulated",f"High traffic on:\n"+"\n".join(zz))

    def _refresh_alerts(self):
        self.alerts_box.config(state="normal"); self.alerts_box.delete("1.0","end")
        for msg,kind,ts in self.db.get_alerts(20):
            icon = "🚨 " if kind=="accident" else "⚠ "
            tag  = "red" if kind=="accident" else "amb"
            self.alerts_box.insert("end", icon+msg+"\n", tag)
            self.alerts_box.insert("end", f"  {ts[-8:]}\n", "dim")
        self.alerts_box.config(state="disabled")

    # ══════════════════════════════════════════
    #  MAP PAGE
    # ══════════════════════════════════════════
    def _pg_map(self, p):
        top=tk.Frame(p,bg=BG); top.pack(fill="x",pady=(0,8))
        tk.Label(top,text="Live congestion shown by node colour and size.",
                 font=FM,fg=DIM,bg=BG).pack(side="left")
        mk_btn(top,"↻ Refresh",self._draw_map,GREEN).pack(side="right")
        cf = card_frame(p); cf.pack(fill="both",expand=True)
        self.mc = tk.Canvas(cf, bg="#F8FAFC", bd=0, highlightthickness=0)
        self.mc.pack(fill="both",expand=True,padx=2,pady=2)
        self.mc.bind("<Configure>", lambda e: self._draw_map())

    def _draw_map(self):
        c=self.mc; c.delete("all"); c.update_idletasks()
        W,H=c.winfo_width() or 800, c.winfo_height() or 480
        def px(z): rx,ry=self.POS[z]; return int(rx*W),int(ry*H)
        drawn=set()
        for z,nbrs in Engine.GRAPH.items():
            for nb,_ in nbrs:
                e=tuple(sorted([z,nb]))
                if e in drawn: continue
                drawn.add(e)
                avg=(self.engine.cong[z]+self.engine.cong[nb])//2
                _,col=self.engine.level(avg)
                x1,y1=px(z); x2,y2=px(nb)
                c.create_line(x1,y1,x2,y2,fill=col,width=3,smooth=True)
        for z in Engine.ZONES:
            x,y=px(z); v=self.engine.cong[z]; lbl,col=self.engine.level(v)
            r=18+v//9
            # shadow
            c.create_oval(x-r+2,y-r+2,x+r+2,y+r+2,fill="#DDDDDD",outline="")
            c.create_oval(x-r,y-r,x+r,y+r,fill=col,outline="white",width=2)
            if z in self.engine.accident_zones:
                c.create_text(x,y-r-10,text="⚠",fill=RED,font=("Segoe UI",12,"bold"))
            c.create_text(x,y,text=f"{v}",fill="white",font=("Segoe UI",9,"bold"))
            # label box
            tw=len(z)*5+10
            c.create_rectangle(x-tw//2,y+r+2,x+tw//2,y+r+16,fill="white",outline=BORDER)
            c.create_text(x,y+r+9,text=z,fill=TXT,font=("Segoe UI",7,"bold"))
        # legend
        for i,(t,col) in enumerate([("LOW",GREEN),("MODERATE",AMBER),("HIGH",ORANGE),("CRITICAL",RED)]):
            lx=14+i*120
            c.create_oval(lx,H-18,lx+12,H-6,fill=col,outline="")
            c.create_text(lx+16,H-12,anchor="w",text=t,fill=col,font=("Segoe UI",8,"bold"))

    # ══════════════════════════════════════════
    #  INCIDENTS PAGE
    # ══════════════════════════════════════════
    def _pg_incidents(self, p):
        left=tk.Frame(p,bg=BG); left.pack(side="left",fill="both",expand=True,padx=(0,8))
        right=tk.Frame(p,bg=BG,width=380); right.pack(side="right",fill="both"); right.pack_propagate(False)

        # Report card
        rc=card_frame(left); rc.pack(fill="x",pady=(0,8))
        tk.Label(rc,text="Report New Incident",font=FH,fg=TXT,bg=CARD).pack(anchor="w",padx=16,pady=(12,8))

        row1=tk.Frame(rc,bg=CARD); row1.pack(fill="x",padx=16,pady=(0,8))
        tk.Label(row1,text="City",font=FM,fg=DIM,bg=CARD).grid(row=0,column=0,sticky="w")
        tk.Label(row1,text="Severity",font=FM,fg=DIM,bg=CARD).grid(row=0,column=1,sticky="w",padx=(20,0))
        self.rep_z=tk.StringVar(value=Engine.ZONES[0])
        ttk.Combobox(row1,textvariable=self.rep_z,values=Engine.ZONES,state="readonly",
                     font=FL,width=16).grid(row=1,column=0,sticky="w")
        self.rep_s=tk.StringVar(value="medium")
        sf=tk.Frame(row1,bg=CARD); sf.grid(row=1,column=1,sticky="w",padx=(20,0))
        for s,c_ in [("low",GREEN),("medium",AMBER),("high",ORANGE),("critical",RED)]:
            tk.Radiobutton(sf,text=s.capitalize(),variable=self.rep_s,value=s,fg=c_,
                           bg=CARD,selectcolor=BG,activebackground=CARD,
                           font=("Segoe UI",9)).pack(side="left",padx=4)

        tk.Label(rc,text="Description",font=FM,fg=DIM,bg=CARD).pack(anchor="w",padx=16)
        self.rep_d=tk.Text(rc,height=3,bg=BG,fg=TXT,font=FL,bd=0,
                           highlightthickness=1,highlightbackground=BORDER,
                           insertbackground=GREEN,padx=8,pady=6)
        self.rep_d.pack(fill="x",padx=16,pady=(4,10))
        bf=tk.Frame(rc,bg=CARD); bf.pack(fill="x",padx=16,pady=(0,14))
        mk_btn(bf,"Submit Report",self._submit,RED).pack(side="left")
        mk_btn(bf,"Clear",lambda:self.rep_d.delete("1.0","end"),DIM,"#444").pack(side="left",padx=8)

        # Manual update card
        mc2=card_frame(left); mc2.pack(fill="x")
        tk.Label(mc2,text="Manual Traffic Update",font=FH,fg=TXT,bg=CARD).pack(anchor="w",padx=16,pady=(12,6))
        row2=tk.Frame(mc2,bg=CARD); row2.pack(fill="x",padx=16,pady=(0,12))
        tk.Label(row2,text="City",font=FM,fg=DIM,bg=CARD).grid(row=0,column=0,sticky="w")
        tk.Label(row2,text="Congestion %",font=FM,fg=DIM,bg=CARD).grid(row=0,column=1,sticky="w",padx=(20,0))
        self.upd_z=tk.StringVar(value=Engine.ZONES[0])
        ttk.Combobox(row2,textvariable=self.upd_z,values=Engine.ZONES,state="readonly",
                     font=FL,width=16).grid(row=1,column=0,sticky="w")
        self.upd_v=tk.StringVar(value="50")
        tk.Entry(row2,textvariable=self.upd_v,bg=BG,fg=TXT,font=FL,
                 highlightthickness=1,highlightbackground=BORDER,bd=0,
                 width=10,insertbackground=GREEN).grid(row=1,column=1,sticky="w",padx=(20,0))
        mk_btn(row2,"Update",self._manual_update,BLUE).grid(row=1,column=2,padx=(12,0))

        # Active incidents table
        ic=card_frame(right); ic.pack(fill="both",expand=True)
        tk.Label(ic,text="Active Incidents",font=FH,fg=TXT,bg=CARD).pack(anchor="w",padx=14,pady=(12,6))
        style=ttk.Style()
        style.configure("Light.Treeview",background=BG,foreground=TXT,
                        fieldbackground=BG,font=("Segoe UI",9),rowheight=26,borderwidth=0)
        style.configure("Light.Treeview.Heading",background=CARD,foreground=DIM,
                        font=("Segoe UI",9,"bold"),relief="flat")
        style.map("Light.Treeview",background=[("selected","#E3F2FD")])
        cols=("ID","City","Severity","Time")
        self.tree=ttk.Treeview(ic,columns=cols,show="headings",height=14,style="Light.Treeview")
        for c_,w in zip(cols,(40,110,90,80)):
            self.tree.heading(c_,text=c_); self.tree.column(c_,width=w,anchor="center")
        self.tree.pack(fill="both",expand=True,padx=8)
        tb=tk.Frame(ic,bg=CARD); tb.pack(fill="x",padx=12,pady=8)
        mk_btn(tb,"✓ Resolve",self._resolve,GREEN).pack(side="left")
        mk_btn(tb,"↻ Refresh",self._load_incidents,BLUE).pack(side="left",padx=6)
        self._load_incidents()

    def _submit(self):
        z,s,d=self.rep_z.get(),self.rep_s.get(),self.rep_d.get("1.0","end").strip()
        if not z: return messagebox.showerror("Error","Select a city.")
        try:
            self.db.accident(z,d or "No description",s)
            self.engine.accident_zones.add(z)
            self.engine.cong[z]=min(100,self.engine.cong[z]+25)
            msg=f"ACCIDENT at {z} ({s.upper()})"
            self.db.alert(msg,"accident"); self._show_banner(msg)
            self._load_incidents(); self._update_cards()
            self.rep_d.delete("1.0","end")
            messagebox.showinfo("Submitted",f"Incident logged for {z}.")
        except ValueError as e: messagebox.showerror("Validation",str(e))

    def _resolve(self):
        sel=self.tree.selection()
        if not sel: return messagebox.showwarning("None","Select an incident first.")
        for item in sel:
            aid,zone=int(self.tree.item(item,"values")[0]),self.tree.item(item,"values")[1]
            self.db.resolve(aid); self.engine.accident_zones.discard(zone)
        self._load_incidents()

    def _load_incidents(self):
        for r in self.tree.get_children(): self.tree.delete(r)
        for aid,loc,desc,sev,ts in self.db.active_accidents():
            self.tree.insert("","end",values=(aid,loc,sev.upper(),ts[-8:]))

    def _manual_update(self):
        z=self.upd_z.get()
        try:
            v=int(self.upd_v.get())
            if not 0<=v<=100: raise ValueError
        except ValueError: return messagebox.showerror("Error","Enter a number 0–100.")
        try:
            self.engine.cong[z]=v; lbl,_=self.engine.level(v)
            self.db.log(z,v,lbl.lower()); self._update_cards()
            messagebox.showinfo("Updated",f"{z} set to {v}% ({lbl})")
        except Exception as e: messagebox.showerror("Error",str(e))

    # ══════════════════════════════════════════
    #  ROUTES PAGE
    # ══════════════════════════════════════════
    def _pg_routes(self, p):
        ctrl=card_frame(p); ctrl.pack(fill="x",pady=(0,10))
        inner=tk.Frame(ctrl,bg=CARD); inner.pack(fill="x",padx=16,pady=12)
        tk.Label(inner,text="From",font=FM,fg=DIM,bg=CARD).grid(row=0,column=0,sticky="w")
        tk.Label(inner,text="To",font=FM,fg=DIM,bg=CARD).grid(row=0,column=1,sticky="w",padx=(20,0))
        self.rt_s=tk.StringVar(value="Lahore"); self.rt_d=tk.StringVar(value="Karachi")
        ttk.Combobox(inner,textvariable=self.rt_s,values=Engine.ZONES,state="readonly",
                     font=FL,width=16).grid(row=1,column=0)
        ttk.Combobox(inner,textvariable=self.rt_d,values=Engine.ZONES,state="readonly",
                     font=FL,width=16).grid(row=1,column=1,padx=(20,0))
        mk_btn(inner,"Find Best Route",self._find_route,GREEN).grid(row=1,column=2,padx=(20,0))
        mk_btn(inner,"Show Alternatives",self._find_alts,BLUE).grid(row=1,column=3,padx=(8,0))

        rc=card_frame(p); rc.pack(fill="both",expand=True)
        tk.Label(rc,text="Route Results",font=FH,fg=TXT,bg=CARD).pack(anchor="w",padx=16,pady=(12,4))
        self.route_out=scrolledtext.ScrolledText(rc,bg=BG,fg=TXT,font=("Segoe UI",10),
                                                  bd=0,state="disabled",padx=12,pady=8)
        self.route_out.pack(fill="both",expand=True,padx=8,pady=(0,8))
        self.route_out.tag_config("head", font=("Segoe UI",11,"bold"), foreground=BLUE)
        self.route_out.tag_config("city", foreground=TXT)
        self.route_out.tag_config("ok",   foreground=GREEN)
        self.route_out.tag_config("warn", foreground=ORANGE)
        self.route_out.tag_config("crit", foreground=RED)

    def _show_routes(self, title, routes):
        self.route_out.config(state="normal"); self.route_out.delete("1.0","end")
        self.route_out.insert("end",f"{title}\n\n","head")
        for i,(path,cost) in enumerate(routes,1):
            avg=sum(self.engine.cong[z] for z in path)//len(path)
            lbl,_=self.engine.level(avg)
            tag="ok" if avg<50 else ("warn" if avg<75 else "crit")
            self.route_out.insert("end",f"  Route {i}:  {'  →  '.join(path)}\n",tag)
            self.route_out.insert("end",f"  Cost Score: {cost:.2f}   Avg Load: {avg}% [{lbl}]\n","city")
            self.route_out.insert("end","  "+("─"*52)+"\n","city")
            for z in path:
                v=self.engine.cong[z]; bar="▓"*(v//10)+"░"*(10-v//10)
                tg="ok" if v<50 else ("warn" if v<75 else "crit")
                self.route_out.insert("end",f"    {z:<16} {bar}  {v:3d}%\n",tg)
            self.route_out.insert("end","\n")
        self.route_out.config(state="disabled")

    def _find_route(self):
        s,d=self.rt_s.get(),self.rt_d.get()
        if s==d: return messagebox.showinfo("Same","Origin equals destination.")
        try: self._show_routes(f"Optimal Route: {s}  →  {d}",[self.engine.route(s,d)])
        except Exception as e: messagebox.showerror("Error",str(e))

    def _find_alts(self):
        s,d=self.rt_s.get(),self.rt_d.get()
        if s==d: return messagebox.showinfo("Same","Origin equals destination.")
        try: self._show_routes(f"Alternative Routes: {s}  →  {d}",self.engine.alt_routes(s,d,3))
        except Exception as e: messagebox.showerror("Error",str(e))

    # ══════════════════════════════════════════
    #  ANALYTICS PAGE
    # ══════════════════════════════════════════
    def _pg_analytics(self, p):
        top=tk.Frame(p,bg=BG); top.pack(fill="x",pady=(0,8))
        mk_btn(top,"Load Statistics",self._load_stats,GREEN).pack(side="left")
        mk_btn(top,"Recent Records",self._load_recent,BLUE).pack(side="left",padx=8)

        cc=card_frame(p); cc.pack(fill="x",pady=(0,8))
        tk.Label(cc,text="Average Congestion by City",font=FH,fg=TXT,bg=CARD).pack(anchor="w",padx=14,pady=(10,4))
        self.ac=tk.Canvas(cc,bg=CARD,height=180,bd=0,highlightthickness=0)
        self.ac.pack(fill="x",padx=8,pady=(0,10))

        tc=card_frame(p); tc.pack(fill="both",expand=True)
        tk.Label(tc,text="Detailed Statistics",font=FH,fg=TXT,bg=CARD).pack(anchor="w",padx=14,pady=(10,4))
        self.at=scrolledtext.ScrolledText(tc,bg=BG,fg=TXT,font=("Courier New",9),
                                          bd=0,state="disabled",padx=12,pady=6)
        self.at.pack(fill="both",expand=True,padx=8,pady=(0,8))

    def _load_stats(self):
        rows=self.db.analytics()
        self.at.config(state="normal"); self.at.delete("1.0","end")
        self.at.insert("end",f"{'CITY':<16}{'AVG':>8}{'PEAK':>8}{'RECORDS':>10}\n"+"─"*44+"\n")
        data=[]
        for loc,avg,mx,cnt in rows:
            self.at.insert("end",f"{loc:<16}{avg:>7.1f}%{mx:>7d}%{cnt:>10d}\n")
            data.append((loc,avg))
        self.at.config(state="disabled"); self._bar_chart(data)

    def _bar_chart(self, data):
        c=self.ac; c.delete("all"); c.update_idletasks()
        W,H=c.winfo_width() or 800,c.winfo_height() or 180
        if not data: return
        pl,pr,pt,pb=12,12,20,30; bw=(W-pl-pr)/max(len(data),1); mv=max(v for _,v in data) or 1
        for i,(lbl,v) in enumerate(data):
            x1=pl+i*bw+bw*.15; x2=x1+bw*.7
            bh=(v/mv)*(H-pt-pb); y1=H-pb-bh; y2=H-pb
            _,col=self.engine.level(int(v))
            # bar shadow
            c.create_rectangle(x1+2,y1+2,x2+2,y2,fill="#E0E0E0",outline="")
            c.create_rectangle(x1,y1,x2,y2,fill=col,outline="")
            c.create_text((x1+x2)/2,y1-6,text=f"{v:.0f}",fill=col,font=("Segoe UI",8,"bold"))
            c.create_text((x1+x2)/2,y2+12,text=lbl[:5],fill=DIM,font=("Segoe UI",7))

    def _load_recent(self):
        self.at.config(state="normal"); self.at.delete("1.0","end")
        self.at.insert("end",f"{'CITY':<16}{'CONG':>6}  {'STATUS':<12}{'TIMESTAMP'}\n"+"─"*56+"\n")
        for loc,cong,ts,status in self.db.recent(30):
            self.at.insert("end",f"{loc:<16}{cong:>5}%  {status:<12}{ts}\n")
        self.at.config(state="disabled")

    # ══════════════════════════════════════════
    #  TESTS PAGE
    # ══════════════════════════════════════════
    def _pg_tests(self, p):
        hc=card_frame(p); hc.pack(fill="x",pady=(0,10))
        tk.Label(hc,text="Unit Test Runner",font=FT,fg=TXT,bg=CARD).pack(anchor="w",padx=16,pady=(14,2))
        tk.Label(hc,text="Validates: prediction accuracy · route optimisation · input validation · database operations",
                 font=FM,fg=DIM,bg=CARD).pack(anchor="w",padx=16,pady=(0,10))
        bf=tk.Frame(hc,bg=CARD); bf.pack(fill="x",padx=16,pady=(0,14))
        mk_btn(bf,"▶  Run All Tests",self._run_tests,GREEN).pack(side="left")
        mk_btn(bf,"Clear",self._clear_tests,DIM,"#444").pack(side="left",padx=8)
        self.tsumm=tk.Label(hc,text="",font=FH,bg=CARD,fg=TXT)
        self.tsumm.pack(anchor="w",padx=16,pady=(0,10))

        tc=card_frame(p); tc.pack(fill="both",expand=True)
        self.tout=scrolledtext.ScrolledText(tc,bg=BG,fg=TXT,font=("Courier New",9),
                                            bd=0,state="disabled",padx=12,pady=8)
        self.tout.pack(fill="both",expand=True,padx=8,pady=8)
        self.tout.tag_config("ok",  foreground=GREEN,  font=("Courier New",9,"bold"))
        self.tout.tag_config("fail",foreground=RED,    font=("Courier New",9,"bold"))
        self.tout.tag_config("head",foreground=BLUE,   font=("Courier New",10,"bold"))
        self.tout.tag_config("dim", foreground=DIM)

    def _run_tests(self):
        self.tout.config(state="normal"); self.tout.delete("1.0","end")
        suite=unittest.TestLoader().loadTestsFromTestCase(Tests)
        total=suite.countTestCases(); passed=0
        self.tout.insert("end",f"Running {total} unit tests…\n\n","head"); self.update()
        for test in suite:
            r=unittest.TestResult(); test.run(r)
            if r.wasSuccessful():
                passed+=1; self.tout.insert("end",f"  ✅  PASS   {test._testMethodName}\n","ok")
            else:
                self.tout.insert("end",f"  ❌  FAIL   {test._testMethodName}\n","fail")
                for _,tb in r.failures+r.errors:
                    for ln in tb.strip().split("\n")[-3:]:
                        self.tout.insert("end",f"              {ln}\n","dim")
            self.update()
        failed=total-passed
        self.tout.insert("end",f"\n{'─'*52}\nResult: {passed} passed,  {failed} failed  (total {total})\n","head")
        self.tsumm.config(text=f"✅ {passed} Passed   ❌ {failed} Failed   ({total} total)",
                          fg=GREEN if not failed else RED)
        self.tout.config(state="disabled")

    def _clear_tests(self):
        self.tout.config(state="normal"); self.tout.delete("1.0","end"); self.tout.config(state="disabled")
        self.tsumm.config(text="")

    # ── Alert banner ───────────────────────────
    def _show_banner(self, msg):
        if self._alerted: return
        self.banner.config(text=f"  🚨  {msg}")
        self.banner.pack(side="right", padx=12)
        self._alerted=True; self.after(5000,self._hide_banner)

    def _hide_banner(self):
        self.banner.pack_forget(); self._alerted=False

    # ── Live thread ────────────────────────────
    def _live(self):
        def worker():
            while self._running:
                time.sleep(10)
                if self._running:
                    self.engine.update()
                    self.after(0,self._on_live)
        threading.Thread(target=worker,daemon=True).start()

    def _on_live(self):
        if self._active_tab==0: self._update_cards(); self._refresh_alerts()
        if self._active_tab==1: self._draw_map()
        for z,v in self.engine.cong.items():
            if v>=80 and not self._alerted:
                self.db.alert(f"HIGH at {z}: {v}%","auto")
                self._show_banner(f"HIGH CONGESTION at {z}: {v}%")
                break

    def destroy(self):
        self._running=False; super().destroy()

if __name__=="__main__":
    App().mainloop()