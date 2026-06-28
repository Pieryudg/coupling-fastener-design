# Formula Derivations

本文档记录当前 Coupling Fastener Design app 中已经实现的公式链和工程等效推导。公式来源以当前 Python 代码为准：

- `coupling_calculations.py`: 简化 flange friction torque model。
- `standards.py`: standard-aware service factor guardrails。
- `ctp_calculations.py`: CTP 0007 cached-formula replica。
- `ctp_database.py` 和 `data/ctp_0007_seed.json`: CTP lookup seed。

> 注意：CTP 0007 当前实现是分阶段复刻。本文覆盖 app 已实现的全部计算公式和状态逻辑，不声明已经逐格复刻 Excel 全部 2243 条公式。

## 1. 符号和单位

除特别说明外：

| Symbol | Meaning | Unit |
| --- | --- | --- |
| `T` | torque | N*m |
| `F` | force / preload / clamp load | N |
| `d`, `D`, `r` | diameter / radius / length | mm |
| `A` | area | mm2 |
| `I` | second moment of area | mm4 |
| `sigma`, `tau` | normal / shear stress | MPa = N/mm2 |
| `mu` | friction coefficient | dimensionless |
| `SF` | safety factor | dimensionless |
| `n` | bolt count or thread count | dimensionless |

Unit conversions used in code:

```text
1 N*m = 1000 N*mm
T_Nm = T_Nmm / 1000
stress_MPa = force_N / area_mm2
```

## 2. Simple Coupling Friction Model

This model is implemented in `calculate()` and keeps the original simplified flange-friction workflow.

### 2.1 Effective Friction Radius

Inputs:

```text
r_i = inner friction radius
r_o = outer friction radius
```

Uniform wear assumes constant `p*r`, so the effective radius is the arithmetic mean:

```text
r_eff = (r_i + r_o) / 2
```

Uniform pressure integrates annular torque:

```text
dF = p * 2*pi*r*dr
dT = mu * dF * r

F = integral(p * 2*pi*r dr) from r_i to r_o
T = integral(mu * p * 2*pi*r^2 dr) from r_i to r_o
```

The effective radius is `T / (mu * F)`:

```text
r_eff = (2/3) * (r_o^3 - r_i^3) / (r_o^2 - r_i^2)
```

### 2.2 Design Torque Selection

The app compares steady-state selection torque, cyclic torque, and maximum transient torque:

```text
T_steady_selection = T_transmitted * service_factor
T_design = max(T_steady_selection, T_cyclic, T_transient)
```

`governing_torque_case` is the label associated with the maximum value.

### 2.3 Residual Pretension

Preload loss is entered as a percent:

```text
loss_factor = 1 - preload_loss_percent / 100
F_residual = F_initial * loss_factor
F_clamp_residual_total = F_residual * bolt_count
```

### 2.4 Slip Torque Capacity

Friction torque capacity follows `T = mu * F * r`, multiplied by the number of friction interfaces. Because radius is in mm, divide by `1000`:

```text
T_slip = mu * F_clamp_residual_total * r_eff * friction_interfaces / 1000
SF_slip = T_slip / T_design
```

If `T_design = 0`, slip safety is reported as infinity.

### 2.5 Required Clamp and Required Initial Preload

Invert the slip capacity equation to find the residual clamp required for the selected design torque:

```text
F_required_residual_total =
    T_design * 1000 / (mu * r_eff * friction_interfaces)

F_required_residual_per_bolt =
    F_required_residual_total / bolt_count

F_required_initial_per_bolt =
    F_required_residual_per_bolt / loss_factor
```

### 2.6 Bolt Yield and Proof Checks

Bolt material strength comes from the local metric bolt database:

```text
F_yield = yield_strength * tensile_stress_area
F_proof = proof_strength * tensile_stress_area
```

Utilizations:

```text
assembly_yield_utilization = F_initial / F_yield
required_preload_yield_utilization = F_required_initial_per_bolt / F_yield
```

Warnings are raised when utilization exceeds the selected `max_yield_utilization`, or when `F_initial > F_proof`.

### 2.7 Bolt-Joint Axial Load Split

The optional separating axial load per bolt is split using a two-spring model:

```text
phi = k_bolt / (k_bolt + k_joint)
```

