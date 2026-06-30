# CTP0007 Issue H Calculation Procedure

This document describes the calculation procedure implemented in `coupling_calculations.py` for the CTP0007 Issue H desktop application. Units are N, mm, MPa, and Nm unless otherwise noted. MPa is treated as N/mm2.

## 1. Input Selection

The screw type and size select a screw record from the embedded CTP 0007 lookup data. For `SPECIAL` screws, the user-entered geometry is used where applicable.

Material yield strength is selected from the material database unless the editable `TYS MPa` field is changed by the user.

Tightening input priority is:

1. User-entered tightening torque.
2. User-entered percent of tensile yield strength, `% TYS`.
3. Standard tightening torque from the selected screw type, size, and material.

If both tightening torque and `% TYS` are entered, the calculation is rejected.

## 2. Geometry

Definitions:

- `d` = thread major diameter
- `p` = thread pitch
- `ds` = shank diameter
- `dg` = groove diameter
- `dc` = contact diameter
- `Sy` = bolt tensile yield strength
- `n` = screw count
- `PCD` = pitch circle diameter

Thread pitch diameter:

```text
dp = d - 0.6495 * p
```

Thread root diameter:

```text
dr = d - 1.2268 * p
```

Tensile stress diameter:

```text
dt = (dp + dr) / 2
```

Tensile stress area:

```text
As = pi * ((dp + dr) / 4)^2
```

Shear and bending diameter:

```text
dsb = dt    when shear plane is Thread
dsb = ds    when shear plane is Shank
```

Contact diameter:

```text
dc = special contact diameter    for SPECIAL screws
dc = special contact diameter    when Nut contact is Special and value > 0
dc = standard record contact diameter otherwise
```

Average annular nut/contact radius:

```text
Ro = dc / 2
Ri = dp / 2
Rn = (2 / 3) * ((Ro^3 - Ri^3) / (Ro^2 - Ri^2))
```

The contact diameter must be greater than the pitch diameter.

## 3. Effective Lever Arm

Effective shear/bending lever arm:

```text
Leff = 0.05 mm                         for Stripper bolt
Leff = 0.15 * pack_thickness_mm        for Drive bolt
Leff = 0.15 * pack_thickness_mm        for Shim
```

Drive bolt and Shim require a positive pack thickness. Stripper bolt uses `N/A` pack thickness.

## 4. Tightening, Pretension, and Friction Torque

Friction definitions:

- `mu_sn` = screw/nut friction coefficient
- `mu_np` = nut/part friction coefficient
- `mu_pp` = part/part friction coefficient
- `Tt` = selected tightening torque
- `Fv` = axial pretension

Axial pretension from tightening torque:

```text
Fv = 1000 * Tt / (0.16 * p + 0.583 * mu_sn * dp + mu_np * Rn)
```

Axial pretension from `% TYS`:

```text
Fv = (%TYS / 100) * As * Sy
```

Reported tightening torque when `% TYS` is used:

```text
Tt_reported = (0.16 * p + 0.583 * mu_sn * dp + mu_np * Rn) * Fv / 1000
```

Preload percent of tensile yield strength:

```text
preload_%TYS = Fv / (As * Sy) * 100
```

Nut/part friction torque component:

```text
T_np = mu_np * Rn * Fv / 1000
```

Torsional tightening torque in the screw:

```text
T_torsion = (0.16 * p + 0.583 * mu_sn * dp) * Fv / 1000
```

Flange friction torque capacity:

```text
T_friction = Fv * n * mu_pp * PCD / 2 / 1000
```

Friction torque ratio is displayed as information:

```text
ratio_% = T_friction / T_duty * 100
```

Friction torque lower than duty torque is not a warning by itself. Any uncovered torque is carried forward into the bolt shear/bending calculation.

## 5. Duty Torque Cases

The app evaluates three duty torque cases:

- Continuous
- Peak
- Momentary

For each case:

```text
T_residual = max(0, T_duty - T_friction)
V_total = 2000 * T_residual / (PCD * n)
```

