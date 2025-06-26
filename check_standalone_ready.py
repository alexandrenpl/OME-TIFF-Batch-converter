#!/usr/bin/env python3
"""
Quick verification script for standalone executable
Checks if everything is ready to create the .exe
"""

import os
import sys
import subprocess
from pathlib import Path

def check_pyinstaller():
    """Check if PyInstaller is available as command"""
    print("🔍 Checking PyInstaller...")
    
    try:
        result = subprocess.run(['pyinstaller', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"  ✅ PyInstaller {result.stdout.strip()}")
            return True
        else:
            print("  ❌ PyInstaller command failed")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("  ❌ PyInstaller not found")
        return False

def check_python_packages():
    """Check if all Python libraries are installed"""
    print("\n🔍 Checking Python libraries...")
    
    packages = {
        'tifffile': 'tifffile',
        'mrcfile': 'mrcfile', 
        'h5py': 'h5py',
        'numpy': 'numpy',
        'skimage': 'scikit-image',
        'ome_types': 'ome-types'
    }
    
    all_ok = True
    for import_name, package_name in packages.items():
        try:
            __import__(import_name)
            print(f"  ✅ {package_name}")
        except ImportError:
            print(f"  ❌ {package_name} - MISSING")
            all_ok = False
    
    return all_ok

def check_cygwin_installation():
    """Check if Cygwin is installed and accessible"""
    print("\n🔍 Checking Cygwin...")
    
    possible_paths = [
        r"C:\cygwin\bin\bash.exe",
        r"C:\cygwin64\bin\bash.exe",
        r"C:\Program Files\Cygwin\bin\bash.exe",
        r"C:\Program Files (x86)\Cygwin\bin\bash.exe"
    ]
    
    cygwin_path = None
    for path in possible_paths:
        if os.path.exists(path):
            cygwin_path = path
            print(f"  ✅ Cygwin found: {path}")
            break
    
    if not cygwin_path:
        print("  ❌ Cygwin not found")
        return None
    
    return cygwin_path

def check_imod_tools(cygwin_path):
    """Check if IMOD tools are available in Cygwin bin OR IMOD bin"""
    print("\n🔍 Checking IMOD tools...")
    
    cygwin_dir = os.path.dirname(cygwin_path)
    imod_dir = os.path.join(os.path.dirname(cygwin_dir), 'usr', 'local', 'IMOD', 'bin')
    required_tools = [
        'extractpieces.exe',
        'blendmont.exe'
    ]
    
    all_ok = True
    found_in_imod = []
    for tool in required_tools:
        tool_cygwin = os.path.join(cygwin_dir, tool)
        tool_imod = os.path.join(imod_dir, tool)
        if os.path.exists(tool_cygwin):
            print(f"  ✅ {tool} in {tool_cygwin}")
        elif os.path.exists(tool_imod):
            print(f"  ✅ {tool} found in IMOD: {tool_imod}")
            found_in_imod.append(tool)
        else:
            print(f"  ❌ {tool} - MISSING in both locations")
            all_ok = False
    
    if found_in_imod and not all_ok:
        print(f"\nNote: Some tools found in IMOD location. This is OK for standalone.")
        print(f"  IMOD location: {imod_dir}")
    
    # Don't fail if tools are found in IMOD location
    if found_in_imod and len(found_in_imod) == len(required_tools):
        all_ok = True
        print("  ✅ All required IMOD tools found")
    
    return all_ok

def check_source_file():
    """Check if source file exists"""
    print("\n🔍 Checking source file...")
    
    source_file = "ome_tiff_batch_gui_v2.py"
    if os.path.exists(source_file):
        print(f"  ✅ {source_file} found")
        return True
    else:
        print(f"  ❌ {source_file} not found")
        return False

def test_cygwin_execution(cygwin_path):
    """Test if Cygwin can be executed"""
    print("\n🔍 Testing Cygwin execution...")
    
    try:
        result = subprocess.run([
            cygwin_path, 
            "-c", 
            "echo 'Cygwin working'"
        ], 
        capture_output=True, 
        text=True, 
        timeout=10
        )
        
        if result.returncode == 0:
            print("  ✅ Cygwin executes correctly")
            return True
        else:
            print(f"  ❌ Execution error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("  ❌ Execution timeout")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def check_disk_space():
    """Check available disk space"""
    print("\n🔍 Checking disk space...")
    
    try:
        import shutil
        total, used, free = shutil.disk_usage(".")
        free_gb = free // (1024**3)
        
        print(f"  📊 Free space: {free_gb} GB")
        
        if free_gb >= 2:
            print("  ✅ Sufficient space")
            return True
        else:
            print("  ⚠️  Low space (recommended: 2+ GB)")
            return False
            
    except Exception as e:
        print(f"  ❌ Error checking space: {e}")
        return False

def main():
    print("🚀 Verification for Standalone Executable")
    print("=" * 50)
    
    all_checks_passed = True
    
    # Check PyInstaller
    if not check_pyinstaller():
        all_checks_passed = False
    
    # Check Python libraries
    if not check_python_packages():
        all_checks_passed = False
    
    # Check Cygwin
    cygwin_path = check_cygwin_installation()
    if not cygwin_path:
        all_checks_passed = False
    else:
        # Check IMOD tools
        if not check_imod_tools(cygwin_path):
            all_checks_passed = False
        
        # Test execution
        if not test_cygwin_execution(cygwin_path):
            all_checks_passed = False
    
    # Check source file
    if not check_source_file():
        all_checks_passed = False
    
    # Check disk space
    check_disk_space()
    
    # Final result
    print("\n" + "=" * 50)
    if all_checks_passed:
        print("🎉 EVERYTHING READY!")
        print("You can run: python create_standalone.py")
    else:
        print("❌ PROBLEMS DETECTED")
        print("Fix the issues above before creating the executable")
    
    print("\n📋 Summary:")
    print("- PyInstaller: " + ("✅" if check_pyinstaller() else "❌"))
    print("- Python libraries: " + ("✅" if check_python_packages() else "❌"))
    print("- Cygwin: " + ("✅" if cygwin_path else "❌"))
    print("- IMOD: " + ("✅" if cygwin_path and check_imod_tools(cygwin_path) else "❌"))
    print("- Source file: " + ("✅" if check_source_file() else "❌"))
    
    return all_checks_passed

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1) 