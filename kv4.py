import struct, math, threading, time, os
import pymem, pymem.process
import customtkinter as ctk

VIEWANGLES = 0x1230274
ELIST      = 0x12043C8
ESIZE      = 0x250
ENAME      = 0x104
EPOS       = 0x184
ON_GROUND  = 0x122E2D4
FORCE_JUMP = 0x131434

pm = None; hw = cl = 0; ok = False

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

def get_angles():  return rv3(hw+VIEWANGLES)
def is_ground():   return ri(hw+ON_GROUND)==1
def ent_b(i):      return hw+ELIST+i*ESIZE
def ent_name(i):   return rstr(ent_b(i)+ENAME)
def ent_pos(i):    return rv3(ent_b(i)+EPOS)

def valid_pos(p):
    return (all(-16000<v<16000 for v in p) and
            any(abs(v)>1 for v in p) and
            -300<p[2]<500)

def find_my_pos():
    for i in range(3):
        p=ent_pos(i)
        if valid_pos(p): return p,i
    return (0.,0.,36.),1

def get_bots(mi,mn):
    out=[]
    for i in range(33):
        if i==mi: continue
        n=ent_name(i)
        if not n or n==mn: continue
        p=ent_pos(i)
        if valid_pos(p): out.append((i,n,p))
    return out

def norm(a):
    while a>180: a-=360
    while a<-180: a+=360
    return a

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
DBG={'pos':'--','aim':'--','bots':0}

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

def esp_loop():
    try:
        import pygame,win32gui,win32con,win32api
    except: return
    pygame.init(); pygame.font.init()
    while not ok: time.sleep(0.5)
    time.sleep(0.5)
    try: SW=win32api.GetSystemMetrics(0); SH=win32api.GetSystemMetrics(1)
    except: SW,SH=1920,1080
    os.environ['SDL_VIDEO_WINDOW_POS']="0,0"
    screen=pygame.display.set_mode((SW,SH),pygame.NOFRAME)
    pygame.display.set_caption("__ov__")
    hwnd=pygame.display.get_wm_info()['window']
    ex=win32gui.GetWindowLong(hwnd,win32con.GWL_EXSTYLE)
    win32gui.SetWindowLong(hwnd,win32con.GWL_EXSTYLE,
        ex|win32con.WS_EX_LAYERED|win32con.WS_EX_TRANSPARENT|win32con.WS_EX_TOPMOST)
    TRANS=(255,0,255)
    win32gui.SetLayeredWindowAttributes(hwnd,win32api.RGB(*TRANS),0,win32con.LWA_COLORKEY)
    win32gui.SetWindowPos(hwnd,win32con.HWND_TOPMOST,0,0,SW,SH,win32con.SWP_NOACTIVATE)
    fnt=pygame.font.SysFont("Arial",11,bold=True)
    clk=pygame.time.Clock()
    RED=(255,60,60); PURP=(140,60,255); YEL=(255,220,0)
    while True:
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: return
        screen.fill(TRANS)
        if S['esp'] and ok:
            try:
                ca=get_angles(); mp,mi=find_my_pos(); mn=ent_name(mi)
                for _,name,pos in get_bots(mi,mn):
                    head=(pos[0],pos[1],pos[2]+36)
                    pr=w2s((head[0]-mp[0],head[1]-mp[1],head[2]-mp[2]),ca,SW,SH)
                    ft=w2s((pos[0]-mp[0],pos[1]-mp[1],pos[2]-mp[2]),ca,SW,SH)
                    if not pr or not ft: continue
                    sx,sy,_=pr; _,fy,_=ft
                    bh=max(8,abs(fy-sy)); bw=max(5,bh//2)
                    pygame.draw.rect(screen,RED,(sx-bw//2,sy,bw,bh),2)
                    pygame.draw.line(screen,PURP,(SW//2,SH),(sx,(sy+fy)//2),1)
                    t=fnt.render(f"{name[:8]} {int(math.dist(mp,pos))}u",True,YEL)
                    screen.blit(t,(sx-t.get_width()//2,fy+2))
            except: pass
        pygame.display.flip(); clk.tick(60)

threading.Thread(target=esp_loop,daemon=True).start()

ctk.set_appearance_mode("dark")
AC="#c850ff"; BG="#0d0d0d"; C1="#161616"; C2="#1a1a1a"
root=ctk.CTk()
root.title("Kereznikov V4"); root.geometry("300x480")
root.resizable(False,False); root.configure(fg_color=BG)

hdr=ctk.CTkFrame(root,fg_color=C1,corner_radius=0,height=50); hdr.pack(fill="x")
ctk.CTkLabel(hdr,text="KEREZNIKOV V4",font=("Arial",14,"bold"),text_color=AC).pack(side="left",padx=14,pady=12)
dot_w=ctk.CTkLabel(hdr,text="●",font=("Arial",17),text_color="#fa0"); dot_w.pack(side="right",padx=10)
slbl_w=ctk.CTkLabel(hdr,text="Жду...",font=("Arial",10),text_color="#fa0"); slbl_w.pack(side="right")

df=ctk.CTkFrame(root,fg_color=C1,corner_radius=8); df.pack(fill="x",padx=12,pady=4)
d1=ctk.CTkLabel(df,text="pos: --",font=("Courier",9),text_color="#555"); d1.pack(anchor="w",padx=8,pady=1)
d2=ctk.CTkLabel(df,text="aim/bots: --",font=("Courier",9),text_color="#555"); d2.pack(anchor="w",padx=8,pady=(0,5))

def make_btn(lbl,key,col):
    btn=ctk.CTkButton(root,text=f"o  {lbl}  --  VYKL",
                      fg_color=C2,hover_color="#222",border_color="#333",border_width=1,
                      font=("Arial",12,"bold"),height=44,corner_radius=8,text_color="#555")
    def click():
        S[key]=not S[key]
        if S[key]: btn.configure(text=f"*  {lbl}  --  VKL",fg_color="#1e1040",border_color=col,text_color=col)
        else: btn.configure(text=f"o  {lbl}  --  VYKL",fg_color=C2,border_color="#333",text_color="#555")
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
        ca=get_angles(); mp,mi=find_my_pos(); mn=ent_name(mi)
        DBG['pos']=f"x={mp[0]:.0f} y={mp[1]:.0f} z={mp[2]:.0f}"
        bots=get_bots(mi,mn); DBG['bots']=len(bots)
        cx,cy=SW//2,SH//2
        best_dx=best_dy=None; best_d=float('inf')
        for _,name,pos in bots:
            tz=pos[2]+(36 if CFG['head'] else 0)
            rel=(pos[0]-mp[0],pos[1]-mp[1],tz-mp[2])
            pr=w2s(rel,ca,SW,SH)
            if not pr: continue
            sx,sy,_=pr
            d=math.hypot(sx-cx,sy-cy)
            if d<best_d:
                best_d=d; best_dx=sx-cx; best_dy=sy-cy
                DBG['aim']=f"{name[:8]} {int(d)}px"
        if best_dx is not None:
            k=CFG['strength']*0.05
            move_mouse(max(-80,min(80,best_dx*k)),max(-80,min(80,best_dy*k)))
    except: pass

def tick():
    aim_tick()
    if ok:
        d1.configure(text=f"pos: {DBG['pos']}",
                     text_color="#4f8" if DBG['pos']!='--' else "#f44")
        d2.configure(text=f"aim:{DBG['aim']} bots:{DBG['bots']}")
    root.after(16,tick)

tick()
root.mainloop()
