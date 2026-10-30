"""Generate Windows file metadata from the application version."""
import sys
from pathlib import Path
from PyInstaller.utils.win32.versioninfo import (VSVersionInfo, FixedFileInfo,
                                                StringFileInfo, StringTable, StringStruct,
                                                VarFileInfo, VarStruct)

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "src"))
from dual_live_captions import __version__  # noqa: E402

version = tuple(int(part) for part in __version__.split(".")) + (0,)
info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version, prodvers=version, mask=0x3f, flags=0,
                     OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", "Dual Live Captions contributors"),
            StringStruct("FileDescription", "Dual Live Captions"),
            StringStruct("FileVersion", __version__),
            StringStruct("InternalName", "DualLiveCaptions"),
            StringStruct("OriginalFilename", "DualLiveCaptions.exe"),
            StringStruct("ProductName", "Dual Live Captions"),
            StringStruct("ProductVersion", __version__),
        ])]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)
target = Path(sys.argv[1])
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(str(info), encoding="utf-8")
