import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import sys
import os
from pathlib import Path
import glob

# Import functions from Script.py
import subprocess
import tifffile
import numpy as np
import mrcfile
import h5py
from skimage.transform import pyramid_reduce
from ome_types.model import OME, Image, Pixels, Channel

# Path to Cygwin bash
def get_cygwin_bash_path():
    """Determines the path to Cygwin bash"""
    # If running as executable, use embedded Cygwin
    if getattr(sys, 'frozen', False):
        # PyInstaller executable
        base_path = sys._MEIPASS
        cygwin_bash = os.path.join(base_path, 'cygwin', 'bin', 'bash.exe')
        if os.path.exists(cygwin_bash):
            return cygwin_bash
    
    # If running as script, use installed Cygwin
    possible_paths = [
        r"C:\cygwin\bin\bash.exe",
        r"C:\cygwin64\bin\bash.exe",
        r"C:\Program Files\Cygwin\bin\bash.exe",
        r"C:\Program Files (x86)\Cygwin\bin\bash.exe"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    raise FileNotFoundError("Cygwin bash not found. Install Cygwin or use the executable.")

CYGWIN_BASH_PATH = get_cygwin_bash_path()

# Function to convert Windows paths to Cygwin
def windows_to_cygwin_path(win_path):
    win_path = Path(win_path).resolve()
    drive = win_path.drive[0].lower()
    rest = str(win_path)[2:].replace('\\', '/')
    return f"/cygdrive/{drive}{rest}"

# Function to run commands via Cygwin
def run_cygwin_command(command):
    result = subprocess.run(
        [CYGWIN_BASH_PATH, "-l", "-c", command],
        capture_output=True,
        text=True
    )
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {command}")
    return result.stdout

def get_mag(ficheiro_mdoc):
    try:
        with open(ficheiro_mdoc, 'r', encoding='utf-8') as f:
            for linha in f:
                if "PixelSpacing" in linha:
                    partes = linha.strip().split(" = ")
                    if len(partes) == 2:
                        try:
                            return float(partes[1].strip())
                        except ValueError:
                            print("Could not convert value to float.")
                            return None
        print("No line with 'PixelSpacing =' found.")
        return None
    except FileNotFoundError:
        print(f"File not found: {ficheiro_mdoc}")
        return None

def calculate_reduction_factor(image_shape, target_pixels=1_000_000_000):
    """Calculate the reduction factor needed to get image below target pixels"""
    current_pixels = image_shape[0] * image_shape[1]
    if current_pixels <= target_pixels:
        return 1
    
    # Calculate reduction factor needed
    reduction_factor = int(np.ceil(np.sqrt(current_pixels / target_pixels)))
    return reduction_factor

def create_ome_bigtiff_pyramid(mrc_base_path, output_path, pixel_spacing_angstrom, min_size=512, tile_size=256, compression='deflate', reduction_factor=1):
    """
    Converts a 2D MRC image to pyramidal OME-TIFF, with OME-XML metadata and correct pixel size.
    """
    # Read MRC image
    with mrcfile.open(mrc_base_path, permissive=True) as mrc:
        base = mrc.data.copy()

    if base.ndim != 2:
        raise ValueError("Image must be 2D.")

    # Apply reduction if specified
    if reduction_factor > 1:
        base = base[::reduction_factor, ::reduction_factor]
        # Adjust pixel size for reduction
        adjusted_pixel_spacing = pixel_spacing_angstrom * reduction_factor
        print(f"Applied {reduction_factor}x reduction. New pixel size: {adjusted_pixel_spacing} Å")
    else:
        adjusted_pixel_spacing = pixel_spacing_angstrom

    # Create pyramid
    pyramid = [base]
    current = base
    while min(current.shape) >= min_size * 2:
        current = pyramid_reduce(current, downscale=2, preserve_range=True).astype(base.dtype)
        pyramid.append(current)

    # Convert pixel size from Å to µm
    pixel_size_um = float(adjusted_pixel_spacing) * 0.0001

    # Create OME metadata
    ome = OME(
        images=[
            Image(
                name=Path(mrc_base_path).name,
                id="Image:0",
                pixels=Pixels(
                    dimension_order="XYCZT",
                    type=str(base.dtype),
                    size_x=base.shape[1],
                    size_y=base.shape[0],
                    size_z=1,
                    size_c=1,
                    size_t=1,
                    physical_size_x=pixel_size_um,
                    physical_size_y=pixel_size_um,
                    channels=[
                        Channel(id="Channel:0:0", name="channel_0", samples_per_pixel=1)
                    ],
                    id="Pixels:0"
                )
            )
        ]
    )
    ome_xml = ome.to_xml()

    # Write pyramidal TIFF with OME-XML
    with tifffile.TiffWriter(output_path, bigtiff=True) as tif:
        tif.write(
            pyramid[0],
            subifds=len(pyramid) - 1,
            photometric='minisblack',
            tile=(tile_size, tile_size),
            compression=compression,
            description=ome_xml,
            metadata=None
        )
        for level in pyramid[1:]:
            tif.write(
                level,
                photometric='minisblack',
                tile=(tile_size, tile_size),
                compression=compression
            )
    
    if reduction_factor > 1:
        print(f"[✔] Reduced OME-TIFF pyramidal created with {reduction_factor}x reduction and pixel size {pixel_size_um:.6f} µm: {output_path}")
    else:
        print(f"[✔] OME-TIFF pyramidal created with pixel size {pixel_size_um:.6f} µm: {output_path}")

def create_hdf5_pyramid(mrc_base_path, output_path, mag, compression='gzip'):
    # Read MRC image
    with mrcfile.open(mrc_base_path, permissive=True) as mrc:
        base = mrc.data.copy()  # .copy() avoids problems with closed files

    # Check if 2D or 3D
    if base.ndim == 3:
        print("Warning: image with multiple slices. Only the first will be used.")
        base = base[0]  # or another slice, as needed

    # Create reduced versions
    half = base[::2, ::2]
    quarter = base[::4, ::4]

    # Convert pixel size from Å to nm and then to µm
    pixel_size_nm = mag / 10  # Pixel size comes in Angstroms
    pixel_size_um = pixel_size_nm / 1000  # Convert to µm

    with h5py.File(output_path, 'w') as f:
        # Main dataset (full resolution)
        dset0 = f.create_dataset('res0', data=base, compression=compression, chunks=True)
        
        # 1/2 resolution dataset
        dset1 = f.create_dataset('res1', data=half, compression=compression, chunks=True)
        
        # 1/4 resolution dataset
        dset2 = f.create_dataset('res2', data=quarter, compression=compression, chunks=True)
        
        # Create dimension scales for calibration
        for i, dset in enumerate([dset0, dset1, dset2]):
            scale_factor = 2**i  # 1, 2, 4 for res0, res1, res2
            current_pixel_size = pixel_size_nm * scale_factor
            
            # Dimension scale for X
            x_scale = f.create_dataset(f'x_scale_res{i}', data=np.arange(dset.shape[1]) * current_pixel_size)
            x_scale.attrs['units'] = 'nm'
            x_scale.attrs['name'] = 'x'
            
            # Dimension scale for Y
            y_scale = f.create_dataset(f'y_scale_res{i}', data=np.arange(dset.shape[0]) * current_pixel_size)
            y_scale.attrs['units'] = 'nm'
            y_scale.attrs['name'] = 'y'
            
            # Attach dimension scales to dataset
            dset.dims[0].attach_scale(y_scale)
            dset.dims[1].attach_scale(x_scale)
            
            # Set dimension labels
            dset.dims[0].label = 'y'
            dset.dims[1].label = 'x'
        
        # Basic metadata
        f.attrs['source'] = 'SerialEM .mdoc'
        f.attrs['pixel_size_nm'] = pixel_size_nm
        f.attrs['pixel_size_um'] = pixel_size_um
        f.attrs['unit'] = 'nm'
    
    # Create XML file in BigDataViewer format
    xml_path = output_path.with_suffix('.xml')
    create_bdv_xml(xml_path, output_path.name, base.shape, pixel_size_um)
    
    print(f"HDF5 pyramidal created: {output_path}")
    print(f"BigDataViewer XML created: {xml_path}")
    print(f"Pixel size configured: {pixel_size_nm:.3f} nm ({pixel_size_um:.6f} µm)")
    print("HDF5 dimension scales included for calibration")
    print("To open in BigDataViewer: File > Open XML > select the generated .xml file")

def create_bdv_xml(xml_path, h5_filename, image_shape, pixel_size_um):
    """Creates XML file in BigDataViewer format with correct calibration"""
    pixel_size_x = pixel_size_um
    pixel_size_y = pixel_size_um
    pixel_size_z = pixel_size_um  # For 2D images, use the same value
    affine_matrix = [
        pixel_size_x, 0.0, 0.0, 0.0,
        0.0, pixel_size_y, 0.0, 0.0,
        0.0, 0.0, pixel_size_z, 0.0
    ]
    xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<SpimData version="0.2">
  <BasePath type="relative">.</BasePath>
  <SequenceDescription>
    <ImageLoader format="bdv.hdf5">
      <hdf5 type="relative">{h5_filename}</hdf5>
    </ImageLoader>
    <ViewSetups>
      <ViewSetup>
        <id>0</id>
        <name>channel 1</name>
        <size>{image_shape[1]} {image_shape[0]} 1</size>
        <voxelSize>
          <unit>μm</unit>
          <size>{pixel_size_x} {pixel_size_y} {pixel_size_z}</size>
        </voxelSize>
        <attributes>
          <channel>1</channel>
        </attributes>
      </ViewSetup>
      <Attributes name="channel">
        <Channel>
          <id>1</id>
          <name>1</name>
        </Channel>
      </Attributes>
    </ViewSetups>
    <Timepoints type="range">
      <first>0</first>
      <last>0</last>
    </Timepoints>
  </SequenceDescription>
  <ViewRegistrations>
    <ViewRegistration timepoint="0" setup="0">
      <ViewTransform type="affine">
        <affine>{' '.join(map(str, affine_matrix))}</affine>
      </ViewTransform>
    </ViewRegistration>
  </ViewRegistrations>
</SpimData>'''
    with open(xml_path, 'w', encoding='utf-8') as f:
        f.write(xml_content)

class RedirectText(object):
    def __init__(self, text_widget):
        self.output = text_widget
    def write(self, string):
        self.output.configure(state='normal')
        self.output.insert(tk.END, string)
        self.output.see(tk.END)
        self.output.configure(state='disabled')
    def flush(self):
        pass

class OMEBatchConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("OME-TIFF Batch Converter")
        self.root.geometry("700x550")
        self.folder_path = tk.StringVar()
        self.recursive = tk.BooleanVar(value=True)
        self.create_h5 = tk.BooleanVar(value=False)  # New checkbox for H5 creation
        self.create_widgets()

    def create_widgets(self):
        # Folder selection frame
        folder_frame = ttk.Frame(self.root)
        folder_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(folder_frame, text="Folder:").pack(side=tk.LEFT)
        self.folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_path, width=50)
        self.folder_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(folder_frame, text="Browse", command=self.browse_folder).pack(side=tk.LEFT)
        ttk.Checkbutton(folder_frame, text="Recursive", variable=self.recursive).pack(side=tk.LEFT, padx=10)

        # Options frame
        options_frame = ttk.Frame(self.root)
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        # H5 creation checkbox
        ttk.Checkbutton(options_frame, text="Create H5 for large images (>2G pixels)", 
                       variable=self.create_h5).pack(anchor=tk.W)
        
        # Informational text
        info_label = ttk.Label(options_frame, 
                              text="If unchecked, reduced resolution image will be created for files >2G pixels",
                              font=('TkDefaultFont', 8), foreground='gray')
        info_label.pack(anchor=tk.W, padx=20)

        # Start button
        self.start_btn = ttk.Button(self.root, text="Start Batch Processing", command=self.start_processing)
        self.start_btn.pack(pady=10)

        # Progress bar
        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=600, mode="determinate")
        self.progress.pack(pady=5)

        # Log
        self.log_text = tk.Text(self.root, height=20, state='disabled', wrap='word')
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        sys.stdout = RedirectText(self.log_text)
        sys.stderr = RedirectText(self.log_text)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path.set(folder)

    def start_processing(self):
        self.start_btn.config(state='disabled')
        self.progress['value'] = 0
        threading.Thread(target=self.run_batch, daemon=True).start()

    def find_mrc_files(self, folder_path, recursive=True):
        """Finds all .mrc files in the folder"""
        mrc_files = []
        folder = Path(folder_path)
        
        if recursive:
            # Recursive search
            pattern = "**/*.mrc"
            mrc_files = list(folder.glob(pattern))
        else:
            # Search only in current folder
            pattern = "*.mrc"
            mrc_files = list(folder.glob(pattern))
        
        return mrc_files

    def process_mrc_file(self, mrc_file):
        """Processes an individual .mrc file"""
        try:
            # Check if corresponding .mdoc exists
            mdoc_file = mrc_file.with_suffix(mrc_file.suffix + ".mdoc")
            if not mdoc_file.exists():
                print(f"Warning: No .mdoc file found for {mrc_file.name}")
                return False
            
            # Get pixel size from .mdoc
            mag = get_mag(mdoc_file)
            if mag is None:
                print(f"Warning: Could not read pixel size from {mdoc_file.name}")
                return False
            
            print(f"Pixel size from .mdoc: {mag} Å")
            
            # === CYGWIN PROTOCOL SEQUENCE ===
            pasta = mrc_file.parent
            name = mrc_file.name
            stem = mrc_file.stem
            blf = f"{stem}_blended.mrc"
            cblf = pasta / f"{stem}_blended.mrc"
            
            # Convert paths to Cygwin
            fcigpath = windows_to_cygwin_path(pasta)
            cigpath = windows_to_cygwin_path(mrc_file)
            
            print(f"Running extractpieces for {name}...")
            run_cygwin_command(f"cd {fcigpath}; extractpieces {name} montage_plf")
            
            print(f"Running blendmont for {name}...")
            run_cygwin_command(rf"cd {fcigpath}; blendmont -imi {name} -pli montage_plf -imo {blf} -roo MONTAGE_EDGES")
            
            # Check if blended file was created
            if not cblf.exists():
                print(f"Error: Blended file {cblf} was not created")
                return False
            
            # Check image size for >2G pixels
            with mrcfile.open(cblf, permissive=True) as mrc:
                image_data = mrc.data
                if image_data.ndim == 3:
                    image_data = image_data[0]  # Use first slice if 3D
                
                total_pixels = image_data.shape[0] * image_data.shape[1]
                is_large_image = total_pixels > 2_000_000_000
            
            # Define output paths
            output_tiff = mrc_file.with_suffix('.ome.tif')
            output_h5 = mrc_file.with_suffix('.h5')
            output_tiff_reduced = mrc_file.parent / f"{mrc_file.stem}_reduced.ome.tif"
            
            # ALWAYS create original TIFF
            print(f"Creating original OME-TIFF: {output_tiff}")
            create_ome_bigtiff_pyramid(cblf, output_tiff, mag)
            
            # Handle large images (>2G pixels)
            if is_large_image:
                print(f"Large image detected ({total_pixels:,} pixels > 2G)")
                
                if self.create_h5.get():
                    # Create H5 file
                    print(f"Creating HDF5: {output_h5}")
                    create_hdf5_pyramid(cblf, output_h5, mag)
                    print("H5 file created for large image")
                else:
                    # Create reduced resolution TIFF
                    reduction_factor = calculate_reduction_factor(image_data.shape, 1_000_000_000)
                    print(f"Creating reduced resolution TIFF with {reduction_factor}x reduction: {output_tiff_reduced}")
                    create_ome_bigtiff_pyramid(cblf, output_tiff_reduced, mag, reduction_factor=reduction_factor)
                    print("Reduced resolution TIFF created for large image")
            
            # === CLEANUP TEMPORARY FILES ===
            print("Cleaning temporary files...")
            for file in pasta.glob('MONTAGE_EDGES*'):
                os.remove(file)
                print(f"Removed: {file}")
            for file in pasta.glob('montage_plf*'):
                os.remove(file)
                print(f"Removed: {file}")
            if cblf.exists():
                os.remove(cblf)
                print(f"Removed: {cblf}")
            
            return True
            
        except Exception as e:
            print(f"Error processing {mrc_file.name}: {str(e)}")
            return False

    def run_batch(self):
        folder = self.folder_path.get()
        if not folder:
            print("Please select a folder.")
            self.start_btn.config(state='normal')
            return
        
        print(f"Starting batch processing in: {folder}")
        print(f"Recursive search: {self.recursive.get()}")
        print(f"Create H5 for large images: {self.create_h5.get()}")
        
        # Find .mrc files
        mrc_files = self.find_mrc_files(folder, self.recursive.get())
        
        if not mrc_files:
            print("No .mrc files found in the selected folder.")
            self.start_btn.config(state='normal')
            return
        
        print(f"Found {len(mrc_files)} .mrc files:")
        for mrc_file in mrc_files:
            print(f"  - {mrc_file}")
        
        # Configure progress bar
        self.progress['maximum'] = len(mrc_files)
        
        # Process each file
        successful = 0
        for i, mrc_file in enumerate(mrc_files, 1):
            print(f"\n--- Processing {mrc_file.name} ({i}/{len(mrc_files)}) ---")
            
            if self.process_mrc_file(mrc_file):
                successful += 1
            
            self.progress['value'] = i
        
        print(f"\nBatch processing finished! {successful}/{len(mrc_files)} files processed successfully.")
        self.root.after(0, lambda: messagebox.showinfo("Done", f"Batch processing finished!\n{successful}/{len(mrc_files)} files processed successfully."))
        self.start_btn.config(state='normal')

if __name__ == "__main__":
    root = tk.Tk()
    app = OMEBatchConverterGUI(root)
    root.mainloop() 