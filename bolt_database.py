from __future__ import annotations

import ast
import sqlite3
from dataclasses import dataclass
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DATABASE_PATH = DATA_DIR / "metric_bolts.sqlite"


@dataclass(frozen=True)
class BoltSize:
    designation: str
    diameter_mm: float
    pitch_mm: float
    tensile_area_mm2: float


@dataclass(frozen=True)
class PropertyClass:
    name: str
    ultimate_mpa: float
    yield_mpa: float
    proof_mpa: float


@dataclass(frozen=True)
class CtpScrewRecord:
    screw_type: str
    size: str
    thread_mm: float
    pitch_mm: float
    shank_diameter_mm: float
    groove_diameter_mm: float
    contact_diameter_mm: float
    thread_type: str
    primary_material: str
    secondary_material: str
    standard_torques_nm: dict[str, float]


@dataclass(frozen=True)
class CtpMaterial:
    code: str
    yield_mpa: float


@dataclass(frozen=True)
class CtpFrictionPreset:
    name: str
    coefficient: float


BOLT_SIZES = [
    ("M3", 3.0, 0.5, 5.03),
    ("M4", 4.0, 0.7, 8.78),
    ("M5", 5.0, 0.8, 14.2),
    ("M6", 6.0, 1.0, 20.1),
    ("M8", 8.0, 1.25, 36.6),
    ("M10", 10.0, 1.5, 58.0),
    ("M12", 12.0, 1.75, 84.3),
    ("M14", 14.0, 2.0, 115.0),
    ("M16", 16.0, 2.0, 157.0),
    ("M18", 18.0, 2.5, 192.0),
    ("M20", 20.0, 2.5, 245.0),
    ("M22", 22.0, 2.5, 303.0),
    ("M24", 24.0, 3.0, 353.0),
    ("M27", 27.0, 3.0, 459.0),
    ("M30", 30.0, 3.5, 561.0),
    ("M33", 33.0, 3.5, 694.0),
    ("M36", 36.0, 4.0, 817.0),
    ("M39", 39.0, 4.0, 976.0),
    ("M42", 42.0, 4.5, 1120.0),
    ("M45", 45.0, 4.5, 1300.0),
    ("M48", 48.0, 5.0, 1470.0),
]


PROPERTY_CLASSES = [
    ("8.8", 800.0, 640.0, 580.0),
    ("10.9", 1000.0, 900.0, 830.0),
    ("12.9", 1200.0, 1080.0, 970.0),
]


CTP_MATERIALS = [
    ("0418 (Classe 8-8)", 640.0),
    ("1557 (Classe 10-9)", 900.0),
    ("0225 (Classe 12-9)", 1080.0),
    ("0336 (42CrMo4)", 650.0),
    ("0435 (EN17/24T)", 635.0),
    ("0436 (EN24X)", 1005.0),
    ("0419 (35-CD-4)", 665.0),
    ("1052 (High T.steel)", 1080.0),
    ("A2/A4-50 S Steel", 210.0),
    ("A2/A4-70 S Steel", 450.0),
    ("A2/A4-80 S Steel", 600.0),
    ("0552 (Inox 70)", 450.0),
    ("0550 (Inox 80)", 600.0),
]


CTP_FRICTION_PRESETS = [
    ("Emuge+Oil", 0.155),
    ("Prevailing+Oil", 0.155),
    ("Prevailing+Moly", 0.114),
    ("Prevailing+Adhesive", 0.138),
    ("Prevailing+Black", 0.212),
    ("Adhesive", 0.12),
    ("Light Oil", 0.12),
    ("API 671", 0.15),
    ("Black", 0.145),
    ("Black+Oil", 0.12),
    ("Zinc", 0.18),
    ("Zinc+Wax", 0.072),
    ("Self", 0.147),
    ("Phosphate+Oil", 0.106),
    ("Moly", 0.095),
    ("Custom", 0.0),
]


