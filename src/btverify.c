/*
 * BTLink Wine USB presence-aware SetupAPI bridge v3.
 * Supported unit: ArteryTek 2e3c:5740, serial 000000000000.
 * Requires BTLink launcher to provide BTLINK_USB_SYSFS pointing to the
 * real USB device node via Wine Z: (not a registry entry or dummy file).
 * Never opens the serial port and never sends firmware/programming commands.
 * MIT licensed compatibility adapter. This DLL does not contain vendor firmware.
 */
#if !defined(_M_IX86) && !defined(__i386__)
#error 32-bit x86 required
#endif
#define WINAPI __attribute__((stdcall))
#define DLLIMPORT __declspec(dllimport)
#define DLLEXPORT __declspec(dllexport)
typedef unsigned long DWORD;
typedef unsigned short WORD;
typedef unsigned char BYTE;
typedef unsigned long ULONG_PTR;
typedef void *HANDLE;
typedef void *HMODULE;
typedef void *HDEVINFO;
typedef void *HWND;
typedef void *FARPROC;
typedef int BOOL;
typedef BYTE *PBYTE;
typedef DWORD *PDWORD;
typedef struct GUID { DWORD Data1; WORD Data2; WORD Data3; BYTE Data4[8]; } GUID;
typedef struct SP_DEVINFO_DATA {
    DWORD cbSize; GUID ClassGuid; DWORD DevInst; ULONG_PTR Reserved;
} SP_DEVINFO_DATA, *PSP_DEVINFO_DATA;
DLLIMPORT HMODULE WINAPI LoadLibraryA(const char *);
DLLIMPORT FARPROC WINAPI GetProcAddress(HMODULE, const char *);
DLLIMPORT void WINAPI SetLastError(DWORD);
DLLIMPORT HANDLE WINAPI GetStdHandle(DWORD);
DLLIMPORT BOOL WINAPI WriteFile(HANDLE, const void *, DWORD, PDWORD, void *);
DLLIMPORT HANDLE WINAPI CreateFileA(const char *, DWORD, DWORD, void *, DWORD, DWORD, HANDLE);
DLLIMPORT BOOL WINAPI ReadFile(HANDLE, void *, DWORD, PDWORD, void *);
DLLIMPORT BOOL WINAPI CloseHandle(HANDLE);
DLLIMPORT DWORD WINAPI GetEnvironmentVariableA(const char *, char *, DWORD);
#define TRUE 1
#define FALSE 0
#define ERROR_NO_MORE_ITEMS 259
#define ERROR_INSUFFICIENT_BUFFER 122
#define ERROR_INVALID_USER_BUFFER 1784
#define ERROR_INVALID_DATA 13
#define ERROR_PROC_NOT_FOUND 127
#define SPDRP_DEVICEDESC      0x00
#define SPDRP_HARDWAREID      0x01
#define SPDRP_COMPATIBLEIDS   0x02
#define SPDRP_SERVICE         0x04
#define SPDRP_CLASS           0x07
#define SPDRP_CLASSGUID       0x08
#define SPDRP_MFG             0x0b
#define SPDRP_FRIENDLYNAME    0x0c
#define SPDRP_ENUMERATOR_NAME 0x16
#define REG_SZ 1
#define REG_MULTI_SZ 7
#define DIGCF_PRESENT 0x2
#define DIGCF_DEVICEINTERFACE 0x10
#define GENERIC_READ 0x80000000UL
#define FILE_SHARE_READ 1
#define FILE_SHARE_WRITE 2
#define FILE_SHARE_DELETE 4
#define OPEN_EXISTING 3
#define FILE_ATTRIBUTE_NORMAL 0x80
#define INVALID_HANDLE_VALUE ((HANDLE)(-1))

static const GUID ports_guid = {0x4d36e978, 0xe325, 0x11ce,
    {0xbf, 0xc1, 0x08, 0x00, 0x2b, 0xe1, 0x03, 0x18}};
static BYTE marker;
#define SYNTH ((HDEVINFO)&marker)
static HMODULE setupapi;

