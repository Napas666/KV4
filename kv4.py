import struct, math, threading, time, os
import pymem, pymem.process
import customtkinter as ctk

VIEWANGLES = 0x1230274
ELIST      = 0x12043C8
ESIZE      = 0x250
ENAME      = 0x104
ON_GROUND  = 0x122E2D4
FORCE_JUMP = 0x131434

pm = None; hw = cl = 0; ok = False
EPOS = 0x184  # сканируется автоматически

def attach():
    global pm, hw, cl, ok
    for proc in ("cs.exe","hl.exe"):
        try:
            pm = pymem.Pymem(proc)
            hw = pymem.process.module_from_name(pm.process_handle,"hw.dll").lpBaseOfDll
            cl = pymem.process.module_from_name(pm.process_handle,"client.dll").lpBaseOfDll
            ok = True; return True, proc
        except: pass
    ok = False; return False, ""

def rv3(a):
    try: return struct.unpack('fff',pm.read_bytes(a,12))
    except: return (0.,0.,0.)
def ri(a):
    try: return pm.read_int(a)
    except: return 0
def wi(a,v):
    try: pm.write_int(a,v)
    except: pass
def rstr(a):
    try: return pm.read_bytes(a,44).split(b'\x00')[0].decode('utf-8','ignore').strip()
    except: return ""

def get_angles(): return rv3(hw+VIEWANGLES)
def ent_b(i):    return hw+ELIST+i*ESIZE
def ent_name(i): return rstr(ent_b(i)+ENAME)
def ent_pos(i):  return rv3(ent_b(i)+EPOS)
def is_ground():  return ri(hw+ON_GROUND)==1

def auto_scan_epos():
    """Сканирует entity 1-4 и ищет offset где z разумный (0-200)."""
    global EPOS
    for off in range(0x100, 0x220, 4):
        votes = 0
        for eidx in range(1, 5):
            try:
                x,y,z = struct.unpack('fff', pm.read_bytes(ent_b(eidx)+off, 12))
                if (-8000<x<8000 and -8000<y<8000 and
                    -100<z<300 and (abs(x)>1 or abs(y)>1)):
                    votes += 1
            except: pass
        if votes >= 2:
            EPOS = off
            return off
    return None

def move_mouse(dx,dy):
    try:
        import win32api,win32con
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE,int(dx),int(dy),0,0)
    except: pass

def w2s(rel,ang,sw,sh):
    p,y=math.radians(ang[0]),math.radians(ang[1])
    cp,sp,cy,sy=math.cos(p),math.sin(p),math.cos(y),math.sin(y)
    fwd=(cp*cy,cp*sy,-sp); right=(sy,-cy,0); up=(sp*cy,sp*sy,cp)
    dx,dy,dz=rel
    f=dx*fwd[0]+dy*fwd[1]+dz*fwd[2]
    r=dx*right[0]+dy*right[1]+dz*right[2]
    u=dx*up[0]+dy*up[1]+dz*up[2]
    if f<0.1: return None
    sc=sw/(2*math.tan(math.radians(45)))
    sx=int(sw/2+r/f*sc); sy2=int(sh/2-u/f*sc)
    if 0<sx<sw and 0<sy2<sh: return sx,sy2,f
    return None

S={'aim':False,'bhop':False,'esp':False}
CFG={'strength':8.,'head':True}
DBG={'pos':'--','aim':'--','epos':'0x184','scan':'не сканировано'}

def bhop_loop():
    air=False
    while True:
        if S['bhop'] and ok:
            try:
                gnd=is_ground()
                if not gnd: wi(cl+FORCE_JUMP,5); air=True
                elif air: wi(cl+FORCE_JUMP,0); air=False
            except: pass
        time.sleep(0.005)
threading.Thread(target=bhop_loop,daemon=True).start()

# ── ESP pygame ────────────────────────────────────────────
ESP_DRAW = []  # список что рисовать: [('box',x1,y1,x2,y2), ('line',...)]

