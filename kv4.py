"""
Kereznikov V4 — fullscreen support
ESP: pygame overlay в отдельном потоке (без tkinter overlay)
AIM: рабочие оффсеты из подтверждённого источника
"""
import struct, math, threading, time, os
import pymem, pymem.process
import customtkinter as ctk

# ── ОФФСЕТЫ (hw.dll) ─────────────────────────────────────
VEC3        = 0x658840    # позиция локального игрока
VIEWANGLES  = 0x1230274   # pitch, yaw, roll
VIEW_MATRIX = 0xEC9780    # 16 float матрица
ENTITY      = 0x120461C   # база entity list
ESIZE       = 592
EPOS_X      = 388
EPOS_Y      = 392
EPOS_Z      = 396
EMODEL      = 300
EALIVE      = 376
ON_GROUND   = 0x122E2D4
FORCE_JUMP  = 0x131434    # client.dll

T_MODELS  = {"leet","terror","guerilla","arctic"}
CT_MODELS = {"gign","sas","urban","gsg9","vip"}

pm = None; hw = cl = 0; ok = False

def attach():
    global pm, hw, cl, ok
    for proc in ("cs.exe","hl.exe"):
        try:
            pm = pymem.Pymem(proc)
            hw = pymem.process.module_from_name(pm.process_handle,"hw.dll").lpBaseOfDll
            cl = pymem.process.module_from_name(pm.process_handle,"client.dll").lpBaseOfDll
            ok = True; return True, proc
        except: continue
    ok = False; return False, ""

def rf(a):
    try: return pm.read_float(a)
    except: return 0.
def rv3(a):
    try: return struct.unpack('fff',pm.read_bytes(a,12))
    except: return (0.,0.,0.)
def ri(a):
    try: return pm.read_int(a)
    except: return 0
def wi(a,v):
    try: pm.write_int(a,v)
    except: pass
def rstr(a,n=32):
    try: return pm.read_bytes(a,n).split(b'\x00')[0].decode('utf-8','ignore').lower().strip()
    except: return ""

def get_angles():   return rv3(hw+VIEWANGLES)
def get_my_pos():   return rv3(hw+VEC3)
def is_ground():    return ri(hw+ON_GROUND)==1
def get_matrix():
    try: return list(struct.unpack('16f',pm.read_bytes(hw+VIEW_MATRIX,64)))
    except: return []

def ent_b(i):     return hw+ENTITY+i*ESIZE
def ent_pos(i):   return (rf(ent_b(i)+EPOS_X),rf(ent_b(i)+EPOS_Y),rf(ent_b(i)+EPOS_Z))
def ent_alive(i): return rf(ent_b(i)+EALIVE)
def ent_team(i):
    m=rstr(ent_b(i)+EMODEL)
    if m in T_MODELS:  return 1
    if m in CT_MODELS: return 2
    return 0

def get_my_team():
    mp=get_my_pos()
    for i in range(32):
        if ent_alive(i)<1: continue
        if math.dist(mp,ent_pos(i))<5:
            return ent_team(i)
    return 0

def w2s(pos, m, sw, sh):
    if len(m)<16: return None
    x,y,z=pos
    cx=x*m[0]+y*m[4]+z*m[8]+m[12]
    cy=x*m[1]+y*m[5]+z*m[9]+m[13]
    cw=x*m[3]+y*m[7]+z*m[11]+m[15]
    if cw<0.001: return None
    nx=cx/cw; ny=cy/cw
    sx=int(sw/2+nx*sw/2)
    sy=int(sh/2-ny*sh/2)
    if 0<=sx<=sw and 0<=sy<=sh: return sx,sy,cw
    return None

def move_mouse(dx,dy):
    try:
        import win32api,win32con
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE,int(dx),int(dy),0,0)
    except: pass

S   = {'aim':False,'bhop':False,'esp':False}
CFG = {'strength':8.,'head':True}
AIM_STATUS = ["—"]

# ── BHOP ─────────────────────────────────────────────────
def bhop_loop():
    air=False
    while True:
        if S['bhop'] and ok:
            try:
                gnd=is_ground()
                if not gnd: wi(cl+FORCE_JUMP,5); air=True
                elif air:   wi(cl+FORCE_JUMP,0); air=False
            except: pass
        time.sleep(0.005)
threading.Thread(target=bhop_loop,daemon=True).start()

