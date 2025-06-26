#!/usr/bin/env python3
"""
Script to create standalone executable of OME-TIFF Batch Converter
Simplified version without embedded Cygwin/IMOD - requires system installation
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_pyinstaller():
    """Check if PyInstaller is available as command-line tool"""
    try:
        result = subprocess.run(['pyinstaller', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✓ PyInstaller {result.stdout.strip()}")
            return True
        else:
            print("✗ PyInstaller command failed")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("✗ PyInstaller not found")
        return False

def check_dependencies():
    """Check if all Python dependencies are installed"""
    required_packages = [
        'tifffile', 'mrcfile', 'h5py', 'numpy', 
        'scikit-image', 'ome-types', 'tkinter'
    ]
    
    missing = []
    for package in required_packages:
        try:
            if package == 'scikit-image':
                __import__('skimage')
            elif package == 'ome-types':
                __import__('ome_types')
            else:
                __import__(package)
            print(f"✓ {package}")
        except ImportError:
            missing.append(package)
            print(f"✗ {package}")
    
    if missing:
        print(f"\nMissing packages: {', '.join(missing)}")
        print("Run: pip install " + " ".join(missing))
        return False
    
    return True

def check_system_requirements():
    """Check if Cygwin and IMOD are installed on system (non-blocking)"""
    print("\nChecking system requirements...")
    
    # Check Cygwin
    cygwin_paths = [
        r"C:\cygwin\bin\bash.exe",
        r"C:\cygwin64\bin\bash.exe",
        r"C:\Program Files\Cygwin\bin\bash.exe",
        r"C:\Program Files (x86)\Cygwin\bin\bash.exe"
    ]
    
    cygwin_found = False
    for path in cygwin_paths:
        if os.path.exists(path):
            print(f"✓ Cygwin found: {path}")
            cygwin_found = True
            break
    
    if not cygwin_found:
        print("⚠️  Cygwin not found - users will need to install it")
    
    return True  # Don't fail build if not found, just warn

def create_spec_file():
    """Create .spec file for PyInstaller (Python-only)"""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['ome_tiff_batch_gui_v2.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tifffile',
        'mrcfile',
        'h5py',
        'numpy',
        'skimage.transform',
        'skimage._shared',
        'ome_types',
        'ome_types.model',
        'xsdata',
        'xsdata.formats.dataclass.parsers',
        'xsdata.formats.dataclass.parsers.dict',
        'xsdata.formats.dataclass.context',
        'xsdata.formats.dataclass.compat',
        'xsdata.utils.hooks',
        'xsdata_pydantic_basemodel',
        'xsdata_pydantic_basemodel.hooks',
        'xsdata_pydantic_basemodel.hooks.class_type',
        'pkg_resources.py2_warn',
        'pathlib',
        'subprocess',
        'threading',
        'glob',
        'os',
        'sys'
    ],
    collect_all=[
        'xsdata',
        'xsdata_pydantic_basemodel',
        'ome_types'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='OME_TIFF_Batch_Converter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
'''
    
    with open('build_standalone.spec', 'w') as f:
        f.write(spec_content)
    
    print("✓ .spec file created: build_standalone.spec")
    return 'build_standalone.spec'

def build_executable(spec_file):
    """Build executable using PyInstaller"""
    print("\nBuilding executable...")
    print("This may take several minutes...")
    
    result = subprocess.run([
        "pyinstaller",
        "--clean",
        spec_file
    ])
    
    if result.returncode == 0:
        print("\n✓ Executable built successfully!")
        exe_path = Path("dist/OME_TIFF_Batch_Converter.exe")
        if exe_path.exists():
            print(f"Executable located at: {exe_path.absolute()}")
            return True
        else:
            print("✗ Executable not found in expected location")
            return False
    else:
        print("\n✗ Error building executable")
        return False

def cleanup_temp_files():
    """Remove temporary files"""
    temp_files = [
        "build_standalone.spec",
        "build",
        "__pycache__"
    ]
    
    for file in temp_files:
        if os.path.exists(file):
            if os.path.isdir(file):
                shutil.rmtree(file)
            else:
                os.remove(file)
            print(f"Removed: {file}")

def main():
    print("=== OME-TIFF Batch Converter - Create Standalone Executable ===\n")
    
    # Check if source file exists
    if not os.path.exists("ome_tiff_batch_gui_v2.py"):
        print("✗ Source file ome_tiff_batch_gui_v2.py not found!")
        return False
    print("✓ Source file found")
    
    # Check PyInstaller first
    print("\nChecking PyInstaller...")
    if not check_pyinstaller():
        print("Installing PyInstaller...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
            print("✓ PyInstaller installed successfully")
            # Verify installation worked
            if not check_pyinstaller():
                print("✗ PyInstaller installation verification failed")
                return False
        except subprocess.CalledProcessError:
            print("✗ Failed to install PyInstaller")
            return False
    
    # Check Python dependencies
    print("\nChecking Python dependencies...")
    if not check_dependencies():
        return False
    
    # Check system requirements (non-blocking)
    check_system_requirements()
    
    # Create .spec file
    print("\nPreparing build configuration...")
    spec_file = create_spec_file()
    
    # Build executable
    success = build_executable(spec_file)
    
    # Cleanup
    print("\nCleaning up temporary files...")
    cleanup_temp_files()
    
    if success:
        print("\n🎉 Standalone executable created successfully!")
        print("The OME_TIFF_Batch_Converter.exe file is ready for distribution.")
        print("\nIMPORTANT: Users must have Cygwin and IMOD installed on their system.")
        print("See README.md for installation instructions.")
        return True
    else:
        print("\n❌ Failed to create executable.")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1) 