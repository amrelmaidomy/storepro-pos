from PyInstaller.utils.hooks import collect_data_files

a = Analysis(['main.py'], pathex=[], binaries=[], datas=collect_data_files('customtkinter') + [('assets/fonts', 'assets/fonts')], hiddenimports=['PIL._tkinter_finder'], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='StorePro', debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='StorePro')
