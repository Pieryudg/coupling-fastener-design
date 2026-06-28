# Coupling Fastener Desktop App

Independent native desktop GUI app for friction-type flange coupling fastener sizing. The main app is built with PySide6/Qt and uses a local SQLite bolt database.

The calculation workflow includes standard-aware guardrails derived from the local John Crane knowledge base:

- API 671 style coupling profiles apply minimum service-factor checks for metallic flexible element, gear, torsional damping/resilient, quill-shaft, and agreed reduced metallic flexible applications.
- Design torque is governed by the largest entered steady-state selection torque, cyclic torque, or maximum transient torque.
- AGMA 9104 mass-elastic guidance is treated as a boundary condition for this app: bolt/joint stiffness remains a vendor, measured, or user-entered value rather than an inferred AGMA value.
- AGMA bore, keyway, fit, and balance requirements are flagged as separate checks outside this friction fastener sizing model.

The app uses a local SQLite database generated at startup:

```text
data/metric_bolts.sqlite
```

The database stores ISO metric coarse bolt sizes from `M3` through `M48` with pitch and tensile stress area, plus bolt material property classes `8.8`, `10.9`, and `12.9`.

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

## CTP 0007 mode

The desktop app now includes a CTP 0007 calculation mode alongside the
original simplified friction model. The first CTP implementation uses a
versioned seed extracted from cached values in:

```text
/Volumes/Seagate/04. Calculation Sheets/Calculation sheets/CTP 0007.xltx
```

The seed is stored at:

```text
data/ctp_0007_seed.json
```

The CTP mode covers the Phase 1 direct formula chain from the workbook:
tightening torque to preload, flange friction torque, residual shear,
bolt/sleeve stress status, thread-root assembly stress, first-thread
pull-out stress, and the combined check summary. Engineering-equivalent
Goal Seek helpers are implemented in the pure calculation module.

Full formula derivations are documented in
[`docs/formula_derivations.md`](docs/formula_derivations.md).

Optional Windows `.exe` build, from PowerShell on Windows:

```powershell
.\build_windows_exe.ps1
```

The executable is written to:

```text
dist\CouplingFastenerDesign.exe
```

Optional macOS `.app` build:

```bash
chmod +x build_macos_app.command
./build_macos_app.command
```

## Model

Friction torque capacity:

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