Additional bolt load and remaining joint clamp:

```text
F_bolt_service = F_residual + phi * F_separating
F_residual_service = F_residual - (1 - phi) * F_separating
service_yield_utilization = F_bolt_service / F_yield
```

Joint separation is reported when:

```text
F_residual_service <= 0
```

### 2.8 Standard-Aware Guardrails

`standards.py` defines selectable coupling profiles. Each profile contributes a minimum service factor:

| Profile key | Label | Minimum service factor |
| --- | --- | ---: |
| `metallic_flexible_element` | Metallic flexible element | 1.5 |
| `gear` | Gear coupling | 1.75 |
| `torsional_resilient` | Torsional damping or resilient | 3.0 |
| `quill_shaft` | Quill-shaft coupling | 1.5 |
| `agreed_reduced_metallic` | Agreed reduced metallic flexible | 1.2 |

The warning check is:

```text
service_factor < profile.minimum_service_factor
```

The standard guardrails also state that the governing torque is the largest of steady-state selection, cyclic, and transient inputs, and that stiffness, bore, keyway, fit, and balance checks remain outside this friction sizing model.

## 3. CTP 0007 Formula Chain

This section documents `calculate_ctp()` and the helper functions in `ctp_calculations.py`.

### 3.1 Lookup and Default Seed

Default CTP seed:

```text
TYPE = 1512
Size = 47xx
Material = 0225 (Classe 12-9)
Screw/Nut friction = Emuge+Oil
Nut/Part friction = Light Oil
Part/Part friction = API 671
Reference = TSKW/0360/KA/GA253480 Hub Bolts
```

Default geometry and material:

```text
d = 16.0 mm
p = 2.0 mm
shank_diameter = 8.0 mm
contact_diameter = 24.0 mm
PCD = 447.0 mm
screw_count = 10
yield_strength = 1080 MPa
standard_tightening_torque = 365 N*m
```

Default friction coefficients:

```text
mu_screw_nut = 0.155
mu_nut_part = 0.120
mu_part_part = 0.150
```

Custom friction labels override the lookup value only when the selected label is `Custom` and a custom value is supplied.

### 3.2 Thread Geometry

For ISO metric thread approximation:

```text
d2 = d - 0.6495 * p
d3 = d - 1.2268 * p
d_tensile = (d2 + d3) / 2
A_t = pi * d_tensile^2 / 4
```

The code writes `A_t` equivalently as:

```text
A_t = ((d2 + d3) / 4)^2 * pi
```

Shear/bending diameter depends on the selected shear plane:

```text
d_sb = shank_diameter       when shear_plane = Shank
d_sb = d_tensile           when shear_plane = Thread
```

### 3.3 Nut Bearing Effective Radius

The nut/part friction torque uses an annular effective radius between the pitch-diameter radius and contact radius:

```text
r_i = d2 / 2
r_o = contact_diameter / 2
R_nut = (2/3) * (r_o^3 - r_i^3) / (r_o^2 - r_i^2)
```

This is the same uniform-pressure annular radius derivation as the simple friction model.

### 3.4 Tightening Torque to Preload

The tightening torque equation is implemented as:

```text
T_tight = F_preload *
          (0.16*p + 0.583*mu_screw_nut*d2 + mu_nut_part*R_nut) / 1000
```

The denominator is:

```text
K_t = 0.16*p + 0.583*mu_screw_nut*d2 + mu_nut_part*R_nut
```

So:

```text
F_preload = 1000 * T_tight / K_t
```

The three terms represent:

```text
0.16*p                         thread helix / pitch term
0.583*mu_screw_nut*d2          screw/nut thread friction term
mu_nut_part*R_nut              nut/part bearing friction term
```

Preload source precedence:

```text
if manual tightening_torque_nm is nonzero:
    F_preload = 1000 * tightening_torque_nm / K_t
elif preload_percent_of_yield is nonzero:
    F_preload = preload_percent_of_yield * A_t * yield_strength / 100
    T_tight = K_t * F_preload / 1000
elif standard_tightening_torque_nm exists:
    F_preload = 1000 * standard_tightening_torque_nm / K_t
else:
    F_preload = 0
    T_tight = 0
```

This precedence matches the current app behavior: entered torque overrides percent tensile yield, which overrides the standard table.

