# CTP0007 Issue H

Independent native desktop GUI app for CTP 0007-style bolted joint core
checking. The main app is built with PySide6/Qt and uses a local SQLite
database for migrated screw, material, friction, and legacy metric bolt data.

The calculation workflow includes standard-aware guardrails derived from the local John Crane knowledge base:

- API 671 style coupling profiles apply minimum service-factor checks for metallic flexible element, gear, torsional damping/resilient, quill-shaft, and agreed reduced metallic flexible applications.
- Design torque is governed by the largest entered steady-state selection torque, cyclic torque, or maximum transient torque.
- AGMA 9104 mass-elastic guidance is treated as a boundary condition for this app: bolt/joint stiffness remains a vendor, measured, or user-entered value rather than an inferred AGMA value.
- AGMA bore, keyway, fit, and balance requirements are flagged as separate checks outside this friction fastener sizing model.

The app uses a local SQLite database generated at startup:

```text
data/metric_bolts.sqlite
```

The database stores ISO metric coarse bolt sizes from `M3` through `M48`, bolt
property classes, CTP material yield strengths, CTP friction presets, and the
CTP 0007 screw lookup rows migrated from the hidden `Donnees Vis` sheet. The
type and size dropdowns are seeded in the same order as the spreadsheet lookup
table, including the standard screw families and `SPECIAL` manual entry.

## Run

macOS setup:

```bash
chmod +x setup_macos.command run_macos.command
./setup_macos.command
```

macOS run:

```bash
./run_macos.command
```

Windows setup:

```powershell
.\setup_windows.ps1
```

Windows Command Prompt run:

```bat
run_windows.cmd
```

Windows PowerShell:

```powershell
.\run_windows.ps1
```

Native app dependency:

```text
PySide6
```

Optional Windows `.exe` build, from PowerShell on Windows:

```powershell
.\build_windows_exe.ps1
```

The executable is written to:

```text
dist\CTP0007 Issue H.exe
```

The detailed calculation procedure is provided as Word and PDF copies. The
procedure includes a cross-reference to the source `CTP 0007.xltx` spreadsheet
cells used by each calculation block:

```text
docs/CTP0007_Issue_H_Calculation_Procedure.docx
docs/CTP0007_Issue_H_Calculation_Procedure.pdf
```

Optional macOS `.app` build:

```bash
chmod +x build_macos_app.command
./build_macos_app.command
```

## Model

The main desktop workflow follows the CTP 0007 core calculation:

- Select or enter screw identity, material, joint geometry, friction presets,
  duty torque cases, and tightening basis.
- Derive thread geometry, tensile stress area, tightening preload, and flange
  friction torque.
- Report continuous, peak, and momentary torque capability, residual torque,
  shear load, bolt safety factors, assembly groove/thread-root checks, and
  warnings.

The original quick friction model is still present in the calculation module
for compatibility and tests.

Quick friction torque capacity:

```text
T_slip = mu * F_clamp,residual,total * r_eff * n_interfaces
T_design = max(T_transmitted * service_factor, T_cyclic, T_transient)
```

Bolt material yield check:

```text
F_yield = yield_strength * tensile_stress_area
yield_utilization = bolt_load / F_yield
```

Residual pretension after preload loss:

```text
F_residual = F_initial * (1 - preload_loss)
```

For the bolt-joint triangle, an optional separating axial load per bolt is split by bolt and joint stiffness:

```text
phi = k_bolt / (k_bolt + k_joint)
F_bolt,service = F_residual + phi * F_axial
F_residual,service = F_residual - (1 - phi) * F_axial
```

The canvas illustrates initial preload, residual pretension, residual pretension after axial load, and the bolt yield load.