# Seeded from CTP 0007.xltx, hidden sheet "Donnees Vis", rows 3:168.
# SPECIAL metric socket-head defaults are from Unbrako_engguide.pdf.
# Columns are type, size, thread, pitch, shank, groove, nut contact,
# thread type, primary material, secondary material, standard torques.
CTP_SCREW_ROW_DATA = """\
1825	0100	9.525	1.058	9.487	0	15.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):25.8
1825	0101	9.525	1.058	9.487	0	15.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):25.8
1825	0102	15.875	1.411	15.824	0	25.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):203
1825	0103	15.875	1.411	15.824	0	25.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):203
1825	0104	9.525	1.058	9.487	0	15.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):25.8
1825	0105	15.875	1.411	15.824	0	25.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):203
1825	0106	9.525	1.058	9.487	0	15.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):25.8
1825	0107	19.05	1.587	18.999	0	30.4	Rolled	1052 (High T.steel)	-	1052 (High T.steel):203
1825	0108	14.287	1.411	14.237	0	23	Rolled	1052 (High T.steel)	-	1052 (High T.steel):81.3
1825	0109	12.7	1.27	12.662	0	21.1	Rolled	1052 (High T.steel)	-	1052 (High T.steel):81.3
1825	0110	12.7	1.27	12.662	0	21.1	Rolled	1052 (High T.steel)	-	1052 (High T.steel):81.3
1825	0111	9.525	1.058	9.487	0	15.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):25.8
1825	0112	9.525	1.058	9.487	0	15.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):25.8
1825	0113	7.937	1.058	7.899	0	13.1	Rolled	1052 (High T.steel)	-	1052 (High T.steel):10.8
1825	0114	6.35	0.907	6.312	0	10.5	Rolled	1052 (High T.steel)	-	1052 (High T.steel):10.8
1825	0115	15.875	1.411	15.824	0	25.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):203
1825	0116	7.937	1.058	7.899	0	13.1	Rolled	1052 (High T.steel)	-	1052 (High T.steel):10.8
1825	0117	12.7	1.27	12.662	0	21.1	Rolled	1052 (High T.steel)	-	1052 (High T.steel):81.3
1825	0118	15.875	1.411	15.824	0	25.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):203
1828	0100	6	1	5.965	0	9.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):14
1828	0101	8	1.25	7.962	0	12.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):30
1828	0102	8	1.25	7.962	0	12.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):30
1828	0103	10	1.5	9.962	0	15.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):55
1828	0104	12	1.5	11.959	0	18.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):95
1828	0105	12	1.5	11.959	0	18.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):95
1828	0106	14	1.5	13.959	0	22.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):160
1828	0107	14	1.5	13.959	0	22.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):160
1828	0108	16	1.5	15.959	0	25.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):220
1828	0109	16	1.5	15.959	0	25.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):220
1828	0110	18	1.5	17.959	0	28.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):270
1828	0111	20	1.5	19.959	0	31.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):370
1828	0112	20	1.5	19.959	0	31.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):370
1828	0113	22	1.5	21.959	0	34.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):500
1828	0114	24	2	23.959	0	38.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):630
1828	0115	24	2	23.959	0	38.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):630
1828	0116	27	2	26.959	0	43	Rolled	1052 (High T.steel)	-	-
1828	0117	33	2	32.95	0	52	Rolled	1052 (High T.steel)	-	1052 (High T.steel):1730
1828	0118	36	2	35.95	0	57	Rolled	1052 (High T.steel)	-	1052 (High T.steel):2200
1828	0119	36	2	35.95	0	57	Rolled	1052 (High T.steel)	-	1052 (High T.steel):2200
1828	0120	12	1.5	11.959	0	18.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):95
1828	0121	14	1.5	13.959	0	22.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):160
1828	0122	6	1	5.965	0	9.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):14
1828	0123	8	1.25	7.962	0	12.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):30
1828	0124	10	1.5	9.962	0	15.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):55
1828	0125	12	1.5	11.959	0	18.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):95
1828	0126	6	1	5.965	0	9.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):14
1828	0127	12	1.5	11.959	0	18.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):95
1828	0128	16	1.5	15.959	0	25.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):220
1828	0129	10	1.5	9.962	0	15.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):55
1828	0130	36	2	35.95	0	57	Rolled	1052 (High T.steel)	-	1052 (High T.steel):2200
1828	0131	6	1	5.965	0	9.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):14
1828	0132	6	1	5.965	0	9.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):14
1828	0133	6	1	5.965	0	9.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):14
1828	0134	8	1.25	7.962	0	12.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):30
1828	0135	12	1.5	11.959	0	18.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):95
1828	0136	16	1.5	15.959	0	25.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):220
1828	0137	18	1.5	17.959	0	28.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):270
1828	0138	20	1.5	19.959	0	31.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):370
1828	0139	22	1.5	21.959	0	34.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):500
1828	0140	22	1.5	21.959	0	34.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):500
1828	0141	24	2	23.959	0	38.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):630
1828	0142	30	2	29.95	0	49	Rolled	1052 (High T.steel)	-	1052 (High T.steel):1290
1828	0143	33	2	32.95	0	52	Rolled	1052 (High T.steel)	-	1052 (High T.steel):1730
1828	0144	36	2	35.95	0	57	Rolled	1052 (High T.steel)	-	1052 (High T.steel):2200
1828	0145	36	2	35.95	0	57	Rolled	1052 (High T.steel)	-	1052 (High T.steel):2200
1828	0146	20	1.5	19.959	0	31.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):370
1828	0147	6	1	5.965	0	9.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):14
1828	0148	8	1.25	7.962	0	12.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):30
1828	0149	12	1.5	11.959	0	18.8	Rolled	1052 (High T.steel)	-	1052 (High T.steel):95
1828	0150	16	1.5	15.959	0	25.3	Rolled	1052 (High T.steel)	-	1052 (High T.steel):220
1121	0011	6	1	5.99	0	9	Machined	0435 (EN17/24T)	0336 (42CrMo4)	0435 (EN17/24T):11|0336 (42CrMo4):11
1121	0027	8	1.25	7.99	0	12	Machined	0435 (EN17/24T)	0336 (42CrMo4)	0435 (EN17/24T):23|0336 (42CrMo4):23
1121	0060	10	1.5	9.99	0	15	Machined	0435 (EN17/24T)	0336 (42CrMo4)	0435 (EN17/24T):47|0336 (42CrMo4):47
1121	0110	12	1.75	11.99	0	18	Machined	0435 (EN17/24T)	0336 (42CrMo4)	0435 (EN17/24T):75|0336 (42CrMo4):75
1121	0180	14	2	13.99	0	21	Machined	0435 (EN17/24T)	0336 (42CrMo4)	0435 (EN17/24T):130|0336 (42CrMo4):130
1121	0260	16	2	15.99	0	24	Machined	0435 (EN17/24T)	0336 (42CrMo4)	0435 (EN17/24T):150|0336 (42CrMo4):150
1121	0400	18	2.5	17.99	0	27	Machined	0435 (EN17/24T)	0336 (42CrMo4)	0435 (EN17/24T):210|0336 (42CrMo4):210
1121	0560	20	2.5	19.99	0	30	Machined	0435 (EN17/24T)	0336 (42CrMo4)	0435 (EN17/24T):280|0336 (42CrMo4):280
1121	0750	22	2.5	21.99	0	33	Machined	0435 (EN17/24T)	0336 (42CrMo4)	0435 (EN17/24T):380|0336 (42CrMo4):380
1121	1120	24	3	23.99	0	36	Machined	0435 (EN17/24T)	0336 (42CrMo4)	0435 (EN17/24T):490|0336 (42CrMo4):490
1135	1400	18	2.5	17.966	14.15	27	Machined	0419 (35-CD-4)	1557 (Classe 10-9)	0419 (35-CD-4):200|1557 (Classe 10-9):245
1135	1850	20	2.5	19.959	16.15	30	Machined	0419 (35-CD-4)	1557 (Classe 10-9)	0419 (35-CD-4):275|1557 (Classe 10-9):345
1135	2400	22	2.5	21.959	18.15	32	Machined	0419 (35-CD-4)	1557 (Classe 10-9)	0419 (35-CD-4):375|1557 (Classe 10-9):465
1135	3000	22	2.5	21.959	18.15	32	Machined	0419 (35-CD-4)	1557 (Classe 10-9)	0419 (35-CD-4):375|1557 (Classe 10-9):465
1135	4200	24	3	23.959	19.35	36	Machined	0419 (35-CD-4)	1557 (Classe 10-9)	0419 (35-CD-4):465|1557 (Classe 10-9):590
1135	6000	30	3.5	29.959	24.75	46	Machined	0419 (35-CD-4)	1557 (Classe 10-9)	0419 (35-CD-4):950|1557 (Classe 10-9):1190
1135	9009	33	3.5	32.95	27.75	50	Machined	0419 (35-CD-4)	1557 (Classe 10-9)	0419 (35-CD-4):1250|1557 (Classe 10-9):1610
1135	9012	36	4	35.95	30.05	55	Machined	0419 (35-CD-4)	1557 (Classe 10-9)	0419 (35-CD-4):1650|1557 (Classe 10-9):2080
1135	9015	36	4	35.95	30.05	55	Machined	0419 (35-CD-4)	1557 (Classe 10-9)	0419 (35-CD-4):1650|1557 (Classe 10-9):2080
1135	9022	42	4.5	41.95	35.5	65	Machined	0419 (35-CD-4)	1557 (Classe 10-9)	0419 (35-CD-4):2350|1557 (Classe 10-9):2960
1135	9033	48	5	47.95	40.75	75	Machined	0419 (35-CD-4)	1557 (Classe 10-9)	-
1161	0010	5	0.8	4.988	4	7.89	Machined	0336 (42CrMo4)	-	-
1161	0021	6	1	5.988	4.7	9.89	Machined	0336 (42CrMo4)	-	-
1161	0055	8	1.25	7.988	6.4	12.865	Machined	0336 (42CrMo4)	-	-
1161	0120	10	1.5	9.988	8.1	16.865	Machined	0336 (42CrMo4)	-	-
1161	0300	12	1.75	11.988	9.8	18.835	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):65
1161	0500	14	2	13.988	11.5	21.835	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):105
1161	0750	16	2	15.988	13.5	23.835	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):160
1161	1050	18	2.5	17.988	14.9	26.58	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):225
1161	1500	20	2.5	19.985	16.9	29.58	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):305
1161	2000	22	2.5	21.985	18.9	31.5	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):425
1161	2600	24	3	23.985	20.3	35.5	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):525
1161	3350	24	3	25.985	20.3	35.5	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):525
1161	4250	27	3	27.985	23.3	40.5	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):785
1161	6010	30	3.5	31.982	25.7	45.5	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):1095
1161	8500	36	4	35.982	31	54.4	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):1860
1161	9013	39	4	40.982	34	59.4	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):2400
1161	9017	45	4.5	44.982	39.4	69.05	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):3700
1161	9021	48	5	47.982	41.8	74.05	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):4450
1161	9036	56	5.5	57.975	49.2	83.9	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):7200
1161	9049	64	6	63.975	56.6	93.9	Machined	0336 (42CrMo4)	-	0336 (42CrMo4):10700
1136	1400	10	1.5	9.986	7.45	17	Machined	0419 (35-CD-4)	-	0419 (35-CD-4):30
1136	1850	10	1.5	11.983	7.45	17	Machined	0419 (35-CD-4)	-	0419 (35-CD-4):30
1136	3000	12	1.75	13.983	9.15	19	Machined	0419 (35-CD-4)	-	0419 (35-CD-4):60
1136	6000	16	2	15.983	12.75	22	Machined	0419 (35-CD-4)	-	0419 (35-CD-4):135
1136	9009	16	2	17.983	12.75	24	Machined	0419 (35-CD-4)	-	0419 (35-CD-4):135
1136	9012	20	2.5	19.98	16.15	30	Machined	0419 (35-CD-4)	-	0419 (35-CD-4):270
1136	9015	20	2.5	21.98	16.15	30	Machined	0419 (35-CD-4)	-	0419 (35-CD-4):375
1412	04xx	2	0.4	2	0	4	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
1412	07xx	2.5	0.45	2.5	0	5	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
1412	10xx	3	0.5	3	0	5.5	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):2.3|0418 (Classe 8-8):1.87|1557 (Classe 10-9):1.9
1412	16xx	4	0.7	4	0	7	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):5.3|0418 (Classe 8-8):3.1|0550 (Inox 80):2.6|0552 (Inox 70):2|1557 (Classe 10-9):4.4
1412	21xx	5	0.8	5	0	8	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):10.5|0418 (Classe 8-8):6.15|0550 (Inox 80):5.1|0552 (Inox 70):3.8|1557 (Classe 10-9):8.6
1412	26xx	6	1	6	0	10	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):17.8|0418 (Classe 8-8):13|0550 (Inox 80):9.1|0552 (Inox 70):6.7|1557 (Classe 10-9):15
1412	31xx	8	1.25	8	0	13	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):43|0418 (Classe 8-8):25|0550 (Inox 80):21.7|0552 (Inox 70):16.3|1557 (Classe 10-9):36
1412	34xx	10	1.5	10	0	16	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):87|0418 (Classe 8-8):50|0550 (Inox 80):44|0552 (Inox 70):33|1557 (Classe 10-9):72
1412	38xx	12	1.75	12	0	18	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):150|0418 (Classe 8-8):86|0550 (Inox 80):74|0552 (Inox 70):56|1557 (Classe 10-9):125
1412	43xx	14	2	14	0	21	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):240|0418 (Classe 8-8):141|0550 (Inox 80):119|0552 (Inox 70):89|1557 (Classe 10-9):198
1412	47xx	16	2	16	0	24	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):365|0418 (Classe 8-8):215|0550 (Inox 80):181|0552 (Inox 70):136|1557 (Classe 10-9):305
1412	50xx	18	2.5	18	0	27	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):500|0418 (Classe 8-8):295|0550 (Inox 80):261|0552 (Inox 70):196|1557 (Classe 10-9):420
1412	54xx	20	2.5	20	0	30	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):710|0418 (Classe 8-8):420|0550 (Inox 80):366|0552 (Inox 70):274|1557 (Classe 10-9):590
1412	55xx	22	2.5	22	0	34	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):960|0418 (Classe 8-8):570|0550 (Inox 80):494|0552 (Inox 70):206|1557 (Classe 10-9):800
1412	58xx	24	3	24	0	36	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):1220|0418 (Classe 8-8):725|0550 (Inox 80):634|0552 (Inox 70):264|1557 (Classe 10-9):1020
1412	62xx	27	3	27	0	41	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):1810|0418 (Classe 8-8):1070|0552 (Inox 70):371|1557 (Classe 10-9):1510
1412	64xx	30	3.5	30	0	46	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):2450|0418 (Classe 8-8):1450|0552 (Inox 70):503|1557 (Classe 10-9):2050
1412	67xx	33	3.5	33	0	50	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):3330|0418 (Classe 8-8):1970|1557 (Classe 10-9):2770
1412	71xx	36	4	36	0	55	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):4280|0418 (Classe 8-8):2530|1557 (Classe 10-9):3560
1412	75xx	39	4	39	0	60	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
1512	04xx	2	0.4	2	0	4	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
1512	07xx	2.5	0.45	2.5	0	5	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
1512	10xx	3	0.5	3	0	5.5	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):2.3|0418 (Classe 8-8):1.87|1557 (Classe 10-9):1.9
1512	16xx	4	0.7	4	0	7	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):5.3|0418 (Classe 8-8):3.1|0550 (Inox 80):2.6|0552 (Inox 70):2|1557 (Classe 10-9):4.4
1512	21xx	5	0.8	5	0	8	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):10.5|0418 (Classe 8-8):6.15|0550 (Inox 80):5.1|0552 (Inox 70):3.8|1557 (Classe 10-9):8.6
1512	26xx	6	1	6	0	10	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):17.8|0418 (Classe 8-8):10.5|0550 (Inox 80):9.1|0552 (Inox 70):6.7|1557 (Classe 10-9):15
1512	31xx	8	1.25	8	0	13	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):43|0418 (Classe 8-8):26|0550 (Inox 80):21.7|0552 (Inox 70):16.3|1557 (Classe 10-9):36
1512	34xx	10	1.5	10	0	16	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):87|0418 (Classe 8-8):51|0550 (Inox 80):44|0552 (Inox 70):33|1557 (Classe 10-9):72
1512	38xx	12	1.75	12	0	18	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):150|0418 (Classe 8-8):89|0550 (Inox 80):74|0552 (Inox 70):56|1557 (Classe 10-9):125
1512	43xx	14	2	14	0	21	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):240|0418 (Classe 8-8):141|0550 (Inox 80):119|0552 (Inox 70):89|1557 (Classe 10-9):198
1512	47xx	16	2	16	0	24	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):365|0418 (Classe 8-8):215|0550 (Inox 80):181|0552 (Inox 70):136|1557 (Classe 10-9):305
1512	50xx	18	2.5	18	0	27	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):500|0418 (Classe 8-8):295|0550 (Inox 80):261|0552 (Inox 70):196|1557 (Classe 10-9):420
1512	54xx	20	2.5	20	0	30	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):710|0418 (Classe 8-8):420|0550 (Inox 80):366|0552 (Inox 70):274|1557 (Classe 10-9):590
1512	55xx	22	2.5	22	0	34	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):960|0418 (Classe 8-8):570|0550 (Inox 80):494|0552 (Inox 70):206|1557 (Classe 10-9):800
1512	58xx	24	3	24	0	36	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):1220|0418 (Classe 8-8):725|0550 (Inox 80):634|0552 (Inox 70):264|1557 (Classe 10-9):1020
1512	62xx	27	3	27	0	41	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):1810|0418 (Classe 8-8):1070|0552 (Inox 70):371|1557 (Classe 10-9):1510
1512	64xx	30	3.5	30	0	46	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):2450|0418 (Classe 8-8):1450|0552 (Inox 70):503|1557 (Classe 10-9):2050
1512	67xx	33	3.5	33	0	50	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):3330|0418 (Classe 8-8):1970|1557 (Classe 10-9):2770
1512	71xx	36	4	36	0	55	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):4280|0418 (Classe 8-8):2530|1557 (Classe 10-9):3560
1512	75xx	39	4	39	0	60	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
1442	21xx	5	0.8	6	3.68	8	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):10.5|0418 (Classe 8-8):6.15|0550 (Inox 80):5.1|0552 (Inox 70):3.8|1557 (Classe 10-9):8.6
1442	26xx	6	1	8	4.4	10	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):17.8|0418 (Classe 8-8):13|0550 (Inox 80):9.1|0552 (Inox 70):6.7|1557 (Classe 10-9):15
1442	31xx	8	1.25	10	6.03	13	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):43|0418 (Classe 8-8):25|0550 (Inox 80):21.7|0552 (Inox 70):16.3|1557 (Classe 10-9):36
1442	34xx	10	1.5	12	7.69	16	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):87|0418 (Classe 8-8):50|0550 (Inox 80):44|0552 (Inox 70):33|1557 (Classe 10-9):72
1442	38xx	12	1.75	16	9.35	18	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):150|0418 (Classe 8-8):86|0550 (Inox 80):74|0552 (Inox 70):56|1557 (Classe 10-9):125
1442	47xx	16	2	20	12.96	24	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):365|0418 (Classe 8-8):215|0550 (Inox 80):181|0552 (Inox 70):136|1557 (Classe 10-9):305
1442	54xx	20	2.5	24	16.3	30	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	0225 (Classe 12-9):710|0418 (Classe 8-8):420|0550 (Inox 80):366|0552 (Inox 70):274|1557 (Classe 10-9):590
SPECIAL	M1.6	1.6	0.35	1.6	0	3	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M2	2	0.4	2	0	3.8	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M2.5	2.5	0.45	2.5	0	4.5	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M3	3	0.5	3	0	5.5	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M4	4	0.7	4	0	7	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M5	5	0.8	5	0	8.5	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M6	6	1	6	0	10	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M8	8	1.25	8	0	13	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M10	10	1.5	10	0	16	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M12	12	1.75	12	0	18	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M14	14	2	14	0	21	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M16	16	2	16	0	24	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M20	20	2.5	20	0	30	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M24	24	3	24	0	36	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M30	30	3.5	30	0	45	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M36	36	4	36	0	54	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M42	42	4.5	42	0	63	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	M48	48	5	48	0	72	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
SPECIAL	Manual	16	2	16	0	24	Machined	0225 (Classe 12-9)	0418 (Classe 8-8)	-
"""