# ── ESP — pygame в отдельном потоке ──────────────────────
def esp_loop():
    try:
        import pygame, win32gui, win32con, win32api
    except: return

    pygame.init(); pygame.font.init()

    # Ждём подключения
    while not ok: time.sleep(0.5)
    time.sleep(0.5)

    # Получаем размер экрана
    try:
        import win32api as wa
        SW = wa.GetSystemMetrics(0)
        SH = wa.GetSystemMetrics(1)
    except:
        SW, SH = 1920, 1080

    # Создаём окно без рамки на весь экран
    os.environ['SDL_VIDEO_WINDOW_POS'] = "0,0"
    screen = pygame.display.set_mode((SW, SH), pygame.NOFRAME)
    pygame.display.set_caption("__esp__")

    hwnd = pygame.display.get_wm_info()['window']
    # Делаем прозрачным и поверх всего, кликабельным насквозь
    ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
        ex | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST)
    # Чёрный цвет = прозрачный
    win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(0,0,0), 0, win32con.LWA_COLORKEY)
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, SW, SH,
        win32con.SWP_NOACTIVATE)

    fnt = pygame.font.SysFont("Arial", 11, bold=True)
    clk = pygame.time.Clock()
    BLACK = (0,0,0)
    RED   = (255,50,50)
    PURP  = (120,40,220)
    YEL   = (255,220,0)

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: return

        screen.fill(BLACK)  # чёрный = прозрачный

        if S['esp'] and ok:
            try:
                mat   = get_matrix()
                mp    = get_my_pos()
                my_tm = get_my_team()

                for i in range(32):
                    if ent_alive(i) < 1: continue
                    tm = ent_team(i)
                    if tm == 0 or tm == my_tm: continue
                    pos = ent_pos(i)
                    if all(abs(v)<1 for v in pos): continue

                    head = (pos[0], pos[1], pos[2]+36)
                    pr = w2s(head, mat, SW, SH)
                    ft = w2s(pos,  mat, SW, SH)
                    if not pr or not ft: continue

                    sx,sy,_ = pr
                    _,fy,_  = ft
                    bh = max(8, abs(fy-sy))
                    bw = max(5, bh//2)
                    x1,y1 = sx-bw//2, sy
                    x2,y2 = sx+bw//2, fy

                    # Рамка
                    pygame.draw.rect(screen, RED, (x1,y1,bw,bh), 2)
                    # Линия
                    pygame.draw.line(screen, PURP, (SW//2, SH), (sx,(sy+fy)//2), 1)
                    # Текст
                    dist = math.dist(mp, pos)
                    t = fnt.render(f"{int(dist)}u", True, YEL)
                    screen.blit(t, (sx-t.get_width()//2, y2+2))
            except: pass

        pygame.display.flip()
        clk.tick(60)

threading.Thread(target=esp_loop, daemon=True).start()

# ── UI ────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
AC="#c850ff"; BG="#0d0d0d"; C1="#161616"; C2="#1a1a1a"

root = ctk.CTk()
root.title("Kereznikov V4")
root.geometry("300x480")
root.resizable(False,False)
root.configure(fg_color=BG)

hdr=ctk.CTkFrame(root,fg_color=C1,corner_radius=0,height=50); hdr.pack(fill="x")
ctk.CTkLabel(hdr,text="KEREZNIKOV V4",font=("Arial",14,"bold"),text_color=AC).pack(side="left",padx=14,pady=12)
dot_w=ctk.CTkLabel(hdr,text="●",font=("Arial",17),text_color="#fa0"); dot_w.pack(side="right",padx=10)
slbl_w=ctk.CTkLabel(hdr,text="Жду...",font=("Arial",10),text_color="#fa0"); slbl_w.pack(side="right")

df=ctk.CTkFrame(root,fg_color=C1,corner_radius=8); df.pack(fill="x",padx=12,pady=4)
d1=ctk.CTkLabel(df,text="pos: --",font=("Courier",9),text_color="#555"); d1.pack(anchor="w",padx=8,pady=1)
d2=ctk.CTkLabel(df,text="aim: --",font=("Courier",9),text_color="#555"); d2.pack(anchor="w",padx=8,pady=(0,5))

def make_btn(lbl,key,col):
    btn=ctk.CTkButton(root,text=f"◯  {lbl}  —  ВЫКЛ",
                      fg_color=C2,hover_color="#222",border_color="#333",border_width=1,
                      font=("Arial",12,"bold"),height=44,corner_radius=8,text_color="#555")
    def click():
        S[key]=not S[key]
        if S[key]: btn.configure(text=f"●  {lbl}  —  ВКЛ", fg_color="#1e1040",border_color=col,text_color=col)
        else:      btn.configure(text=f"◯  {lbl}  —  ВЫКЛ",fg_color=C2,border_color="#333",text_color="#555")
    btn.configure(command=click); btn.pack(fill="x",padx=12,pady=3)

make_btn("AIMBOT",         "aim",  AC)
make_btn("WALLHACK / ESP", "esp",  "#ff5050")
make_btn("BHOP",           "bhop", "#50ffaa")

ff=ctk.CTkFrame(root,fg_color=C1,corner_radius=10); ff.pack(fill="x",padx=12,pady=4)
rw=ctk.CTkFrame(ff,fg_color="transparent"); rw.pack(fill="x",padx=12,pady=(8,0))
ctk.CTkLabel(rw,text="СИЛА",font=("Arial",11,"bold"),text_color="#ccc").pack(side="left")
vl=ctk.CTkLabel(rw,text="8",font=("Arial",11,"bold"),text_color=AC); vl.pack(side="right")
def sf(v): vl.configure(text=f"{int(v)}"); CFG['strength']=float(v)
sldr=ctk.CTkSlider(ff,from_=1,to=30,command=sf,button_color=AC,progress_color=AC)
sldr.set(8); sldr.pack(fill="x",padx=12,pady=(2,10))

tf=ctk.CTkFrame(root,fg_color=C1,corner_radius=10); tf.pack(fill="x",padx=12,pady=4)
tr=ctk.CTkFrame(tf,fg_color="transparent"); tr.pack(fill="x",padx=12,pady=10)
ctk.CTkLabel(tr,text="ЦЕЛЬ",font=("Arial",11,"bold"),text_color="#ccc").pack(side="left")
tb=ctk.CTkSegmentedButton(tr,values=["ГОЛОВА","ТЕЛО"],
    command=lambda v:CFG.update({'head':v=="ГОЛОВА"}),
    selected_color="#2a1040",unselected_color=C2,font=("Arial",11,"bold"))
tb.set("ГОЛОВА"); tb.pack(side="right")

def auto_loop():
    while not ok:
        res,proc=attach()
        if res: dot_w.configure(text_color="#4f8"); slbl_w.configure(text=f"{proc}")
        else: time.sleep(2)
threading.Thread(target=auto_loop,daemon=True).start()

def aim_tick():
    if not (S['aim'] and ok): return
    try:
        import win32api
        SW=win32api.GetSystemMetrics(0); SH=win32api.GetSystemMetrics(1)
        mat=get_matrix()
        if not mat: return
        mp=get_my_pos(); my_tm=get_my_team()
        cx,cy=SW//2,SH//2
        best_dx=best_dy=None; best_d=float('inf')
        for i in range(32):
            if ent_alive(i)<1: continue
            tm=ent_team(i)
            if tm==0 or tm==my_tm: continue
            pos=ent_pos(i)
            if all(abs(v)<1 for v in pos): continue
            head=(pos[0],pos[1],pos[2]+(36 if CFG['head'] else 0))
            pr=w2s(head,mat,SW,SH)
            if not pr: continue
            sx,sy,_=pr
            d=math.hypot(sx-cx,sy-cy)
            if d<best_d:
                best_d=d; best_dx=sx-cx; best_dy=sy-cy
                AIM_STATUS[0]=f"{rstr(ent_b(i)+EMODEL)} {int(d)}px"
        if best_dx is not None:
            k=CFG['strength']*0.05
            move_mouse(max(-80,min(80,best_dx*k)),max(-80,min(80,best_dy*k)))
    except: pass

def tick():
    aim_tick()
    if ok:
        mp=get_my_pos()
        d1.configure(
            text=f"pos: {mp[0]:.0f} {mp[1]:.0f} {mp[2]:.0f}",
            text_color="#4f8" if any(abs(v)>5 for v in mp) else "#f44")
        d2.configure(text=f"aim: {AIM_STATUS[0]}")
    root.after(16,tick)

tick()
root.mainloop()