def esp_loop():
    try:
        import pygame,win32gui,win32con,win32api
    except: return
    pygame.init(); pygame.font.init()
    while not ok: time.sleep(0.5)
    time.sleep(1)
    try: SW=win32api.GetSystemMetrics(0); SH=win32api.GetSystemMetrics(1)
    except: SW,SH=1920,1080
    os.environ['SDL_VIDEO_WINDOW_POS']="0,0"
    screen=pygame.display.set_mode((SW,SH),pygame.NOFRAME)
    pygame.display.set_caption("__ov__")
    hwnd=pygame.display.get_wm_info()['window']
    ex=win32gui.GetWindowLong(hwnd,win32con.GWL_EXSTYLE)
    win32gui.SetWindowLong(hwnd,win32con.GWL_EXSTYLE,
        ex|win32con.WS_EX_LAYERED|win32con.WS_EX_TRANSPARENT|
        win32con.WS_EX_TOPMOST|win32con.WS_EX_NOACTIVATE)
    TRANS=(255,0,255)
    win32gui.SetLayeredWindowAttributes(hwnd,win32api.RGB(*TRANS),0,win32con.LWA_COLORKEY)
    win32gui.SetWindowPos(hwnd,win32con.HWND_TOPMOST,0,0,SW,SH,
        win32con.SWP_NOACTIVATE|win32con.SWP_SHOWWINDOW)
    fnt=pygame.font.SysFont("Arial",12,bold=True)
    clk=pygame.time.Clock()
    TRANS_C=(255,0,255); RED=(255,60,60); YEL=(255,220,0); PURP=(140,60,255)

    while True:
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: return
        screen.fill(TRANS_C)

        # Тестовый прямоугольник — всегда виден если overlay работает
        if S['esp']:
            pygame.draw.rect(screen,RED,(10,10,120,30),3)
            t=fnt.render("ESP ON",True,YEL)
            screen.blit(t,(15,15))

        # Entity ESP
        if S['esp'] and ok:
            try:
                ca=get_angles()
                mp=ent_pos(1)
                mn=ent_name(1)
                for i in range(2,33):
                    n=ent_name(i)
                    if not n or n==mn: continue
                    pos=ent_pos(i)
                    if all(abs(v)<1 for v in pos): continue
                    rel=(pos[0]-mp[0],pos[1]-mp[1],pos[2]-mp[2]+36)
                    pr=w2s(rel,ca,SW,SH)
                    if not pr: continue
                    sx,sy,dist=pr
                    bh=max(10,int(1400/max(dist,1))); bw=max(6,bh//2)
                    pygame.draw.rect(screen,RED,(sx-bw//2,sy-bh,bw,bh),2)
                    pygame.draw.line(screen,PURP,(SW//2,SH),(sx,sy),1)
                    t=fnt.render(f"{n[:8]} {int(dist)}u",True,YEL)
                    screen.blit(t,(sx,sy+2))
            except: pass

        pygame.display.flip(); clk.tick(60)

threading.Thread(target=esp_loop,daemon=True).start()

# ── UI ────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
AC="#c850ff"; BG="#0d0d0d"; C1="#161616"; C2="#1a1a1a"
root=ctk.CTk()
root.title("Kereznikov V4"); root.geometry("300x580")
root.resizable(False,False); root.configure(fg_color=BG)

hdr=ctk.CTkFrame(root,fg_color=C1,corner_radius=0,height=50); hdr.pack(fill="x")
ctk.CTkLabel(hdr,text="KEREZNIKOV V4",font=("Arial",14,"bold"),text_color=AC).pack(side="left",padx=14,pady=12)
dot_w=ctk.CTkLabel(hdr,text="●",font=("Arial",17),text_color="#fa0"); dot_w.pack(side="right",padx=10)
slbl_w=ctk.CTkLabel(hdr,text="Жду...",font=("Arial",10),text_color="#fa0"); slbl_w.pack(side="right")

df=ctk.CTkFrame(root,fg_color=C1,corner_radius=8); df.pack(fill="x",padx=12,pady=4)
d_scan=ctk.CTkLabel(df,text="epos: не сканировано",font=("Courier",9),text_color="#555"); d_scan.pack(anchor="w",padx=8,pady=1)
d_pos =ctk.CTkLabel(df,text="pos: --",font=("Courier",9),text_color="#555"); d_pos.pack(anchor="w",padx=8,pady=1)
d_aim =ctk.CTkLabel(df,text="aim: --",font=("Courier",9),text_color="#555"); d_aim.pack(anchor="w",padx=8,pady=(0,5))

# SCAN кнопка
def do_scan():
    if not ok:
        d_scan.configure(text="Сначала подключись!",text_color="#f44"); return
    d_scan.configure(text="Сканирую...",text_color="#fc8")
    def _r():
        off=auto_scan_epos()
        if off:
            d_scan.configure(text=f"НАЙДЕНО epos=0x{off:X}",text_color="#4f8")
            p=ent_pos(1)
            d_pos.configure(text=f"pos: x={p[0]:.0f} y={p[1]:.0f} z={p[2]:.0f}",
                           text_color="#4f8" if -100<p[2]<300 else "#f44")
        else:
            d_scan.configure(text="Не найдено — зайди на карту",text_color="#f44")
    threading.Thread(target=_r,daemon=True).start()

ctk.CTkButton(root,text="SCAN EPOS (зайди на карту сначала)",
              command=do_scan,fg_color="#0a1a0a",hover_color="#143014",
              border_color="#4f8",border_width=1,
              font=("Arial",10,"bold"),height=30,corner_radius=6).pack(fill="x",padx=12,pady=2)

# Тест мыши
def test_mouse():
    move_mouse(200,0)
    time.sleep(0.1)
    move_mouse(-200,0)
ctk.CTkButton(root,text="TEST MOUSE (двигает вправо и назад)",
              command=lambda:threading.Thread(target=test_mouse,daemon=True).start(),
              fg_color="#1a1a00",hover_color="#2a2a00",
              border_color="#fc8",border_width=1,
              font=("Arial",10,"bold"),height=30,corner_radius=6).pack(fill="x",padx=12,pady=2)

def make_btn(lbl,key,col):
    btn=ctk.CTkButton(root,text=f"o  {lbl}  -- VYKL",
                      fg_color=C2,hover_color="#222",border_color="#333",border_width=1,
                      font=("Arial",12,"bold"),height=44,corner_radius=8,text_color="#555")
    def click():
        S[key]=not S[key]
        if S[key]: btn.configure(text=f"* {lbl} -- VKL",fg_color="#1e1040",border_color=col,text_color=col)
        else: btn.configure(text=f"o  {lbl}  -- VYKL",fg_color=C2,border_color="#333",text_color="#555")
    btn.configure(command=click); btn.pack(fill="x",padx=12,pady=3)

make_btn("AIMBOT","aim",AC)
make_btn("WALLHACK/ESP","esp","#ff5050")
make_btn("BHOP","bhop","#50ffaa")

ff=ctk.CTkFrame(root,fg_color=C1,corner_radius=10); ff.pack(fill="x",padx=12,pady=4)
rw=ctk.CTkFrame(ff,fg_color="transparent"); rw.pack(fill="x",padx=12,pady=(8,0))
ctk.CTkLabel(rw,text="SILA",font=("Arial",11,"bold"),text_color="#ccc").pack(side="left")
vl=ctk.CTkLabel(rw,text="8",font=("Arial",11,"bold"),text_color=AC); vl.pack(side="right")
def sf(v): vl.configure(text=f"{int(v)}"); CFG['strength']=float(v)
sldr=ctk.CTkSlider(ff,from_=1,to=30,command=sf,button_color=AC,progress_color=AC)
sldr.set(8); sldr.pack(fill="x",padx=12,pady=(2,10))

def auto_loop():
    while not ok:
        res,proc=attach()
        if res: dot_w.configure(text_color="#4f8"); slbl_w.configure(text=proc)
        else: time.sleep(2)
threading.Thread(target=auto_loop,daemon=True).start()

def aim_tick():
    if not (S['aim'] and ok): return
    try:
        import win32api
        SW=win32api.GetSystemMetrics(0); SH=win32api.GetSystemMetrics(1)
        ca=get_angles(); mp=ent_pos(1); mn=ent_name(1)
        cx,cy=SW//2,SH//2
        best_dx=best_dy=None; best_d=float('inf')
        for i in range(2,33):
            n=ent_name(i)
            if not n or n==mn: continue
            pos=ent_pos(i)
            if all(abs(v)<1 for v in pos): continue
            tz=pos[2]+(36 if CFG['head'] else 0)
            rel=(pos[0]-mp[0],pos[1]-mp[1],tz-mp[2])
            pr=w2s(rel,ca,SW,SH)
            if not pr: continue
            sx,sy,_=pr
            d=math.hypot(sx-cx,sy-cy)
            if d<best_d:
                best_d=d; best_dx=sx-cx; best_dy=sy-cy
                DBG['aim']=f"{n[:8]} {int(d)}px"
        if best_dx is not None:
            k=CFG['strength']*0.05
            move_mouse(max(-80,min(80,best_dx*k)),max(-80,min(80,best_dy*k)))
    except: pass

def tick():
    aim_tick()
    if ok:
        mp=ent_pos(1)
        d_pos.configure(text=f"pos: x={mp[0]:.0f} y={mp[1]:.0f} z={mp[2]:.0f}",
                        text_color="#4f8" if -100<mp[2]<300 else "#f44")
        d_aim.configure(text=f"aim:{DBG['aim']}")
    root.after(16,tick)

tick()
root.mainloop()