def _cell_text(value: str) -> str:
    return "" if value == "-" else value


def _standard_torque_map(value: str) -> dict[str, float]:
    if value == "-":
        return {}
    torques: dict[str, float] = {}
    for item in value.split("|"):
        material_code, torque = item.rsplit(":", 1)
        torques[material_code] = float(torque)
    return torques


def _parse_ctp_screw_rows() -> list[tuple[str, str, float, float, float, float, float, str, str, str, dict[str, float]]]:
    rows = []
    for line in CTP_SCREW_ROW_DATA.splitlines():
        parts = line.split("\t")
        if len(parts) != 11:
            raise ValueError(f"Invalid CTP screw row: {line!r}")
        (
            screw_type,
            size,
            thread_mm,
            pitch_mm,
            shank_diameter_mm,
            groove_diameter_mm,
            contact_diameter_mm,
            thread_type,
            primary_material,
            secondary_material,
            standard_torques,
        ) = parts
        rows.append(
            (
                screw_type,
                size,
                float(thread_mm),
                float(pitch_mm),
                float(shank_diameter_mm),
                float(groove_diameter_mm),
                float(contact_diameter_mm),
                thread_type,
                _cell_text(primary_material),
                _cell_text(secondary_material),
                _standard_torque_map(standard_torques),
            )
        )
    return rows