`V_total` is the shear load per joint/bolt station.

If a sleeve is present and sleeve OD is greater than the thread major diameter:

```text
V_sleeve = V_total * (OD^2 - d^2) / OD^2
V_bolt = V_total - V_sleeve
```

If no sleeve is present:

```text
V_sleeve = 0
V_bolt = V_total
```

## 6. Sleeve Stress and Safety Factor

Sleeve check is only numeric when `sleeve OD > d`. Otherwise the result is `No Sleeve`.

Sleeve bending stress:

```text
I_sleeve = pi / 64 * (OD^4 - d^4)
sigma_b_sleeve = V_sleeve * Leff * OD / 2 / I_sleeve
```

Sleeve shear stress, as implemented:

```text
tau_sleeve = V_total / (pi / 4 * OD^2)
```

Sleeve Von Mises stress:

```text
VM_sleeve = sqrt(sigma_b_sleeve^2 + 3 * tau_sleeve^2)
```

Sleeve yield safety factor:

```text
SF_sleeve = sleeve_yield / VM_sleeve
```

Sleeve material options:

```text
GMC 0401  = 245 MPa
GMC 0336  = 650 MPa
GMC0433   = 800 MPa
```

When sleeve OD is `N/A`, sleeve material and sleeve yield are `N/A`.

## 7. Bolt Shear/Bending Area Stress and Safety Factor

Bolt axial stress:

```text
sigma_axial = 4 * Fv / (pi * dsb^2)
```

Bolt bending stress:

```text
I_bolt = pi / 64 * dsb^4
sigma_b_bolt = V_bolt * Leff * dsb / 2 / I_bolt
```

Bolt shear stress:

```text
tau_bolt = V_bolt / (pi / 4 * dsb^2)
```

Bolt maximum Von Mises stress:

```text
VM_bolt = sqrt((sigma_axial + sigma_b_bolt)^2 + 3 * tau_bolt^2)
```

Bolt yield safety factor:

```text
SF_bolt = Sy / VM_bolt
```

The table column `Maxi Stress (VM) MPa` reports `VM_bolt`.

## 8. Assembly Stress in Groove Area

If `dg <= 0`, the result is `No groove`.

Groove axial stress:

```text
sigma_groove = 4 * Fv / (pi * dg^2)
```

Groove twisting stress:

```text
tau_groove = 16 * T_torsion * 1000 / (pi * dg^3)
```

Groove Von Mises stress:

```text
VM_groove = sqrt(sigma_groove^2 + 3 * tau_groove^2)
```

Groove yield safety factor:

```text
SF_groove = Sy / VM_groove
```

## 9. Assembly Stress in Thread Root Area

Thread-root axial stress:

```text
sigma_thread = Fv / As
```

Thread-root twisting stress:

```text
tau_thread = T_torsion * 1000 * dr / 2 / (pi / 32 * dr^4)
```

Thread-root Von Mises stress:

```text
VM_thread = sqrt(sigma_thread^2 + 3 * tau_thread^2)
```

Thread-root yield safety factor:

```text
SF_thread_root = Sy / VM_thread
```

## 10. Thread Pull-Out Stress

Thread engagement:

```text
L = user-entered engagement
L = 1.2 * d    when thread engagement mode is Thread/default
```

Thread pull-out area:

```text
A_pullout = pi / 2 * dp * L
```

Engaged thread quantity:

```text
N_engaged = L / p
```

First-thread load factor for `Emuge` or `Prevailing` screw/nut friction presets:

```text
K = max(1,
        0.001762 * N_engaged^3
      - 0.028314 * N_engaged^2
      + 0.182016 * N_engaged
      + 0.720405)
```

First-thread load factor for other screw/nut friction presets:

```text
K = max(1,
        0.002317 * N_engaged^3
      - 0.039254 * N_engaged^2
      + 0.416953 * N_engaged
      + 0.436158)
```

Thread pull-out stress:

```text
sigma_pullout = Fv / A_pullout * K
```