### 3.5 Tightening Torque Components

Nut/part bearing friction torque:

```text
T_nut_friction = mu_nut_part * R_nut * F_preload / 1000
```

Thread tightening torque:

```text
T_thread =
    (0.16*p + 0.583*mu_screw_nut*d2) * F_preload / 1000
```

The sum of `T_nut_friction + T_thread` equals the tightening torque from section 3.4, except for floating point rounding.

### 3.6 Flange Friction Torque

The flange friction radius is the bolt pitch-circle radius:

```text
r_pcd = PCD / 2
```

Each screw contributes clamp `F_preload`, so the total torque capacity is:

```text
T_friction =
    F_preload * screw_count * mu_part_part * PCD / 2 / 1000
```

This corresponds to Excel baseline `P43` in the CTP Phase 1 tests.

### 3.7 Torque Cases

The app evaluates three duty cases:

```text
T_continuous = continuous_torque_nm
T_peak = T_continuous * peak_factor
T_momentary = T_peak * momentary_factor
```

Default values:

```text
continuous = 40100 N*m
peak_factor = 2.0
momentary_factor = 1.15
momentary = 40100 * 2.0 * 1.15 = 92230 N*m
```

### 3.8 Torque Ratio and Residual Shear

Torque ratio:

```text
torque_ratio = T_friction / T_case
```

If `T_case = 0`, the status is `Torque ?`.

Residual torque after friction capacity:

```text
T_residual = max(0, T_case - T_friction)
```

Residual shear load per fastener follows torque equilibrium at pitch-circle radius:

```text
T_residual_Nmm = T_residual * 1000
r_pcd = PCD / 2

F_residual_shear =
    T_residual_Nmm / (r_pcd * screw_count)
  = 2000 * T_residual / (PCD * screw_count)
```

If `T_residual = 0`, residual shear is `0`.

### 3.9 Sleeve Load Share and Sleeve Stress

Sleeve is active only when:

```text
sleeve_outer_diameter_mm > 0
```

When active, the code estimates sleeve share with an area-ratio equivalent:

```text
F_sleeve =
    F_residual_shear *
    (sleeve_OD^2 - d^2) / sleeve_OD^2
```

Bolt shear load is the remaining load:

```text
F_bolt_shear = F_residual_shear - F_sleeve
```

Sleeve section inertia:

```text
I_sleeve = pi/64 * (sleeve_OD^4 - d^4)
```

Sleeve bending stress:

```text
sigma_sleeve_bending =
    F_sleeve * leverarm * (sleeve_OD / 2) / I_sleeve
```

Sleeve shear stress uses the gross sleeve circular area in the current implementation:

```text
tau_sleeve =
    F_residual_shear / (pi/4 * sleeve_OD^2)
```

Von Mises equivalent stress and safety factor:

```text
sigma_vm_sleeve =
    sqrt(sigma_sleeve_bending^2 + 3*tau_sleeve^2)

SF_sleeve = sleeve_yield_strength / sigma_vm_sleeve
```

If the sleeve is inactive or equivalent stress is zero, sleeve status is `No Sleeve` and no numeric sleeve SF is included in the minimum-SF calculation.

### 3.10 Bolt Shear, Bending, Axial Stress

Bolt axial stress from preload:

```text
sigma_bolt_axial =
    F_preload / (pi/4 * d_sb^2)
  = 4 * F_preload / (pi * d_sb^2)
```

Bolt bending inertia:

```text
I_bolt = pi/64 * d_sb^4
```

Bolt bending stress:

```text
sigma_bolt_bending =
    F_bolt_shear * leverarm * (d_sb / 2) / I_bolt
```

Bolt shear stress:

```text
tau_bolt =
    F_bolt_shear / (pi/4 * d_sb^2)
```

The current engineering equivalent combines axial and bending normal stresses linearly before Von Mises:

```text
sigma_vm_bolt =
    sqrt((sigma_bolt_axial + sigma_bolt_bending)^2 + 3*tau_bolt^2)

SF_bolt = material_yield_strength / sigma_vm_bolt
```

If `sigma_vm_bolt = 0`, the status is `N/A`.

### 3.11 Groove Stress

Groove calculations are active only when:

```text
groove_diameter > 0
```

If no groove diameter is present, axial and twist statuses are `No groove`, and groove SF is blank.