static DWORD length(const char *s) {
    DWORD n=0; while (s[n]) n++; return n;
}
static void logline(const char *msg) {
    DWORD wrote = 0;
    HANDLE stream = GetStdHandle((DWORD)-12);
    if (stream && stream != INVALID_HANDLE_VALUE)
        WriteFile(stream, msg, length(msg), &wrote, (void*)0);
}
static FARPROC original(const char *function) {
    if (!setupapi) setupapi = LoadLibraryA("setupapi.dll");
    return setupapi ? GetProcAddress(setupapi, function) : (FARPROC)0;
}
static BOOL same_guid(const GUID *a, const GUID *b) {
    const BYTE *x=(const BYTE *)a, *y=(const BYTE *)b;
    unsigned int i;
    if (!a || !b) return FALSE;
    for (i=0;i<sizeof(GUID);++i) if (x[i]!=y[i]) return FALSE;
    return TRUE;
}
static BOOL valid(SP_DEVINFO_DATA *data) {
    return data && data->cbSize == sizeof(SP_DEVINFO_DATA);
}
static BOOL return_prop(const void *src, DWORD size, DWORD type,
    PDWORD type_out, PBYTE destination, DWORD capacity, PDWORD needed)
{
    DWORD i;
    const BYTE *bytes=(const BYTE *)src;
    if (type_out) *type_out = type;
    if (needed) *needed = size;
    if (!destination || capacity < size) {
        SetLastError(ERROR_INSUFFICIENT_BUFFER); return FALSE;
    }
    for (i=0;i<size;++i) destination[i] = bytes[i];
    SetLastError(0); return TRUE;
}

/* Read a value from Wine's Z:\\sys\\devices\\... USB sysfs directory.
 * The loader provides the *resolved* USB parent path so no Wine path
 * normalization can remove Linux symlinks or change parent components.
 * Does not use a software-created "device present" sentinel.
 */