CTP_SCREW_ROWS = _parse_ctp_screw_rows()


def connect(path: Path = DATABASE_PATH) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS metric_bolt_sizes (
            designation TEXT PRIMARY KEY,
            diameter_mm REAL NOT NULL,
            pitch_mm REAL NOT NULL,
            tensile_area_mm2 REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS property_classes (
            name TEXT PRIMARY KEY,
            ultimate_mpa REAL NOT NULL,
            yield_mpa REAL NOT NULL,
            proof_mpa REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ctp_screw_rows (
            screw_type TEXT NOT NULL,
            size TEXT NOT NULL,
            thread_mm REAL NOT NULL,
            pitch_mm REAL NOT NULL,
            shank_diameter_mm REAL NOT NULL,
            groove_diameter_mm REAL NOT NULL,
            contact_diameter_mm REAL NOT NULL,
            thread_type TEXT NOT NULL,
            primary_material TEXT NOT NULL,
            secondary_material TEXT NOT NULL,
            standard_torques_nm TEXT NOT NULL,
            PRIMARY KEY (screw_type, size)
        );

        CREATE TABLE IF NOT EXISTS ctp_materials (
            code TEXT PRIMARY KEY,
            yield_mpa REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ctp_friction_presets (
            name TEXT PRIMARY KEY,
            coefficient REAL NOT NULL
        );
        """
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO metric_bolt_sizes
            (designation, diameter_mm, pitch_mm, tensile_area_mm2)
        VALUES (?, ?, ?, ?)
        """,
        BOLT_SIZES,
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO property_classes
            (name, ultimate_mpa, yield_mpa, proof_mpa)
        VALUES (?, ?, ?, ?)
        """,
        PROPERTY_CLASSES,
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO ctp_materials (code, yield_mpa)
        VALUES (?, ?)
        """,
        CTP_MATERIALS,
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO ctp_friction_presets (name, coefficient)
        VALUES (?, ?)
        """,
        CTP_FRICTION_PRESETS,
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO ctp_screw_rows
            (screw_type, size, thread_mm, pitch_mm, shank_diameter_mm,
             groove_diameter_mm, contact_diameter_mm, thread_type,
             primary_material, secondary_material, standard_torques_nm)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                screw_type,
                size,
                thread_mm,
                pitch_mm,
                shank_diameter_mm,
                groove_diameter_mm,
                contact_diameter_mm,
                thread_type,
                primary_material,
                secondary_material,
                repr(standard_torques_nm),
            )
            for (
                screw_type,
                size,
                thread_mm,
                pitch_mm,
                shank_diameter_mm,
                groove_diameter_mm,
                contact_diameter_mm,
                thread_type,
                primary_material,
                secondary_material,
                standard_torques_nm,
            ) in CTP_SCREW_ROWS
        ],
    )
    conn.commit()


def list_bolt_sizes(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT designation FROM metric_bolt_sizes ORDER BY diameter_mm"
    ).fetchall()
    return [row["designation"] for row in rows]


def list_property_classes(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM property_classes ORDER BY yield_mpa"
    ).fetchall()
    return [row["name"] for row in rows]


def get_bolt_size(conn: sqlite3.Connection, designation: str) -> BoltSize:
    row = conn.execute(
        """
        SELECT designation, diameter_mm, pitch_mm, tensile_area_mm2
        FROM metric_bolt_sizes
        WHERE designation = ?
        """,
        (designation,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown bolt size: {designation}")
    return BoltSize(
        designation=row["designation"],
        diameter_mm=row["diameter_mm"],
        pitch_mm=row["pitch_mm"],
        tensile_area_mm2=row["tensile_area_mm2"],
    )


def get_property_class(conn: sqlite3.Connection, name: str) -> PropertyClass:
    row = conn.execute(
        """
        SELECT name, ultimate_mpa, yield_mpa, proof_mpa
        FROM property_classes
        WHERE name = ?
        """,
        (name,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown property class: {name}")
    return PropertyClass(
        name=row["name"],
        ultimate_mpa=row["ultimate_mpa"],
        yield_mpa=row["yield_mpa"],
        proof_mpa=row["proof_mpa"],
    )


def recommend_bolt_size(
    conn: sqlite3.Connection,
    property_class: PropertyClass,
    required_initial_preload_n: float,
    max_yield_utilization: float,
) -> BoltSize | None:
    rows = conn.execute(
        """
        SELECT designation, diameter_mm, pitch_mm, tensile_area_mm2
        FROM metric_bolt_sizes
        ORDER BY diameter_mm
        """
    ).fetchall()
    for row in rows:
        yield_load = property_class.yield_mpa * row["tensile_area_mm2"]
        if required_initial_preload_n <= yield_load * max_yield_utilization:
            return BoltSize(
                designation=row["designation"],
                diameter_mm=row["diameter_mm"],
                pitch_mm=row["pitch_mm"],
                tensile_area_mm2=row["tensile_area_mm2"],
            )
    return None


def list_ctp_screw_types(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT screw_type
        FROM ctp_screw_rows
        GROUP BY screw_type
        ORDER BY MIN(rowid)
        """
    ).fetchall()
    return [row["screw_type"] for row in rows]


def list_ctp_sizes(conn: sqlite3.Connection, screw_type: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT size FROM ctp_screw_rows
        WHERE screw_type = ?
        ORDER BY rowid
        """,
        (screw_type,),
    ).fetchall()
    return [row["size"] for row in rows]


def get_ctp_screw_record(
    conn: sqlite3.Connection,
    screw_type: str,
    size: str,
) -> CtpScrewRecord:
    row = conn.execute(
        """
        SELECT screw_type, size, thread_mm, pitch_mm, shank_diameter_mm,
               groove_diameter_mm, contact_diameter_mm, thread_type,
               primary_material, secondary_material, standard_torques_nm
        FROM ctp_screw_rows
        WHERE screw_type = ? AND size = ?
        """,
        (screw_type, size),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown CTP screw row: {screw_type} {size}")
    return CtpScrewRecord(
        screw_type=row["screw_type"],
        size=row["size"],
        thread_mm=row["thread_mm"],
        pitch_mm=row["pitch_mm"],
        shank_diameter_mm=row["shank_diameter_mm"],
        groove_diameter_mm=row["groove_diameter_mm"],
        contact_diameter_mm=row["contact_diameter_mm"],
        thread_type=row["thread_type"],
        primary_material=row["primary_material"],
        secondary_material=row["secondary_material"],
        standard_torques_nm=ast.literal_eval(row["standard_torques_nm"]),
    )


def list_material_codes(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT code FROM ctp_materials ORDER BY rowid").fetchall()
    return [row["code"] for row in rows]


def get_material_yield(conn: sqlite3.Connection, code: str) -> float:
    row = conn.execute(
        "SELECT yield_mpa FROM ctp_materials WHERE code = ?",
        (code,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown material code: {code}")
    return row["yield_mpa"]


def list_friction_presets(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM ctp_friction_presets ORDER BY rowid").fetchall()
    return [row["name"] for row in rows]


def get_friction_factor(conn: sqlite3.Connection, name: str) -> float:
    row = conn.execute(
        "SELECT coefficient FROM ctp_friction_presets WHERE name = ?",
        (name,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown friction preset: {name}")
    return row["coefficient"]