When active:

```text
sigma_groove_axial =
    4 * F_preload / (pi * groove_diameter^2)
```

Thread torque is converted from N*m to N*mm:

```text
tau_groove_twist =
    16 * T_thread * 1000 / (pi * groove_diameter^3)
```

Von Mises and safety factor:

```text
sigma_vm_groove =
    sqrt(sigma_groove_axial^2 + 3*tau_groove_twist^2)

SF_groove = material_yield_strength / sigma_vm_groove
```

### 3.12 Thread-Root Assembly Stress

Thread-root axial stress uses tensile stress area:

```text
sigma_thread_root_axial = F_preload / A_t
```

Thread-root torsional shear stress uses root diameter `d3`:

```text
J = pi/32 * d3^4
tau_thread_root =
    T_thread * 1000 * (d3 / 2) / J
```

Equivalent simplified form:

```text
tau_thread_root =
    16 * T_thread * 1000 / (pi * d3^3)
```

Von Mises and safety factor:

```text
sigma_vm_thread_root =
    sqrt(sigma_thread_root_axial^2 + 3*tau_thread_root^2)

SF_thread_root =
    material_yield_strength / sigma_vm_thread_root
```

This corresponds to the Phase 1 golden value `U76`.

### 3.13 Thread Engagement and First-Thread Pull-Out Stress

Minimum thread engagement:

```text
L_e = entered_thread_engagement_mm
      if supplied
      else 1.2 * d
```

Engaged thread count:

```text
n_e = L_e / p
```

Pull-out shear area:

```text
A_pullout = pi/2 * d2 * L_e
```

First-thread load factor depends on the screw/nut friction label.

For labels containing `Emuge` or `Prevailing`:

```text
k_first =
    0.001762*n_e^3
  - 0.028314*n_e^2
  + 0.182016*n_e
  + 0.720405
```

For all other labels:

```text
k_first =
    0.002317*n_e^3
  - 0.039254*n_e^2
  + 0.416953*n_e
  + 0.436158
```

The factor is clamped to at least `1.0`:

```text
k_first = max(1.0, k_first)
```

First-thread pull-out stress:

```text
sigma_first_thread_pullout =
    sigma_thread_root_axial * A_t / A_pullout * k_first
```

Because `sigma_thread_root_axial * A_t = F_preload`, this is equivalently:

```text
sigma_first_thread_pullout =
    F_preload / A_pullout * k_first
```

### 3.14 Minimum Safety Factor

The minimum safety factor includes numeric values from:

```text
all torque-case sleeve SF values
all torque-case bolt SF values
groove SF, when numeric
thread-root SF
```

Formula:

```text
minimum_safety_factor = min(all_numeric_safety_factors)
```

Non-numeric statuses such as `No Sleeve`, `No groove`, `N/A`, and `Torque ?` are excluded.

Current implementation note: torque ratio and first-thread pull-out stress are reported, but they are not included as numeric safety factors in `minimum_safety_factor`.

### 3.15 Check Summary

The check summary starts with the rounded minimum safety factor:

```text
{minimum_safety_factor} Check:
```

Thresholds for sleeve and bolt case checks:

| Case | Threshold |
| --- | ---: |
| continuous | 1.50 |
| peak | 1.25 |
| momentary | 1.10 |

Summary terms are appended when:

```text
groove SF is numeric and < 1.10:
    "Min groove diameter"

any sleeve SF is numeric and below its case threshold:
    "+ Sleeve outer diameter"

any bolt SF is numeric and below its case threshold:
    "+ critical shear and bending plane"  when leverarm != 0
    "+ critical shear plane"             when leverarm == 0

thread-root SF is numeric and < 1.10:
    "+ Axial pretension in screw+{screw_nut_friction_label}"
```

Warnings are generated when:

```text
minimum_safety_factor < 1.0
torque_ratio < 1.0 for any case
groove SF < 1.10
thread-root SF < 1.10
```

If no warnings exist:

```text
All CTP 0007 checks pass.
```

## 4. CTP Goal Seek Equivalent Solvers

The Excel template includes Goal Seek comments. The app implements deterministic bisection-style equivalents.

### 4.1 Sleeve OD Solver

Function:

```text
solve_sleeve_od(inputs, target_sf=1.0)
```