static BOOL read_sysfs(const char *base, const char *key, char *value, DWORD cap) {
    char path[900];
    DWORD a=length(base), b=length(key), i, got=0;
    HANDLE h;
    if (a<4 || a+b+2>=sizeof(path) || cap<2) return FALSE;
    for(i=0;i<a;++i) path[i]=base[i];
    if (path[a-1]!='\\') path[a++]='\\';
    for(i=0;i<b;++i) path[a++]=key[i];
    path[a]=0;
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
                    (void*)0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, (HANDLE)0);
    if (h == INVALID_HANDLE_VALUE) return FALSE;
    if (!ReadFile(h, value, cap-1, &got, (void*)0)) { CloseHandle(h); return FALSE; }
    CloseHandle(h);
    if (!got || got>=cap) return FALSE;
    value[got]=0;
    for (i=0;i<got;++i) if (value[i]=='\r' || value[i]=='\n') { value[i]=0; break; }
    return TRUE;
}
static BOOL equals_ci(const char *a, const char *b) {
    DWORD i=0;
    for (;;) {
        char c=a[i], d=b[i];
        if (c>='A' && c<='Z') c = (char)(c+('a'-'A'));
        if (d>='A' && d<='Z') d = (char)(d+('a'-'A'));
        if (c!=d) return FALSE;
        if (!c) return TRUE;
        i++;
    }
}
static BOOL physical_present(void) {
    char base[750], v[64], p[64], s[64];
    DWORD n=GetEnvironmentVariableA("BTLINK_USB_SYSFS", base, sizeof(base));
    if (n==0 || n>=sizeof(base)) return FALSE;
    if (!(base[0]=='Z' || base[0]=='z') || base[1]!=':' || base[2]!='\\') return FALSE;
    if (!read_sysfs(base,"idVendor",v,sizeof(v)) || !equals_ci(v,"2e3c")) return FALSE;
    if (!read_sysfs(base,"idProduct",p,sizeof(p)) || !equals_ci(p,"5740")) return FALSE;
    if (!read_sysfs(base,"serial",s,sizeof(s)) || !equals_ci(s,"000000000000")) return FALSE;
    return TRUE;
}
DLLEXPORT HDEVINFO WINAPI SetupDiGetClassDevsA(const GUID *guid,
    const char *enumerator, HWND hwnd, DWORD flags)
{
    typedef HDEVINFO (WINAPI *real_t)(const GUID *, const char *, HWND, DWORD);
    real_t fn;
    if (same_guid(guid, &ports_guid) && !enumerator &&
        (flags & DIGCF_PRESENT) && !(flags & DIGCF_DEVICEINTERFACE) && physical_present()) {
        logline("BTVERIFY: real ArteryTek device confirmed; exposing COM3\r\n");
        SetLastError(0);
        return SYNTH;
    }
    fn=(real_t)original("SetupDiGetClassDevsA");
    if (fn) return fn(guid, enumerator, hwnd, flags);
    SetLastError(ERROR_PROC_NOT_FOUND);
    return (HDEVINFO)(-1);
}
DLLEXPORT BOOL WINAPI SetupDiEnumDeviceInfo(HDEVINFO set, DWORD index,
    SP_DEVINFO_DATA *data)
{
    typedef BOOL (WINAPI *real_t)(HDEVINFO, DWORD, SP_DEVINFO_DATA *);
    real_t fn;
    if (set==SYNTH) {
        if (!physical_present() || index!=0) { SetLastError(ERROR_NO_MORE_ITEMS); return FALSE; }
        if (!valid(data)) { SetLastError(ERROR_INVALID_USER_BUFFER); return FALSE; }
        data->ClassGuid=ports_guid; data->DevInst=0x2e3c; data->Reserved=0;
        logline("BTVERIFY: returned checked Ports device\r\n");
        SetLastError(0); return TRUE;
    }
    fn=(real_t)original("SetupDiEnumDeviceInfo");
    if (fn) return fn(set,index,data);
    SetLastError(ERROR_PROC_NOT_FOUND); return FALSE;
}
DLLEXPORT BOOL WINAPI SetupDiGetDeviceRegistryPropertyA(HDEVINFO set,
    SP_DEVINFO_DATA *data, DWORD property, PDWORD type, PBYTE buffer,
    DWORD capacity, PDWORD needed)
{
    typedef BOOL (WINAPI *real_t)(HDEVINFO, SP_DEVINFO_DATA *, DWORD,
        PDWORD, PBYTE, DWORD, PDWORD);
    static const char hwids[] = "USB\\VID_2E3C&PID_5740\0USB\\VID_2E3C&PID_5740&REV_0200\0\0";
    static const char compids[] = "USB\\Class_02&SubClass_02&Prot_01\0USB\\Class_02&SubClass_02\0\0";
    const char *value=(const char *)0;
    real_t fn;
    if (set==SYNTH) {
        if (!physical_present()) { SetLastError(ERROR_NO_MORE_ITEMS); return FALSE; }
        if (!valid(data)) { SetLastError(ERROR_INVALID_USER_BUFFER); return FALSE; }
        switch (property) {
            case SPDRP_HARDWAREID:
                return return_prop(hwids,sizeof(hwids),REG_MULTI_SZ,type,buffer,capacity,needed);
            case SPDRP_COMPATIBLEIDS:
                return return_prop(compids,sizeof(compids),REG_MULTI_SZ,type,buffer,capacity,needed);
            case SPDRP_FRIENDLYNAME: value="Artery Virtual COM Port (COM3)"; break;
            case SPDRP_DEVICEDESC: value="Artery Virtual COM Port"; break;
            case SPDRP_MFG: value="ArteryTek"; break;
            case SPDRP_CLASS: value="Ports"; break;
            case SPDRP_CLASSGUID: value="{4D36E978-E325-11CE-BFC1-08002BE10318}"; break;
            case SPDRP_ENUMERATOR_NAME: value="USB"; break;
            case SPDRP_SERVICE: value="usbser"; break;
            default: SetLastError(ERROR_INVALID_DATA); return FALSE;
        }
        return return_prop(value,length(value)+1,REG_SZ,type,buffer,capacity,needed);
    }
    fn=(real_t)original("SetupDiGetDeviceRegistryPropertyA");
    if (fn) return fn(set,data,property,type,buffer,capacity,needed);
    SetLastError(ERROR_PROC_NOT_FOUND); return FALSE;
}
DLLEXPORT BOOL WINAPI SetupDiGetDeviceInstanceIdA(HDEVINFO set,
    SP_DEVINFO_DATA *data, char *output, DWORD capacity, PDWORD needed)
{
    typedef BOOL (WINAPI *real_t)(HDEVINFO, SP_DEVINFO_DATA *, char *, DWORD, PDWORD);
    static const char identity[]="USB\\VID_2E3C&PID_5740\\000000000000";
    real_t fn;
    if (set==SYNTH) {
        if (!physical_present()) { SetLastError(ERROR_NO_MORE_ITEMS); return FALSE; }
        if (!valid(data)) { SetLastError(ERROR_INVALID_USER_BUFFER); return FALSE; }
        if (needed) *needed=sizeof(identity);
        if (!output || capacity<sizeof(identity)) {
            SetLastError(ERROR_INSUFFICIENT_BUFFER); return FALSE;
        }
        { DWORD i; for(i=0;i<sizeof(identity);++i) output[i]=identity[i]; }
        logline("BTVERIFY: returned validated device instance ID\r\n");
        SetLastError(0); return TRUE;
    }
    fn=(real_t)original("SetupDiGetDeviceInstanceIdA");
    if (fn) return fn(set,data,output,capacity,needed);
    SetLastError(ERROR_PROC_NOT_FOUND); return FALSE;
}
DLLEXPORT BOOL WINAPI SetupDiDestroyDeviceInfoList(HDEVINFO set) {
    typedef BOOL (WINAPI *real_t)(HDEVINFO);
    real_t fn;
    if (set==SYNTH) { SetLastError(0); return TRUE; }
    fn=(real_t)original("SetupDiDestroyDeviceInfoList");
    if (fn) return fn(set);
    SetLastError(ERROR_PROC_NOT_FOUND); return FALSE;
}