The tapped-hole yield strength field is optional. If entered, tapped-hole yield must be greater than or equal to thread pull-out stress.

## 11. Minimum Safety Factor

The reported minimum safety factor is the minimum of all numeric safety factors:

```text
minimum_SF = min(
    all bolt shear/bending SF values,
    groove SF when groove exists,
    thread-root SF,
    all sleeve SF values when sleeve exists
)
```

## 12. Checking Criteria

### 12.1 API 671 5th Edition

Yield safety factor limits for bolt shear/bending and sleeve area:

```text
Continuous torque: SF >= 1.50
Peak torque:       SF >= 1.15
Momentary torque:  SF >= 1.00
```

### 12.2 API 671 4th Edition

Yield safety factor limits for bolt shear/bending and sleeve area:

```text
Continuous torque: SF >= 1.25
Peak torque:       SF >= 1.15
Momentary torque:  SF >= 1.00
```

### 12.3 Groove Area

```text
SF_groove >= 1.10
```

### 12.4 Thread Root Area

```text
SF_thread_root >= 1.00 required
SF_thread_root >= 1.10 preferred
```

The preferred value is used because residual torque can reduce by about 20 percent upon loading.

### 12.5 Tightening Preload Percent

```text
Stripper bolt: preload_%TYS <= 60
Shim:          preload_%TYS <= 60
Drive bolt:    preload_%TYS <= 75
```

### 12.6 Thread Pull-Out

```text
tapped_hole_yield >= sigma_pullout
```

If tapped-hole yield is blank or zero, the app reports the pull-out stress with a note rather than a pass/fail result.

## 13. Input Validation

The calculation rejects invalid input before solving:

- `PCD > 0`
- `screw_count >= 1`
- `thread > 0`
- `pitch > 0`
- checking standard must be recognized
- joint type must be recognized
- pack thickness must be zero or positive
- Drive bolt and Shim require positive pack thickness
- contact diameter must be greater than zero
- tightening torque and `% TYS` cannot both be entered
- screw/nut, nut/part, and part/part friction coefficients must be greater than zero
- sleeve OD must be zero or positive
- tapped-hole yield must be zero or positive
- lever arm must be zero or positive

## 14. Legacy Quick Friction Model Appendix

The module retains an older quick friction fastener model for compatibility and tests. It is not the main CTP0007 Issue H GUI workflow.

Effective friction radius:

```text
r_eff = (inner_radius + outer_radius) / 2
```

when the radius model is uniform wear, otherwise:

```text
r_eff = (2 / 3) * ((outer_radius^3 - inner_radius^3) /
                   (outer_radius^2 - inner_radius^2))
```

Design torque:

```text
T_steady = transmitted_torque * service_factor
T_design = max(T_steady, cyclic_torque, transient_torque)
```

Residual pretension after preload loss:

```text
F_residual = F_initial * (1 - preload_loss_percent / 100)
```

Slip torque capacity:

```text
T_slip = mu * (F_residual * bolt_count) * r_eff * friction_interfaces / 1000
SF_slip = T_slip / T_design
```

Required clamp load:

```text
F_required_total = T_design * 1000 / (mu * r_eff * friction_interfaces)
F_required_per_bolt = F_required_total / bolt_count
F_required_initial = F_required_per_bolt / (1 - preload_loss_percent / 100)
```

Bolt yield and proof loads:

```text
F_yield = yield_strength * tensile_area
F_proof = proof_strength * tensile_area
```

Bolt/joint stiffness split:

```text
phi = k_bolt / (k_bolt + k_joint)
F_bolt_service = F_residual + phi * F_axial
F_residual_service = F_residual - (1 - phi) * F_axial
```

Yield utilization values:

```text
assembly_yield_utilization = F_initial / F_yield
service_yield_utilization = F_bolt_service / F_yield
required_preload_yield_utilization = F_required_initial / F_yield
```

Legacy quick model warnings include low service factor, transient/cyclic torque governing, slip capacity below demand, preload/yield utilization above the selected limit, preload above proof load, and joint separation.