Search variable:

```text
sleeve_outer_diameter_mm
```

Initial bracket:

```text
lower = max(d * 1.001, 0.001)
upper = max(lower * 2, d * 3)
```

If `lower` already satisfies the target sleeve SF, the solver returns immediately. Otherwise it expands:

```text
upper = upper * 1.6
```

until either the target is bracketed or:

```text
upper >= d * 20
```

Then it bisects until:

```text
abs(upper - lower) < 1e-6
```

Failure message:

```text
Target sleeve safety factor is not bracketed.
```

### 4.2 Bending Torque Share Solver

Function:

```text
solve_bending_torque_share(inputs, target_sf=1.00001)
```

This solver searches for the largest momentary torque that still satisfies the target momentary bolt SF.

Base peak torque:

```text
T_peak_base = continuous_torque * peak_factor
```

Search variable is expressed through `momentary_factor`:

```text
momentary_factor = T_momentary_trial / T_peak_base
```

The solver expands the high torque while the momentary bolt SF remains above target:

```text
while SF_momentary_bolt(high) >= target_sf:
    low = high
    high = high * 1.6
```

Failure if:

```text
T_peak_base <= 0
high > T_peak_base * 1000
```

Then it bisects to the maximum acceptable momentary torque.

### 4.3 Preload for Bending Solver

Function:

```text
solve_preload_for_bending(inputs, target_sf=1.00001, max_torque_nm=2000)
```

Search variable:

```text
tightening_torque_nm
```

For each trial torque:

```text
preload_percent_of_yield = None
standard_tightening_torque_nm = None
F_preload = 1000 * tightening_torque_nm / K_t
```

The solver samples `80` torque points from `0` to `max_torque_nm` and finds a bracket where the minimum bolt SF crosses from satisfying to failing:

```text
previous_sf >= target_sf and current_sf < target_sf
```

Then it bisects that bracket. Current behavior therefore finds the largest tightening torque/preload that still keeps bolt bending SF at or above the target.

Failure message:

```text
Target preload safety factor is not bracketed.
```

## 5. Input Validation

CTP validation rejects:

```text
thread_diameter <= 0
pitch <= 0
PCD <= 0
screw_count < 1
contact_diameter <= thread_diameter
leverarm < 0
shear_plane not in {Thread, Shank}
continuous_torque < 0
peak_factor < 0
momentary_factor < 0
any friction coefficient <= 0
material yield <= 0
sleeve yield <= 0
```

Simple model validation rejects negative torque inputs, nonpositive service factor, invalid radius geometry, nonpositive stiffnesses, invalid preload loss percent, and yield utilization limits outside `(0, 1]`.

## 6. Default CTP Golden Baseline

The current tests compare the Python replica against cached values from `/Volumes/Seagate/04. Calculation Sheets/Calculation sheets/CTP 0007.xltx`.

Expected default results:

| Result | Value |
| --- | ---: |
| `preload_n` | `128891.948946884` |
| `friction_torque_nm` | `43211.025884442861` |
| momentary `torque_ratio` | `0.468513779512554` |
| momentary `bolt_safety_factor` | `1.2536471142890915` |
| `thread_root_safety_factor` | `0.9677950537105884` |
| `check_summary` | contains `0.968 Check` |

These values are asserted in `tests/test_ctp_0007.py`.

## 7. Implementation Traceability

| Topic | Code |
| --- | --- |
| Simple effective radius and slip capacity | `coupling_calculations.py::effective_radius`, `calculate` |
| Standard profile thresholds | `standards.py` |
| CTP geometry, preload, torque, stress chain | `ctp_calculations.py::calculate_ctp` |
| CTP torque-case stress calculations | `ctp_calculations.py::_calculate_case` |
| CTP groove stress | `ctp_calculations.py::_calculate_groove` |
| CTP first-thread factor | `ctp_calculations.py::_first_thread_load_factor` |
| CTP minimum SF and summary text | `ctp_calculations.py::_minimum_safety_factor`, `_check_summary`, `_warnings` |
| Goal Seek equivalents | `ctp_calculations.py::solve_sleeve_od`, `solve_bending_torque_share`, `solve_preload_for_bending` |
| CTP lookup seed | `data/ctp_0007_seed.json` |
